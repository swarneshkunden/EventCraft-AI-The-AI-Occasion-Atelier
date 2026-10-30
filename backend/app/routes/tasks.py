"""Task routes – list, update, generate via AI."""
import json
from datetime import date

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.models.models import User
from app.services.ai_fallbacks import fallback_task_list
from app.services.ai_generation import generate_with_fallback, mark_source
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
from app.validators.schemas import AITaskList, TaskCreate, TaskResponse, TaskUpdate

router = APIRouter(prefix="/api/events/{event_id}/tasks", tags=["tasks"])


@router.get("")
async def get_task_list(
    event_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    tasks = get_tasks(event_id, current_user.id, db)
    readiness = compute_task_readiness(tasks)
    return {
        "tasks": [
            {
                **TaskResponse.model_validate(item["task"]).model_dump(),
                "is_ready": item["is_ready"],
                "blocked_by": item["blocked_by"],
            }
            for item in readiness
        ]
    }


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


@router.post("/generate")
async def generate_tasks(
    event_id: str,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
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

    readiness = compute_task_readiness(tasks)
    return {
        "tasks": [
            {
                **TaskResponse.model_validate(item["task"]).model_dump(),
                "is_ready": item["is_ready"],
                "blocked_by": item["blocked_by"],
            }
            for item in readiness
        ]
    }
