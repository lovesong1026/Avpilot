"""Durable multi-stage deep-research workflow."""

from __future__ import annotations

import json
import re
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.agent.schemas import AgentToolContext, ToolCitation
from app.application.agent.tools import build_agent_tools
from app.application.task_queue import (
    RESEARCH_TASK,
    enqueue_task,
    task_dedupe_key,
)
from app.infrastructure.database.models.knowledge import KnowledgeBase
from app.infrastructure.database.models.research import (
    ResearchEvidence,
    ResearchStep,
    ResearchTask,
)
from app.infrastructure.database.models.task import TaskOutbox
from app.infrastructure.database.postgres import get_session_factory
from app.infrastructure.llm.bailian import BailianGateway


async def create_research_task(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    question: str,
    title: str | None,
    knowledge_base_ids: list[uuid.UUID],
    use_memory: bool,
    allow_web: bool,
    max_iterations: int,
) -> tuple[ResearchTask, str]:
    if knowledge_base_ids:
        owned = set(
            await session.scalars(
                select(KnowledgeBase.id).where(
                    KnowledgeBase.user_id == user_id,
                    KnowledgeBase.id.in_(knowledge_base_ids),
                )
            )
        )
        if owned != set(knowledge_base_ids):
            raise LookupError("包含不存在或无权访问的知识库")
    if not knowledge_base_ids and not use_memory and not allow_web:
        raise ValueError("知识库、长期记忆和联网搜索至少启用一种")
    normalized_question = question.strip()
    if len(normalized_question) < 5:
        raise ValueError("研究课题至少需要 5 个有效字符")
    normalized_title = title.strip() if title and title.strip() else normalized_question
    task = ResearchTask(
        user_id=user_id,
        title=normalized_title[:256],
        question=normalized_question,
        status="pending",
        stage="queued",
        progress=0.0,
        knowledge_base_ids=[str(item) for item in knowledge_base_ids],
        use_memory=use_memory,
        allow_web=allow_web,
        max_iterations=max_iterations,
    )
    session.add(task)
    await session.flush()
    key = task_dedupe_key("research", task.id)
    enqueue_task(
        session,
        task_name=RESEARCH_TASK,
        queue="research",
        dedupe_key=key,
        payload={"research_id": str(task.id)},
    )
    await session.commit()
    await session.refresh(task)
    return task, key


async def list_research_tasks(
    session: AsyncSession, user_id: uuid.UUID, limit: int = 50
) -> list[ResearchTask]:
    return list(
        await session.scalars(
            select(ResearchTask)
            .where(ResearchTask.user_id == user_id)
            .order_by(ResearchTask.created_at.desc())
            .limit(limit)
        )
    )


async def get_research_task(
    session: AsyncSession, user_id: uuid.UUID, task_id: uuid.UUID
) -> tuple[ResearchTask, list[ResearchStep], list[ResearchEvidence]] | None:
    task = await session.scalar(
        select(ResearchTask).where(ResearchTask.id == task_id, ResearchTask.user_id == user_id)
    )
    if task is None:
        return None
    steps = list(
        await session.scalars(
            select(ResearchStep)
            .where(ResearchStep.task_id == task.id)
            .order_by(ResearchStep.position.asc())
        )
    )
    evidence = list(
        await session.scalars(
            select(ResearchEvidence)
            .outerjoin(ResearchStep, ResearchStep.id == ResearchEvidence.step_id)
            .where(ResearchEvidence.task_id == task.id)
            .order_by(
                ResearchStep.position.asc().nulls_last(),
                ResearchEvidence.source_type.asc(),
                ResearchEvidence.source_id.asc(),
                ResearchEvidence.chunk_id.asc().nulls_last(),
            )
        )
    )
    return task, steps, evidence


async def delete_research_task(
    session: AsyncSession, user_id: uuid.UUID, task_id: uuid.UUID
) -> bool:
    task = await session.scalar(
        select(ResearchTask).where(ResearchTask.id == task_id, ResearchTask.user_id == user_id)
    )
    if task is None:
        return False
    if task.status not in {"completed", "failed"}:
        raise ValueError("研究正在执行，暂时不能删除")
    event = await session.scalar(
        select(TaskOutbox).where(TaskOutbox.dedupe_key == task_dedupe_key("research", task.id))
    )
    if event is not None:
        await session.delete(event)
    await session.delete(task)
    await session.commit()
    return True


async def retry_research_task(
    session: AsyncSession, user_id: uuid.UUID, task_id: uuid.UUID
) -> tuple[ResearchTask, str]:
    task = await session.scalar(
        select(ResearchTask).where(ResearchTask.id == task_id, ResearchTask.user_id == user_id)
    )
    if task is None:
        raise LookupError("研究任务不存在")
    if task.status != "failed":
        raise ValueError("只有失败的研究任务可以重试")
    task.status = "pending"
    task.stage = "queued"
    task.progress = 0.0
    task.error_code = None
    task.error_message = None
    task.finished_at = None
    key = task_dedupe_key("research", task.id)
    event = await session.scalar(select(TaskOutbox).where(TaskOutbox.dedupe_key == key))
    if event is None:
        enqueue_task(
            session,
            task_name=RESEARCH_TASK,
            queue="research",
            dedupe_key=key,
            payload={"research_id": str(task.id)},
        )
    else:
        event.status = "pending"
        event.available_at = datetime.now(UTC)
        event.finished_at = None
        event.error_message = None
    await session.commit()
    return task, key


async def process_research_task(research_id: uuid.UUID) -> None:
    gateway = BailianGateway()
    try:
        async with get_session_factory()() as session:
            task = await session.get(ResearchTask, research_id)
            if task is None:
                raise LookupError("研究任务不存在")
            await _reset_execution(session, task)
            task.status = "planning"
            task.stage = "planning"
            task.progress = 0.05
            task.started_at = datetime.now(UTC)
            await session.commit()

            plan, usage = await _plan_research(gateway, task.question)
            _add_usage(task, usage)
            task.plan = plan
            questions = _plan_questions(plan, task.question)
            steps = [
                ResearchStep(
                    task_id=task.id,
                    position=index,
                    question=question,
                    status="pending",
                )
                for index, question in enumerate(questions, 1)
            ]
            session.add_all(steps)
            await session.commit()

            task.status = "researching"
            task.stage = "collecting_evidence"
            tools = _enabled_tools(task)
            for index, step in enumerate(steps):
                await _execute_step(session, task, step, tools, gateway)
                task.progress = 0.12 + 0.48 * ((index + 1) / len(steps))
                await session.commit()

            verifier: dict[str, object] = {}
            for iteration in range(task.max_iterations):
                task.status = "verifying"
                task.stage = "verifying_evidence"
                task.progress = 0.62 + iteration * 0.08
                task.iteration_count = iteration + 1
                await session.commit()
                evidence = await _task_evidence(session, task.id)
                verifier, usage = await _verify_research(
                    gateway, task.question, questions, evidence
                )
                _add_usage(task, usage)
                task.verifier_result = verifier
                await session.commit()
                follow_ups = _follow_up_queries(verifier)
                if bool(verifier.get("sufficient")) or not follow_ups:
                    break
                if iteration + 1 >= task.max_iterations:
                    break
                for query in follow_ups[:3]:
                    step = ResearchStep(
                        task_id=task.id,
                        position=len(steps) + 1,
                        question=query,
                        status="pending",
                    )
                    session.add(step)
                    await session.commit()
                    steps.append(step)
                    await _execute_step(session, task, step, tools, gateway)

            task.status = "writing"
            task.stage = "writing_report"
            task.progress = 0.88
            await session.commit()
            evidence = await _task_evidence(session, task.id)
            report, usage = await _write_report(
                gateway, task.title, task.question, evidence, verifier
            )
            _add_usage(task, usage)
            task.report_markdown = report
            task.status = "completed"
            task.stage = "completed"
            task.progress = 1.0
            task.finished_at = datetime.now(UTC)
            task.error_code = None
            task.error_message = None
            await session.commit()
    except Exception as exc:
        async with get_session_factory()() as session:
            task = await session.get(ResearchTask, research_id)
            if task is not None:
                task.status = "failed"
                task.stage = "failed"
                task.finished_at = datetime.now(UTC)
                task.error_code = type(exc).__name__[:64]
                task.error_message = (str(exc) or type(exc).__name__)[:2000]
                await session.commit()
        raise
    finally:
        await gateway.close()


async def _reset_execution(session: AsyncSession, task: ResearchTask) -> None:
    await session.execute(delete(ResearchEvidence).where(ResearchEvidence.task_id == task.id))
    await session.execute(delete(ResearchStep).where(ResearchStep.task_id == task.id))
    task.plan = None
    task.verifier_result = None
    task.report_markdown = None
    task.iteration_count = 0
    task.input_tokens = 0
    task.output_tokens = 0
    task.total_tokens = 0
    task.finished_at = None
    task.error_code = None
    task.error_message = None


def _enabled_tools(task: ResearchTask):
    context = AgentToolContext(
        user_id=task.user_id,
        knowledge_base_ids=[uuid.UUID(item) for item in task.knowledge_base_ids],
        allow_web=task.allow_web,
    )
    tools = build_agent_tools(context)
    return [
        tool
        for tool in tools
        if (tool.name != "knowledge_search" or task.knowledge_base_ids)
        and (tool.name != "memory_search" or task.use_memory)
    ]


async def _execute_step(
    session: AsyncSession,
    task: ResearchTask,
    step: ResearchStep,
    tools,
    gateway: BailianGateway,
) -> None:
    step.status = "running"
    step.started_at = datetime.now(UTC)
    await session.commit()
    citations: list[ToolCitation] = []
    for tool in tools:
        result = await tool.handler({"query": step.question, "top_k": 5})
        citations.extend(result.citations)
    persisted = await _persist_evidence(session, task, step, step.question, citations)
    evidence_text = _evidence_text(persisted)
    if evidence_text:
        finding, usage = await _summarize_step(gateway, task.question, step.question, evidence_text)
        _add_usage(task, usage)
    else:
        finding = "当前启用的数据源没有找到能够支持该子问题的可靠证据。"
    step.finding = finding
    step.evidence_count = len(persisted)
    step.status = "completed"
    step.finished_at = datetime.now(UTC)
    await session.commit()


async def _persist_evidence(
    session: AsyncSession,
    task: ResearchTask,
    step: ResearchStep,
    query: str,
    citations: list[ToolCitation],
) -> list[ResearchEvidence]:
    existing = {
        (row.source_type, row.source_id, row.chunk_id)
        for row in await _task_evidence(session, task.id)
    }
    if len(existing) >= 40:
        return []
    output: list[ResearchEvidence] = []
    for citation in citations:
        key = (citation.source_type, citation.source_id, citation.chunk_id)
        if key in existing or not citation.quote.strip():
            continue
        if len(existing) >= 40:
            break
        existing.add(key)
        row = ResearchEvidence(
            task_id=task.id,
            step_id=step.id,
            source_type=citation.source_type,
            source_id=citation.source_id,
            chunk_id=citation.chunk_id,
            title=citation.title,
            quote=citation.quote,
            url=citation.url,
            locator=citation.locator,
            score=citation.score,
            query=query,
        )
        session.add(row)
        output.append(row)
    await session.flush()
    return output


async def _task_evidence(session: AsyncSession, task_id: uuid.UUID) -> list[ResearchEvidence]:
    return list(
        await session.scalars(
            select(ResearchEvidence)
            .outerjoin(ResearchStep, ResearchStep.id == ResearchEvidence.step_id)
            .where(ResearchEvidence.task_id == task_id)
            .order_by(
                ResearchStep.position.asc().nulls_last(),
                ResearchEvidence.source_type.asc(),
                ResearchEvidence.source_id.asc(),
                ResearchEvidence.chunk_id.asc().nulls_last(),
            )
        )
    )


async def _plan_research(
    gateway: BailianGateway, question: str
) -> tuple[dict[str, object], dict[str, int]]:
    response = await gateway.chat(
        [
            {
                "role": "system",
                "content": (
                    "你是研究规划员。只返回 JSON 对象，格式为"
                    '{"objective":"研究目标","questions":["子问题"],'
                    '"deliverables":["交付内容"]}。将复杂问题拆成 3 到 6 个相互补充、'
                    "可独立检索的子问题，不要直接回答。"
                ),
            },
            {"role": "user", "content": question},
        ],
        temperature=0.1,
    )
    content = response.choices[0].message.content or "{}"
    return _json_object(content), _usage(response)


async def _summarize_step(
    gateway: BailianGateway,
    topic: str,
    question: str,
    evidence_text: str,
) -> tuple[str, dict[str, int]]:
    response = await gateway.chat(
        [
            {
                "role": "system",
                "content": (
                    "你是严谨的研究助理。仅根据给定证据形成一段事实笔记；"
                    "指出证据冲突和不确定性，不得补写证据之外的事实。"
                ),
            },
            {
                "role": "user",
                "content": f"总课题：{topic}\n子问题：{question}\n\n证据：\n{evidence_text}",
            },
        ],
        temperature=0.1,
    )
    return response.choices[0].message.content or "未形成研究笔记。", _usage(response)


async def _verify_research(
    gateway: BailianGateway,
    topic: str,
    questions: list[str],
    evidence: list[ResearchEvidence],
) -> tuple[dict[str, object], dict[str, int]]:
    response = await gateway.chat(
        [
            {
                "role": "system",
                "content": (
                    "你是研究证据审查员。只返回 JSON："
                    '{"sufficient":true,"coverage":0.0,"gaps":["缺口"],'
                    '"conflicts":["冲突"],"follow_up_queries":["补充检索问题"]}。'
                    "仅当每个关键子问题都有直接证据时 sufficient 才为 true；"
                    "补充问题最多 3 个。"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"课题：{topic}\n子问题：{json.dumps(questions, ensure_ascii=False)}"
                    f"\n\n现有证据：\n{_evidence_text(evidence)}"
                ),
            },
        ],
        temperature=0.0,
    )
    return _json_object(response.choices[0].message.content or "{}"), _usage(response)


async def _write_report(
    gateway: BailianGateway,
    title: str,
    topic: str,
    evidence: list[ResearchEvidence],
    verifier: dict[str, object],
) -> tuple[str, dict[str, int]]:
    if not evidence:
        gaps = verifier.get("gaps")
        gap_rows = (
            [str(item).strip() for item in gaps if str(item).strip()]
            if isinstance(gaps, list)
            else []
        )
        gap_text = "\n".join(f"- {item}" for item in gap_rows) or "- 当前没有可用证据"
        return (
            f"# {title}\n\n"
            "## 执行摘要\n\n"
            "当前启用的数据源没有返回可用于支持结论的证据，因此本次研究不能形成"
            "事实性判断，也不会生成任何占位引用。\n\n"
            "## 已识别的证据缺口\n\n"
            f"{gap_text}\n\n"
            "## 结论\n\n"
            "请补充相关知识库资料、长期记忆，或允许联网搜索后重新运行研究。\n\n"
            "## 参考资料\n\n"
            "本次研究没有可引用的资料。\n",
            {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
        )
    response = await gateway.chat(
        [
            {
                "role": "system",
                "content": (
                    "你是研究报告撰写人。输出 Markdown 报告，包含执行摘要、研究发现、"
                    "风险与不确定性、结论和参考资料。所有事实性结论必须使用 [1] 形式"
                    "引用给定证据编号；不得编造引用、URL、数据或结论。证据不足处要明确说明。"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"报告标题：{title}\n研究课题：{topic}\n"
                    f"审查结果：{json.dumps(verifier, ensure_ascii=False)}\n\n"
                    f"可用证据：\n{_evidence_text(evidence)}"
                ),
            },
        ],
        temperature=0.1,
    )
    content = response.choices[0].message.content or ""
    if not content.strip():
        raise RuntimeError("模型没有生成研究报告")
    return _sanitize_report_citations(content, len(evidence)), _usage(response)


def _plan_questions(plan: dict[str, object], fallback: str) -> list[str]:
    rows = plan.get("questions")
    questions = (
        [str(item).strip()[:1000] for item in rows if str(item).strip()]
        if isinstance(rows, list)
        else []
    )
    return questions[:6] or [
        f"{fallback}的核心概念、范围和背景是什么？",
        f"{fallback}有哪些主要方案、事实和代表性案例？",
        f"{fallback}面临哪些限制、风险和不确定性？",
    ]


def _follow_up_queries(verifier: dict[str, object]) -> list[str]:
    rows = verifier.get("follow_up_queries")
    if not isinstance(rows, list):
        return []
    return [str(item).strip()[:1000] for item in rows if str(item).strip()]


def _evidence_text(evidence: list[ResearchEvidence]) -> str:
    return "\n\n".join(
        f"[{index}] {row.title}\n{row.quote[:1200]}" + (f"\nURL: {row.url}" if row.url else "")
        for index, row in enumerate(evidence[:40], 1)
    )


def _json_object(content: str) -> dict[str, object]:
    normalized = content.strip()
    if normalized.startswith("```"):
        lines = normalized.splitlines()
        normalized = "\n".join(lines[1:-1]).strip()
    value = json.loads(normalized)
    if not isinstance(value, dict):
        raise ValueError("模型没有返回 JSON 对象")
    return value


def _sanitize_report_citations(content: str, evidence_count: int) -> str:
    """Remove citation markers that cannot resolve to persisted evidence."""

    def replace(match: re.Match[str]) -> str:
        index = int(match.group(1))
        return match.group(0) if 1 <= index <= evidence_count else "（证据不足）"

    return re.sub(r"\[(\d+)\]", replace, content)


def _usage(response: Any) -> dict[str, int]:
    usage = response.usage
    return {
        "input_tokens": int(getattr(usage, "prompt_tokens", 0) or 0),
        "output_tokens": int(getattr(usage, "completion_tokens", 0) or 0),
        "total_tokens": int(getattr(usage, "total_tokens", 0) or 0),
    }


def _add_usage(task: ResearchTask, usage: dict[str, int]) -> None:
    task.input_tokens += usage["input_tokens"]
    task.output_tokens += usage["output_tokens"]
    task.total_tokens += usage["total_tokens"]
