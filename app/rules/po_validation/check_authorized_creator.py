from app.rules.base import BaseRule, RuleContext
from app.services.ai_service import AIService, RuleEvaluation

_LEAD_DOMAIN = "@leadschool.in"


class CheckAuthorizedCreatorRule(BaseRule):
    rule_id = "po_rule_authorized_creator"
    name = "PO created by authorized LEAD user"
    section = "Authorization"
    required_context = ["po_data"]

    def _get_prompt(self) -> str:
        return f"Verify the PO was created by a user with a {_LEAD_DOMAIN} email address."

    async def evaluate(self, context: RuleContext, ai_service: AIService) -> RuleEvaluation:
        po = context.deal_data
        created_by = po.get("created_by", "")

        if created_by.lower().endswith(_LEAD_DOMAIN):
            return RuleEvaluation(
                status="pass",
                confidence=1.0,
                evidence=f"Creator {created_by} is a verified LEAD domain user.",
                reasoning="The created_by email belongs to the @leadschool.in domain, confirming an authorized internal creator.",
                runtime_ms=0,
            )
        return RuleEvaluation(
            status="fail",
            confidence=1.0,
            evidence=f"Creator email {created_by} is not a LEAD domain address.",
            reasoning=(
                f"The PO creator ({created_by}) does not have a {_LEAD_DOMAIN} email. "
                "Only verified LEAD employees may raise POs in ORP. "
                "This may indicate a data entry error or an unauthorized submission."
            ),
            runtime_ms=0,
        )
