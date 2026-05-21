from app.rules.base import BaseRule


class CheckRegulatoryComplianceRule(BaseRule):
    rule_id = "rule_check_regulatory_compliance"
    name = "EdTech Regulatory Compliance"
    section = "Policy"
    required_context = ["documents", "deal.products"]

    def _get_prompt(self) -> str:
        return (
            "Verify EdTech regulatory compliance: "
            "(1) DPDP Act data processing clauses are present in the agreement, "
            "(2) no prohibited content or activities under NEP 2020, "
            "(3) entity is not classified as a coaching centre under pending regulation."
        )
