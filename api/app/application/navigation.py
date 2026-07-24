"""Search/navigation use cases backed by Elasticsearch, PostgreSQL, and Neo4j."""

from __future__ import annotations

import asyncio
import math
import uuid
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from elasticsearch import NotFoundError
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.observability import observability_summary
from app.infrastructure.database.models.conversation import Conversation, Message
from app.infrastructure.database.models.knowledge import (
    Document,
    Favorite,
    ImageAsset,
    Tag,
    document_tags,
    image_tags,
)
from app.infrastructure.database.models.memory import MemorySource
from app.infrastructure.database.models.review import DailyReview
from app.infrastructure.database.repositories.tags import TAG_COLORS, normalize_tag_name
from app.infrastructure.graph.memory_graph import MemoryGraphRepository
from app.infrastructure.llm.bailian import BailianGateway
from app.infrastructure.search.chunk_index import CHUNK_INDEX
from app.infrastructure.search.elasticsearch import get_elasticsearch


async def global_search(
    user_id: uuid.UUID, query: str, top_k: int, min_score: float
) -> dict[str, list[dict[str, Any]]]:
    gateway = BailianGateway()
    try:
        vector = (await gateway.embed([query]))[0]
        documents, images, memory_rows = await asyncio.gather(
            _search_es(user_id, vector, "document", top_k, min_score),
            _search_es(user_id, vector, "image", top_k, min_score),
            MemoryGraphRepository().searchable_statements(str(user_id)),
        )
        memories = _rank_memories(memory_rows, vector, top_k, min_score)
        return {"documents": documents, "images": images, "memories": memories}
    finally:
        await gateway.close()


async def _search_es(
    user_id: uuid.UUID,
    vector: list[float],
    source_type: str,
    top_k: int,
    min_score: float,
) -> list[dict[str, Any]]:
    chunk_type = "child" if source_type == "document" else "image"
    try:
        response = await get_elasticsearch().search(
            index=CHUNK_INDEX,
            size=max(top_k * 3, 20),
            knn={
                "field": "vector",
                "query_vector": vector,
                "k": max(top_k * 3, 20),
                "num_candidates": max(top_k * 10, 100),
                "filter": [
                    {"term": {"user_id": str(user_id)}},
                    {"term": {"source_type": source_type}},
                    {"term": {"chunk_type": chunk_type}},
                ],
            },
            source_excludes=["vector"],
        )
    except NotFoundError:
        return []
    output: list[dict[str, Any]] = []
    seen: set[str] = set()
    for hit in response["hits"]["hits"]:
        source = hit["_source"]
        target_id = source["source_id"]
        score = max(0.0, min(1.0, float(hit["_score"]) * 2 - 1))
        if score < min_score or target_id in seen:
            continue
        seen.add(target_id)
        output.append(
            {
                "target_type": source_type,
                "target_id": target_id,
                "title": source["source_title"],
                "excerpt": source["content"][:480],
                "score": round(score, 4),
                "tags": source.get("tags") or [],
                "metadata": {
                    "chunk_id": source["chunk_id"],
                    "knowledge_base_id": source["knowledge_base_id"],
                    **(source.get("locator") or {}),
                },
            }
        )
        if len(output) >= top_k:
            break
    return output


def _cosine(left: list[float] | None, right: list[float]) -> float:
    if not left or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    return dot / (left_norm * right_norm) if left_norm and right_norm else 0.0


def _rank_memories(
    rows: list[dict[str, Any]], vector: list[float], top_k: int, min_score: float
) -> list[dict[str, Any]]:
    ranked = sorted(
        ((row, _cosine(row.get("embedding"), vector)) for row in rows),
        key=lambda item: item[1],
        reverse=True,
    )
    return [
        {
            "target_type": "memory",
            "target_id": row["id"],
            "title": "事件记忆" if row["statement_type"] == "event" else "画像记忆",
            "excerpt": row["text"],
            "score": round(score, 4),
            "tags": [],
            "metadata": {
                "source_id": row["source_id"],
                "statement_type": row["statement_type"],
                "event_time": row.get("event_time"),
                "subject": row["subject"],
                "predicate": row["predicate"],
                "object": row["object"],
            },
        }
        for row, score in ranked[:top_k]
        if score >= min_score
    ]


class FavoriteService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(
        self, user_id: uuid.UUID, target_type: str, target_id: str, snapshot: dict | None
    ) -> Favorite:
        await self.session.execute(
            pg_insert(Favorite)
            .values(
                id=uuid.uuid4(),
                user_id=user_id,
                target_type=target_type,
                target_id=target_id,
                snapshot=snapshot,
            )
            .on_conflict_do_update(
                constraint="uq_favorite_target", set_={"snapshot": snapshot}
            )
        )
        await self.session.commit()
        result = await self.session.scalar(
            select(Favorite).where(
                Favorite.user_id == user_id,
                Favorite.target_type == target_type,
                Favorite.target_id == target_id,
            )
        )
        if result is None:
            raise RuntimeError("收藏创建失败")
        return result

    async def list(self, user_id: uuid.UUID) -> list[Favorite]:
        statement = (
            select(Favorite)
            .where(Favorite.user_id == user_id)
            .order_by(Favorite.created_at.desc())
        )
        return list(await self.session.scalars(statement))

    async def remove(self, user_id: uuid.UUID, favorite_id: uuid.UUID) -> bool:
        result = await self.session.execute(
            delete(Favorite).where(Favorite.id == favorite_id, Favorite.user_id == user_id)
        )
        await self.session.commit()
        return bool(result.rowcount)


async def list_tags(session: AsyncSession, user_id: uuid.UUID) -> list[dict[str, Any]]:
    docs = (
        select(document_tags.c.tag_id, func.count().label("count"))
        .group_by(document_tags.c.tag_id)
        .subquery()
    )
    images = (
        select(image_tags.c.tag_id, func.count().label("count"))
        .group_by(image_tags.c.tag_id)
        .subquery()
    )
    rows = await session.execute(
        select(
            Tag,
            func.coalesce(docs.c.count, 0),
            func.coalesce(images.c.count, 0),
        )
        .outerjoin(docs, docs.c.tag_id == Tag.id)
        .outerjoin(images, images.c.tag_id == Tag.id)
        .where(Tag.user_id == user_id)
        .order_by(Tag.name)
    )
    return [
        {
            "id": tag.id,
            "name": tag.name,
            "color": tag.color,
            "source": tag.source,
            "document_count": int(document_count),
            "image_count": int(image_count),
        }
        for tag, document_count, image_count in rows.all()
    ]


async def create_tag(
    session: AsyncSession, user_id: uuid.UUID, name: str, color: str | None
) -> Tag:
    normalized = normalize_tag_name(name)
    existing = await session.scalar(
        select(Tag).where(Tag.user_id == user_id, Tag.normalized_name == normalized)
    )
    if existing:
        return existing
    selected_color = color or TAG_COLORS[sum(map(ord, normalized)) % len(TAG_COLORS)]
    tag = Tag(
        user_id=user_id,
        name=name.strip(),
        normalized_name=normalized,
        color=selected_color,
        source="manual",
    )
    session.add(tag)
    await session.commit()
    await session.refresh(tag)
    return tag


async def update_tag(
    session: AsyncSession,
    user_id: uuid.UUID,
    tag_id: uuid.UUID,
    *,
    name: str | None,
    color: str | None,
) -> Tag | None:
    tag = await session.scalar(select(Tag).where(Tag.id == tag_id, Tag.user_id == user_id))
    if tag is None:
        return None
    old_name = tag.name
    if name is not None:
        normalized = normalize_tag_name(name)
        conflict = await session.scalar(
            select(Tag).where(
                Tag.user_id == user_id,
                Tag.normalized_name == normalized,
                Tag.id != tag.id,
            )
        )
        if conflict:
            raise ValueError("同名标签已存在")
        tag.name = name.strip()
        tag.normalized_name = normalized
    if color is not None:
        tag.color = color
    await session.commit()
    await session.refresh(tag)
    if name is not None and old_name != tag.name:
        await _replace_es_tag(user_id, old_name, tag.name)
    return tag


async def delete_tag(session: AsyncSession, user_id: uuid.UUID, tag_id: uuid.UUID) -> bool:
    tag = await session.scalar(select(Tag).where(Tag.id == tag_id, Tag.user_id == user_id))
    if tag is None:
        return False
    name = tag.name
    await session.delete(tag)
    await session.commit()
    await _replace_es_tag(user_id, name, None)
    return True


async def _replace_es_tag(user_id: uuid.UUID, old_name: str, new_name: str | None) -> None:
    if not await get_elasticsearch().indices.exists(index=CHUNK_INDEX):
        return
    script = "ctx._source.tags.removeIf(t -> t == params.old);"
    if new_name:
        script += " if (!ctx._source.tags.contains(params.new)) {ctx._source.tags.add(params.new)}"
    await get_elasticsearch().update_by_query(
        index=CHUNK_INDEX,
        query={
            "bool": {
                "filter": [
                    {"term": {"user_id": str(user_id)}},
                    {"term": {"tags": old_name}},
                ]
            }
        },
        script={"lang": "painless", "source": script, "params": {"old": old_name, "new": new_name}},
        refresh=True,
        conflicts="proceed",
    )


async def get_daily_review(
    session: AsyncSession, user_id: uuid.UUID, review_date: date, refresh: bool
) -> DailyReview:
    existing = await session.scalar(
        select(DailyReview).where(
            DailyReview.user_id == user_id, DailyReview.review_date == review_date
        )
    )
    if existing is not None and not refresh:
        return existing
    start = datetime.combine(
        review_date, time.min, tzinfo=ZoneInfo("Asia/Shanghai")
    ).astimezone(UTC)
    end = start + timedelta(days=1)
    messages = list(
        await session.scalars(
            select(Message.content)
            .join(Conversation, Conversation.id == Message.conversation_id)
            .where(
                Conversation.user_id == user_id,
                Message.role == "user",
                Message.created_at >= start,
                Message.created_at < end,
            )
            .limit(20)
        )
    )
    memories = list(
        await session.scalars(
            select(MemorySource.raw_text)
            .where(
                MemorySource.user_id == user_id,
                MemorySource.created_at >= start,
                MemorySource.created_at < end,
            )
            .limit(20)
        )
    )
    documents = list(
        await session.scalars(
            select(Document.title).where(
                Document.user_id == user_id,
                Document.created_at >= start,
                Document.created_at < end,
            )
        )
    )
    images = list(
        await session.scalars(
            select(ImageAsset.file_name).where(
                ImageAsset.user_id == user_id,
                ImageAsset.created_at >= start,
                ImageAsset.created_at < end,
            )
        )
    )
    stats = {
        "questions": len(messages),
        "memories": len(memories),
        "documents": len(documents),
        "images": len(images),
    }
    total = sum(stats.values())
    content = "今天还没有新动态。整理一下已有知识，或记录一个新的想法吧。"
    if total:
        gateway = BailianGateway()
        try:
            prompt = (
                "请为用户生成一段不超过180字的中文每日回顾，语气温和、具体，不编造。\n"
                f"提问：{'；'.join(messages[:8]) or '无'}\n"
                f"记忆：{'；'.join(memories[:8]) or '无'}\n"
                f"文档：{'、'.join(documents[:8]) or '无'}\n"
                f"图片：{'、'.join(images[:8]) or '无'}"
            )
            response = await gateway.chat([{"role": "user", "content": prompt}], temperature=0.5)
            content = response.choices[0].message.content or content
        finally:
            await gateway.close()
    if existing:
        existing.content = content.strip()
        existing.stats = stats
        review = existing
    else:
        review = DailyReview(
            user_id=user_id,
            review_date=review_date,
            content=content.strip(),
            stats=stats,
        )
        session.add(review)
    await session.commit()
    await session.refresh(review)
    return review


async def dashboard_data(session: AsyncSession, user_id: uuid.UUID) -> dict[str, Any]:
    models = {
        "documents": Document,
        "images": ImageAsset,
        "conversations": Conversation,
        "memories": MemorySource,
        "favorites": Favorite,
        "tags": Tag,
    }
    counts = {
        name: int(
            await session.scalar(
                select(func.count()).select_from(model).where(model.user_id == user_id)
            )
            or 0
        )
        for name, model in models.items()
    }
    tags = await list_tags(session, user_id)
    tag_distribution = [
        {"name": item["name"], "value": item["document_count"] + item["image_count"]}
        for item in tags
        if item["document_count"] + item["image_count"] > 0
    ]
    today = date.today()
    start = today - timedelta(days=13)
    rows = await session.execute(
        select(func.date(MemorySource.created_at), func.count())
        .where(MemorySource.user_id == user_id, MemorySource.created_at >= start)
        .group_by(func.date(MemorySource.created_at))
    )
    day_counts = {str(day): int(count) for day, count in rows.all()}
    memory_trend = [
        {
            "date": (start + timedelta(days=offset)).isoformat(),
            "value": day_counts.get((start + timedelta(days=offset)).isoformat(), 0),
        }
        for offset in range(14)
    ]
    communities = await MemoryGraphRepository().rebuild_communities(str(user_id))
    counts["entities"] = sum(item["member_count"] for item in communities)
    counts["communities"] = len(communities)
    return {
        "counts": counts,
        "tag_distribution": sorted(
            tag_distribution, key=lambda item: item["value"], reverse=True
        )[:10],
        "memory_trend": memory_trend,
        "community_distribution": [
            {"name": item["name"], "value": item["member_count"]}
            for item in communities[:10]
        ],
        "observability": await observability_summary(session, user_id, 14),
    }
