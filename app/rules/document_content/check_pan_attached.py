from app.rules.base import BaseRule


class CheckPanAttachedRule(BaseRule):
    rule_id = "rule_check_pan_attached"
    name = "PAN Card Attached & Valid"
    section = "Document Content"
    required_context = ["documents", "deal.customer_name"]

    def _get_prompt(self) -> str:
        return (
            "Verify that a valid PAN card document is attached to this deal submission. "
            "Check that: (1) the PAN card is clearly legible, "
            "(2) it is self-attested by an authorised signatory, "
            "(3) the entity name on the PAN matches the customer name on the agreement, "
            "(4) the PAN number format is valid (10-character alphanumeric)."
        )
