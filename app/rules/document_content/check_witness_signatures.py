from app.rules.base import BaseRule


class CheckWitnessSignaturesRule(BaseRule):
    rule_id = "rule_check_witness_signatures"
    name = "Witness Signatures Present"
    section = "Document Content"
    required_context = ["documents"]

    def _get_prompt(self) -> str:
        return (
            "Verify that the execution page contains at least two witness signatures, "
            "each with a printed name and date matching the execution date."
        )
