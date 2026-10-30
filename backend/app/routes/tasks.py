"""Task routes – list, update, generate via AI."""
import json
from datetime import date

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.models.models import User
from app.services.ai_fallbacks import fallback_task_list
from app.services.ai_generation import (
    AI_SOURCE_RESPONSES,
    generate_with_fallback,
    mark_source,
)
from app.services.auth_service import get_current_user
from app.services.event_service import (
    bulk_create_tasks,
    compute_task_readiness,
    create_task,
    get_event,
    get_tasks,
    update_task,
)
from app.services.prompts import TASK_GENERATION_SYSTEM, TASK_GENERATION_USER
from app.validators.schemas import (
    AITaskList,
    TaskCreate,
    TaskListResponse,
    TaskReadinessResponse,
    TaskResponse,
    TaskUpdate,
)

router = APIRouter(prefix="/api/events/{event_id}/tasks", tags=["tasks"])


def _task_list_payload(readiness: list[dict]) -> TaskListResponse:
    """Attach readiness state to each task in a single typed envelope."""
    return TaskListResponse(
        tasks=[
            TaskReadinessResponse(
                **TaskResponse.model_validate(item["task"]).model_dump(),
                is_ready=item["is_ready"],
                blocked_by=item["blocked_by"],
            )
            for item in readiness
        ]
    )


@router.get("", response_model=TaskListResponse)
async def get_task_list(
    event_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TaskListResponse:
    tasks = get_tasks(event_id, current_user.id, db)
    return _task_list_payload(compute_task_readiness(tasks))


@router.post("", status_code=201, response_model=TaskResponse)
async def create_single_task(
    event_id: str,
    body: TaskCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TaskResponse:
    task = create_task(event_id, current_user.id, body, db)
    db.commit()
    db.refresh(task)
    return task


@router.patch("/{task_id}", response_model=TaskResponse)
async def update_task_status(
    event_id: str,
    task_id: str,
    body: TaskUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TaskResponse:
    task = update_task(event_id, task_id, current_user.id, body, db)
    db.commit()
    db.refresh(task)
    return task


@router.post(
    "/generate",
    response_model=TaskListResponse,
    responses=AI_SOURCE_RESPONSES,
)
async def generate_tasks(
    event_id: str,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TaskListResponse:
    """Generate a prioritized task list from the event profile via AI."""
    event = get_event(event_id, current_user.id, db)

    event_date = event.event_date or (
        date.today().replace(year=date.today().year + 1).isoformat()
    )

    user_prompt = TASK_GENERATION_USER.format(
        profile_json=json.dumps(event.profile, indent=2),
        event_date=event_date,
        today=date.today().isoformat(),
    )

    validated, used_ai = await generate_with_fallback(
        TASK_GENERATION_SYSTEM,
        user_prompt,
        AITaskList,
        lambda: fallback_task_list(event),
        use_cache=True,
        label="Task generation",
    )
    mark_source(response, used_ai)

    tasks = bulk_create_tasks(
        event_id,
        current_user.id,
        [task.model_dump() for task in validated.tasks],
        db,
    )
    db.commit()
    return _task_list_payload(compute_task_readiness(tasks))
