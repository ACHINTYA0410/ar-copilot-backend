from collections.abc import AsyncIterator
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.checklist import Checklist
from app.models.deal import Deal, DealStatus
from app.models.validation import ActionTaken, RuleResult, RuleResultStatus, ValidationRun, ValidationRunStatus
from app.rules import RULE_REGISTRY
from app.rules.base import RuleContext
from app.services.ai_service import AIService
from app.services.audit_service import AuditService


class ValidationEngine:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.ai_service = AIService()
        self.audit_service = AuditService(db)

    async def run_checklist(
        self,
        deal_id: str,
        checklist_id: str,
    ) -> AsyncIterator[RuleResult]:
        deal = await self.db.get(Deal, deal_id)
        if not deal:
            raise ValueError(f"Deal {deal_id} not found")

        checklist = await self.db.get(Checklist, checklist_id)
        rule_ids = checklist.rule_ids if checklist else list(RULE_REGISTRY.keys())

        run = ValidationRun(
            deal_id=deal_id,
            checklist_id=checklist_id,
            status=ValidationRunStatus.running,
            total_rules=len(rule_ids),
            started_at=datetime.now(timezone.utc),
        )
        self.db.add(run)
        await self.db.flush()

        await self.audit_service.log_validation_start(deal_id, run.id)
        await self.db.commit()

        context = RuleContext(
            deal_id=deal_id,
            deal_data={
                "customer_name": deal.customer_name,
                "amount": float(deal.amount),
                "region": deal.region,
                "products": deal.products,
                "submitted_at": deal.submitted_at.isoformat() if deal.submitted_at else None,
            },
            documents=[],
        )

        passed = warnings = failed = 0

        for rule_id in rule_ids:
            rule_instance = RULE_REGISTRY.get(rule_id)
            if not rule_instance:
                continue

            result_row = RuleResult(
                validation_run_id=run.id,
                rule_id=rule_instance.rule_id,
                rule_name=rule_instance.name,
                section=rule_instance.section,
                status=RuleResultStatus.running,
                executed_at=datetime.now(timezone.utc),
            )
            self.db.add(result_row)
            await self.db.flush()

            evaluation = await rule_instance.evaluate(context, self.ai_service)

            status_map = {
                "pass": RuleResultStatus.pass_,
                "warning": RuleResultStatus.warning,
                "fail": RuleResultStatus.fail,
            }
            result_row.status = status_map.get(evaluation.status, RuleResultStatus.pass_)
            result_row.confidence = evaluation.confidence
            result_row.evidence = evaluation.evidence
            result_row.ai_reasoning = evaluation.reasoning
            result_row.action_taken = ActionTaken.none
            result_row.executed_at = datetime.now(timezone.utc)

            if evaluation.status == "pass":
                passed += 1
            elif evaluation.status == "warning":
                warnings += 1
            else:
                failed += 1

            await self.db.flush()
            await self.db.commit()

            yield result_row

        run.status = ValidationRunStatus.completed
        run.passed = passed
        run.warnings = warnings
        run.failed = failed
        run.completed_at = datetime.now(timezone.utc)

        deal.validation_score_passed = passed
        deal.validation_score_total = len(rule_ids)
        deal.critical_issues_count = failed

        if failed == 0 and warnings == 0:
            deal.status = DealStatus.auto_approved
        elif failed > 0:
            deal.status = DealStatus.auto_rejected
        else:
            deal.status = DealStatus.needs_review

        await self.audit_service.log_validation_complete(deal_id, run.id, passed, warnings, failed)
        await self.db.commit()

    async def get_or_create_default_checklist_id(self) -> str:
        result = await self.db.execute(
            select(Checklist).where(Checklist.status == "active").limit(1)
        )
        checklist = result.scalar_one_or_none()
        if checklist:
            return checklist.id
        return "default"
