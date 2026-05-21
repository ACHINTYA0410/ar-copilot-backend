from app.rules.base import BaseRule


class CheckSlaTermsRule(BaseRule):
    rule_id = "rule_check_sla_terms"
    name = "SLA Terms Within Standard Tier"
    section = "Policy"
    required_context = ["documents", "deal.products"]

    def _get_prompt(self) -> str:
        return (
            "Extract the uptime SLA commitment from the agreement. "
            "Compare with the standard SLA for the contracted product tier: "
            "Starter=99.5%, Professional=99.7%, Enterprise=99.9%. "
            "Above-tier SLA requires Engineering VP approval (policy ENG-POL-009)."
        )
