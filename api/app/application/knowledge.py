"""Knowledge-base lifecycle and asynchronous document ingestion."""

import hashlib
import logging
import uuid
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.knowledge import KnowledgeBaseCreate
from app.application.auto_tagging import assign_auto_tags
from app.application.chunking import chunk_text
from app.application.document_parser import (
    SUPPORTED_EXTENSIONS,
    DocumentParseError,
    parse_document,
)
from app.application.task_queue import (
    DOCUMENT_TASK,
    WEB_DOCUMENT_TASK,
    enqueue_task,
    task_dedupe_key,
)
from app.application.web_crawler import fetch_web_page
from app.infrastructure.database.models.knowledge import Document, IngestionJob, KnowledgeBase
from app.infrastructure.database.postgres import get_session_factory
from app.infrastructure.database.repositories.knowledge import KnowledgeRepository
from app.infrastructure.llm.bailian import BailianGateway
from app.infrastructure.search.chunk_store import (
    build_index_actions,
    bulk_index,
    delete_document_chunks,
    delete_source_chunks,
)
from app.infrastructure.storage.local import LocalDocumentStorage
from app.shared.config import get_settings

logger = logging.getLogger(__name__)


class KnowledgeNotFoundError(Exception):
    """A user-scoped knowledge base or document was not found."""


class KnowledgeConflictError(Exception):
    """A knowledge base name or document content already exists."""


class InvalidUploadError(Exception):
    """An uploaded file violates the ingestion contract."""


class DefaultKnowledgeBaseError(Exception):
    """The automatically provisioned default knowledge base cannot be deleted."""


class KnowledgeService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = KnowledgeRepository(session)
        self.storage = LocalDocumentStorage()

    async def create_knowledge_base(
        self, user_id: uuid.UUID, request: KnowledgeBaseCreate
    ) -> KnowledgeBase:
        name = request.name.strip()
        if await self.repository.find_knowledge_base_by_name(user_id, name):
            raise KnowledgeConflictError("知识库名称已存在")
        knowledge_base = KnowledgeBase(
            user_id=user_id,
            name=name,
            description=request.description.strip() if request.description else None,
            is_default=False,
            chat_enabled=True,
        )
        self.repository.add_knowledge_base(knowledge_base)
        await self.session.commit()
        await self.session.refresh(knowledge_base)
        return knowledge_base

    async def delete_knowledge_base(self, user_id: uuid.UUID, knowledge_base_id: uuid.UUID) -> None:
        knowledge_base = await self.repository.get_knowledge_base(user_id, knowledge_base_id)
        if knowledge_base is None:
            raise KnowledgeNotFoundError
        if knowledge_base.is_default:
            raise DefaultKnowledgeBaseError("默认知识库不能删除")
        documents = await self.repository.list_documents(user_id, knowledge_base_id)
        images = await self.repository.list_images(user_id, knowledge_base_id)
        await self.session.delete(knowledge_base)
        await self.session.commit()
        for document in documents:
            await delete_document_chunks(user_id, document.id)
            if document.file_key:
                await self.storage.delete(document.file_key)
        for image in images:
            await delete_source_chunks(user_id, image.id, source_type="image")
            await self.storage.delete(image.file_key)

    async def upload_document(
        self,
        *,
        user_id: uuid.UUID,
        knowledge_base_id: uuid.UUID,
        upload: UploadFile,
    ) -> tuple[Document, IngestionJob]:
        knowledge_base = await self.repository.get_knowledge_base(user_id, knowledge_base_id)
        if knowledge_base is None:
            raise KnowledgeNotFoundError
        file_name = Path(upload.filename or "").name
        extension = Path(file_name).suffix.lower()
        if not file_name or extension not in SUPPORTED_EXTENSIONS:
            supported = "、".join(sorted(SUPPORTED_EXTENSIONS))
            raise InvalidUploadError(f"仅支持 {supported} 文件")
        max_bytes = get_settings().max_upload_size_mb * 1024 * 1024
        content = await upload.read(max_bytes + 1)
        if not content:
            raise InvalidUploadError("文件内容为空")
        if len(content) > max_bytes:
            raise InvalidUploadError(f"文件不能超过 {get_settings().max_upload_size_mb} MB")
        content_hash = hashlib.sha256(content).hexdigest()
        if await self.repository.find_document_by_hash(user_id, knowledge_base_id, content_hash):
            raise KnowledgeConflictError("这个文件已经在当前知识库中")

        document = Document(
            user_id=user_id,
            knowledge_base_id=knowledge_base_id,
            title=Path(file_name).stem,
            source_type="file",
            file_name=file_name,
            mime_type=upload.content_type or "application/octet-stream",
            file_size=len(content),
            content_hash=content_hash,
            status="pending",
            chunk_count=0,
        )
        self.repository.add_document(document)
        await self.session.flush()
        document.file_key = self.storage.build_key(user_id, document.id, extension)
        job = IngestionJob(
            user_id=user_id,
            target_type="document",
            target_id=document.id,
            status="pending",
            stage="queued",
            progress=0.0,
            attempts=0,
        )
        self.repository.add_job(job)
        await self.session.flush()
        enqueue_task(
            self.session,
            task_name=DOCUMENT_TASK,
            queue="ingestion",
            dedupe_key=task_dedupe_key("document", job.id),
            payload={"document_id": str(document.id), "job_id": str(job.id)},
        )
        try:
            await self.storage.save(document.file_key, content)
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            await self.storage.delete(document.file_key)
            raise
        await self.session.refresh(document)
        await self.session.refresh(job)
        return document, job

    async def delete_document(self, user_id: uuid.UUID, document_id: uuid.UUID) -> None:
        document = await self.repository.get_document(user_id, document_id)
        if document is None:
            raise KnowledgeNotFoundError
        file_key = document.file_key
        await self.session.delete(document)
        await self.session.commit()
        await delete_document_chunks(user_id, document_id)
        if file_key:
            await self.storage.delete(file_key)

    async def create_web_document(
        self, *, user_id: uuid.UUID, knowledge_base_id: uuid.UUID, url: str
    ) -> tuple[Document, IngestionJob]:
        if await self.repository.get_knowledge_base(user_id, knowledge_base_id) is None:
            raise KnowledgeNotFoundError
        normalized_url = url.strip()
        if await self.repository.find_document_by_url(user_id, knowledge_base_id, normalized_url):
            raise KnowledgeConflictError("这个网页已经在当前知识库中")
        document = Document(
            user_id=user_id,
            knowledge_base_id=knowledge_base_id,
            title=normalized_url[:512],
            source_type="web",
            source_url=normalized_url,
            file_name=None,
            mime_type="text/html",
            file_size=0,
            status="pending",
            chunk_count=0,
        )
        self.repository.add_document(document)
        await self.session.flush()
        job = IngestionJob(
            user_id=user_id,
            target_type="document",
            target_id=document.id,
            status="pending",
            stage="queued",
            progress=0.0,
            attempts=0,
        )
        self.repository.add_job(job)
        await self.session.flush()
        enqueue_task(
            self.session,
            task_name=WEB_DOCUMENT_TASK,
            queue="ingestion",
            dedupe_key=task_dedupe_key("document", job.id),
            payload={"document_id": str(document.id), "job_id": str(job.id)},
        )
        await self.session.commit()
        await self.session.refresh(document)
        await self.session.refresh(job)
        return document, job


async def process_document(
    document_id: uuid.UUID,
    job_id: uuid.UUID,
    *,
    increment_attempt: bool = True,
    raise_on_failure: bool = False,
) -> None:
    """Process one persisted upload in a fresh session after the response is returned."""
    async with get_session_factory()() as session:
        document = await session.get(Document, document_id)
        job = await session.get(IngestionJob, job_id)
        if document is None or job is None or not document.file_key:
            return
        gateway: BailianGateway | None = None
        try:
            job.status = "processing"
            job.stage = "parsing"
            job.progress = 0.1
            if increment_attempt:
                job.attempts += 1
            document.status = "processing"
            await session.commit()

            content = await LocalDocumentStorage().read(document.file_key)
            parse_name = (
                "web.txt" if document.source_type == "web" else document.file_name or document.title
            )
            parsed = parse_document(parse_name, content)
            job.stage = "chunking"
            job.progress = 0.35
            await session.commit()

            parents = chunk_text(parsed.text)
            child_texts = [child.text for parent in parents for child in parent.children]
            if not child_texts:
                raise DocumentParseError("文档无法生成有效片段")
            job.stage = "embedding"
            job.progress = 0.55
            await session.commit()

            gateway = BailianGateway()
            vectors = await gateway.embed(child_texts)
            job.stage = "indexing"
            job.progress = 0.82
            await session.commit()

            tags = await assign_auto_tags(
                session=session,
                gateway=gateway,
                user_id=document.user_id,
                target_type="document",
                target_id=document.id,
                content=parsed.text,
            )

            await delete_document_chunks(document.user_id, document.id)
            actions = build_index_actions(
                user_id=document.user_id,
                knowledge_base_id=document.knowledge_base_id,
                document_id=document.id,
                title=document.title,
                file_name=(
                    document.source_url if document.source_type == "web" else document.file_name
                ),
                parsed=parsed,
                parents=parents,
                child_vectors=vectors,
                tags=[tag.name for tag in tags],
            )
            await bulk_index(actions)
            document.status = "ready"
            document.chunk_count = len(child_texts)
            document.error_code = None
            document.error_message = None
            job.status = "completed"
            job.stage = "completed"
            job.progress = 1.0
            job.error_code = None
            job.error_message = None
            await session.commit()
        except Exception as exc:
            logger.exception("Document ingestion failed: %s", document_id)
            await session.rollback()
            document = await session.get(Document, document_id)
            job = await session.get(IngestionJob, job_id)
            error_message = str(exc)[:2000] or "文档处理失败"
            if document is not None:
                document.status = "failed"
                document.error_code = type(exc).__name__
                document.error_message = error_message
            if job is not None:
                job.status = "failed"
                job.stage = "failed"
                job.error_code = type(exc).__name__
                job.error_message = error_message
            await session.commit()
            if raise_on_failure:
                raise
        finally:
            if gateway is not None:
                await gateway.close()


async def process_web_document(
    document_id: uuid.UUID,
    job_id: uuid.UUID,
    *,
    raise_on_failure: bool = False,
) -> None:
    """Fetch a public page safely, persist its text snapshot, then run document ingestion."""
    async with get_session_factory()() as session:
        document = await session.get(Document, document_id)
        job = await session.get(IngestionJob, job_id)
        if document is None or job is None or not document.source_url:
            return
        try:
            job.status = "processing"
            job.stage = "fetching"
            job.progress = 0.05
            job.attempts += 1
            document.status = "processing"
            await session.commit()
            title, text, final_url = await fetch_web_page(document.source_url)
            content = text.encode("utf-8")
            document.title = title
            document.source_url = final_url
            document.file_size = len(content)
            document.content_hash = hashlib.sha256(content).hexdigest()
            document.file_key = LocalDocumentStorage().build_key(
                document.user_id, document.id, ".txt"
            )
            await LocalDocumentStorage().save(document.file_key, content)
            await session.commit()
        except Exception as exc:
            logger.exception("Web ingestion failed: %s", document_id)
            await session.rollback()
            document = await session.get(Document, document_id)
            job = await session.get(IngestionJob, job_id)
            error_message = str(exc)[:2000] or "网页抓取失败"
            if document is not None:
                document.status = "failed"
                document.error_code = type(exc).__name__
                document.error_message = error_message
            if job is not None:
                job.status = "failed"
                job.stage = "failed"
                job.error_code = type(exc).__name__
                job.error_message = error_message
            await session.commit()
            if raise_on_failure:
                raise
            return
    await process_document(
        document_id,
        job_id,
        increment_attempt=False,
        raise_on_failure=raise_on_failure,
    )
