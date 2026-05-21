from app.rules.base import BaseRule


class CheckTerritoryConflictRule(BaseRule):
    rule_id = "rule_check_territory_conflict"
    name = "Territory Conflict Check"
    section = "Policy"
    required_context = ["deal.region", "deal.products", "hubspot.territory"]

    def _get_prompt(self) -> str:
        return (
            "Check the number of active accounts in the same territory and product segment. "
            "Flag as warning if this deal would make 3+ active accounts in the same segment-territory. "
            "Require zone manager sign-off acknowledgement if triggered."
        )
