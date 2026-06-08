import logging

import mysql.connector
from fastapi import APIRouter, HTTPException, Query

from app.services.reconciliation_service import reconcile_order
from app.services.s3_service import (
    S3AccessDeniedError,
    S3ConfigError,
    S3DocumentNotFoundError,
    S3FetchError,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/po-validation", tags=["po-validation"])


@router.post("/reconcile")
async def reconcile_po(
    order_id: int = Query(..., description="ORP order_id to reconcile"),
):
    """
    Reconcile the PO proof document against ORP order line items.

    Pipeline:
      1. Look up the proof PDF via order_assets
      2. Fetch from S3 + AI vision extraction (Phase 1 + 2)
      3. Fetch ORP order line items
      4. AI semantic matching — item names only, quantities never sent to AI
      5. Deterministic quantity comparison + verdict (pure Python)

    Returns a full reconciliation result with per-item status, unmatched items
    on both sides, and a green / amber / red verdict.
    """
    try:
        return await reconcile_order(order_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except S3ConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except S3DocumentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except S3AccessDeniedError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except S3FetchError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    except NotImplementedError as exc:
        raise HTTPException(status_code=501, detail=str(exc))
    except mysql.connector.Error:
        raise HTTPException(
            status_code=503,
            detail="Cannot reach ORP MySQL. Check VPN/network access and retry.",
        )
    except Exception as exc:
        logger.exception("Unexpected error reconciling order_id=%s", order_id)
        raise HTTPException(status_code=500, detail=f"Reconciliation error: {exc}")
