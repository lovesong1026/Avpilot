"""Registration, login, token rotation, and current-user endpoints."""

from fastapi import APIRouter, HTTPException, status

from app.api.dependencies import CurrentUser, SessionDependency
from app.api.schemas.auth import (
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    TokenPairResponse,
    UserResponse,
)
from app.application.identity import AuthenticationError, IdentityConflictError, IdentityService
from app.infrastructure.database.models.identity import User

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenPairResponse, status_code=status.HTTP_201_CREATED)
async def register(request: RegisterRequest, session: SessionDependency) -> TokenPairResponse:
    try:
        return await IdentityService(session).register(request)
    except IdentityConflictError as exc:
        raise HTTPException(status_code=409, detail="Username or email already exists") from exc


@router.post("/login", response_model=TokenPairResponse)
async def login(request: LoginRequest, session: SessionDependency) -> TokenPairResponse:
    try:
        return await IdentityService(session).login(request)
    except AuthenticationError as exc:
        raise HTTPException(status_code=401, detail="Invalid credentials") from exc


@router.post("/refresh", response_model=TokenPairResponse)
async def refresh(request: RefreshRequest, session: SessionDependency) -> TokenPairResponse:
    try:
        return await IdentityService(session).refresh(request.refresh_token)
    except AuthenticationError as exc:
        raise HTTPException(status_code=401, detail="Invalid refresh token") from exc


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: LogoutRequest, session: SessionDependency) -> None:
    await IdentityService(session).logout(request.refresh_token)


@router.get("/me", response_model=UserResponse)
async def me(user: CurrentUser) -> User:
    return user
