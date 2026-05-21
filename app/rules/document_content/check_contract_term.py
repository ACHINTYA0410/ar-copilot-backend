from app.rules.base import BaseRule


class CheckContractTermRule(BaseRule):
    rule_id = "rule_check_contract_term"
    name = "Contract Term Within Approved Range"
    section = "Document Content"
    required_context = ["documents"]

    def _get_prompt(self) -> str:
        return (
            "Extract the contract duration from the agreement. "
            "Verify the term falls within the approved range (12–36 months). "
            "Check that auto-renewal and termination clauses are present and standard."
        )
