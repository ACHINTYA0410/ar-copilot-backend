from app.rules.base import BaseRule, RuleContext
from app.services.ai_service import AIService, RuleEvaluation


class CheckNotificationRoutingRule(BaseRule):
    rule_id = "po_rule_notification_routing"
    name = "Notification target matches deal distribution model"
    section = "Customer Approval Flow"
    required_context = ["po_data"]

    def _get_prompt(self) -> str:
        # TODO: becomes deterministic once deals.distribution_model is added to the deals table
        return (
            "Verify that the notification_sent_to field (school or distributor) matches the "
            "expected distribution model for this deal. Flag if the routing appears inconsistent."
        )

    async def evaluate(self, context: RuleContext, ai_service: AIService) -> RuleEvaluation:
        # Delegates to the mocked AI service so the lookup hits _PO_RESPONSES in ai_service
        from app.models.rule import Rule, ActionOnFail

        rule_obj = Rule(
            id=self.rule_id,
            name=self.name,
            section=self.section,
            prompt=self._get_prompt(),
            required_context=self.required_context,
            confidence_threshold=0.7,
            action_on_fail=ActionOnFail.flag_review,
        )
        po_context = {"order_id": context.deal_id, **context.deal_data}
        return await ai_service.evaluate_po_rule(rule_obj, po_context)
