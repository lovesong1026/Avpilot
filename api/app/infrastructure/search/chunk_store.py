"""Write and remove parent-child document chunks in Elasticsearch."""

import uuid
from datetime import UTC, datetime
from typing import Any

from elasticsearch.helpers import async_bulk

from app.domain.chunking import ParentChunk
from app.domain.documents import ParsedDocument
from app.infrastructure.search.chunk_index import CHUNK_INDEX, ensure_chunk_index
from app.infrastructure.search.elasticsearch import get_elasticsearch


def build_index_actions(
    *,
    user_id: uuid.UUID,
    knowledge_base_id: uuid.UUID,
    document_id: uuid.UUID,
    title: str,
    file_name: str | None,
    parsed: ParsedDocument,
    parents: list[ParentChunk],
    child_vectors: list[list[float]],
) -> list[dict[str, Any]]:
    expected_children = sum(len(parent.children) for parent in parents)
    if expected_children != len(child_vectors):
        raise ValueError("Child chunk and embedding counts do not match")

    now = datetime.now(UTC).isoformat()
    vector_index = 0
    actions: list[dict[str, Any]] = []
    for parent in parents:
        parent_id = uuid.uuid4().hex
        parent_page = parsed.page_for_offset(parent.start_char)
        actions.append(
            _action(
                chunk_id=parent_id,
                user_id=user_id,
                knowledge_base_id=knowledge_base_id,
                document_id=document_id,
                title=title,
                file_name=file_name,
                chunk_type="parent",
                parent_id=None,
                content=parent.text,
                vector=None,
                page=parent_page,
                start_char=parent.start_char,
                end_char=parent.end_char,
                created_at=now,
            )
        )
        for child in parent.children:
            child_id = uuid.uuid4().hex
            actions.append(
                _action(
                    chunk_id=child_id,
                    user_id=user_id,
                    knowledge_base_id=knowledge_base_id,
                    document_id=document_id,
                    title=title,
                    file_name=file_name,
                    chunk_type="child",
                    parent_id=parent_id,
                    content=child.text,
                    vector=child_vectors[vector_index],
                    page=parsed.page_for_offset(child.start_char),
                    start_char=child.start_char,
                    end_char=child.end_char,
                    created_at=now,
                )
            )
            vector_index += 1
    return actions


def _action(
    *,
    chunk_id: str,
    user_id: uuid.UUID,
    knowledge_base_id: uuid.UUID,
    document_id: uuid.UUID,
    title: str,
    file_name: str | None,
    chunk_type: str,
    parent_id: str | None,
    content: str,
    vector: list[float] | None,
    page: int | None,
    start_char: int,
    end_char: int,
    created_at: str,
) -> dict[str, Any]:
    source: dict[str, Any] = {
        "user_id": str(user_id),
        "knowledge_base_id": str(knowledge_base_id),
        "source_type": "document",
        "source_id": str(document_id),
        "source_title": title,
        "chunk_id": chunk_id,
        "chunk_type": chunk_type,
        "parent_id": parent_id,
        "content": content,
        "tags": [],
        "locator": {
            "file_name": file_name,
            "page": page,
            "start_char": start_char,
            "end_char": end_char,
        },
        "created_at": created_at,
    }
    if vector is not None:
        source["vector"] = vector
    return {"_op_type": "index", "_index": CHUNK_INDEX, "_id": chunk_id, "_source": source}


async def bulk_index(actions: list[dict[str, Any]]) -> int:
    if not actions:
        return 0
    await ensure_chunk_index()
    success, _ = await async_bulk(get_elasticsearch(), actions, raise_on_error=True)
    await get_elasticsearch().indices.refresh(index=CHUNK_INDEX)
    return int(success)


async def delete_document_chunks(user_id: uuid.UUID, document_id: uuid.UUID) -> int:
    if not await get_elasticsearch().indices.exists(index=CHUNK_INDEX):
        return 0
    response = await get_elasticsearch().delete_by_query(
        index=CHUNK_INDEX,
        query={
            "bool": {
                "filter": [
                    {"term": {"user_id": str(user_id)}},
                    {"term": {"source_id": str(document_id)}},
                ]
            }
        },
        refresh=True,
    )
    return int(response.get("deleted", 0))
