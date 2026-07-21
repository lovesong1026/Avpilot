"""Identity application service."""

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.auth import LoginRequest, RegisterRequest, TokenPairResponse
from app.infrastructure.database.models.identity import RefreshToken, User
from app.infrastructure.database.models.knowledge import KnowledgeBase
from app.infrastructure.database.repositories.identity import IdentityRepository
from app.shared.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)


class AuthenticationError(Exception):
    """Credentials or refresh token are invalid."""


class IdentityConflictError(Exception):
    """Username or email already exists."""


class IdentityService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = IdentityRepository(session)

    async def register(self, request: RegisterRequest) -> TokenPairResponse:
        if await self.repository.username_or_email_exists(request.username, str(request.email)):
            raise IdentityConflictError

        user = User(
            username=request.username.strip(),
            email=str(request.email).lower(),
            password_hash=hash_password(request.password),
            display_name=request.display_name,
        )
        self.repository.add_user(user)
        await self.session.flush()
        self.session.add(
            KnowledgeBase(
                user_id=user.id,
                name="默认知识库",
                description="自动创建的默认知识库",
                is_default=True,
                chat_enabled=True,
            )
        )
        response = self._issue_token_pair(user)
        await self.session.commit()
        return response

    async def login(self, request: LoginRequest) -> TokenPairResponse:
        user = await self.repository.get_user_by_identifier(request.identifier)
        if (
            user is None
            or not user.is_active
            or not verify_password(request.password, user.password_hash)
        ):
            raise AuthenticationError
        response = self._issue_token_pair(user)
        await self.session.commit()
        return response

    async def refresh(self, raw_token: str) -> TokenPairResponse:
        token = await self.repository.get_refresh_token_for_update(hash_refresh_token(raw_token))
        now = datetime.now(UTC)
        if token is None or token.revoked_at is not None or token.expires_at <= now:
            raise AuthenticationError
        user = await self.repository.get_user_by_id(token.user_id)
        if user is None or not user.is_active:
            raise AuthenticationError
        token.revoked_at = now
        response = self._issue_token_pair(user)
        await self.session.commit()
        return response

    async def logout(self, raw_token: str) -> None:
        token = await self.repository.get_refresh_token_for_update(hash_refresh_token(raw_token))
        if token is not None and token.revoked_at is None:
            token.revoked_at = datetime.now(UTC)
            await self.session.commit()

    def _issue_token_pair(self, user: User) -> TokenPairResponse:
        access_token, access_expires_at = create_access_token(user.id)
        raw_refresh, refresh_hash, refresh_expires_at = create_refresh_token()
        self.repository.add_refresh_token(
            RefreshToken(
                user_id=user.id,
                token_hash=refresh_hash,
                expires_at=refresh_expires_at,
            )
        )
        return TokenPairResponse(
            access_token=access_token,
            refresh_token=raw_refresh,
            access_token_expires_at=access_expires_at,
            user=user,
        )
