from app.rules.base import BaseRule


class CheckSignaturesRule(BaseRule):
    rule_id = "rule_check_signatures"
    name = "Signatures & Seal Verification"
    section = "Document Content"
    required_context = ["documents", "deal.submitted_by_name"]

    def _get_prompt(self) -> str:
        return (
            "Review all pages of the uploaded agreement. Verify that: "
            "(1) both the customer's authorised signatory and Stitch's countersignatory have signed, "
            "(2) corporate seals are affixed on required pages, "
            "(3) all signature blocks are legible. "
            "Report any missing, illegible, or incomplete signatures."
        )
