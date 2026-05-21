from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.models.rule import Rule
from app.services.ai_service import AIService, RuleEvaluation


@dataclass
class RuleContext:
    deal_id: str
    deal_data: dict
    documents: list
    hubspot_data: dict | None = None


class BaseRule(ABC):
    rule_id: str
    name: str
    section: str
    required_context: list[str] = []

    async def evaluate(self, context: RuleContext, ai_service: AIService) -> RuleEvaluation:
        rule_obj = Rule(
            id=self.rule_id,
            name=self.name,
            section=self.section,
            prompt=self._get_prompt(),
            required_context=self.required_context,
        )
        deal_context = {"deal_id": context.deal_id, **context.deal_data}
        return await ai_service.evaluate_rule(rule_obj, deal_context, context.documents)

    @abstractmethod
    def _get_prompt(self) -> str:
        ...
