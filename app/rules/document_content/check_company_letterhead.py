from app.rules.base import BaseRule


class CheckCompanyLetterheadRule(BaseRule):
    rule_id = "rule_check_company_letterhead"
    name = "Company Letterhead & CIN"
    section = "Document Content"
    required_context = ["documents", "deal.customer_name"]

    def _get_prompt(self) -> str:
        return (
            "Verify that the document bears official company letterhead on the cover page. "
            "Extract the CIN and verify it against MCA21 registry records. "
            "Confirm the registered address on the letterhead matches HubSpot."
        )
