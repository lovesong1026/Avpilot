"""Authenticated multimodal image library routes."""

import uuid
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import Response

from app.api.dependencies import CurrentUser, SessionDependency
from app.api.schemas.images import (
    ImageAssetResponse,
    ImageSearchRequest,
    ImageSearchResponse,
)
from app.api.schemas.knowledge import IngestionJobResponse
from app.application.images import (
    ImageConflictError,
    ImageNotFoundError,
    ImageService,
    InvalidImageUploadError,
)
from app.application.knowledge_search import search_image_assets
from app.application.task_queue import (
    dispatch_outbox,
    prepare_ingestion_retry,
    task_dedupe_key,
)
from app.infrastructure.database.models.knowledge import ImageAsset, IngestionJob
from app.infrastructure.database.repositories.knowledge import KnowledgeRepository
from app.infrastructure.database.repositories.tags import TagRepository
from app.infrastructure.storage.local import LocalDocumentStorage

router = APIRouter(prefix="/images", tags=["images"])


def _image_response(
    image: ImageAsset, job: IngestionJob | None = None, tags: list[object] | None = None
) -> ImageAssetResponse:
    job_response = IngestionJobResponse.model_validate(job) if job else None
    return ImageAssetResponse.model_validate(image).model_copy(
        update={
            "content_url": f"/api/images/{image.id}/content",
            "ingestion_job": job_response,
            "tags": tags or [],
        }
    )


@router.get("", response_model=list[ImageAssetResponse])
async def list_images(
    user: CurrentUser,
    session: SessionDependency,
    knowledge_base_id: Annotated[uuid.UUID | None, Query()] = None,
) -> list[ImageAssetResponse]:
    repository = KnowledgeRepository(session)
    tag_repository = TagRepository(session)
    images = await repository.list_images(user.id, knowledge_base_id)
    return [
        _image_response(
            image,
            await repository.get_latest_image_job(user.id, image.id),
            await tag_repository.image_tags(image.id),
        )
        for image in images
    ]


@router.post("", response_model=ImageAssetResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_image(
    user: CurrentUser,
    session: SessionDependency,
    knowledge_base_id: Annotated[uuid.UUID, Form()],
    file: Annotated[UploadFile, File()],
) -> ImageAssetResponse:
    try:
        image, job = await ImageService(session).upload(
            user_id=user.id,
            knowledge_base_id=knowledge_base_id,
            upload=file,
        )
    except ImageNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvalidImageUploadError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ImageConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    await dispatch_outbox(task_dedupe_key("image", job.id))
    return _image_response(image, job)


@router.post("/{image_id}/retry", response_model=ImageAssetResponse)
async def retry_image(
    image_id: uuid.UUID, user: CurrentUser, session: SessionDependency
) -> ImageAssetResponse:
    try:
        job, key = await prepare_ingestion_retry(
            session,
            user_id=user.id,
            target_type="image",
            target_id=image_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    await dispatch_outbox(key)
    image = await KnowledgeRepository(session).get_image(user.id, image_id)
    if image is None:
        raise HTTPException(status_code=404, detail="图片不存在")
    return _image_response(
        image,
        job,
        await TagRepository(session).image_tags(image.id),
    )


@router.post("/search", response_model=ImageSearchResponse)
async def search_images(
    request: ImageSearchRequest, user: CurrentUser, session: SessionDependency
) -> ImageSearchResponse:
    repository = KnowledgeRepository(session)
    knowledge_base_ids = list(dict.fromkeys(request.knowledge_base_ids))
    if not knowledge_base_ids:
        rows = await repository.list_knowledge_bases(user.id)
        knowledge_base_ids = [item.id for item, _, _ in rows]
    for knowledge_base_id in knowledge_base_ids:
        if await repository.get_knowledge_base(user.id, knowledge_base_id) is None:
            raise HTTPException(status_code=422, detail="所选知识库不存在或无权访问")
    hits = await search_image_assets(
        user_id=user.id,
        knowledge_base_ids=knowledge_base_ids,
        query=request.query.strip(),
        top_k=request.top_k,
    )
    return ImageSearchResponse(query=request.query, hits=hits)


@router.get("/{image_id}", response_model=ImageAssetResponse)
async def get_image(
    image_id: uuid.UUID, user: CurrentUser, session: SessionDependency
) -> ImageAssetResponse:
    repository = KnowledgeRepository(session)
    tag_repository = TagRepository(session)
    image = await repository.get_image(user.id, image_id)
    if image is None:
        raise HTTPException(status_code=404, detail="图片不存在")
    return _image_response(
        image,
        await repository.get_latest_image_job(user.id, image.id),
        await tag_repository.image_tags(image.id),
    )


@router.get("/{image_id}/content")
async def get_image_content(
    image_id: uuid.UUID, user: CurrentUser, session: SessionDependency
) -> Response:
    image = await KnowledgeRepository(session).get_image(user.id, image_id)
    if image is None:
        raise HTTPException(status_code=404, detail="图片不存在")
    try:
        content = await LocalDocumentStorage().read(image.file_key)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="图片文件不存在") from exc
    return Response(content=content, media_type=image.mime_type)


@router.delete("/{image_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_image(image_id: uuid.UUID, user: CurrentUser, session: SessionDependency) -> None:
    try:
        await ImageService(session).delete(user.id, image_id)
    except ImageNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
