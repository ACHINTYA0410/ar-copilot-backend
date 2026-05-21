from app.rules.base import BaseRule


class CheckProductsConfiguredRule(BaseRule):
    rule_id = "rule_check_products_configured"
    name = "Products Configured in HubSpot"
    section = "Field Completeness"
    required_context = ["hubspot.products", "deal.products"]

    def _get_prompt(self) -> str:
        return (
            "Verify that all products listed in the deal are configured in HubSpot as active SKUs. "
            "Check that quantities, billing frequencies, and combined value match the deal amount."
        )
