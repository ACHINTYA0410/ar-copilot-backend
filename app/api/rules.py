from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.rule import Rule
from app.schemas.rule import (
    RuleResponse, RulesBySectionResponse, RuleTestRequest, RuleTestResponse, RuleUpdate,
)
from app.services.audit_service import AuditService

router = APIRouter(prefix="/rules", tags=["rules"])


@router.get("", response_model=list[RulesBySectionResponse])
async def list_rules(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Rule).order_by(Rule.section, Rule.name))
    rules = result.scalars().all()

    sections: dict[str, list[RuleResponse]] = {}
    for rule in rules:
        sections.setdefault(rule.section, []).append(RuleResponse.model_validate(rule))

    return [RulesBySectionResponse(section=s, rules=r) for s, r in sections.items()]


@router.get("/{rule_id}", response_model=RuleResponse)
async def get_rule(rule_id: str, db: AsyncSession = Depends(get_db)):
    rule = await db.get(Rule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail=f"Rule {rule_id} not found")
    return RuleResponse.model_validate(rule)


@router.patch("/{rule_id}", response_model=RuleResponse)
async def update_rule(rule_id: str, payload: RuleUpdate, db: AsyncSession = Depends(get_db)):
    rule = await db.get(Rule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail=f"Rule {rule_id} not found")

    before = RuleResponse.model_validate(rule).model_dump(mode="json")
    update_data = payload.model_dump(exclude_none=True)
    for field, value in update_data.items():
        setattr(rule, field, value)

    after = RuleResponse.model_validate(rule).model_dump(mode="json")
    audit = AuditService(db)
    await audit.log_rule_change("API User", rule_id, before, after)
    await db.flush()

    return RuleResponse.model_validate(rule)


@router.post("/{rule_id}/test", response_model=RuleTestResponse)
async def test_rule(rule_id: str, payload: RuleTestRequest, db: AsyncSession = Depends(get_db)):
    from app.rules import RULE_REGISTRY
    from app.rules.base import RuleContext
    from app.services.ai_service import AIService

    from app.models.deal import Deal
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    rule_instance = RULE_REGISTRY.get(rule_id)
    if not rule_instance:
        raise HTTPException(status_code=404, detail=f"Rule {rule_id} not found in registry")

    result = await db.execute(
        select(Deal)
        .options(selectinload(Deal.documents))
        .where(Deal.id == payload.deal_id)
    )
    deal = result.scalar_one_or_none()
    
    if deal:
        deal_data = {
            "id": deal.id,
            "status": deal.status.value if deal.status else None,
            "customer_name": deal.customer_name,
            "amount": deal.amount,
            "submitted_by_name": deal.submitted_by_name,
            "submitted_at": deal.submitted_at.isoformat() if deal.submitted_at else None,
        }
        documents = [
            {"id": doc.id, "filename": doc.filename, "document_type": doc.document_type.value if doc.document_type else None}
            for doc in deal.documents
        ]
    else:
        deal_data = {}
        documents = []

    ai = AIService()
    context = RuleContext(
        deal_id=payload.deal_id,
        deal_data=deal_data,
        documents=documents,
    )
    evaluation = await rule_instance.evaluate(context, ai)

    return RuleTestResponse(
        rule_id=rule_id,
        status=evaluation.status,
        confidence=evaluation.confidence,
        evidence=evaluation.evidence,
        reasoning=evaluation.reasoning,
        runtime_ms=evaluation.runtime_ms,
    )
