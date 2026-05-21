from app.rules.base import BaseRule


class MatchPanRule(BaseRule):
    rule_id = "rule_match_pan"
    name = "PAN Matches HubSpot Record"
    section = "HubSpot Match"
    required_context = ["documents", "hubspot.pan"]

    def _get_prompt(self) -> str:
        return (
            "Extract the PAN number from the attached PAN card document. "
            "Compare it exactly with the PAN number stored in the HubSpot KYC record for this customer. "
            "The match must be exact (case-insensitive). Any discrepancy is a failure."
        )
