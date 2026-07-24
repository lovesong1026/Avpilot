"""Image upload, multimodal analysis, indexing, and lifecycle operations."""

import asyncio
import hashlib
import logging
import uuid
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.auto_tagging import assign_auto_tags
from app.application.image_processing import (
    IMAGE_MIME_BY_EXTENSION,
    SUPPORTED_IMAGE_EXTENSIONS,
    InvalidImageError,
    build_searchable_image_text,
    normalize_vision_result,
    prepare_image_for_vision,
)
from app.application.task_queue import IMAGE_TASK, enqueue_task, task_dedupe_key
from app.infrastructure.database.models.knowledge import ImageAsset, IngestionJob
from app.infrastructure.database.postgres import get_session_factory
from app.infrastructure.database.repositories.knowledge import KnowledgeRepository
from app.infrastructure.llm.bailian import BailianGateway
from app.infrastructure.search.chunk_store import (
    build_image_action,
    bulk_index,
    delete_source_chunks,
)
from app.infrastructure.storage.local import LocalDocumentStorage
from app.shared.config import get_settings

logger = logging.getLogger(__name__)


class ImageNotFoundError(Exception):
    """The requested user-scoped image does not exist."""


class ImageConflictError(Exception):
    """The same image already exists in the selected knowledge base."""


class InvalidImageUploadError(Exception):
    """The image upload violates size, format, or integrity requirements."""


class ImageService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = KnowledgeRepository(session)
        self.storage = LocalDocumentStorage()

    async def upload(
        self,
        *,
        user_id: uuid.UUID,
        knowledge_base_id: uuid.UUID,
        upload: UploadFile,
    ) -> tuple[ImageAsset, IngestionJob]:
        if await self.repository.get_knowledge_base(user_id, knowledge_base_id) is None:
            raise ImageNotFoundError("知识库不存在")
        file_name = Path(upload.filename or "").name
        extension = Path(file_name).suffix.lower()
        if not file_name or extension not in SUPPORTED_IMAGE_EXTENSIONS:
            supported = "、".join(sorted(SUPPORTED_IMAGE_EXTENSIONS))
            raise InvalidImageUploadError(f"仅支持 {supported} 图片")
        max_bytes = min(get_settings().max_upload_size_mb, 20) * 1024 * 1024
        content = await upload.read(max_bytes + 1)
        if not content:
            raise InvalidImageUploadError("图片内容为空")
        if len(content) > max_bytes:
            raise InvalidImageUploadError(f"图片不能超过 {max_bytes // 1024 // 1024} MB")
        try:
            await asyncio.to_thread(prepare_image_for_vision, content)
        except InvalidImageError as exc:
            raise InvalidImageUploadError(str(exc)) from exc
        content_hash = hashlib.sha256(content).hexdigest()
        if await self.repository.find_image_by_hash(
            user_id, knowledge_base_id, content_hash
        ):
            raise ImageConflictError("这张图片已经在当前知识库中")

        image = ImageAsset(
            user_id=user_id,
            knowledge_base_id=knowledge_base_id,
            file_name=file_name,
            file_key="",
            mime_type=IMAGE_MIME_BY_EXTENSION[extension],
            file_size=len(content),
            content_hash=content_hash,
            status="pending",
        )
        self.repository.add_image(image)
        await self.session.flush()
        image.file_key = self.storage.build_image_key(user_id, image.id, extension)
        job = IngestionJob(
            user_id=user_id,
            target_type="image",
            target_id=image.id,
            status="pending",
            stage="queued",
            progress=0.0,
            attempts=0,
        )
        self.repository.add_job(job)
        await self.session.flush()
        enqueue_task(
            self.session,
            task_name=IMAGE_TASK,
            queue="ingestion",
            dedupe_key=task_dedupe_key("image", job.id),
            payload={"image_id": str(image.id), "job_id": str(job.id)},
        )
        try:
            await self.storage.save(image.file_key, content)
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            await self.storage.delete(image.file_key)
            raise
        await self.session.refresh(image)
        await self.session.refresh(job)
        return image, job

    async def delete(self, user_id: uuid.UUID, image_id: uuid.UUID) -> None:
        image = await self.repository.get_image(user_id, image_id)
        if image is None:
            raise ImageNotFoundError("图片不存在")
        file_key = image.file_key
        await self.session.delete(image)
        await self.session.commit()
        await delete_source_chunks(user_id, image_id, source_type="image")
        await self.storage.delete(file_key)


async def process_image(
    image_id: uuid.UUID,
    job_id: uuid.UUID,
    *,
    raise_on_failure: bool = False,
) -> None:
    """Analyze and index one persisted image in a fresh database session."""
    async with get_session_factory()() as session:
        image = await session.get(ImageAsset, image_id)
        job = await session.get(IngestionJob, job_id)
        if image is None or job is None:
            return
        gateway: BailianGateway | None = None
        try:
            image.status = "processing"
            job.status = "processing"
            job.stage = "vision"
            job.progress = 0.15
            job.attempts += 1
            await session.commit()

            content = await LocalDocumentStorage().read(image.file_key)
            image_url = await asyncio.to_thread(prepare_image_for_vision, content)
            gateway = BailianGateway()
            info = normalize_vision_result(await gateway.describe_image(image_url))
            searchable = build_searchable_image_text(info)
            if not searchable:
                raise RuntimeError("视觉模型没有返回可检索内容")
            image.description = info["description"]
            image.ocr_text = info["ocr_text"]
            image.objects = info["objects"]
            image.scene = info["scene"]
            job.stage = "embedding"
            job.progress = 0.62
            await session.commit()

            vector = (await gateway.embed([searchable]))[0]
            job.stage = "indexing"
            job.progress = 0.84
            await session.commit()
            tags = await assign_auto_tags(
                session=session,
                gateway=gateway,
                user_id=image.user_id,
                target_type="image",
                target_id=image.id,
                content=searchable,
            )
            await delete_source_chunks(image.user_id, image.id, source_type="image")
            await bulk_index(
                [
                    build_image_action(
                        user_id=image.user_id,
                        knowledge_base_id=image.knowledge_base_id,
                        image_id=image.id,
                        file_name=image.file_name,
                        content=searchable,
                        vector=vector,
                        tags=[tag.name for tag in tags],
                    )
                ]
            )
            image.status = "ready"
            image.error_code = None
            image.error_message = None
            job.status = "completed"
            job.stage = "completed"
            job.progress = 1.0
            job.error_code = None
            job.error_message = None
            await session.commit()
        except Exception as exc:
            logger.exception("Image ingestion failed: %s", image_id)
            await session.rollback()
            image = await session.get(ImageAsset, image_id)
            job = await session.get(IngestionJob, job_id)
            error_message = str(exc)[:2000] or "图片处理失败"
            if image is not None:
                image.status = "failed"
                image.error_code = type(exc).__name__
                image.error_message = error_message
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
