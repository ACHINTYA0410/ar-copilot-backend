"""PAN card validation: format rules + DB trace save."""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.kyc_document import EntityKycDocument
from app.services.pan_ocr_service import OCRResult

_PAN_RE = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")


@dataclass
class RuleResult:
    rule: str
    status: str  # PASS | FAIL | WARNING
    input_value: str | None
    database_value: str | None
    message: str


@dataclass
class DatabaseInfo:
    matched: bool = False
    pan_number: str | None = None
    entity_name: str | None = None
    entity_id: str | None = None
    trace_id: str | None = None
    note: str | None = None


@dataclass
class PANValidationResult:
    status: str  # PASS | FAIL | WARNING
    extracted: dict
    database: dict
    rules: list[dict]


def _run_format_rules(ocr: OCRResult) -> tuple[list[RuleResult], str]:
    """Run format-level rules. Returns (rule_results, overall_status)."""
    results: list[RuleResult] = []
    overall = "PASS"

    # Rule 1: OCR extraction
    if ocr.error:
        results.append(RuleResult(
            rule="PAN OCR Extraction",
            status="FAIL",
            input_value=None,
            database_value=None,
            message=f"OCR failed: {ocr.error}",
        ))
        return results, "FAIL"

    ocr_status = "PASS" if ocr.pan_number else "FAIL"
    results.append(RuleResult(
        rule="PAN OCR Extraction",
        status=ocr_status,
        input_value=ocr.pan_number,
        database_value=None,
        message=(
            f"PAN number extracted: {ocr.pan_number}"
            if ocr.pan_number
            else "PAN number is missing or could not be extracted from the document."
        ),
    ))
    if ocr_status == "FAIL":
        return results, "FAIL"

    # Rule 2: PAN mandatory
    if not ocr.pan_number:
        results.append(RuleResult(
            rule="PAN Required",
            status="FAIL",
            input_value=None,
            database_value=None,
            message="PAN number is mandatory.",
        ))
        return results, "FAIL"

    results.append(RuleResult(
        rule="PAN Required",
        status="PASS",
        input_value=ocr.pan_number,
        database_value=None,
        message="PAN number is present.",
    ))

    # Rule 3: Format validation
    if len(ocr.pan_number) != 10:
        results.append(RuleResult(
            rule="PAN Format",
            status="FAIL",
            input_value=ocr.pan_number,
            database_value=None,
            message=f"PAN number must be exactly 10 characters. Got {len(ocr.pan_number)}.",
        ))
        overall = "FAIL"
        return results, overall

    if not _PAN_RE.match(ocr.pan_number):
        results.append(RuleResult(
            rule="PAN Format",
            status="FAIL",
            input_value=ocr.pan_number,
            database_value=None,
            message="PAN number format is invalid. Expected format: ABCDE1234F.",
        ))
        overall = "FAIL"
        return results, overall

    results.append(RuleResult(
        rule="PAN Format",
        status="PASS",
        input_value=ocr.pan_number,
        database_value=None,
        message="PAN format is valid (5 letters, 4 digits, 1 letter).",
    ))

    return results, overall


async def _check_master_pan(db: AsyncSession, pan: str) -> DatabaseInfo:
    """
    Look for pan in existing master tables.
    Currently no master PAN column exists in deals/documents tables,
    so we return a truthful note instead of a fake match.
    """
    # If the schema is extended in future to include a PAN column on deals or
    # a vendor master table, query it here. For now we report the honest state.
    return DatabaseInfo(
        matched=False,
        note=(
            "No master PAN field exists in the current schema for database match. "
            "OCR extraction and format validation succeeded. "
            "Store the above trace record for auditing."
        ),
    )


async def save_kyc_trace(
    db: AsyncSession,
    ocr: OCRResult,
    validation_status: str,
    validation_message: str,
    filename: str | None = None,
) -> EntityKycDocument:
    record = EntityKycDocument(
        id=str(uuid.uuid4()),
        document_type="pan_card",
        original_file_name=filename,
        extracted_pan_number=ocr.pan_number,
        extracted_name=ocr.name,
        extracted_father_name=ocr.father_name,
        extracted_date_of_birth=ocr.date_of_birth,
        ocr_confidence=ocr.confidence,
        ocr_raw_text=ocr.raw_text,
        validation_status=validation_status,
        validation_message=validation_message,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(record)
    await db.flush()
    return record


async def validate_pan_document(
    db: AsyncSession,
    ocr: OCRResult,
    filename: str | None = None,
) -> PANValidationResult:
    format_rules, overall = _run_format_rules(ocr)

    db_info = DatabaseInfo()
    db_rule: RuleResult | None = None

    if overall != "FAIL" and ocr.pan_number:
        db_info = await _check_master_pan(db, ocr.pan_number)
        if db_info.matched:
            db_rule = RuleResult(
                rule="Database Match",
                status="PASS",
                input_value=ocr.pan_number,
                database_value=db_info.pan_number,
                message=f"PAN matched with database. Entity: {db_info.entity_name}",
            )
        else:
            db_rule = RuleResult(
                rule="Database Match",
                status="WARNING",
                input_value=ocr.pan_number,
                database_value=None,
                message=db_info.note or "No master PAN field for database comparison.",
            )
            if overall == "PASS":
                overall = "WARNING"

    all_rules = format_rules + ([db_rule] if db_rule else [])

    # Determine overall validation message
    if overall == "PASS":
        final_message = "PAN number is valid and matched with database."
    elif overall == "WARNING":
        final_message = (
            "PAN format is valid and OCR extraction succeeded. "
            + (db_info.note or "No master PAN for database match.")
        )
    else:
        failed = next((r for r in all_rules if r.status == "FAIL"), None)
        final_message = failed.message if failed else "PAN validation failed."

    # Save audit trace
    trace = await save_kyc_trace(
        db, ocr, overall, final_message, filename
    )
    db_info.trace_id = trace.id

    return PANValidationResult(
        status=overall,
        extracted={
            "pan_number": ocr.pan_number,
            "name": ocr.name,
            "father_name": ocr.father_name,
            "date_of_birth": ocr.date_of_birth,
            "confidence": ocr.confidence,
            "raw_text": ocr.raw_text,
            "possible_pan_numbers": ocr.possible_pan_numbers,
        },
        database={
            "matched": db_info.matched,
            "pan_number": db_info.pan_number,
            "entity_name": db_info.entity_name,
            "entity_id": db_info.entity_id,
            "trace_id": db_info.trace_id,
            "note": db_info.note,
        },
        rules=[
            {
                "rule": r.rule,
                "status": r.status,
                "inputValue": r.input_value,
                "databaseValue": r.database_value,
                "message": r.message,
            }
            for r in all_rules
        ],
    )
