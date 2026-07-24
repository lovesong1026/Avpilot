"""Knowledge-base CRUD, document upload/status, and hybrid-search endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from app.api.dependencies import CurrentUser, SessionDependency
from app.api.schemas.knowledge import (
    DocumentResponse,
    IngestionJobResponse,
    KnowledgeBaseCreate,
    KnowledgeBaseResponse,
    SearchRequest,
    SearchResponse,
    WebDocumentCreate,
)
from app.application.knowledge import (
    DefaultKnowledgeBaseError,
    InvalidUploadError,
    KnowledgeConflictError,
    KnowledgeNotFoundError,
    KnowledgeService,
)
from app.application.knowledge_search import search_knowledge_base
from app.application.task_queue import (
    dispatch_outbox,
    prepare_ingestion_retry,
    task_dedupe_key,
)
from app.infrastructure.database.models.knowledge import Document, IngestionJob, KnowledgeBase
from app.infrastructure.database.repositories.knowledge import KnowledgeRepository
from app.infrastructure.database.repositories.tags import TagRepository

router = APIRouter(prefix="/knowledge-bases", tags=["knowledge"])


def _knowledge_response(
    item: KnowledgeBase, document_count: int = 0, image_count: int = 0
) -> KnowledgeBaseResponse:
    return KnowledgeBaseResponse.model_validate(item).model_copy(
        update={"document_count": document_count, "image_count": image_count}
    )


def _document_response(
    document: Document, job: IngestionJob | None = None, tags: list[object] | None = None
) -> DocumentResponse:
    job_response = IngestionJobResponse.model_validate(job) if job else None
    return DocumentResponse.model_validate(document).model_copy(
        update={"ingestion_job": job_response, "tags": tags or []}
    )


@router.get("", response_model=list[KnowledgeBaseResponse])
async def list_knowledge_bases(
    user: CurrentUser, session: SessionDependency
) -> list[KnowledgeBaseResponse]:
    rows = await KnowledgeRepository(session).list_knowledge_bases(user.id)
    return [
        _knowledge_response(item, document_count, image_count)
        for item, document_count, image_count in rows
    ]


@router.post("", response_model=KnowledgeBaseResponse, status_code=status.HTTP_201_CREATED)
async def create_knowledge_base(
    request: KnowledgeBaseCreate, user: CurrentUser, session: SessionDependency
) -> KnowledgeBaseResponse:
    try:
        item = await KnowledgeService(session).create_knowledge_base(user.id, request)
        return _knowledge_response(item)
    except KnowledgeConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.delete("/{knowledge_base_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_knowledge_base(
    knowledge_base_id: uuid.UUID, user: CurrentUser, session: SessionDependency
) -> None:
    try:
        await KnowledgeService(session).delete_knowledge_base(user.id, knowledge_base_id)
    except KnowledgeNotFoundError as exc:
        raise HTTPException(status_code=404, detail="知识库不存在") from exc
    except DefaultKnowledgeBaseError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/{knowledge_base_id}/documents", response_model=list[DocumentResponse])
async def list_documents(
    knowledge_base_id: uuid.UUID, user: CurrentUser, session: SessionDependency
) -> list[DocumentResponse]:
    repository = KnowledgeRepository(session)
    if await repository.get_knowledge_base(user.id, knowledge_base_id) is None:
        raise HTTPException(status_code=404, detail="知识库不存在")
    documents = await repository.list_documents(user.id, knowledge_base_id)
    tag_repository = TagRepository(session)
    return [
        _document_response(
            document,
            await repository.get_latest_job(user.id, document.id),
            await tag_repository.document_tags(document.id),
        )
        for document in documents
    ]


@router.post(
    "/{knowledge_base_id}/documents",
    response_model=DocumentResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_document(
    knowledge_base_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDependency,
    file: Annotated[UploadFile, File()],
) -> DocumentResponse:
    try:
        document, job = await KnowledgeService(session).upload_document(
            user_id=user.id,
            knowledge_base_id=knowledge_base_id,
            upload=file,
        )
    except KnowledgeNotFoundError as exc:
        raise HTTPException(status_code=404, detail="知识库不存在") from exc
    except InvalidUploadError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except KnowledgeConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    await dispatch_outbox(task_dedupe_key("document", job.id))
    return _document_response(document, job)


@router.post(
    "/{knowledge_base_id}/web-pages",
    response_model=DocumentResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def add_web_page(
    knowledge_base_id: uuid.UUID,
    request: WebDocumentCreate,
    user: CurrentUser,
    session: SessionDependency,
) -> DocumentResponse:
    try:
        document, job = await KnowledgeService(session).create_web_document(
            user_id=user.id,
            knowledge_base_id=knowledge_base_id,
            url=str(request.url),
        )
    except KnowledgeNotFoundError as exc:
        raise HTTPException(status_code=404, detail="知识库不存在") from exc
    except KnowledgeConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    await dispatch_outbox(task_dedupe_key("document", job.id))
    return _document_response(document, job)


@router.post("/documents/{document_id}/retry", response_model=DocumentResponse)
async def retry_document(
    document_id: uuid.UUID, user: CurrentUser, session: SessionDependency
) -> DocumentResponse:
    try:
        job, key = await prepare_ingestion_retry(
            session,
            user_id=user.id,
            target_type="document",
            target_id=document_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    await dispatch_outbox(key)
    document = await KnowledgeRepository(session).get_document(user.id, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="文档不存在")
    return _document_response(
        document,
        job,
        await TagRepository(session).document_tags(document.id),
    )


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: uuid.UUID, user: CurrentUser, session: SessionDependency
) -> None:
    try:
        await KnowledgeService(session).delete_document(user.id, document_id)
    except KnowledgeNotFoundError as exc:
        raise HTTPException(status_code=404, detail="文档不存在") from exc


@router.post("/{knowledge_base_id}/search", response_model=SearchResponse)
async def search(
    knowledge_base_id: uuid.UUID,
    request: SearchRequest,
    user: CurrentUser,
    session: SessionDependency,
) -> SearchResponse:
    if await KnowledgeRepository(session).get_knowledge_base(user.id, knowledge_base_id) is None:
        raise HTTPException(status_code=404, detail="知识库不存在")
    hits = await search_knowledge_base(
        user_id=user.id,
        knowledge_base_id=knowledge_base_id,
        query=request.query.strip(),
        top_k=request.top_k,
        use_rerank=request.use_rerank,
    )
    return SearchResponse(query=request.query, hits=hits)
