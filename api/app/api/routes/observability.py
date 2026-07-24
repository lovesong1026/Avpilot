"""User-isolated Agent traces, spans, retrieval snapshots, and Token totals."""

import uuid

from fastapi import APIRouter, HTTPException, Query

from app.api.dependencies import CurrentUser, SessionDependency
from app.api.schemas.observability import (
    AgentSpanItem,
    AgentTraceDetail,
    AgentTraceItem,
    ModelUsageItem,
    ObservabilitySummary,
    RetrievalSnapshotItem,
)
from app.application.observability import (
    get_agent_trace_detail,
    list_agent_traces,
    observability_summary,
)

router = APIRouter(prefix="/observability", tags=["observability"])


@router.get("/summary", response_model=ObservabilitySummary)
async def summary(
    user: CurrentUser,
    session: SessionDependency,
    days: int = Query(default=14, ge=1, le=90),
) -> ObservabilitySummary:
    return ObservabilitySummary.model_validate(await observability_summary(session, user.id, days))


@router.get("/traces", response_model=list[AgentTraceItem])
async def traces(
    user: CurrentUser,
    session: SessionDependency,
    limit: int = Query(default=30, ge=1, le=100),
) -> list[AgentTraceItem]:
    rows = await list_agent_traces(session, user.id, limit)
    return [AgentTraceItem.model_validate(row) for row in rows]


@router.get("/traces/{trace_id}", response_model=AgentTraceDetail)
async def trace_detail(
    trace_id: uuid.UUID, user: CurrentUser, session: SessionDependency
) -> AgentTraceDetail:
    result = await get_agent_trace_detail(session, user.id, trace_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Trace 不存在")
    trace, spans, usages, snapshots = result
    return AgentTraceDetail.model_validate(trace).model_copy(
        update={
            "spans": [AgentSpanItem.model_validate(item) for item in spans],
            "model_usages": [ModelUsageItem.model_validate(item) for item in usages],
            "retrieval_snapshots": [
                RetrievalSnapshotItem.model_validate(item) for item in snapshots
            ],
        }
    )
