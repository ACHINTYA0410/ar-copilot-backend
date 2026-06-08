"""
Vision extraction service for PO PDF documents.

Architecture:
  PODocumentExtractor  — abstract base
  GroqVisionExtractor  — active implementation (Groq vision API via httpx)
  GeminiVisionExtractor — stubbed for Phase 3+
  get_extractor()      — factory; reads VISION_PROVIDER from config

PDF pages are rendered to PNG via PyMuPDF and sent as base64 data-URLs.
The model is instructed to return ONLY JSON; fences are stripped defensively.
"""

import abc
import asyncio
import base64
import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Extraction prompt
# ---------------------------------------------------------------------------

EXTRACTION_PROMPT = """\
You are a purchase order data extractor. You will receive one or more images of a PO document.

Your task: extract structured data and return it as a SINGLE valid JSON object.

REQUIRED OUTPUT FORMAT — return ONLY this JSON, no markdown fences, no explanation:

{
  "deal_id": "string or null",
  "school_name": "string or null",
  "academic_year": "string or null",
  "term": "string or null",
  "line_items": [
    {
      "item": "string",
      "quantity": 0,
      "price_per_unit": 0.0,
      "total": 0.0
    }
  ],
  "total_order_value": 0.0,
  "tranches": [
    {
      "tranche_no": 1,
      "date": "string",
      "amount": 0.0
    }
  ],
  "amount_due": 0.0
}

RULES:
- Extract EVERY row from the line-item table — do not skip any row.
- For the "item" field: copy the label EXACTLY as printed, character for character.
  Do not paraphrase, abbreviate, or correct it. Grade numbers and roman numerals
  (I, II, III, IV, V, VI, VII, VIII, IX, X) must be transcribed precisely —
  "CLASS VII" must not become "CLASS VIII", "Grade 5" must not become "Grade 6".
- Numbers must be plain numbers (no ₹, $, commas, or units). Example: "1,20,000" → 120000.
- For "price_per_unit": look for columns labelled Rate, Price, MRP, Unit Price, Per Unit, or similar.
  Read the actual number printed in that cell. Do NOT write 0 if a number is visible.
- For "total": look for columns labelled Amount, Total, Net Amount, Value, or similar.
  Read the actual number printed in that cell. Do NOT write 0 if a number is visible.
- If a numeric cell is genuinely blank or illegible, use null — never default to 0.
- Use null for any text field you cannot find in the document.
- Do NOT invent, estimate, or hallucinate values.
- Return valid JSON only. No markdown fences. No extra text before or after the JSON.\
"""

# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass
class ExtractionResult:
    raw: str
    parsed: dict[str, Any] | None = None
    parse_error: str | None = None
    pages_sent: int = 0
    model: str = field(default="")


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------


class PODocumentExtractor(abc.ABC):
    @abc.abstractmethod
    async def extract(self, pdf_bytes: bytes) -> ExtractionResult:
        """Convert PDF bytes to structured PO data."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def _strip_fences(text: str) -> str:
    return _FENCE_RE.sub("", text).strip()


def _pdf_pages_to_b64(pdf_bytes: bytes) -> list[str]:
    """
    Render ALL PDF pages to 2x-zoom PNGs and return base64 strings.
    Runs synchronously — call via asyncio.to_thread.
    """
    import fitz  # PyMuPDF

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    zoom = fitz.Matrix(2.0, 2.0)  # 144 dpi — good balance of quality vs payload size
    return [
        base64.b64encode(doc[i].get_pixmap(matrix=zoom, alpha=False).tobytes("png")).decode()
        for i in range(len(doc))
    ]


def _parse_json_safe(raw: str) -> tuple[dict | None, str | None]:
    """
    Try to parse raw model output as JSON.
    Returns (parsed_dict, None) on success, (None, error_message) on failure.
    """
    cleaned = _strip_fences(raw)
    try:
        return json.loads(cleaned), None
    except json.JSONDecodeError as exc:
        return None, f"JSONDecodeError at position {exc.pos}: {exc.msg}"


# ---------------------------------------------------------------------------
# Groq implementation
# ---------------------------------------------------------------------------


class GroqVisionExtractor(PODocumentExtractor):
    _API_URL = "https://api.groq.com/openai/v1/chat/completions"

    async def extract(self, pdf_bytes: bytes) -> ExtractionResult:
        if not settings.GROQ_API_KEY:
            raise ValueError("GROQ_API_KEY is not configured.")

        pages_b64 = await asyncio.to_thread(_pdf_pages_to_b64, pdf_bytes)
        if not pages_b64:
            raise ValueError("PDF rendered 0 pages — file may be corrupt.")

        # Build message: all page images first, then the text prompt
        content: list[dict] = [
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{b64}"},
            }
            for b64 in pages_b64
        ]
        content.append({"type": "text", "text": EXTRACTION_PROMPT})

        payload = {
            "model": settings.GROQ_VISION_MODEL,
            "messages": [{"role": "user", "content": content}],
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }

        async with httpx.AsyncClient(timeout=90.0) as client:
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
        # Log first 500 chars so we can diagnose unexpected output without
        # dumping the full (potentially large) response into logs
        logger.info("Groq vision raw output (%d chars): %s…", len(raw), raw[:500])

        parsed, parse_error = _parse_json_safe(raw)
        return ExtractionResult(
            raw=raw,
            parsed=parsed,
            parse_error=parse_error,
            pages_sent=len(pages_b64),
            model=settings.GROQ_VISION_MODEL,
        )


# ---------------------------------------------------------------------------
# Gemini stub (Phase 3+)
# ---------------------------------------------------------------------------


class GeminiVisionExtractor(PODocumentExtractor):
    async def extract(self, pdf_bytes: bytes) -> ExtractionResult:
        raise NotImplementedError(
            "GeminiVisionExtractor is not yet implemented. "
            "Set VISION_PROVIDER=groq to use the active extractor."
        )


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def get_extractor() -> PODocumentExtractor:
    provider = (settings.VISION_PROVIDER or "groq").lower()
    if provider == "groq":
        return GroqVisionExtractor()
    if provider == "gemini":
        return GeminiVisionExtractor()
    raise ValueError(
        f"Unknown VISION_PROVIDER={provider!r}. Valid options: 'groq', 'gemini'."
    )
