"""Unified search and navigation endpoints."""

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from app.api.dependencies import CurrentUser, SessionDependency
from app.api.schemas.navigation import (
    DailyReviewResponse,
    DashboardResponse,
    FavoriteCreate,
    FavoriteResponse,
    GlobalSearchRequest,
    GlobalSearchResponse,
    TagCreate,
    TagManagementResponse,
    TagUpdate,
)
from app.application.navigation import (
    FavoriteService,
    create_tag,
    dashboard_data,
    delete_tag,
    get_daily_review,
    global_search,
    list_tags,
    update_tag,
)

router = APIRouter(tags=["navigation"])


@router.post("/search", response_model=GlobalSearchResponse)
async def search_all(request: GlobalSearchRequest, user: CurrentUser) -> GlobalSearchResponse:
    result = await global_search(
        user.id, request.query.strip(), request.top_k, request.min_score
    )
    return GlobalSearchResponse(query=request.query.strip(), **result)


@router.get("/favorites", response_model=list[FavoriteResponse])
async def list_favorites(
    user: CurrentUser, session: SessionDependency
) -> list[FavoriteResponse]:
    rows = await FavoriteService(session).list(user.id)
    return [FavoriteResponse.model_validate(item) for item in rows]


@router.post(
    "/favorites", response_model=FavoriteResponse, status_code=status.HTTP_201_CREATED
)
async def add_favorite(
    request: FavoriteCreate, user: CurrentUser, session: SessionDependency
) -> FavoriteResponse:
    favorite = await FavoriteService(session).add(
        user.id, request.target_type, request.target_id, request.snapshot
    )
    return FavoriteResponse.model_validate(favorite)


@router.delete("/favorites/{favorite_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_favorite(
    favorite_id: uuid.UUID, user: CurrentUser, session: SessionDependency
) -> None:
    if not await FavoriteService(session).remove(user.id, favorite_id):
        raise HTTPException(status_code=404, detail="收藏不存在")


@router.get("/tags", response_model=list[TagManagementResponse])
async def tags(user: CurrentUser, session: SessionDependency) -> list[TagManagementResponse]:
    rows = await list_tags(session, user.id)
    return [TagManagementResponse.model_validate(item) for item in rows]


@router.post("/tags", response_model=TagManagementResponse, status_code=status.HTTP_201_CREATED)
async def add_tag(
    request: TagCreate, user: CurrentUser, session: SessionDependency
) -> TagManagementResponse:
    tag = await create_tag(session, user.id, request.name, request.color)
    return TagManagementResponse(
        id=tag.id,
        name=tag.name,
        color=tag.color,
        source=tag.source,
        document_count=0,
        image_count=0,
    )


@router.patch("/tags/{tag_id}", response_model=TagManagementResponse)
async def edit_tag(
    tag_id: uuid.UUID,
    request: TagUpdate,
    user: CurrentUser,
    session: SessionDependency,
) -> TagManagementResponse:
    try:
        tag = await update_tag(
            session, user.id, tag_id, name=request.name, color=request.color
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if tag is None:
        raise HTTPException(status_code=404, detail="标签不存在")
    usage = next(
        item for item in await list_tags(session, user.id) if item["id"] == tag.id
    )
    return TagManagementResponse.model_validate(usage)


@router.delete("/tags/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_tag(
    tag_id: uuid.UUID, user: CurrentUser, session: SessionDependency
) -> None:
    if not await delete_tag(session, user.id, tag_id):
        raise HTTPException(status_code=404, detail="标签不存在")


@router.get("/daily-review", response_model=DailyReviewResponse)
async def daily_review(
    user: CurrentUser,
    session: SessionDependency,
    day: Annotated[date | None, Query()] = None,
    refresh: bool = False,
) -> DailyReviewResponse:
    review = await get_daily_review(session, user.id, day or date.today(), refresh)
    return DailyReviewResponse(
        id=review.id,
        review_date=review.review_date,
        content=review.content,
        stats=review.stats or {},
        created_at=review.created_at,
        updated_at=review.updated_at,
    )


@router.get("/dashboard", response_model=DashboardResponse)
async def dashboard(user: CurrentUser, session: SessionDependency) -> DashboardResponse:
    return DashboardResponse.model_validate(await dashboard_data(session, user.id))
