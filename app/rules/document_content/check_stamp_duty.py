from app.rules.base import BaseRule


class CheckStampDutyRule(BaseRule):
    rule_id = "rule_check_stamp_duty"
    name = "Stamp Duty Compliance"
    section = "Document Content"
    required_context = ["documents", "deal.amount", "deal.region"]

    def _get_prompt(self) -> str:
        return (
            "Verify that the e-stamp certificate is attached, legible, and valid. "
            "Check that the stamp value is compliant with the applicable state regulations "
            "for the contract value and state. Confirm the certificate date precedes the agreement execution date."
        )
