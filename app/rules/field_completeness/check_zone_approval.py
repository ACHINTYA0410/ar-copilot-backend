from app.rules.base import BaseRule


class CheckZoneApprovalRule(BaseRule):
    rule_id = "rule_check_zone_approval"
    name = "Zone Manager Approval Recorded"
    section = "Field Completeness"
    required_context = ["deal.amount", "deal.submitted_by_zone", "hubspot.activity_log"]

    def _get_prompt(self) -> str:
        return (
            "Verify that Zone Manager approval is recorded in HubSpot for this deal. "
            "If deal amount ≤ ₹50L, zone manager solo approval is sufficient. "
            "If amount > ₹50L, verify escalation approval is also present."
        )
