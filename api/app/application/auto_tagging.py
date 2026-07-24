"""AI content classification that preferentially reuses existing user tags."""

import json
import logging
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models.knowledge import Tag
from app.infrastructure.database.repositories.tags import TagRepository, normalize_tag_name
from app.infrastructure.llm.bailian import BailianGateway

logger = logging.getLogger(__name__)


async def assign_auto_tags(
    *,
    session: AsyncSession,
    gateway: BailianGateway,
    user_id: uuid.UUID,
    target_type: str,
    target_id: uuid.UUID,
    content: str,
) -> list[Tag]:
    """Classify content into at most two broad tags without blocking ingestion on failure."""
    try:
        repository = TagRepository(session)
        existing = await repository.list_tags(user_id)
        names = await suggest_tag_names(gateway, content, [tag.name for tag in existing])
        if not names:
            return await _target_tags(repository, target_type, target_id)
        async with session.begin_nested():
            tags = [await repository.get_or_create(user_id, name) for name in names]
            if target_type == "document":
                await repository.set_document_tags(target_id, [tag.id for tag in tags])
            elif target_type == "image":
                await repository.set_image_tags(target_id, [tag.id for tag in tags])
            else:
                raise ValueError("不支持的标签目标类型")
        await session.flush()
        return tags
    except Exception as exc:
        logger.warning("AI auto-tagging skipped for %s %s: %s", target_type, target_id, exc)
        try:
            return await _target_tags(TagRepository(session), target_type, target_id)
        except Exception:
            return []


async def _target_tags(
    repository: TagRepository, target_type: str, target_id: uuid.UUID
) -> list[Tag]:
    if target_type == "document":
        return await repository.document_tags(target_id)
    if target_type == "image":
        return await repository.image_tags(target_id)
    raise ValueError("不支持的标签目标类型")


async def suggest_tag_names(
    gateway: BailianGateway, content: str, existing_names: list[str]
) -> list[str]:
    existing = "、".join(existing_names) if existing_names else "（暂无已有标签）"
    prompt = (
        "你是 Avpilot 的内容分类器。为下方内容选择 1 到 2 个宽泛的中文主题标签。\n"
        f"已有标签：{existing}\n"
        "必须优先复用语义合适的已有标签；只有全部不合适时才能创建一个新标签。"
        "不要创建同义词或过细标签。每个标签 2 到 6 个字。"
        '只返回 JSON 数组，例如 ["技术","学习"]。\n\n'
        f"内容：\n{content[:1800]}"
    )
    response = await gateway.chat([{"role": "user", "content": prompt}], temperature=0.1)
    answer = response.choices[0].message.content or ""
    return parse_tag_names(answer, existing_names)


def parse_tag_names(answer: str, existing_names: list[str] | None = None) -> list[str]:
    start = answer.find("[")
    end = answer.rfind("]")
    if start < 0 or end <= start:
        return []
    try:
        value: Any = json.loads(answer[start : end + 1])
    except json.JSONDecodeError:
        return []
    if not isinstance(value, list):
        return []
    existing_by_normalized = {normalize_tag_name(name): name for name in existing_names or []}
    result: list[str] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, str):
            continue
        name = item.strip()[:64]
        normalized = normalize_tag_name(name)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(existing_by_normalized.get(normalized, name))
        if len(result) == 2:
            break
    return result
