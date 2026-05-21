from app.rules.base import BaseRule


class CheckOnboardingDateRule(BaseRule):
    rule_id = "rule_check_onboarding_date"
    name = "Onboarding Date Feasibility"
    section = "Field Completeness"
    required_context = ["deal.submitted_at", "hubspot.onboarding_start_date"]

    def _get_prompt(self) -> str:
        return (
            "Check that the onboarding start date is at least 14 days after the submission date. "
            "Flag as warning if the gap is 14–21 days. Flag as fail if less than 14 days."
        )
