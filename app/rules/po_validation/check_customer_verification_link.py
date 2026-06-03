from app.rules.base import BaseRule, RuleContext
from app.services.ai_service import AIService, RuleEvaluation


class CheckCustomerVerificationLinkRule(BaseRule):
    rule_id = "po_rule_customer_verification"
    name = "Customer verification link is healthy"
    section = "Customer Approval Flow"
    required_context = ["po_data"]

    def _get_prompt(self) -> str:
        return (
            "Verify that the customer verification link has been sent and is in a healthy state. "
            "FIN_APPROVED POs must have an APPROVED link; ACTIVE links without po_approved_on are stalled."
        )

    async def evaluate(self, context: RuleContext, ai_service: AIService) -> RuleEvaluation:
        po = context.deal_data
        order_status = po.get("current_order_status", "")
        link_status = po.get("po_link_status")
        approved_on = po.get("po_approved_on")
        customer = po.get("customer_name", "the customer")

        if order_status == "FIN_APPROVED" and link_status is None:
            return RuleEvaluation(
                status="fail",
                confidence=0.97,
                evidence="PO is Finance-approved but no verification link has been sent to the customer.",
                reasoning=(
                    "A FIN_APPROVED PO must have a customer verification link issued before the order "
                    "can be considered fully complete. Missing link means the customer has not confirmed "
                    "receipt, which is a compliance gap."
                ),
                runtime_ms=0,
            )

        if link_status == "INACTIVE":
            return RuleEvaluation(
                status="warning",
                confidence=0.88,
                evidence=f"Verification link for {customer} is INACTIVE — customer may not have received it.",
                reasoning=(
                    "An INACTIVE link typically means the WhatsApp delivery failed or the link expired. "
                    "Customer approval cannot be collected until a fresh link is issued."
                ),
                runtime_ms=0,
            )

        if link_status == "APPROVED":
            return RuleEvaluation(
                status="pass",
                confidence=0.99,
                evidence=f"Customer {customer} approved via verification link (approved on {approved_on}).",
                reasoning="Link status APPROVED confirms the customer acknowledged and accepted the PO.",
                runtime_ms=0,
            )

        if link_status == "ACTIVE" and not approved_on:
            return RuleEvaluation(
                status="warning",
                confidence=0.82,
                evidence=f"Verification link sent to {customer} but customer has not approved yet.",
                reasoning=(
                    "The link is live (ACTIVE) but po_approved_on is null, meaning the customer "
                    "has not clicked through. Consider sending a reminder if too much time has elapsed."
                ),
                runtime_ms=0,
            )

        return RuleEvaluation(
            status="pass",
            confidence=0.90,
            evidence=f"Verification link status is {link_status!r} — no issues detected.",
            reasoning="Verification link state is acceptable for the current order status.",
            runtime_ms=0,
        )
