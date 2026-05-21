from app.rules.base import BaseRule


class MatchContactDetailsRule(BaseRule):
    rule_id = "rule_match_contact_details"
    name = "Contact Details Match HubSpot"
    section = "HubSpot Match"
    required_context = ["documents", "hubspot.contact_email", "hubspot.contact_phone"]

    def _get_prompt(self) -> str:
        return (
            "Extract the signatory's email and phone from the agreement. "
            "Compare with HubSpot primary contact record. "
            "Flag any discrepancy in email domain or phone number as a warning. "
            "An exact mismatch on both email and phone is a failure."
        )
