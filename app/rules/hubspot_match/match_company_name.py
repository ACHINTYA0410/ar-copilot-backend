from app.rules.base import BaseRule


class MatchCompanyNameRule(BaseRule):
    rule_id = "rule_match_company_name"
    name = "Company Name Matches HubSpot"
    section = "HubSpot Match"
    required_context = ["documents", "hubspot.company_name"]

    def _get_prompt(self) -> str:
        return (
            "Extract the customer company name from the agreement. "
            "Compare it with the HubSpot Company Name field using normalisation "
            "(expand abbreviations: Pvt→Private, Ltd→Limited). "
            "After normalisation, the names must match exactly."
        )
