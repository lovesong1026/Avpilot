"""Conversation CRUD and citation-grounded SSE chat routes."""

import uuid

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse

from app.api.dependencies import CurrentUser, SessionDependency
from app.api.schemas.chat import (
    ChatStreamRequest,
    ConversationCreate,
    ConversationResponse,
    ConversationUpdate,
    MessageResponse,
)
from app.application.chat import (
    ConversationNotFoundError,
    ConversationService,
    InvalidKnowledgeSelectionError,
    stream_chat_turn,
)
from app.infrastructure.database.models.conversation import Citation, Conversation, Message
from app.infrastructure.database.repositories.conversation import (
    ConversationRepository,
    MessageRepository,
)

router = APIRouter(tags=["chat"])


async def _conversation_response(
    repository: ConversationRepository, conversation: Conversation
) -> ConversationResponse:
    knowledge_base_ids = await repository.knowledge_base_ids(conversation.id)
    return ConversationResponse.model_validate(conversation).model_copy(
        update={"knowledge_base_ids": knowledge_base_ids}
    )


@router.get("/conversations", response_model=list[ConversationResponse])
async def list_conversations(
    user: CurrentUser, session: SessionDependency
) -> list[ConversationResponse]:
    repository = ConversationRepository(session)
    conversations = await repository.list_conversations(user.id)
    return [await _conversation_response(repository, item) for item in conversations]


@router.post(
    "/conversations",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_conversation(
    request: ConversationCreate, user: CurrentUser, session: SessionDependency
) -> ConversationResponse:
    try:
        conversation = await ConversationService(session).create(user.id, request)
        return await _conversation_response(ConversationRepository(session), conversation)
    except InvalidKnowledgeSelectionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.patch("/conversations/{conversation_id}", response_model=ConversationResponse)
async def update_conversation(
    conversation_id: uuid.UUID,
    request: ConversationUpdate,
    user: CurrentUser,
    session: SessionDependency,
) -> ConversationResponse:
    try:
        conversation = await ConversationService(session).update(
            user.id, conversation_id, request
        )
        return await _conversation_response(ConversationRepository(session), conversation)
    except ConversationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="对话不存在") from exc
    except InvalidKnowledgeSelectionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: uuid.UUID, user: CurrentUser, session: SessionDependency
) -> None:
    try:
        await ConversationService(session).delete(user.id, conversation_id)
    except ConversationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="对话不存在") from exc


@router.get("/conversations/{conversation_id}/messages", response_model=list[MessageResponse])
async def list_messages(
    conversation_id: uuid.UUID, user: CurrentUser, session: SessionDependency
) -> list[MessageResponse]:
    if await ConversationRepository(session).get(user.id, conversation_id) is None:
        raise HTTPException(status_code=404, detail="对话不存在")
    repository = MessageRepository(session)
    messages = await repository.list_messages(conversation_id)
    citations = await repository.citations_for_messages([item.id for item in messages])
    return [_message_response(item, citations.get(item.id, [])) for item in messages]


def _message_response(message: Message, citations: list[Citation]) -> MessageResponse:
    return MessageResponse.model_validate(message).model_copy(update={"citations": citations})


@router.post("/chat/stream")
async def stream_chat(request: ChatStreamRequest, user: CurrentUser) -> StreamingResponse:
    return StreamingResponse(
        stream_chat_turn(user.id, request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
