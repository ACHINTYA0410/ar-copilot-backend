"""
Shared Groq enrichment helper for PO validation rules.

Call enrich_with_groq() after the deterministic check. It replaces confidence and
reasoning with Groq-generated values while keeping the deterministic status as
ground truth. Falls back silently to the deterministic values on any failure.
"""
import logging

from app.services.ai_service import RuleEvaluation

logger = logging.getLogger(__name__)


async def enrich_with_groq(
    deterministic: RuleEvaluation,
    rule_name: str,
    rule_purpose: str,
    po_data: dict,
) -> RuleEvaluation:
    """
    Enrich a deterministic RuleEvaluation with Groq confidence + reasoning.

    - Status (pass/warning/fail) is NEVER changed — deterministic logic is ground truth.
    - Evidence is kept from the deterministic check.
    - confidence and reasoning come from Groq when USE_GROQ_FOR_PO=True and key is present.
    - Any Groq failure (timeout, rate-limit, bad JSON, no key) falls back silently.
    """
    from app.config import settings
    from app.services import groq_service

    if not settings.USE_GROQ_FOR_PO or not settings.GROQ_API_KEY:
        return deterministic

    try:
        scored = await groq_service.score_rule(
            rule_name=rule_name,
            rule_purpose=rule_purpose,
            deterministic_status=deterministic.status,
            po_data=po_data,
        )
        return RuleEvaluation(
            status=deterministic.status,
            confidence=scored["confidence"],
            evidence=deterministic.evidence,
            reasoning=scored["reasoning"] or deterministic.reasoning,
            runtime_ms=deterministic.runtime_ms,
        )
    except Exception as exc:
        logger.warning("Groq enrichment failed for rule '%s': %s", rule_name, exc)
        return deterministic
