from app.rules.base import BaseRule


class CheckEffectiveDateRule(BaseRule):
    rule_id = "rule_check_effective_date"
    name = "Effective Date Matches Deal ID"
    section = "Document Content"
    required_context = ["documents", "deal.submitted_at", "deal.id"]

    def _get_prompt(self) -> str:
        return (
            "Extract the effective date from the agreement and compare it with: "
            "(1) the Deal ID creation timestamp in the system, "
            "(2) the Onboarding Start Date in HubSpot. "
            "Flag any discrepancies greater than 7 calendar days as a warning. "
            "Discrepancies greater than 30 days should be flagged as a failure."
        )
