"""Demo route – load pre-seeded demo event for evaluators."""
import logging

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.services.auth_service import create_access_token, create_refresh_token
from app.services.demo_seeder import seed_demo_event, _DEMO_EMAIL, _DEMO_PASSWORD
from app.models.models import User

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/demo", tags=["demo"])

_COOKIE_KWARGS = {
    "httponly": True,
    "secure": False,
    "samesite": "lax",
    "path": "/",
}


@router.post("/load")
async def load_demo(
    response: Response,
    db: Session = Depends(get_db),
) -> dict:
    """
    One-click demo: seeds the demo event and logs the caller in as the demo user.
    Returns the event_id so the frontend can navigate directly to it.
    """
    from app.config.settings import get_settings
    settings = get_settings()
    cookie_kwargs = {**_COOKIE_KWARGS, "secure": settings.APP_ENV == "production"}

    event = seed_demo_event(db)
    user = db.query(User).filter(User.email == _DEMO_EMAIL).first()
    if not user:
        raise HTTPException(status_code=500, detail="Demo user not found after seeding")

    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id, db)
    db.commit()

    response.set_cookie("access_token", access_token,
                        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60, **cookie_kwargs)
    response.set_cookie("refresh_token", refresh_token,
                        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400, **cookie_kwargs)

    return {
        "event_id": event.id,
        "message": "Demo loaded. Explore the sample wedding event!",
        "demo_credentials": {
            "email": _DEMO_EMAIL,
            "password": _DEMO_PASSWORD,
            "note": "These credentials are only for the demo. Real users should create their own account.",
        },
    }
