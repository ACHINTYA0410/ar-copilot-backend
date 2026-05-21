from app.rules.base import BaseRule


class CheckPageCompletenessRule(BaseRule):
    rule_id = "rule_check_page_completeness"
    name = "All Annexures & Schedules Present"
    section = "Document Content"
    required_context = ["documents"]

    def _get_prompt(self) -> str:
        return (
            "Extract the table of contents from the agreement. "
            "Verify that every referenced annexure and schedule is present and not blank. "
            "Report any missing or blank pages that correspond to required sections."
        )
