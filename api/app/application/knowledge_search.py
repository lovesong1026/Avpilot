"""User-scoped BM25 and vector retrieval with reciprocal-rank fusion."""

import logging
import uuid
from typing import Any

from app.domain.model_gateway import RerankUnavailableError
from app.infrastructure.llm.bailian import BailianGateway
from app.infrastructure.search.chunk_index import CHUNK_INDEX
from app.infrastructure.search.elasticsearch import get_elasticsearch

logger = logging.getLogger(__name__)


def reciprocal_rank_fusion(
    rankings: list[list[str]], *, rank_constant: int = 60
) -> dict[str, float]:
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, chunk_id in enumerate(ranking, start=1):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (rank_constant + rank)
    return scores


async def search_knowledge_base(
    *,
    user_id: uuid.UUID,
    knowledge_base_id: uuid.UUID,
    query: str,
    top_k: int,
    use_rerank: bool,
) -> list[dict[str, Any]]:
    return await search_knowledge_bases(
        user_id=user_id,
        knowledge_base_ids=[knowledge_base_id],
        query=query,
        top_k=top_k,
        use_rerank=use_rerank,
    )


async def search_knowledge_bases(
    *,
    user_id: uuid.UUID,
    knowledge_base_ids: list[uuid.UUID],
    query: str,
    top_k: int,
    use_rerank: bool,
) -> list[dict[str, Any]]:
    if not knowledge_base_ids:
        return []
    gateway = BailianGateway()
    try:
        query_vector = (await gateway.embed([query]))[0]
        candidates = await _retrieve_candidates(
            user_id=user_id,
            knowledge_base_ids=knowledge_base_ids,
            query=query,
            query_vector=query_vector,
            recall_size=max(20, top_k * 4),
        )
        if use_rerank and candidates:
            candidates = await _rerank(gateway, query, candidates, top_k)
        return await _resolve_results(candidates, top_k)
    finally:
        await gateway.close()


async def _retrieve_candidates(
    *,
    user_id: uuid.UUID,
    knowledge_base_ids: list[uuid.UUID],
    query: str,
    query_vector: list[float],
    recall_size: int,
) -> list[dict[str, Any]]:
    client = get_elasticsearch()
    filters = [
        {"term": {"user_id": str(user_id)}},
        {"terms": {"knowledge_base_id": [str(item) for item in knowledge_base_ids]}},
        {"term": {"source_type": "document"}},
        {"term": {"chunk_type": "child"}},
    ]
    vector_response = await client.search(
        index=CHUNK_INDEX,
        size=recall_size,
        knn={
            "field": "vector",
            "query_vector": query_vector,
            "k": recall_size,
            "num_candidates": recall_size * 5,
            "filter": {"bool": {"filter": filters}},
        },
        source_excludes=["vector"],
    )
    bm25_response = await client.search(
        index=CHUNK_INDEX,
        size=recall_size,
        query={"bool": {"must": [{"match": {"content": query}}], "filter": filters}},
        source_excludes=["vector"],
    )
    vector_hits = list(vector_response["hits"]["hits"])
    bm25_hits = list(bm25_response["hits"]["hits"])
    sources = {hit["_id"]: hit["_source"] for hit in [*vector_hits, *bm25_hits]}
    fused = reciprocal_rank_fusion(
        [[hit["_id"] for hit in vector_hits], [hit["_id"] for hit in bm25_hits]]
    )
    ordered = sorted(fused, key=fused.get, reverse=True)
    top_score = fused[ordered[0]] if ordered else 1.0
    return [
        {
            "chunk_id": chunk_id,
            "source": sources[chunk_id],
            "score": fused[chunk_id] / top_score,
        }
        for chunk_id in ordered
    ]


async def _rerank(
    gateway: BailianGateway, query: str, candidates: list[dict[str, Any]], top_k: int
) -> list[dict[str, Any]]:
    try:
        reranked = await gateway.rerank(
            query,
            [candidate["source"]["content"] for candidate in candidates],
            top_n=min(top_k, len(candidates)),
        )
    except RerankUnavailableError as exc:
        logger.info("Rerank is not configured; using RRF order: %s", exc)
        return candidates
    except Exception as exc:
        logger.warning("Rerank unavailable; using RRF order: %s", exc)
        return candidates
    return [
        {**candidates[item.index], "score": item.relevance_score}
        for item in reranked
        if 0 <= item.index < len(candidates)
    ]


async def _resolve_results(
    candidates: list[dict[str, Any]], top_k: int
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    seen_parents: set[str] = set()
    for candidate in candidates:
        parent_id = candidate["source"].get("parent_id")
        dedupe_key = parent_id or candidate["chunk_id"]
        if dedupe_key in seen_parents:
            continue
        seen_parents.add(dedupe_key)
        selected.append(candidate)
        if len(selected) >= top_k:
            break

    parent_ids = [item["source"].get("parent_id") for item in selected]
    parent_ids = [parent_id for parent_id in parent_ids if parent_id]
    parent_content: dict[str, str] = {}
    if parent_ids:
        response = await get_elasticsearch().mget(
            index=CHUNK_INDEX,
            ids=parent_ids,
            source_excludes=["vector"],
        )
        parent_content = {
            item["_id"]: item["_source"]["content"]
            for item in response["docs"]
            if item.get("found")
        }

    results: list[dict[str, Any]] = []
    for item in selected:
        source = item["source"]
        locator = source.get("locator") or {}
        results.append(
            {
                "chunk_id": item["chunk_id"],
                "content": parent_content.get(source.get("parent_id"), source["content"]),
                "excerpt": source["content"],
                "score": round(float(item["score"]), 4),
                "citation": {
                    "document_id": source["source_id"],
                    "document_title": source["source_title"],
                    "file_name": locator.get("file_name"),
                    "page": locator.get("page"),
                    "start_char": locator.get("start_char"),
                    "end_char": locator.get("end_char"),
                },
            }
        )
    return results
