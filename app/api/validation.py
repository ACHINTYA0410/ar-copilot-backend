import asyncio
import json

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import AsyncSessionLocal, get_db
from app.models.validation import RuleResult, ValidationRun
from app.schemas.validation import (
    ReviewerActionRequest, ReviewerActionResponse,
    RuleResultResponse, ValidationRunResponse, ValidationTriggerResponse,
)
from app.services.validation_engine import ValidationEngine

router = APIRouter(tags=["validation"])


@router.post("/deals/{deal_id}/validate", response_model=ValidationTriggerResponse, status_code=202)
async def trigger_validation(
    deal_id: str,
    background_tasks: BackgroundTasks,
    checklist_id: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    engine = ValidationEngine(db)
    if not checklist_id:
        checklist_id = await engine.get_or_create_default_checklist_id()

    # Create the run record up-front so we can return the ID immediately
    from app.models.validation import ValidationRun, ValidationRunStatus
    from datetime import datetime, timezone

    run = ValidationRun(
        deal_id=deal_id,
        checklist_id=checklist_id,
        status=ValidationRunStatus.pending,
    )
    db.add(run)
    await db.flush()
    run_id = run.id

    async def _run():
        async with AsyncSessionLocal() as session:
            eng = ValidationEngine(session)
            async for _ in eng.run_checklist(deal_id, checklist_id):
                pass

    background_tasks.add_task(_run)

    return ValidationTriggerResponse(validation_run_id=run_id, deal_id=deal_id)


@router.get("/validation-runs/{run_id}", response_model=ValidationRunResponse)
async def get_validation_run(run_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ValidationRun)
        .options(selectinload(ValidationRun.rule_results))
        .where(ValidationRun.id == run_id)
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Validation run not found")
    return ValidationRunResponse.model_validate(run)


@router.get("/validation-runs/{run_id}/stream")
async def stream_validation(run_id: str, db: AsyncSession = Depends(get_db)):
    run = await db.get(ValidationRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Validation run not found")

    async def event_generator():
        seen_ids: set[str] = set()
        max_polls = 180  # 3 minutes max at 1s intervals

        for _ in range(max_polls):
            async with AsyncSessionLocal() as session:
                fresh_result = await session.execute(
                    select(ValidationRun)
                    .options(selectinload(ValidationRun.rule_results))
                    .where(ValidationRun.id == run_id)
                )
                fresh_run = fresh_result.scalar_one_or_none()
                if not fresh_run:
                    break

                for rr in fresh_run.rule_results:
                    if rr.id not in seen_ids and rr.status not in ("pending", "running"):
                        seen_ids.add(rr.id)
                        data = RuleResultResponse.model_validate(rr).model_dump(mode="json")
                        yield f"data: {json.dumps(data)}\n\n"

                if fresh_run.status in ("completed", "failed"):
                    summary = {
                        "event": "complete",
                        "run_id": run_id,
                        "passed": fresh_run.passed,
                        "warnings": fresh_run.warnings,
                        "failed": fresh_run.failed,
                        "status": fresh_run.status,
                    }
                    yield f"data: {json.dumps(summary)}\n\n"
                    return

            await asyncio.sleep(1)

        yield f"data: {json.dumps({'event': 'timeout'})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/rule-results/{result_id}/action", response_model=ReviewerActionResponse)
async def apply_reviewer_action(
    result_id: str,
    payload: ReviewerActionRequest,
    db: AsyncSession = Depends(get_db),
):
    result_row = await db.get(RuleResult, result_id)
    if not result_row:
        raise HTTPException(status_code=404, detail="Rule result not found")

    result_row.action_taken = payload.action
    result_row.reviewer_comment = payload.comment
    await db.flush()

    return ReviewerActionResponse(result_id=result_id, action_taken=payload.action)
