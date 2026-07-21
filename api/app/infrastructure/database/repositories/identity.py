"""Identity repository backed by PostgreSQL."""

import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models.identity import RefreshToken, User


class IdentityRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_user_by_id(self, user_id: uuid.UUID) -> User | None:
        return await self.session.get(User, user_id)

    async def get_user_by_identifier(self, identifier: str) -> User | None:
        normalized = identifier.strip().lower()
        statement = select(User).where(
            or_(func.lower(User.username) == normalized, func.lower(User.email) == normalized)
        )
        return await self.session.scalar(statement)

    async def username_or_email_exists(self, username: str, email: str) -> bool:
        statement = select(User.id).where(
            or_(
                func.lower(User.username) == username.lower(),
                func.lower(User.email) == email.lower(),
            )
        )
        return await self.session.scalar(statement) is not None

    def add_user(self, user: User) -> None:
        self.session.add(user)

    async def get_refresh_token_for_update(self, token_hash: str) -> RefreshToken | None:
        statement = (
            select(RefreshToken).where(RefreshToken.token_hash == token_hash).with_for_update()
        )
        return await self.session.scalar(statement)

    def add_refresh_token(self, token: RefreshToken) -> None:
        self.session.add(token)
