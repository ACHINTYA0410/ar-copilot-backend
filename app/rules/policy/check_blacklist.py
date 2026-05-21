from app.rules.base import BaseRule


class CheckBlacklistRule(BaseRule):
    rule_id = "rule_check_blacklist"
    name = "Entity Not on Restricted Lists"
    section = "Policy"
    required_context = ["deal.customer_name", "hubspot.pan", "hubspot.directors"]

    def _get_prompt(self) -> str:
        return (
            "Check the entity and its directors against: "
            "(1) internal blacklist, (2) MCA-21 disqualified directors list, "
            "(3) RBI caution list, (4) SFIO watchlist. "
            "Any match is an immediate failure."
        )
