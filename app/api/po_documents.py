import logging
import tempfile

from fastapi import APIRouter, HTTPException, Query

from app.services.s3_service import (
    S3AccessDeniedError,
    S3ConfigError,
    S3DocumentNotFoundError,
    S3FetchError,
    check_s3_connectivity,
    fetch_po_document,
    parse_deal_id_from_key,
)
from app.services.vision_service import get_extractor

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/po-documents", tags=["po-documents"])

_PDF_MAGIC = b"%PDF"


@router.get("/health")
async def po_documents_health():
    """
    Verify S3 credentials and bucket reachability using a HEAD request.
    No data is downloaded.
    """
    try:
        info = await check_s3_connectivity()
        return {"status": "ok", "s3": info}
    except S3ConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except S3AccessDeniedError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except S3FetchError as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.get("/fetch")
async def fetch_po_document_metadata(
    s3_key: str = Query(..., description="Full S3 object key for the PO PDF"),
    save_temp: bool = Query(False, description="Save to a temp file and return its path"),
):
    """
    Download a PO PDF from S3 and return its metadata.

    Returns file size, content type, parsed deal_id, and (optionally) a temp
    file path.  Raw bytes are never returned — use save_temp=true to inspect
    the file locally.
    """
    deal_id = parse_deal_id_from_key(s3_key)

    try:
        pdf_bytes = await fetch_po_document(s3_key)
    except S3ConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except S3DocumentNotFoundError:
        raise HTTPException(status_code=404, detail=f"Document not found: {s3_key}")
    except S3AccessDeniedError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except S3FetchError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    is_pdf = pdf_bytes[:4] == _PDF_MAGIC
    content_type = "application/pdf" if is_pdf else "application/octet-stream"

    temp_path = None
    if save_temp:
        suffix = ".pdf" if is_pdf else ".bin"
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=suffix, prefix="po_doc_"
        ) as tmp:
            tmp.write(pdf_bytes)
            temp_path = tmp.name

    return {
        "fetched": True,
        "s3_key": s3_key,
        "deal_id": deal_id,
        "file_size_bytes": len(pdf_bytes),
        "content_type": content_type,
        "is_valid_pdf": is_pdf,
        **({"temp_path": temp_path} if temp_path else {}),
    }


@router.post("/extract")
async def extract_po_document(
    s3_key: str = Query(..., description="Full S3 object key for the PO PDF"),
):
    """
    Download a PO PDF from S3 and extract structured line-item data using AI vision.

    Returns both the parsed JSON and the raw model output.
    If the model returns malformed JSON, a 422 is returned with the raw output
    so you can inspect what the model actually said.
    """
    deal_id = parse_deal_id_from_key(s3_key)

    # --- fetch from S3 ---
    try:
        pdf_bytes = await fetch_po_document(s3_key)
    except S3ConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except S3DocumentNotFoundError:
        raise HTTPException(status_code=404, detail=f"Document not found: {s3_key}")
    except S3AccessDeniedError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except S3FetchError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    if pdf_bytes[:4] != _PDF_MAGIC:
        raise HTTPException(status_code=422, detail="S3 object does not appear to be a PDF.")

    # --- run vision extraction ---
    try:
        extractor = get_extractor()
        result = await extractor.extract(pdf_bytes)
    except NotImplementedError as exc:
        raise HTTPException(status_code=501, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        logger.exception("Vision extraction failed for %s", s3_key)
        raise HTTPException(status_code=502, detail=f"Vision extraction error: {exc}")

    # --- return result ---
    if result.parse_error:
        # Model responded but JSON was unparseable — return 422 with raw so
        # the caller can see exactly what the model said
        raise HTTPException(
            status_code=422,
            detail={
                "error": "Model returned non-JSON output",
                "parse_error": result.parse_error,
                "raw_model_output": result.raw,
                "model": result.model,
                "pages_sent": result.pages_sent,
            },
        )

    return {
        "s3_key": s3_key,
        "deal_id": deal_id,
        "model": result.model,
        "pages_sent": result.pages_sent,
        "extracted": result.parsed,
        "raw_model_output": result.raw,
    }
