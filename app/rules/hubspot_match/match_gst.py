from app.rules.base import BaseRule


class MatchGstRule(BaseRule):
    rule_id = "rule_match_gst"
    name = "GST Number Matches HubSpot"
    section = "HubSpot Match"
    required_context = ["documents", "hubspot.gst"]

    def _get_prompt(self) -> str:
        return (
            "Extract the GST number from the attached GST certificate. "
            "Compare it with the HubSpot GST field. Match must be exact. "
            "Also validate: (1) the PAN embedded in the GSTIN matches the PAN card, "
            "(2) the state code is consistent with the registered address."
        )
