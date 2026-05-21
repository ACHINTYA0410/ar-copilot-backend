from app.rules.base import BaseRule


class CheckPaymentTermsRule(BaseRule):
    rule_id = "rule_check_payment_terms"
    name = "Payment Terms Standard"
    section = "Field Completeness"
    required_context = ["documents"]

    def _get_prompt(self) -> str:
        return (
            "Extract payment terms from the agreement (Section 5 or equivalent). "
            "Verify they are standard: Annual upfront, Net-30 invoice. "
            "Flag any non-standard terms (extended credit, milestone-based, heavy discount) as requiring additional approval."
        )
