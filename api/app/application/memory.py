"""Asynchronous memory extraction and four-layer provenance orchestration."""

from __future__ import annotations

import json
import logging
import math
import re
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.application.task_queue import (
    MEMORY_TASK,
    dispatch_outbox,
    enqueue_task,
    task_dedupe_key,
)
from app.infrastructure.database.models.memory import MemorySource
from app.infrastructure.database.postgres import get_session_factory
from app.infrastructure.database.repositories.memory import MemoryRepository
from app.infrastructure.graph.memory_graph import MemoryGraphRepository
from app.infrastructure.llm.bailian import BailianGateway, _parse_json_object

logger = logging.getLogger(__name__)

_ENTITY_SIMILARITY = 0.90
_STATEMENT_SIMILARITY = 0.94


async def create_memory_source(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    text: str,
    source_type: str,
    source_message_id: uuid.UUID | None = None,
) -> MemorySource:
    source = MemorySource(
        user_id=user_id,
        raw_text=text.strip(),
        source_type=source_type,
        source_message_id=source_message_id,
        status="pending",
    )
    MemoryRepository(session).add(source)
    await session.flush()
    enqueue_task(
        session,
        task_name=MEMORY_TASK,
        queue="memory",
        dedupe_key=task_dedupe_key("memory", source.id),
        payload={"source_id": str(source.id)},
    )
    await session.commit()
    await session.refresh(source)
    return source


async def process_memory_source(
    source_id: uuid.UUID, *, raise_on_failure: bool = False
) -> None:
    """Run extraction outside the request session and persist an auditable status."""
    gateway: BailianGateway | None = None
    async with get_session_factory()() as session:
        repository = MemoryRepository(session)
        source = await repository.get(source_id)
        if source is None:
            return
        try:
            source.status = "extracting"
            source.error_code = None
            source.error_message = None
            await session.commit()

            gateway = BailianGateway()
            extracted = await _extract(gateway, source.raw_text)
            graph_stats = await _prepare_and_write(gateway, source, extracted)
            source.status = "completed"
            source.graph_source_id = str(source.id)
            source.graph_stats = graph_stats
            await session.commit()
        except Exception as exc:
            logger.exception("Memory extraction failed: source=%s", source_id)
            source.status = "failed"
            source.error_code = type(exc).__name__[:64]
            source.error_message = str(exc)[:2000]
            await session.commit()
            if raise_on_failure:
                raise
        finally:
            if gateway is not None:
                await gateway.close()


async def _extract(gateway: BailianGateway, text: str) -> dict[str, Any]:
    prompt = f"""
你是 Avpilot 星航仪的长期记忆萃取器。当前时间：{datetime.now(UTC).isoformat()}。
从文本中只提取未来对用户确有帮助的稳定画像、偏好、目标、人物关系和明确事件。
普通问句、寒暄、助手建议、无法确认的猜测不要记忆。用户自称统一写成“用户本人”。

只返回以下 JSON，不要 Markdown：
{{
  "statements": [
    {{
      "text": "一条可独立理解的原子陈述",
      "subject": "实体名称",
      "predicate": "简短中文关系",
      "object": "实体名称或值",
      "subject_type": "person|organization|place|topic|preference|goal|other",
      "object_type": "person|organization|place|topic|preference|goal|other",
      "statement_type": "profile|event",
      "event_time": "ISO 8601 时间；无明确时间则为 null",
      "confidence": 0.0
    }}
  ]
}}
最多 12 条。没有值得记忆的内容时返回 {{"statements":[]}}。

待萃取文本：
<memory>{text}</memory>
""".strip()
    response = await gateway.chat(
        [{"role": "user", "content": prompt}], temperature=0.0
    )
    content = response.choices[0].message.content
    if not content:
        return {"statements": []}
    return _parse_json_object(content)


async def _prepare_and_write(
    gateway: BailianGateway, source: MemorySource, extracted: dict[str, Any]
) -> dict[str, int]:
    now = datetime.now(UTC).isoformat()
    raw_statements = extracted.get("statements")
    if not isinstance(raw_statements, list):
        raw_statements = []
    clean = [_clean_statement(item) for item in raw_statements if isinstance(item, dict)]
    clean = [item for item in clean if item is not None]

    fragment_texts = _split_fragments(source.raw_text)
    fragments = [
        {
            "id": uuid.uuid5(source.id, f"{index}:{value}").hex,
            "user_id": str(source.user_id),
            "text": value,
            "sequence": index,
            "created_at": now,
        }
        for index, value in enumerate(fragment_texts)
    ]
    entity_inputs: dict[tuple[str, str], dict[str, str]] = {}
    for item in clean:
        for side in ("subject", "object"):
            name = item[side]
            entity_type = item[f"{side}_type"]
            entity_inputs.setdefault(
                (_normalize(name), entity_type), {"name": name, "entity_type": entity_type}
            )

    graph = MemoryGraphRepository()
    existing_entities = await graph.existing_entities(str(source.user_id))
    existing_statements = await graph.existing_statements(str(source.user_id))
    entity_values = list(entity_inputs.values())
    entity_vectors = await gateway.embed([item["name"] for item in entity_values])
    entities, entity_ids, entity_reused = _dedupe_entities(
        str(source.user_id), entity_values, entity_vectors, existing_entities, now
    )

    statement_texts = [item["text"] for item in clean]
    statement_vectors = await gateway.embed(statement_texts)
    statements: list[dict[str, Any]] = []
    statement_reused = 0
    for item, embedding in zip(clean, statement_vectors, strict=True):
        normalized_key = _statement_key(item)
        match = _match_statement(item, normalized_key, embedding, existing_statements)
        statement_id = match["id"] if match else uuid.uuid4().hex
        statement_reused += int(match is not None)
        fragment = _best_fragment(item["text"], fragments)
        statements.append(
            {
                "id": statement_id,
                "user_id": str(source.user_id),
                "fragment_id": fragment["id"],
                "text": item["text"],
                "normalized_key": normalized_key,
                "statement_type": item["statement_type"],
                "event_time": item["event_time"],
                "confidence": item["confidence"],
                "predicate": item["predicate"],
                "subject_id": entity_ids[(_normalize(item["subject"]), item["subject_type"])],
                "object_id": entity_ids[(_normalize(item["object"]), item["object_type"])],
                "embedding": embedding,
                "created_at": now,
                "updated_at": now,
            }
        )

    await graph.write_extraction(
        source={
            "id": str(source.id),
            "user_id": str(source.user_id),
            "raw_text": source.raw_text,
            "source_type": source.source_type,
            "source_message_id": (
                str(source.source_message_id) if source.source_message_id else None
            ),
            "created_at": source.created_at.isoformat(),
            "updated_at": now,
        },
        fragments=fragments,
        entities=entities,
        statements=statements,
    )
    await graph.prune_orphans(str(source.user_id))
    communities = await graph.rebuild_communities(str(source.user_id))
    return {
        "fragments": len(fragments),
        "statements": len(statements),
        "entities": len(entities),
        "entities_reused": entity_reused,
        "statements_reused": statement_reused,
        "communities": len(communities),
    }


def _clean_statement(item: dict[str, Any]) -> dict[str, Any] | None:
    required = ("text", "subject", "predicate", "object")
    values = {key: str(item.get(key) or "").strip() for key in required}
    if any(not values[key] for key in required):
        return None
    confidence = max(0.0, min(1.0, float(item.get("confidence") or 0.8)))
    if confidence < 0.55:
        return None
    statement_type = str(item.get("statement_type") or "profile").lower()
    if statement_type not in {"profile", "event"}:
        statement_type = "profile"
    event_time = item.get("event_time")
    if not isinstance(event_time, str) or not event_time.strip():
        event_time = None
    return {
        **values,
        "subject_type": _entity_type(item.get("subject_type")),
        "object_type": _entity_type(item.get("object_type")),
        "statement_type": statement_type,
        "event_time": event_time,
        "confidence": confidence,
    }


def _entity_type(value: object) -> str:
    normalized = str(value or "other").lower()
    allowed = {"person", "organization", "place", "topic", "preference", "goal", "other"}
    return normalized if normalized in allowed else "other"


def _normalize(value: str) -> str:
    normalized = re.sub(r"[\s\W_]+", "", value.casefold())
    if normalized in {"我", "本人", "用户", "用户本人"}:
        return "用户本人"
    return normalized


def _split_fragments(text: str, size: int = 900) -> list[str]:
    paragraphs = [value.strip() for value in re.split(r"\n{2,}", text) if value.strip()]
    if not paragraphs:
        return [text.strip()]
    fragments: list[str] = []
    current = ""
    for paragraph in paragraphs:
        candidate = f"{current}\n\n{paragraph}".strip()
        if current and len(candidate) > size:
            fragments.append(current)
            current = paragraph
        else:
            current = candidate
    if current:
        fragments.append(current)
    return fragments


def _cosine(left: list[float] | None, right: list[float] | None) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    norm_left = math.sqrt(sum(value * value for value in left))
    norm_right = math.sqrt(sum(value * value for value in right))
    return dot / (norm_left * norm_right) if norm_left and norm_right else 0.0


def _dedupe_entities(
    user_id: str,
    values: list[dict[str, str]],
    vectors: list[list[float]],
    existing: list[dict[str, Any]],
    now: str,
) -> tuple[list[dict[str, Any]], dict[tuple[str, str], str], int]:
    output: list[dict[str, Any]] = []
    ids: dict[tuple[str, str], str] = {}
    reused = 0
    candidates = list(existing)
    for value, embedding in zip(values, vectors, strict=True):
        key = (_normalize(value["name"]), value["entity_type"])
        exact = next(
            (
                row
                for row in candidates
                if row.get("normalized_name") == key[0]
            ),
            None,
        )
        semantic = exact or max(
            (
                row
                for row in candidates
                if row.get("entity_type") == key[1]
                and _cosine(embedding, row.get("embedding")) >= _ENTITY_SIMILARITY
            ),
            key=lambda row: _cosine(embedding, row.get("embedding")),
            default=None,
        )
        entity_id = semantic["id"] if semantic else uuid.uuid4().hex
        reused += int(semantic is not None)
        previous_aliases = semantic.get("aliases") or [] if semantic else []
        aliases = list(dict.fromkeys([*previous_aliases, value["name"]]))
        entity = {
            "id": entity_id,
            "user_id": user_id,
            "name": semantic.get("name", value["name"]) if semantic else value["name"],
            "normalized_name": semantic.get("normalized_name", key[0]) if semantic else key[0],
            "entity_type": (
                semantic.get("entity_type", value["entity_type"])
                if semantic
                else value["entity_type"]
            ),
            "aliases": aliases,
            "embedding": embedding,
            "mention_increment": 1,
            "created_at": semantic.get("created_at", now) if semantic else now,
            "updated_at": now,
        }
        output.append(entity)
        ids[key] = entity_id
        candidates.append(entity)
    unique = {item["id"]: item for item in output}
    return list(unique.values()), ids, reused


def _statement_key(item: dict[str, Any]) -> str:
    parts = (_normalize(item["subject"]), _normalize(item["predicate"]), _normalize(item["object"]))
    event = item["event_time"] or ""
    return "|".join((*parts, event[:10]))


def _match_statement(
    item: dict[str, Any],
    normalized_key: str,
    embedding: list[float],
    existing: list[dict[str, Any]],
) -> dict[str, Any] | None:
    exact = next((row for row in existing if row.get("normalized_key") == normalized_key), None)
    if exact:
        return exact
    for row in existing:
        if row.get("statement_type") != item["statement_type"]:
            continue
        if item["statement_type"] == "event":
            old_date = str(row.get("event_time") or "")[:10]
            new_date = str(item["event_time"] or "")[:10]
            if old_date != new_date:
                continue
        if _cosine(embedding, row.get("embedding")) >= _STATEMENT_SIMILARITY:
            return row
    return None


def _best_fragment(statement: str, fragments: list[dict[str, Any]]) -> dict[str, Any]:
    words = set(_normalize(statement))
    return max(fragments, key=lambda item: len(words & set(_normalize(item["text"]))))


def extraction_preview(value: dict[str, Any]) -> str:
    """Stable helper used by tests and diagnostics."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


async def extract_conversation_memory(
    user_id: uuid.UUID, text: str, source_message_id: uuid.UUID
) -> None:
    """Persist and dispatch conversation memory without running extraction in the API."""
    try:
        async with get_session_factory()() as session:
            source = await create_memory_source(
                session,
                user_id=user_id,
                text=text,
                source_type="conversation",
                source_message_id=source_message_id,
            )
        await dispatch_outbox(task_dedupe_key("memory", source.id))
    except Exception:
        logger.exception("Could not dispatch conversation memory: message=%s", source_message_id)
