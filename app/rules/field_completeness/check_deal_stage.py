from app.rules.base import BaseRule


class CheckDealStageRule(BaseRule):
    rule_id = "rule_check_deal_stage"
    name = "Deal Stage Valid for Submission"
    section = "Field Completeness"
    required_context = ["hubspot.deal_stage", "hubspot.stage_history"]

    def _get_prompt(self) -> str:
        return (
            "Verify the deal stage is 'Contract Sent'. "
            "Check the stage progression history for any skipped or reversed stages."
        )
