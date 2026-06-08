"""
Groq LLM service for PO rule confidence scoring.

Provides calibrated confidence (0-1) and 1-2 sentence reasoning for a deterministic
rule result. The deterministic status is ground truth — Groq never overrides it.
"""
import json
import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
_TIMEOUT = 8.0

_SYSTEM_PROMPT = (
    "You are a PO validation assistant. Given a rule, its deterministic result, and the PO data, "
    "output ONLY a JSON object with 'confidence' (0-1 float) and 'reasoning' (1-2 sentences). "
    "Do not change the verdict; explain it and rate your confidence in the data quality."
)


async def score_rule(
    rule_name: str,
    rule_purpose: str,
    deterministic_status: str,
    po_data: dict,
) -> dict:
    """
    Call Groq to get calibrated confidence + reasoning for a deterministic PO rule result.

    Returns {"confidence": float, "reasoning": str}.
    Raises on network/API errors — callers must catch and fall back.
    """
    # Sanitise po_data: drop large or internal fields that bloat the prompt
    safe_po = {
        k: v for k, v in po_data.items()
        if not k.startswith("_") and v is not None
    }

    user_prompt = (
        f"Rule: {rule_name}\n"
        f"Purpose: {rule_purpose}\n"
        f"Deterministic verdict: {deterministic_status}\n"
        f"PO data:\n{json.dumps(safe_po, indent=2)}\n\n"
        "Return a JSON object with exactly two keys: "
        "'confidence' (float 0.0–1.0) and 'reasoning' (1-2 sentences explaining the verdict)."
    )

    payload = {
        "model": settings.GROQ_MODEL,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
    }

    headers = {
        "Authorization": f"Bearer {settings.GROQ_API_KEY}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(_GROQ_API_URL, json=payload, headers=headers)
        resp.raise_for_status()

    content = resp.json()["choices"][0]["message"]["content"]
    parsed = _parse_json(content)

    confidence = float(parsed.get("confidence", 0.85))
    # Clamp to valid range in case the model strays slightly outside [0, 1]
    confidence = max(0.0, min(1.0, confidence))

    return {
        "confidence": confidence,
        "reasoning": str(parsed.get("reasoning", "")).strip(),
    }


def _parse_json(text: str) -> dict:
    """Parse JSON, stripping markdown code fences defensively."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        # Drop opening fence (```json or ```) and closing fence (```)
        inner = lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
        text = "\n".join(inner).strip()
    return json.loads(text)
