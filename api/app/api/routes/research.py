"""Deep-research lifecycle, progress, evidence, and report routes."""

import uuid

from fastapi import APIRouter, HTTPException, Query, Response, status

from app.api.dependencies import CurrentUser, SessionDependency
from app.api.schemas.research import (
    ResearchCreate,
    ResearchEvidenceResponse,
    ResearchStepResponse,
    ResearchTaskDetail,
    ResearchTaskResponse,
)
from app.application.research import (
    create_research_task,
    delete_research_task,
    get_research_task,
    list_research_tasks,
    retry_research_task,
)
from app.application.task_queue import dispatch_outbox

router = APIRouter(prefix="/research", tags=["research"])


@router.post("", response_model=ResearchTaskResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_research(
    request: ResearchCreate,
    user: CurrentUser,
    session: SessionDependency,
) -> ResearchTaskResponse:
    try:
        task, key = await create_research_task(
            session,
            user_id=user.id,
            question=request.question,
            title=request.title,
            knowledge_base_ids=request.knowledge_base_ids,
            use_memory=request.use_memory,
            allow_web=request.allow_web,
            max_iterations=request.max_iterations,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    await dispatch_outbox(key)
    return ResearchTaskResponse.model_validate(task)


@router.get("", response_model=list[ResearchTaskResponse])
async def list_research(
    user: CurrentUser,
    session: SessionDependency,
    limit: int = Query(default=50, ge=1, le=200),
) -> list[ResearchTaskResponse]:
    tasks = await list_research_tasks(session, user.id, limit)
    return [ResearchTaskResponse.model_validate(item) for item in tasks]


@router.get("/{task_id}", response_model=ResearchTaskDetail)
async def research_detail(
    task_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDependency,
) -> ResearchTaskDetail:
    result = await get_research_task(session, user.id, task_id)
    if result is None:
        raise HTTPException(status_code=404, detail="研究任务不存在")
    task, steps, evidence = result
    return ResearchTaskDetail.model_validate(task).model_copy(
        update={
            "steps": [ResearchStepResponse.model_validate(item) for item in steps],
            "evidence": [ResearchEvidenceResponse.model_validate(item) for item in evidence],
        }
    )


@router.post("/{task_id}/retry", response_model=ResearchTaskResponse)
async def retry_research(
    task_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDependency,
) -> ResearchTaskResponse:
    try:
        task, key = await retry_research_task(session, user.id, task_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    await dispatch_outbox(key)
    return ResearchTaskResponse.model_validate(task)


@router.get("/{task_id}/export")
async def export_research(
    task_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDependency,
) -> Response:
    result = await get_research_task(session, user.id, task_id)
    if result is None:
        raise HTTPException(status_code=404, detail="研究任务不存在")
    task, _, _ = result
    if task.status != "completed" or not task.report_markdown:
        raise HTTPException(status_code=409, detail="研究报告尚未完成")
    return Response(
        content=task.report_markdown,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="research-{task.id}.md"'},
    )


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_research(
    task_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDependency,
) -> None:
    try:
        deleted = await delete_research_task(session, user.id, task_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="研究任务不存在")
