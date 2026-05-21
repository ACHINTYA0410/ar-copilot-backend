from app.rules.base import BaseRule


class MatchAmountRule(BaseRule):
    rule_id = "rule_match_amount"
    name = "Onboarding Amount Matches HubSpot"
    section = "HubSpot Match"
    required_context = ["documents", "deal.amount", "hubspot.deal_amount"]

    def _get_prompt(self) -> str:
        return (
            "Extract the total contract value from the agreement document. "
            "Compare it with the Deal Amount field in HubSpot. "
            "Allow a tolerance of up to 2% for rounding differences. "
            "A discrepancy greater than 2% is a failure. "
            "Report the exact extracted value and the HubSpot value."
        )
