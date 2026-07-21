"""PostgreSQL repository for knowledge bases, documents, and ingestion jobs."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models.knowledge import Document, IngestionJob, KnowledgeBase


class KnowledgeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_knowledge_bases(self, user_id: uuid.UUID) -> list[tuple[KnowledgeBase, int]]:
        statement = (
            select(KnowledgeBase, func.count(Document.id))
            .outerjoin(Document, Document.knowledge_base_id == KnowledgeBase.id)
            .where(KnowledgeBase.user_id == user_id)
            .group_by(KnowledgeBase.id)
            .order_by(KnowledgeBase.is_default.desc(), KnowledgeBase.created_at.asc())
        )
        rows = await self.session.execute(statement)
        return [(knowledge_base, int(count)) for knowledge_base, count in rows.all()]

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
