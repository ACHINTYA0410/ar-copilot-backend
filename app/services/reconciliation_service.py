"""
Phase 3: Reconcile PO proof items against ORP order line items.

Two-stage pipeline — strict separation enforced by design:

  Stage 1 — AI semantic matching  (ItemMatcher, swappable via MATCHING_PROVIDER)
    The model receives item *names* only. Quantities are intentionally withheld
    so the model cannot influence quantity comparison even if prompted to try.

  Stage 2 — Deterministic comparison  (pure Python, zero AI involvement)
    Quantities are summed and compared here. Verdict is computed here.
    The AI's output is only consumed for the match mapping.
"""

import abc
import asyncio
import json
import logging
import re
from dataclasses import dataclass
from typing import Any

import httpx

from app.config import settings
from app.services.s3_service import fetch_po_document
from app.services.vision_service import get_extractor

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# ORP data access — sync MySQL calls wrapped for the async event loop
# ---------------------------------------------------------------------------


def _sync_fetch_order_assets(order_id: int) -> list[dict]:
    """Return active PO proof rows from order_assets for this order."""
    from orp_db import get_orp_connection

    conn = get_orp_connection()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            """
            SELECT order_id, file_name
            FROM order_assets
            WHERE asset_type = 'PO'
              AND is_active = 1
              AND order_id = %s
            ORDER BY order_id DESC
            """,
            (order_id,),
        )
        return cur.fetchall()
    finally:
        cur.close()
        conn.close()


def _sync_fetch_order_items(order_id: int) -> list[dict]:
    """Return kit line items for this order with kit-master details."""
    from orp_db import get_orp_connection

    conn = get_orp_connection()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            """
            SELECT oi.kit_id,
                   oi.req_qty,
                   km.hubspot_name,
                   km.class,
                   km.term,
                   km.subscription
            FROM order_items oi
            LEFT JOIN kit_master km ON km.id = oi.kit_id
            WHERE oi.order_id = %s
            """,
            (order_id,),
        )
        return cur.fetchall()
    finally:
        cur.close()
        conn.close()


async def fetch_order_assets(order_id: int) -> list[dict]:
    return await asyncio.to_thread(_sync_fetch_order_assets, order_id)


async def fetch_order_items(order_id: int) -> list[dict]:
    return await asyncio.to_thread(_sync_fetch_order_items, order_id)


# ---------------------------------------------------------------------------
# Charge-line detection  (used by both the pre-filter and Stage 2)
# ---------------------------------------------------------------------------


def _is_charge_line(orp_item: dict) -> bool:
    """True when an ORP line is a logistics/charge item, not a product."""
    cls = (orp_item.get("class") or "").strip().upper()
    return cls in ("NA", "N/A", "", "NULL") or orp_item.get("class") is None


# ---------------------------------------------------------------------------
# Class-number helpers — deterministic pre-filter before AI matching
# ---------------------------------------------------------------------------

# Covers Class 1–12; anything outside this range returns None safely.
_ROMAN_VALUES: dict[str, int] = {
    "I": 1, "II": 2, "III": 3, "IV": 4, "V": 5,
    "VI": 6, "VII": 7, "VIII": 8, "IX": 9, "X": 10,
    "XI": 11, "XII": 12,
}

_CLASS_ARABIC_RE = re.compile(r"\b(?:CLASS|GRADE|STD)\s+(\d+)\b", re.IGNORECASE)
_CLASS_ROMAN_RE = re.compile(r"\b(?:CLASS|GRADE|STD)\s+([IVXLCDM]+)\b", re.IGNORECASE)
_ORP_CLASS_RE = re.compile(r"[Cc]lass\s*(\d+)")


def _parse_class_number(text: str) -> int | None:
    """
    Parse the class/grade number from a proof item label.
    'ACTIVE ENGLISH CLASS VI' → 6
    'SCIENCE BOOK GRADE 5'   → 5
    Returns None if no class number found.
    """
    m = _CLASS_ARABIC_RE.search(text)
    if m:
        return int(m.group(1))
    m = _CLASS_ROMAN_RE.search(text)
    if m:
        return _ROMAN_VALUES.get(m.group(1).upper())
    return None


def _parse_orp_class_number(orp_item: dict) -> int | None:
    """Parse class number from ORP class field. 'Class6' → 6."""
    m = _ORP_CLASS_RE.match((orp_item.get("class") or "").strip())
    return int(m.group(1)) if m else None


def _filter_orp_candidates(proof_text: str, orp_items: list[dict]) -> list[dict]:
    """
    Return only ORP items whose class matches the class in the proof item text.
    Charge lines (class=NA/null) are always excluded.
    If no class can be parsed from the proof text, return all non-charge items.
    """
    proof_class = _parse_class_number(proof_text)
    result = []
    for item in orp_items:
        if _is_charge_line(item):
            continue
        if proof_class is None:
            result.append(item)
        elif _parse_orp_class_number(item) == proof_class:
            result.append(item)
    return result


# ---------------------------------------------------------------------------
# Stage 1 — AI semantic matching
# ---------------------------------------------------------------------------

# Prompt is built without .format() to avoid brace conflicts with JSON schema.
_MATCHING_PROMPT_HEADER = """\
You are a purchase order reconciliation assistant.
Match each proof item to the BEST ORP candidate from its own pre-filtered list.
Quantities are intentionally omitted — do not mention them.

RULES:
- Each proof item may match AT MOST ONE ORP product.
- A product may have multiple kit_ids for different delivery terms (e.g. term=1
  and term=2 for the same product). Include ALL kit_ids for the matched product
  in orp_kit_ids — they MUST all represent the same product, just different terms.
- If no candidate is a plausible match, omit it from "matches" and add it to
  "proof_unmatched_items".
- match_confidence: 0.9-1.0 = certain, 0.6-0.89 = likely, below 0.6 = uncertain.
- Do NOT match across different grades or products. Only match within the given candidates.

INPUT — each proof item with its class-filtered ORP candidates:
"""

_MATCHING_PROMPT_TASK = """

Return ONLY valid JSON with this exact structure. No markdown fences. No explanation:
{
  "matches": [
    {
      "proof_item": "<exact proof item text as given>",
      "orp_kit_ids": [<all kit_ids for the single matched product>],
      "match_confidence": <0.0 to 1.0 float>,
      "match_reason": "<one sentence explaining the match>"
    }
  ],
  "proof_unmatched_items": ["<proof item texts with no plausible ORP match>"]
}
"""


def _build_matching_prompt(per_item_data: list[dict]) -> str:
    """
    per_item_data: [{"proof_item": str, "orp_candidates": [...]}, ...]
    Each entry already has candidates pre-filtered to the same class.
    """
    return (
        _MATCHING_PROMPT_HEADER
        + json.dumps(per_item_data, indent=2, ensure_ascii=False)
        + _MATCHING_PROMPT_TASK
    )


_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def _strip_fences(text: str) -> str:
    return _FENCE_RE.sub("", text).strip()


@dataclass
class MatchingOutput:
    matches: list[dict]
    orp_unmatched_kit_ids: list[int]
    proof_unmatched_items: list[str]
    raw: str
    model: str = ""
    parse_error: str | None = None


class ItemMatcher(abc.ABC):
    @abc.abstractmethod
    async def match(
        self,
        proof_items: list[dict],
        orp_items: list[dict],
    ) -> MatchingOutput:
        """Semantically match proof item names to ORP kit_ids. Never receives quantities."""


class GroqItemMatcher(ItemMatcher):
    _API_URL = "https://api.groq.com/openai/v1/chat/completions"

    async def match(self, proof_items: list[dict], orp_items: list[dict]) -> MatchingOutput:
        if not settings.GROQ_API_KEY:
            raise ValueError("GROQ_API_KEY is not configured.")

        # Build per-item candidate lists — class-filtered in Python so the AI
        # cannot see ORP rows from a different grade. Quantities intentionally excluded.
        per_item_data = [
            {
                "proof_item": p["item"],
                "orp_candidates": [
                    {
                        "kit_id": o["kit_id"],
                        "hubspot_name": o.get("hubspot_name"),
                        "class": o.get("class"),
                        "term": o.get("term"),
                    }
                    for o in _filter_orp_candidates(p["item"], orp_items)
                ],
            }
            for p in proof_items
        ]

        prompt = _build_matching_prompt(per_item_data)

        payload = {
            "model": settings.GROQ_MATCHING_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                self._API_URL,
                headers={
                    "Authorization": f"Bearer {settings.GROQ_API_KEY}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            resp.raise_for_status()

        raw = resp.json()["choices"][0]["message"]["content"]
        logger.info("Groq matching raw output (%d chars): %s…", len(raw), raw[:500])

        cleaned = _strip_fences(raw)
        try:
            data = json.loads(cleaned)
            matches = data.get("matches", [])

            # Compute unmatched ORP kit_ids deterministically — don't trust AI to report them.
            matched_kit_ids = {
                int(kid)
                for m in matches
                for kid in m.get("orp_kit_ids", [])
            }
            orp_unmatched = [
                o["kit_id"] for o in orp_items if o["kit_id"] not in matched_kit_ids
            ]

            return MatchingOutput(
                matches=matches,
                orp_unmatched_kit_ids=orp_unmatched,
                proof_unmatched_items=data.get("proof_unmatched_items", []),
                raw=raw,
                model=settings.GROQ_MATCHING_MODEL,
            )
        except json.JSONDecodeError as exc:
            logger.warning("Matching JSON parse failed: %s | raw: %s", exc, raw[:300])
            return MatchingOutput(
                matches=[],
                orp_unmatched_kit_ids=[o["kit_id"] for o in orp_items],
                proof_unmatched_items=[p["item"] for p in proof_items],
                raw=raw,
                model=settings.GROQ_MATCHING_MODEL,
                parse_error=f"JSONDecodeError at pos {exc.pos}: {exc.msg}",
            )


class GeminiItemMatcher(ItemMatcher):
    async def match(self, proof_items: list[dict], orp_items: list[dict]) -> MatchingOutput:
        raise NotImplementedError(
            "GeminiItemMatcher is not yet implemented. "
            "Set MATCHING_PROVIDER=groq to use the active matcher."
        )


def get_matcher() -> ItemMatcher:
    provider = (settings.MATCHING_PROVIDER or "groq").lower()
    if provider == "groq":
        return GroqItemMatcher()
    if provider == "gemini":
        return GeminiItemMatcher()
    raise ValueError(
        f"Unknown MATCHING_PROVIDER={provider!r}. Valid options: 'groq', 'gemini'."
    )


# ---------------------------------------------------------------------------
# Stage 2 — Deterministic comparison and verdict  (NO AI beyond this point)
# ---------------------------------------------------------------------------


def _build_orp_index(orp_items: list[dict]) -> dict[int, dict]:
    return {row["kit_id"]: row for row in orp_items}


def _compare(
    order_id: int,
    deal_id: str | None,
    s3_key: str,
    proof_items: list[dict],
    orp_items: list[dict],
    matching: MatchingOutput,
) -> dict[str, Any]:
    """
    Pure Python reconciliation.  The AI matching output provides the mapping;
    all arithmetic, comparisons, and verdict logic are done here.
    """
    orp_index = _build_orp_index(orp_items)

    # Build a lookup from proof item text → quantity for the comparison step
    proof_qty_by_item: dict[str, Any] = {p["item"]: p.get("quantity") for p in proof_items}

    # ------------------------------------------------------------------
    # Matched items
    # ------------------------------------------------------------------
    matched = []
    for m in matching.matches:
        proof_qty = proof_qty_by_item.get(m["proof_item"])

        # Sum req_qty across ALL matched kit_ids (handles term-split rows)
        orp_detail = []
        orp_total_qty = 0
        for kit_id in m.get("orp_kit_ids", []):
            row = orp_index.get(int(kit_id))
            if row:
                qty = row.get("req_qty") or 0
                orp_total_qty += qty
                orp_detail.append({
                    "kit_id": row["kit_id"],
                    "hubspot_name": row.get("hubspot_name"),
                    "term": row.get("term"),
                    "req_qty": row.get("req_qty"),
                })

        # Deterministic quantity comparison — AI never touches this logic
        if proof_qty is None:
            # Extraction returned no quantity for this line; can't confirm or
            # refute — record as match with null proof_qty so reviewers see it
            status = "match"
        elif proof_qty == orp_total_qty:
            status = "match"
        else:
            status = "quantity_mismatch"

        matched.append({
            "proof_item": m["proof_item"],
            "proof_qty": proof_qty,
            "orp_items": orp_detail,
            "orp_total_qty": orp_total_qty,
            "status": status,
            "match_confidence": m.get("match_confidence"),
            "match_reason": m.get("match_reason"),
        })

    # ------------------------------------------------------------------
    # ORP items not found in the proof
    # ------------------------------------------------------------------
    in_order_not_in_proof = []
    for kit_id in matching.orp_unmatched_kit_ids:
        row = orp_index.get(int(kit_id))
        if not row:
            continue
        in_order_not_in_proof.append({
            "kit_id": row["kit_id"],
            "hubspot_name": row.get("hubspot_name"),
            "qty": row.get("req_qty"),
            "class": row.get("class"),
            "is_charge_line": _is_charge_line(row),
        })

    # ------------------------------------------------------------------
    # Proof items not found in this order
    # ------------------------------------------------------------------
    in_proof_not_in_order = [
        {
            "proof_item": item_text,
            "qty": proof_qty_by_item.get(item_text),
            "note": "not found in this order — may belong to another order in the same deal",
        }
        for item_text in matching.proof_unmatched_items
    ]

    # ------------------------------------------------------------------
    # Verdict — deterministic, no AI
    # ------------------------------------------------------------------
    has_qty_mismatch = any(m["status"] == "quantity_mismatch" for m in matched)
    has_low_confidence = any((m.get("match_confidence") or 1.0) < 0.6 for m in matched)
    # Charge lines (logistics etc.) should NOT by themselves trigger amber/red
    extras_non_charge = [x for x in in_order_not_in_proof if not x["is_charge_line"]]

    if has_qty_mismatch:
        verdict = "red"
    elif extras_non_charge or in_proof_not_in_order or has_low_confidence:
        verdict = "amber"
    else:
        verdict = "green"

    summary = {
        "matched_count": len(matched),
        "quantity_mismatches": sum(1 for m in matched if m["status"] == "quantity_mismatch"),
        "extras_in_order": len(in_order_not_in_proof),
        "missing_from_order": len(in_proof_not_in_order),
        "low_confidence_matches": sum(
            1 for m in matched if (m.get("match_confidence") or 1.0) < 0.6
        ),
        "verdict": verdict,
    }

    return {
        "order_id": order_id,
        "deal_id": deal_id,
        "proof_source": {
            "s3_key": s3_key,
            "extracted_item_count": len(proof_items),
        },
        "matched": matched,
        "in_order_not_in_proof": in_order_not_in_proof,
        "in_proof_not_in_order": in_proof_not_in_order,
        "summary": summary,
        "_ai_matching_meta": {
            "model": matching.model,
            "parse_error": matching.parse_error,
        },
    }


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


async def reconcile_order(order_id: int) -> dict[str, Any]:
    """
    Full reconciliation pipeline:
      1. Look up the proof PDF via order_assets
      2. Fetch from S3 + AI vision extraction  (Phase 1 + 2)
      3. Fetch ORP order_items
      4. Stage 1: AI semantic matching  (names only — no quantities sent to AI)
      5. Stage 2: Deterministic comparison + verdict
    """
    # Step 1 — find proof PDF
    assets = await fetch_order_assets(order_id)
    if not assets:
        raise ValueError(f"No active PO proof asset found for order_id={order_id}.")
    s3_key = assets[0]["file_name"]

    # Step 2 — fetch + extract
    pdf_bytes = await fetch_po_document(s3_key)
    extraction = await get_extractor().extract(pdf_bytes)

    if extraction.parse_error:
        raise ValueError(
            f"Vision extraction returned unparseable JSON. "
            f"parse_error={extraction.parse_error!r}  "
            f"raw_prefix={extraction.raw[:200]!r}"
        )

    proof_items: list[dict] = (extraction.parsed or {}).get("line_items", [])
    deal_id: str | None = (extraction.parsed or {}).get("deal_id")

    if not proof_items:
        raise ValueError(
            "Vision extraction succeeded but returned no line_items. "
            f"Raw prefix: {extraction.raw[:200]!r}"
        )

    # Step 3 — fetch ORP items
    orp_items = await fetch_order_items(order_id)
    if not orp_items:
        raise ValueError(f"No order_items found in ORP for order_id={order_id}.")

    # Step 4 — AI matching  (quantities intentionally withheld from AI)
    matching = await get_matcher().match(proof_items, orp_items)

    # Step 5 — deterministic comparison + verdict
    return _compare(order_id, deal_id, s3_key, proof_items, orp_items, matching)
