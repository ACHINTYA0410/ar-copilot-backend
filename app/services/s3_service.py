"""
S3 service for fetching PO PDF documents.

boto3 is synchronous; all blocking calls run via asyncio.to_thread so they
don't stall the FastAPI event loop.
"""

import asyncio
import logging
import re
from typing import Optional

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

from app.config import settings

logger = logging.getLogger(__name__)

# S3 key pattern:  .../<deal_id>/PO/<filename>
# The deal_id is the numeric segment immediately before "/PO/"
_DEAL_ID_RE = re.compile(r"/(\d+)/PO/")


class S3ConfigError(Exception):
    """Raised when required S3 configuration is missing."""


class S3DocumentNotFoundError(Exception):
    """Raised when the requested S3 key does not exist."""


class S3AccessDeniedError(Exception):
    """Raised when credentials lack permission for the operation."""


class S3FetchError(Exception):
    """Raised for any other S3 or network error."""


def _get_client():
    """Build a boto3 S3 client from settings. Never logs credentials."""
    if not settings.AWS_ACCESS_KEY_ID or not settings.AWS_SECRET_ACCESS_KEY:
        raise S3ConfigError("AWS credentials are not configured.")
    if not settings.S3_BUCKET_NAME:
        raise S3ConfigError("S3_BUCKET_NAME is not configured.")

    return boto3.client(
        "s3",
        region_name=settings.AWS_REGION,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    )


def parse_deal_id_from_key(s3_key: str) -> Optional[str]:
    """
    Extract the deal_id from an S3 key like:
      oms/prod/uploads/6071536739/PO/Commitment_6534_2026-06-03_5Fvikz.pdf

    Returns the numeric deal_id string, or None if the pattern doesn't match.
    """
    match = _DEAL_ID_RE.search(s3_key)
    return match.group(1) if match else None


def _sync_fetch(s3_key: str) -> bytes:
    """Blocking download — intended to run in a thread pool."""
    client = _get_client()
    try:
        response = client.get_object(Bucket=settings.S3_BUCKET_NAME, Key=s3_key)
        return response["Body"].read()
    except ClientError as exc:
        code = exc.response["Error"]["Code"]
        if code in ("NoSuchKey", "404"):
            raise S3DocumentNotFoundError(f"Key not found: {s3_key}") from exc
        if code in ("AccessDenied", "403"):
            raise S3AccessDeniedError("Access denied — check IAM permissions.") from exc
        # Do NOT include exc message; it may contain bucket/key internals but
        # credentials are never in ClientError messages so logging code is safe.
        logger.warning("S3 ClientError %s fetching document", code)
        raise S3FetchError(f"S3 error ({code}) while fetching document.") from exc
    except NoCredentialsError as exc:
        raise S3ConfigError("AWS credentials are invalid or expired.") from exc


def _sync_head_bucket() -> dict:
    """Blocking HEAD-bucket call — used for the health check."""
    client = _get_client()
    try:
        client.head_bucket(Bucket=settings.S3_BUCKET_NAME)
        return {"bucket": settings.S3_BUCKET_NAME, "region": settings.AWS_REGION}
    except ClientError as exc:
        code = exc.response["Error"]["Code"]
        if code in ("AccessDenied", "403"):
            raise S3AccessDeniedError("Credentials valid but access to bucket is denied.") from exc
        if code in ("NoSuchBucket", "404"):
            raise S3DocumentNotFoundError(f"Bucket '{settings.S3_BUCKET_NAME}' does not exist.") from exc
        logger.warning("S3 health check ClientError %s", code)
        raise S3FetchError(f"S3 error ({code}) during health check.") from exc
    except NoCredentialsError as exc:
        raise S3ConfigError("AWS credentials are invalid or expired.") from exc


async def fetch_po_document(s3_key: str) -> bytes:
    """
    Download a PO PDF from S3 and return its raw bytes.

    Raises:
        S3ConfigError           — credentials or bucket name missing/invalid
        S3DocumentNotFoundError — the key does not exist in the bucket
        S3AccessDeniedError     — IAM permission denied
        S3FetchError            — any other S3 / network error
    """
    return await asyncio.to_thread(_sync_fetch, s3_key)


async def check_s3_connectivity() -> dict:
    """
    Verify S3 access with a HEAD-bucket request (no download).

    Returns a dict with bucket and region on success.
    Raises S3ConfigError / S3AccessDeniedError / S3FetchError on failure.
    """
    return await asyncio.to_thread(_sync_head_bucket)
