"""Active memory, provenance graph, timeline, and community routes."""

import uuid

from fastapi import APIRouter, HTTPException, Query, status

from app.api.dependencies import CurrentUser, SessionDependency
from app.api.schemas.memory import (
    CommunityItem,
    MemoryCreate,
    MemoryEdge,
    MemoryGraphResponse,
    MemoryNode,
    MemorySourceResponse,
    TimelineItem,
)
from app.application.memory import create_memory_source
from app.application.task_queue import (
    dispatch_outbox,
    prepare_memory_retry,
    task_dedupe_key,
)
from app.infrastructure.database.repositories.memory import MemoryRepository
from app.infrastructure.graph.memory_graph import MemoryGraphRepository

router = APIRouter(prefix="/memories", tags=["memory"])


@router.post("", response_model=MemorySourceResponse, status_code=status.HTTP_202_ACCEPTED)
async def remember(
    request: MemoryCreate,
    user: CurrentUser,
    session: SessionDependency,
) -> MemorySourceResponse:
    source = await create_memory_source(
        session, user_id=user.id, text=request.text, source_type="manual"
    )
    await dispatch_outbox(task_dedupe_key("memory", source.id))
    return MemorySourceResponse.model_validate(source)


@router.post("/{source_id}/retry", response_model=MemorySourceResponse)
async def retry_memory(
    source_id: uuid.UUID, user: CurrentUser, session: SessionDependency
) -> MemorySourceResponse:
    try:
        source, key = await prepare_memory_retry(
            session, user_id=user.id, source_id=source_id
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    await dispatch_outbox(key)
    return MemorySourceResponse.model_validate(source)


@router.get("", response_model=list[MemorySourceResponse])
async def list_memories(
    user: CurrentUser,
    session: SessionDependency,
    limit: int = Query(default=50, ge=1, le=200),
) -> list[MemorySourceResponse]:
    rows = await MemoryRepository(session).list_for_user(user.id, limit)
    return [MemorySourceResponse.model_validate(item) for item in rows]


@router.get("/graph", response_model=MemoryGraphResponse)
async def memory_graph(user: CurrentUser) -> MemoryGraphResponse:
    payload = await MemoryGraphRepository().graph(str(user.id))
    nodes = []
    for item in payload["nodes"]:
        kind = MemoryGraphRepository._kind(item.get("labels") or [])
        nodes.append(
            MemoryNode(
                id=item["id"],
                kind=kind,
                label=str(item.get("name") or item["id"])[:160],
                properties={
                    key: value
                    for key, value in item.items()
                    if key not in {"id", "labels", "name"} and value is not None
                },
            )
        )
    return MemoryGraphResponse(
        nodes=nodes,
        edges=[MemoryEdge.model_validate(item) for item in payload["edges"]],
        stats=payload["stats"],
    )


@router.get("/timeline", response_model=list[TimelineItem])
async def memory_timeline(user: CurrentUser) -> list[TimelineItem]:
    rows = await MemoryGraphRepository().timeline(str(user.id))
    return [TimelineItem.model_validate(item) for item in rows]


@router.get("/communities", response_model=list[CommunityItem])
async def memory_communities(user: CurrentUser) -> list[CommunityItem]:
    rows = await MemoryGraphRepository().rebuild_communities(str(user.id))
    return [CommunityItem.model_validate(item) for item in rows]


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_memory(
    source_id: uuid.UUID, user: CurrentUser, session: SessionDependency
) -> None:
    source = await MemoryRepository(session).get_for_user(user.id, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="记忆来源不存在")
    await MemoryGraphRepository().delete_source(str(user.id), str(source.id))
    await session.delete(source)
    await session.commit()
