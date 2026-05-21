from app.rules.base import BaseRule


class MatchAddressRule(BaseRule):
    rule_id = "rule_match_address"
    name = "Registered Address Matches HubSpot"
    section = "HubSpot Match"
    required_context = ["documents", "hubspot.billing_address"]

    def _get_prompt(self) -> str:
        return (
            "Extract the registered address from the agreement. "
            "Compare with HubSpot billing address using standard normalisation. "
            "Pincode, city, and state must match exactly after normalisation."
        )
