from app.rules.base import BaseRule


class CheckRequiredFieldsRule(BaseRule):
    rule_id = "rule_check_required_fields"
    name = "All Compulsory HubSpot Fields Filled"
    section = "Field Completeness"
    required_context = ["hubspot.all_fields"]

    REQUIRED_FIELDS = [
        "company_name", "pan", "gst", "billing_address", "contact_name",
        "contact_email", "contact_phone", "deal_owner", "deal_stage",
        "amount", "products", "region", "onboarding_start_date", "contract_term",
    ]

    def _get_prompt(self) -> str:
        fields = ", ".join(self.REQUIRED_FIELDS)
        return (
            f"Check that the following 14 mandatory HubSpot fields are all populated "
            f"with non-null, non-empty values for this deal: {fields}. "
            "Report any missing or empty fields. A single missing field is a failure."
        )
