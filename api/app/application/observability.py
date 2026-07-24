"""Persistence and user-scoped queries for Agent observability."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.agent.schemas import AgentRun, ToolCitation
from app.infrastructure.database.models.observability import (
    AgentSpan,
    AgentTrace,
    ModelUsage,
    RetrievalSnapshot,
)
from app.infrastructure.database.postgres import get_session_factory
from app.shared.config import get_settings


async def create_agent_trace(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    conversation_id: uuid.UUID,
    user_message_id: uuid.UUID,
    question: str,
    started_at: datetime,
) -> AgentTrace:
    trace = AgentTrace(
        user_id=user_id,
        conversation_id=conversation_id,
        user_message_id=user_message_id,
        status="running",
        question=question,
        started_at=started_at,
        tool_call_count=0,
        citation_count=0,
    )
    session.add(trace)
    await session.commit()
    await session.refresh(trace)
    return trace


async def complete_agent_trace(
    session: AsyncSession,
    *,
    trace: AgentTrace,
    assistant_message_id: uuid.UUID,
    run: AgentRun,
    citations: list[ToolCitation],
    final_usage: dict[str, object] | None,
    answer_model: str,
    trace_started: datetime,
    agent_started: datetime,
    agent_finished: datetime,
    answer_started: datetime,
    finished_at: datetime,
    tool_spans: list[dict[str, Any]],
) -> None:
    trace.status = "completed"
    trace.mode = run.mode
    trace.assistant_message_id = assistant_message_id
    trace.finished_at = finished_at
    trace.duration_ms = _duration_ms(trace_started, finished_at)
    trace.tool_call_count = len(run.tool_calls)
    trace.citation_count = len(citations)
    trace.error_code = None
    trace.error_message = None

    session.add(
        AgentSpan(
            trace_id=trace.id,
            kind="agent",
            name="agent_orchestration",
            status="completed",
            started_at=agent_started,
            finished_at=agent_finished,
            duration_ms=_duration_ms(agent_started, agent_finished),
            input_summary={"question_length": len(trace.question)},
            output_summary={
                "mode": run.mode,
                "tool_call_count": len(run.tool_calls),
            },
        )
    )
    session.add(
        AgentSpan(
            trace_id=trace.id,
            kind="model",
            name="answer_generation",
            status="completed",
            started_at=answer_started,
            finished_at=finished_at,
            duration_ms=_duration_ms(answer_started, finished_at),
            output_summary={"citation_count": len(citations)},
        )
    )
    for item in tool_spans:
        session.add(
            AgentSpan(
                trace_id=trace.id,
                kind="tool",
                name=str(item["name"])[:128],
                status=str(item["status"])[:24],
                started_at=item["started_at"],
                finished_at=item["finished_at"],
                duration_ms=_duration_ms(item["started_at"], item["finished_at"]),
                input_summary={"arguments": item.get("arguments") or {}},
                output_summary={"hit_count": int(item.get("hit_count") or 0)},
                error_message=(str(item["error"])[:2000] if item.get("error") else None),
            )
        )

    result_by_name: dict[str, list[Any]] = {}
    for result in run.results:
        result_by_name.setdefault(result.tool_name, []).append(result)
    for record in run.tool_calls:
        name = str(record.get("name") or "unknown")
        results = result_by_name.get(name) or []
        result = results.pop(0) if results else None
        citation_payloads = (
            [citation.model_dump(mode="json") for citation in result.citations]
            if result is not None
            else []
        )
        scores = [
            float(item["score"]) for item in citation_payloads if item.get("score") is not None
        ]
        arguments = record.get("arguments")
        if not isinstance(arguments, dict):
            arguments = {}
        metadata = result.metadata if result is not None else record.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}
        session.add(
            RetrievalSnapshot(
                trace_id=trace.id,
                tool_call_id=str(record.get("tool_call_id") or uuid.uuid4().hex)[:64],
                tool_name=name[:64],
                query=str(arguments.get("query") or trace.question)[:20_000],
                hit_count=int(metadata.get("hit_count") or len(citation_payloads)),
                duration_ms=int(record.get("duration_ms") or 0),
                status=str(record.get("status") or "completed")[:24],
                citations=citation_payloads or None,
                result_metadata=_json_safe(metadata),
                top_score=max(scores) if scores else None,
            )
        )

    for usage in run.model_usages:
        session.add(_model_usage(trace, usage))
    if final_usage is not None:
        session.add(
            _model_usage(
                trace,
                {
                    "operation": "answer_generation",
                    "model": answer_model,
                    "status": "completed",
                    **final_usage,
                    "duration_ms": _duration_ms(answer_started, finished_at),
                },
                message_id=assistant_message_id,
            )
        )
    await session.commit()


async def fail_agent_trace(trace_id: uuid.UUID, exc: Exception) -> None:
    async with get_session_factory()() as session:
        trace = await session.get(AgentTrace, trace_id)
        if trace is None or trace.status == "completed":
            return
        now = datetime.now(UTC)
        trace.status = "failed"
        trace.finished_at = now
        trace.duration_ms = _duration_ms(trace.started_at, now)
        trace.error_code = type(exc).__name__[:64]
        trace.error_message = (str(exc) or type(exc).__name__)[:2000]
        await session.commit()


async def recover_stale_agent_traces() -> int:
    """Close traces left running after an API process interruption."""
    settings = get_settings()
    now = datetime.now(UTC)
    cutoff = now - timedelta(seconds=settings.task_stale_after_seconds)
    async with get_session_factory()() as session:
        traces = list(
            await session.scalars(
                select(AgentTrace).where(
                    AgentTrace.status == "running",
                    AgentTrace.started_at < cutoff,
                )
            )
        )
        for trace in traces:
            trace.status = "failed"
            trace.finished_at = now
            trace.duration_ms = _duration_ms(trace.started_at, now)
            trace.error_code = "TraceAbandoned"
            trace.error_message = "Agent trace exceeded the running timeout."
        await session.commit()
        return len(traces)


def _model_usage(
    trace: AgentTrace,
    usage: dict[str, object],
    *,
    message_id: uuid.UUID | None = None,
) -> ModelUsage:
    input_tokens = int(usage.get("input_tokens") or usage.get("prompt_tokens") or 0)
    output_tokens = int(usage.get("output_tokens") or usage.get("completion_tokens") or 0)
    return ModelUsage(
        user_id=trace.user_id,
        trace_id=trace.id,
        message_id=message_id,
        operation=str(usage.get("operation") or "agent_planning")[:48],
        provider="bailian",
        model=str(usage.get("model") or get_settings().bailian_chat_model)[:128],
        status=str(usage.get("status") or "completed")[:24],
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=int(usage.get("total_tokens") or input_tokens + output_tokens),
        duration_ms=(int(usage["duration_ms"]) if usage.get("duration_ms") is not None else None),
        error_message=(str(usage["error"])[:2000] if usage.get("error") else None),
    )


async def observability_summary(
    session: AsyncSession, user_id: uuid.UUID, days: int = 14
) -> dict[str, Any]:
    today = datetime.now(UTC).date()
    first_day = today - timedelta(days=days - 1)
    start = datetime.combine(first_day, datetime.min.time(), tzinfo=UTC)
    trace_row = (
        await session.execute(
            select(
                func.count(AgentTrace.id),
                func.sum(case((AgentTrace.status == "failed", 1), else_=0)),
                func.avg(AgentTrace.duration_ms),
                func.sum(AgentTrace.tool_call_count),
            ).where(AgentTrace.user_id == user_id, AgentTrace.started_at >= start)
        )
    ).one()
    usage_row = (
        await session.execute(
            select(
                func.sum(ModelUsage.input_tokens),
                func.sum(ModelUsage.output_tokens),
                func.sum(ModelUsage.total_tokens),
            ).where(ModelUsage.user_id == user_id, ModelUsage.created_at >= start)
        )
    ).one()
    token_rows = await session.execute(
        select(
            func.date(ModelUsage.created_at),
            func.sum(ModelUsage.input_tokens),
            func.sum(ModelUsage.output_tokens),
        )
        .where(ModelUsage.user_id == user_id, ModelUsage.created_at >= start)
        .group_by(func.date(ModelUsage.created_at))
    )
    token_map = {
        str(day): (int(input_tokens or 0), int(output_tokens or 0))
        for day, input_tokens, output_tokens in token_rows.all()
    }
    tool_rows = await session.execute(
        select(AgentSpan.name, func.count())
        .join(AgentTrace, AgentTrace.id == AgentSpan.trace_id)
        .where(
            AgentTrace.user_id == user_id,
            AgentSpan.kind == "tool",
            AgentSpan.created_at >= start,
        )
        .group_by(AgentSpan.name)
        .order_by(func.count().desc())
    )
    traces = int(trace_row[0] or 0)
    failures = int(trace_row[1] or 0)
    return {
        "period_days": days,
        "traces": traces,
        "failed_traces": failures,
        "success_rate": round((traces - failures) / traces, 4) if traces else 1.0,
        "avg_duration_ms": round(float(trace_row[2] or 0)),
        "tool_calls": int(trace_row[3] or 0),
        "input_tokens": int(usage_row[0] or 0),
        "output_tokens": int(usage_row[1] or 0),
        "total_tokens": int(usage_row[2] or 0),
        "token_trend": [
            {
                "date": (first_day + timedelta(days=offset)).isoformat(),
                "input_tokens": token_map.get(
                    (first_day + timedelta(days=offset)).isoformat(), (0, 0)
                )[0],
                "output_tokens": token_map.get(
                    (first_day + timedelta(days=offset)).isoformat(), (0, 0)
                )[1],
            }
            for offset in range(days)
        ],
        "tool_distribution": [
            {"name": name, "value": int(count)} for name, count in tool_rows.all()
        ],
    }


async def list_agent_traces(
    session: AsyncSession, user_id: uuid.UUID, limit: int = 30
) -> list[AgentTrace]:
    return list(
        await session.scalars(
            select(AgentTrace)
            .where(AgentTrace.user_id == user_id)
            .order_by(AgentTrace.started_at.desc())
            .limit(limit)
        )
    )


async def get_agent_trace_detail(
    session: AsyncSession, user_id: uuid.UUID, trace_id: uuid.UUID
) -> tuple[AgentTrace, list[AgentSpan], list[ModelUsage], list[RetrievalSnapshot]] | None:
    trace = await session.scalar(
        select(AgentTrace).where(AgentTrace.id == trace_id, AgentTrace.user_id == user_id)
    )
    if trace is None:
        return None
    spans = list(
        await session.scalars(
            select(AgentSpan)
            .where(AgentSpan.trace_id == trace.id)
            .order_by(AgentSpan.started_at.asc())
        )
    )
    usages = list(
        await session.scalars(
            select(ModelUsage)
            .where(ModelUsage.trace_id == trace.id)
            .order_by(ModelUsage.created_at.asc())
        )
    )
    snapshots = list(
        await session.scalars(
            select(RetrievalSnapshot)
            .where(RetrievalSnapshot.trace_id == trace.id)
            .order_by(RetrievalSnapshot.created_at.asc())
        )
    )
    return trace, spans, usages, snapshots


def _duration_ms(start: datetime, end: datetime) -> int:
    return max(0, round((end - start).total_seconds() * 1000))


def _json_safe(value: dict[str, object]) -> dict[str, object]:
    return {
        str(key): item
        for key, item in value.items()
        if isinstance(item, (str, int, float, bool, list, dict)) or item is None
    }
