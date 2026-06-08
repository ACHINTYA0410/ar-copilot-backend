from app.rules.base import BaseRule, RuleContext
from app.rules.po_validation._groq_helper import enrich_with_groq
from app.services.ai_service import AIService, RuleEvaluation

_AGING_WARN_THRESHOLD_MINUTES = 30


class CheckFinanceApprovalAgingRule(BaseRule):
    rule_id = "po_rule_finance_approval_aging"
    name = "PO is not stuck awaiting Finance approval"
    section = "Workflow Health"
    required_context = ["po_data"]

    def _get_prompt(self) -> str:
        return (
            f"If the PO is in FIN_HOLD status and has been waiting more than "
            f"{_AGING_WARN_THRESHOLD_MINUTES} minutes, flag it as a warning."
        )

    async def evaluate(self, context: RuleContext, ai_service: AIService) -> RuleEvaluation:
        po = context.deal_data
        status = po.get("current_order_status", "")
        aging = po.get("approval_aging_minutes")

        if status != "FIN_HOLD":
            result = RuleEvaluation(
                status="pass",
                confidence=1.0,
                evidence=f"PO status is {status} — Finance aging check not applicable.",
                reasoning="Rule only triggers when the PO is in FIN_HOLD. No action required.",
                runtime_ms=0,
            )
        elif aging is None:
            result = RuleEvaluation(
                status="pass",
                confidence=0.85,
                evidence="PO is in FIN_HOLD but approval_aging_minutes is not recorded.",
                reasoning="Cannot determine aging without the timestamp. Treating as non-blocking.",
                runtime_ms=0,
            )
        elif aging > _AGING_WARN_THRESHOLD_MINUTES:
            result = RuleEvaluation(
                status="warning",
                confidence=0.9,
                evidence=(
                    f"PO has been in FIN_HOLD for {aging} minutes "
                    f"(threshold: {_AGING_WARN_THRESHOLD_MINUTES} min) — consider chasing Finance."
                ),
                reasoning=(
                    f"The PO entered FIN_HOLD {aging} minutes ago. Prolonged holds delay revenue "
                    "recognition and school onboarding. Recommend escalating to Finance."
                ),
                runtime_ms=0,
            )
        else:
            result = RuleEvaluation(
                status="pass",
                confidence=0.95,
                evidence=f"PO is in FIN_HOLD for {aging} minutes — within acceptable wait time.",
                reasoning=f"Aging ({aging} min) is below the {_AGING_WARN_THRESHOLD_MINUTES}-minute threshold. No action needed yet.",
                runtime_ms=0,
            )

        return await enrich_with_groq(result, self.name, self._get_prompt(), po)
