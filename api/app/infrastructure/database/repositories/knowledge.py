"""PostgreSQL repository for knowledge bases, documents, and ingestion jobs."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models.knowledge import (
    Document,
    ImageAsset,
    IngestionJob,
    KnowledgeBase,
)


class KnowledgeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_knowledge_bases(
        self, user_id: uuid.UUID
    ) -> list[tuple[KnowledgeBase, int, int]]:
        document_counts = (
            select(Document.knowledge_base_id, func.count(Document.id).label("document_count"))
            .group_by(Document.knowledge_base_id)
            .subquery()
        )
        image_counts = (
            select(ImageAsset.knowledge_base_id, func.count(ImageAsset.id).label("image_count"))
            .group_by(ImageAsset.knowledge_base_id)
            .subquery()
        )
        statement = (
            select(
                KnowledgeBase,
                func.coalesce(document_counts.c.document_count, 0),
                func.coalesce(image_counts.c.image_count, 0),
            )
            .outerjoin(
                document_counts,
                document_counts.c.knowledge_base_id == KnowledgeBase.id,
            )
            .outerjoin(image_counts, image_counts.c.knowledge_base_id == KnowledgeBase.id)
            .where(KnowledgeBase.user_id == user_id)
            .order_by(KnowledgeBase.is_default.desc(), KnowledgeBase.created_at.asc())
        )
        rows = await self.session.execute(statement)
        return [
            (knowledge_base, int(document_count), int(image_count))
            for knowledge_base, document_count, image_count in rows.all()
        ]

    async def get_knowledge_base(
        self, user_id: uuid.UUID, knowledge_base_id: uuid.UUID
    ) -> KnowledgeBase | None:
        statement = select(KnowledgeBase).where(
            KnowledgeBase.id == knowledge_base_id,
            KnowledgeBase.user_id == user_id,
        )
        return await self.session.scalar(statement)

    async def find_knowledge_base_by_name(
        self, user_id: uuid.UUID, name: str
    ) -> KnowledgeBase | None:
        statement = select(KnowledgeBase).where(
            KnowledgeBase.user_id == user_id,
            func.lower(KnowledgeBase.name) == name.strip().lower(),
        )
        return await self.session.scalar(statement)

    def add_knowledge_base(self, knowledge_base: KnowledgeBase) -> None:
        self.session.add(knowledge_base)

    async def list_documents(
        self, user_id: uuid.UUID, knowledge_base_id: uuid.UUID
    ) -> list[Document]:
        statement = (
            select(Document)
            .where(
                Document.user_id == user_id,
                Document.knowledge_base_id == knowledge_base_id,
            )
            .order_by(Document.created_at.desc())
        )
        return list(await self.session.scalars(statement))

    async def get_document(self, user_id: uuid.UUID, document_id: uuid.UUID) -> Document | None:
        statement = select(Document).where(
            Document.id == document_id,
            Document.user_id == user_id,
        )
        return await self.session.scalar(statement)

    async def find_document_by_hash(
        self, user_id: uuid.UUID, knowledge_base_id: uuid.UUID, content_hash: str
    ) -> Document | None:
        statement = select(Document).where(
            Document.user_id == user_id,
            Document.knowledge_base_id == knowledge_base_id,
            Document.content_hash == content_hash,
        )
        return await self.session.scalar(statement)

    async def find_document_by_url(
        self, user_id: uuid.UUID, knowledge_base_id: uuid.UUID, source_url: str
    ) -> Document | None:
        statement = select(Document).where(
            Document.user_id == user_id,
            Document.knowledge_base_id == knowledge_base_id,
            Document.source_url == source_url,
        )
        return await self.session.scalar(statement)

    def add_document(self, document: Document) -> None:
        self.session.add(document)

    def add_job(self, job: IngestionJob) -> None:
        self.session.add(job)

    async def get_latest_job(
        self, user_id: uuid.UUID, document_id: uuid.UUID
    ) -> IngestionJob | None:
        statement = (
            select(IngestionJob)
            .where(
                IngestionJob.user_id == user_id,
                IngestionJob.target_type == "document",
                IngestionJob.target_id == document_id,
            )
            .order_by(IngestionJob.created_at.desc())
            .limit(1)
        )
        return await self.session.scalar(statement)

    async def get_job(self, job_id: uuid.UUID) -> IngestionJob | None:
        return await self.session.get(IngestionJob, job_id)

    async def list_images(
        self, user_id: uuid.UUID, knowledge_base_id: uuid.UUID | None = None
    ) -> list[ImageAsset]:
        statement = select(ImageAsset).where(ImageAsset.user_id == user_id)
        if knowledge_base_id is not None:
            statement = statement.where(ImageAsset.knowledge_base_id == knowledge_base_id)
        statement = statement.order_by(ImageAsset.created_at.desc())
        return list(await self.session.scalars(statement))

    async def get_image(self, user_id: uuid.UUID, image_id: uuid.UUID) -> ImageAsset | None:
        statement = select(ImageAsset).where(
            ImageAsset.id == image_id,
            ImageAsset.user_id == user_id,
        )
        return await self.session.scalar(statement)

    async def find_image_by_hash(
        self, user_id: uuid.UUID, knowledge_base_id: uuid.UUID, content_hash: str
    ) -> ImageAsset | None:
        statement = select(ImageAsset).where(
            ImageAsset.user_id == user_id,
            ImageAsset.knowledge_base_id == knowledge_base_id,
            ImageAsset.content_hash == content_hash,
        )
        return await self.session.scalar(statement)

    def add_image(self, image: ImageAsset) -> None:
        self.session.add(image)

    async def get_latest_image_job(
        self, user_id: uuid.UUID, image_id: uuid.UUID
    ) -> IngestionJob | None:
        statement = (
            select(IngestionJob)
            .where(
                IngestionJob.user_id == user_id,
                IngestionJob.target_type == "image",
                IngestionJob.target_id == image_id,
            )
            .order_by(IngestionJob.created_at.desc())
            .limit(1)
        )
        return await self.session.scalar(statement)
