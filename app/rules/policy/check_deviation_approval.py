from app.rules.base import BaseRule


class CheckDeviationApprovalRule(BaseRule):
    rule_id = "rule_check_deviation_approval"
    name = "Deviation % Drives ZCEO/Arvind Approval"
    section = "Policy"
    required_context = ["deal.amount", "hubspot.list_price", "documents"]

    def _get_prompt(self) -> str:
        return (
            "Calculate the discount percentage: ((list_price - contract_value) / list_price) * 100. "
            "If discount > 10%, verify that a ZCEO approval email from Arvind Sharma is attached "
            "to the document bundle or recorded in the HubSpot activity log. "
            "If discount > 20%, verify that both ZCEO and CFO approvals are present. "
            "A missing required approval is a failure. Report the exact discount percentage calculated."
        )
