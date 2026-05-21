from app.rules.base import BaseRule


class CheckCreditLimitRule(BaseRule):
    rule_id = "rule_check_credit_limit"
    name = "Customer Credit Limit Check"
    section = "Policy"
    required_context = ["deal.amount", "hubspot.credit_limit", "hubspot.overdue_invoices"]

    def _get_prompt(self) -> str:
        return (
            "Compare the deal value against the customer's approved credit limit in HubSpot Finance. "
            "Check for any overdue invoices on the account. "
            "Deal value exceeding credit limit is a failure. Overdue invoices are a warning."
        )
