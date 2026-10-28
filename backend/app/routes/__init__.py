from app.routes.auth import router as auth_router
from app.routes.budget import router as budget_router
from app.routes.chat import router as chat_router
from app.routes.demo import router as demo_router
from app.routes.events import router as events_router
from app.routes.guests import router as guests_router
from app.routes.plan_health import router as plan_health_router
from app.routes.tasks import router as tasks_router
from app.routes.vendors import router as vendors_router

__all__ = [
    "auth_router",
    "budget_router",
    "chat_router",
    "demo_router",
    "events_router",
    "guests_router",
    "plan_health_router",
    "tasks_router",
    "vendors_router",
]
