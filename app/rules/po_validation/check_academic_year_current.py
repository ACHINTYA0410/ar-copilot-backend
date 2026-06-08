from app.rules.base import BaseRule, RuleContext
from app.rules.po_validation._groq_helper import enrich_with_groq
from app.services.ai_service import AIService, RuleEvaluation

# TODO: source this from config/settings once the academic cycle is configurable
_CURRENT_ACADEMIC_YEAR = "26-27"


class CheckAcademicYearCurrentRule(BaseRule):
    rule_id = "po_rule_academic_year_current"
    name = "PO academic year matches current cycle"
    section = "Deal Linkage"
    required_context = ["po_data"]

    def _get_prompt(self) -> str:
        return f"Verify the PO's order_academic_year matches the current cycle ({_CURRENT_ACADEMIC_YEAR})."

    async def evaluate(self, context: RuleContext, ai_service: AIService) -> RuleEvaluation:
        po = context.deal_data
        year = po.get("order_academic_year", "")

        if year == _CURRENT_ACADEMIC_YEAR:
            result = RuleEvaluation(
                status="pass",
                confidence=1.0,
                evidence=f"Academic year {year} matches the current cycle ({_CURRENT_ACADEMIC_YEAR}).",
                reasoning="The PO's academic year is the active cycle. No mismatch detected.",
                runtime_ms=0,
            )
        else:
            result = RuleEvaluation(
                status="fail",
                confidence=1.0,
                evidence=f"Academic year {year} is not the current cycle ({_CURRENT_ACADEMIC_YEAR}).",
                reasoning=(
                    f"The PO was raised for academic year {year}, which is not the active cycle "
                    f"({_CURRENT_ACADEMIC_YEAR}). Processing a stale-year PO risks booking revenue "
                    "against the wrong period."
                ),
                runtime_ms=0,
            )

        return await enrich_with_groq(result, self.name, self._get_prompt(), po)
