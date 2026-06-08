from app.rules.base import BaseRule, RuleContext
from app.rules.po_validation._groq_helper import enrich_with_groq
from app.services.ai_service import AIService, RuleEvaluation


class CheckLinkedDealExistsRule(BaseRule):
    rule_id = "po_rule_linked_deal_exists"
    name = "PO is linked to an existing deal"
    section = "Deal Linkage"
    required_context = ["po_data"]

    def _get_prompt(self) -> str:
        return "Verify the PO's deal_id references an existing deal in the AR Co-Pilot system."

    async def evaluate(self, context: RuleContext, ai_service: AIService) -> RuleEvaluation:
        po = context.deal_data
        deal_id = po.get("deal_id", "")
        found = po.get("_linked_deal_found", False)

        if found:
            result = RuleEvaluation(
                status="pass",
                confidence=1.0,
                evidence=f"Deal ID {deal_id} found in the deals table.",
                reasoning="Direct DB lookup confirmed the referenced deal exists in the local system.",
                runtime_ms=0,
            )
        else:
            result = RuleEvaluation(
                status="fail",
                confidence=1.0,
                evidence=f"Deal ID {deal_id} not found in deals table.",
                reasoning=(
                    "The PO references a deal ID that does not exist in the AR Co-Pilot deals table. "
                    "This is an orphan PO — it may belong to a deal not yet synced from HubSpot."
                ),
                runtime_ms=0,
            )

        return await enrich_with_groq(result, self.name, self._get_prompt(), po)
