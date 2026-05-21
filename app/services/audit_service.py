from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import ActionType, ActorType, AuditLog, TargetType


class AuditService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def log(
        self,
        actor_type: ActorType,
        actor_name: str,
        action_type: ActionType,
        target_type: TargetType,
        target_id: str,
        description: str,
        before_value: dict[str, Any] | None = None,
        after_value: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AuditLog:
        entry = AuditLog(
            timestamp=datetime.now(timezone.utc),
            actor_type=actor_type,
            actor_name=actor_name,
            action_type=action_type,
            target_type=target_type,
            target_id=target_id,
            description=description,
            before_value=before_value,
            after_value=after_value,
            metadata_=metadata,
        )
        self.db.add(entry)
        await self.db.flush()
        return entry

    async def log_upload(self, actor_name: str, deal_id: str, filename: str) -> AuditLog:
        return await self.log(
            actor_type=ActorType.user,
            actor_name=actor_name,
            action_type=ActionType.uploaded,
            target_type=TargetType.document,
            target_id=deal_id,
            description=f"Document '{filename}' uploaded for deal {deal_id}",
            metadata={"filename": filename, "deal_id": deal_id},
        )

    async def log_validation_start(self, deal_id: str, run_id: str) -> AuditLog:
        return await self.log(
            actor_type=ActorType.ai_agent,
            actor_name="Validation Engine",
            action_type=ActionType.auto_approved,
            target_type=TargetType.deal,
            target_id=deal_id,
            description=f"Validation run {run_id} started for deal {deal_id}",
            metadata={"run_id": run_id},
        )

    async def log_validation_complete(
        self, deal_id: str, run_id: str, passed: int, warnings: int, failed: int
    ) -> AuditLog:
        if failed > 0:
            action = ActionType.auto_rejected
            desc = f"Validation completed for {deal_id}: {passed} pass, {warnings} warning, {failed} fail — auto-rejected"
        elif warnings > 0:
            action = ActionType.pattern_detected
            desc = f"Validation completed for {deal_id}: {passed} pass, {warnings} warning — flagged for review"
        else:
            action = ActionType.auto_approved
            desc = f"Validation completed for {deal_id}: {passed} pass — auto-approved"

        return await self.log(
            actor_type=ActorType.ai_agent,
            actor_name="Validation Engine",
            action_type=action,
            target_type=TargetType.deal,
            target_id=deal_id,
            description=desc,
            metadata={"run_id": run_id, "passed": passed, "warnings": warnings, "failed": failed},
        )

    async def log_deal_status_change(
        self, actor_name: str, deal_id: str, old_status: str, new_status: str, comment: str | None = None
    ) -> AuditLog:
        action = ActionType.approved if "approved" in new_status else ActionType.rejected
        return await self.log(
            actor_type=ActorType.user,
            actor_name=actor_name,
            action_type=action,
            target_type=TargetType.deal,
            target_id=deal_id,
            description=f"Deal {deal_id} status changed from {old_status} to {new_status}"
            + (f": {comment}" if comment else ""),
            before_value={"status": old_status},
            after_value={"status": new_status},
        )

    async def log_rule_change(
        self, actor_name: str, rule_id: str, before: dict, after: dict
    ) -> AuditLog:
        return await self.log(
            actor_type=ActorType.user,
            actor_name=actor_name,
            action_type=ActionType.modified_rule,
            target_type=TargetType.rule,
            target_id=rule_id,
            description=f"Rule '{rule_id}' configuration updated by {actor_name}",
            before_value=before,
            after_value=after,
        )
