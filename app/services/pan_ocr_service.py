"""PAN card OCR using Groq vision API (Llama 4 Scout)."""
from __future__ import annotations

import base64
import json
import logging
import re
from dataclasses import dataclass, field

import httpx

from app.config import settings

log = logging.getLogger(__name__)

_GROQ_BASE = "https://api.groq.com/openai/v1"

_OCR_PROMPT = (
    "Extract PAN card details from this document. "
    "Return ONLY valid JSON with exactly these keys: "
    "pan_number, name, father_name, date_of_birth, raw_text, confidence, possible_pan_numbers. "
    "The PAN number must match the Indian PAN pattern: five uppercase letters, four digits, one uppercase letter "
    "(example: ABCDE1234F). "
    "confidence must be a float between 0 and 1 representing your extraction certainty. "
    "possible_pan_numbers must be a list of strings of any other PAN-like values found. "
    "If a value is not visible return null. Do not invent values. Do not include markdown fences."
)

_PAN_RE = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")
_PAN_LOOSE = re.compile(r"[A-Z]{5}[0-9]{4}[A-Z]")


@dataclass
class OCRResult:
    pan_number: str | None = None
    name: str | None = None
    father_name: str | None = None
    date_of_birth: str | None = None
    raw_text: str | None = None
    confidence: float | None = None
    possible_pan_numbers: list[str] = field(default_factory=list)
    error: str | None = None


def _normalize_pan(pan: str | None) -> str | None:
    if not pan:
        return None
    return pan.upper().replace(" ", "").replace("-", "").strip()


def _extract_json(text: str) -> dict:
    """Strip markdown fences and parse JSON. Falls back to regex field extraction."""
    cleaned = re.sub(r"^```[a-z]*\n?", "", text.strip(), flags=re.MULTILINE)
    cleaned = re.sub(r"```$", "", cleaned.strip())
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Fallback: try to find a JSON object anywhere in the response
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    # Last resort: regex-extract PAN-like strings from raw text
    pans = _PAN_LOOSE.findall(text)
    return {
        "pan_number": pans[0] if pans else None,
        "name": None,
        "father_name": None,
        "date_of_birth": None,
        "raw_text": text,
        "confidence": 0.3 if pans else 0.1,
        "possible_pan_numbers": pans[1:] if len(pans) > 1 else [],
    }


def _parse_ocr_response(raw: str) -> OCRResult:
    data = _extract_json(raw)

    pans: list[str] = [p for p in (data.get("possible_pan_numbers") or []) if isinstance(p, str)]
    pan = _normalize_pan(data.get("pan_number"))

    # If pan_number missing but a valid PAN sits in possible_pan_numbers, promote it
    if not pan:
        for candidate in pans:
            c = _normalize_pan(candidate)
            if c and _PAN_RE.match(c):
                pan = c
                break

    confidence_raw = data.get("confidence")
    try:
        confidence = float(confidence_raw) if confidence_raw is not None else None
    except (TypeError, ValueError):
        confidence = None

    return OCRResult(
        pan_number=pan,
        name=data.get("name"),
        father_name=data.get("father_name"),
        date_of_birth=data.get("date_of_birth"),
        raw_text=data.get("raw_text"),
        confidence=confidence,
        possible_pan_numbers=pans,
    )


async def _ocr_image_bytes(image_bytes: bytes, mime: str) -> OCRResult:
    api_key = settings.GROQ_API_KEY
    if not api_key:
        return OCRResult(error="GROQ_API_KEY is not configured. Set it in your .env file.")

    b64 = base64.b64encode(image_bytes).decode()
    data_url = f"data:{mime};base64,{b64}"

    payload = {
        "model": settings.GROQ_VISION_MODEL,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": data_url}},
                    {"type": "text", "text": _OCR_PROMPT},
                ],
            }
        ],
        "temperature": 0,
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(f"{_GROQ_BASE}/chat/completions", json=payload, headers=headers)

    if resp.status_code != 200:
        safe_detail = resp.text[:300].replace(api_key, "[redacted]")
        log.error("Groq OCR error %s: %s", resp.status_code, safe_detail)
        return OCRResult(error=f"Groq API returned status {resp.status_code}: {safe_detail}")

    body = resp.json()
    content = body["choices"][0]["message"]["content"]
    log.debug("Groq OCR raw response length=%d", len(content))
    return _parse_ocr_response(content)


def _pdf_to_image_bytes(pdf_bytes: bytes) -> tuple[bytes, str] | None:
    """Convert first PDF page to PNG bytes. Returns (png_bytes, 'image/png') or None."""
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        page = doc[0]
        mat = fitz.Matrix(2, 2)  # 2x zoom for better OCR quality
        pix = page.get_pixmap(matrix=mat)
        return pix.tobytes("png"), "image/png"
    except ImportError:
        pass

    try:
        from pypdf import PdfReader
        import io
        reader = PdfReader(io.BytesIO(pdf_bytes))
        text = ""
        for page in reader.pages:
            text += page.extract_text() or ""
        if text.strip():
            return None  # signal caller to use text path
    except ImportError:
        pass

    return None


async def _ocr_pdf_bytes(pdf_bytes: bytes) -> OCRResult:
    result = _pdf_to_image_bytes(pdf_bytes)
    if result is not None:
        img_bytes, mime = result
        return await _ocr_image_bytes(img_bytes, mime)

    # Try plain text extraction via pypdf
    try:
        from pypdf import PdfReader
        import io
        reader = PdfReader(io.BytesIO(pdf_bytes))
        text = "\n".join(p.extract_text() or "" for p in reader.pages)
        if text.strip():
            pans = _PAN_LOOSE.findall(text.upper())
            pan = _normalize_pan(pans[0]) if pans else None
            return OCRResult(
                pan_number=pan,
                raw_text=text,
                confidence=0.7 if pan else 0.2,
                possible_pan_numbers=pans[1:],
            )
    except ImportError:
        pass

    return OCRResult(
        error=(
            "PDF image rendering is not available. "
            "Install PyMuPDF (`pip install pymupdf`) for scanned PDF support, "
            "or upload a PNG/JPG image of the PAN card."
        )
    )


async def run_pan_ocr(file_bytes: bytes, filename: str, content_type: str) -> OCRResult:
    """Main entry point. Accepts image or PDF bytes, returns OCRResult."""
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""

    is_pdf = ext == "pdf" or content_type == "application/pdf"
    if is_pdf:
        return await _ocr_pdf_bytes(file_bytes)

    # Image path
    mime_map = {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "webp": "image/webp",
    }
    mime = mime_map.get(ext) or content_type or "image/jpeg"
    return await _ocr_image_bytes(file_bytes, mime)
