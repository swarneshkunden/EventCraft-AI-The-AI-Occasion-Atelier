"""Auth routes – signup, login, refresh, logout."""
import asyncio
import logging
import secrets

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.config.settings import get_settings
from app.middleware.rate_limit import get_rate_limit_store
from app.models.models import User
from app.services.auth_service import (
    create_access_token,
    create_refresh_token,
    get_current_user,
    hash_password,
    revoke_all_user_tokens,
    rotate_refresh_token,
    verify_password,
)
from app.validators.schemas import LoginRequest, SignupRequest, UserResponse

log = logging.getLogger(__name__)
settings = get_settings()
_DUMMY_PASSWORD_HASH = bcrypt.hashpw(secrets.token_bytes(32), bcrypt.gensalt()).decode()

router = APIRouter(prefix="/api/auth", tags=["auth"])

_COOKIE_KWARGS = {
    "httponly": True,
    "secure": settings.APP_ENV == "production",
    "samesite": "lax",
    "path": "/",
}


def _set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    response.set_cookie(
        "access_token",
        access_token,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        **_COOKIE_KWARGS,
    )
    response.set_cookie(
        "refresh_token",
        refresh_token,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        **_COOKIE_KWARGS,
    )


@router.post("/signup", status_code=202)
async def signup(
    body: SignupRequest,
    db: Session = Depends(get_db),
) -> dict:
    hashed_password = hash_password(body.password)
    existing = db.query(User).filter(User.email == body.email).first()
    if not existing:
        user = User(
            email=body.email,
            hashed_password=hashed_password,
            display_name=body.display_name,
            currency=body.currency,
        )
        db.add(user)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
    return {
        "message": "If the address was available, the account was created. Sign in to continue."
    }


@router.post("/login")
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> dict:
    store = get_rate_limit_store()
    account_key = f"auth_fail_account:{body.email.lower()}"
    ip = request.client.host if request.client else "unknown"
    ip_key = f"auth_fail_ip:{ip}"
    account_allowed = await store.is_allowed(
        f"auth_account:{body.email.lower()}",
        settings.RATE_AUTH_ACCOUNT_WINDOW_SECONDS,
        settings.RATE_AUTH_ACCOUNT_MAX_REQUESTS,
    )
    if not account_allowed:
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Please wait before trying again.",
            headers={"Retry-After": str(settings.RATE_AUTH_ACCOUNT_WINDOW_SECONDS)},
        )

    delay = max(
        await store.get_auth_failure_delay(account_key),
        await store.get_auth_failure_delay(ip_key),
    )
    if delay > 0:
        await asyncio.sleep(delay)

    user = db.query(User).filter(User.email == body.email, User.is_active.is_(True)).first()
    password_hash = user.hashed_password if user else _DUMMY_PASSWORD_HASH
    password_matches = verify_password(body.password, password_hash)
    if not user or not password_matches:
        await store.record_auth_failure(account_key)
        await store.record_auth_failure(ip_key)
        raise HTTPException(status_code=401, detail="Invalid email or password")

    await store.reset_auth_failures(account_key)
    await store.reset_auth_failures(ip_key)

    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id, db)
    db.commit()

    _set_auth_cookies(response, access_token, refresh_token)
    return {"message": "Logged in", "display_name": user.display_name}


@router.post("/refresh")
async def refresh_token(
    response: Response,
    db: Session = Depends(get_db),
) -> dict:
    # Refresh token comes from httpOnly cookie only
    raise HTTPException(status_code=400, detail="Use the cookie-based refresh endpoint")


@router.post("/refresh-cookie")
async def refresh_cookie(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> dict:
    raw_refresh = request.cookies.get("refresh_token")
    if not raw_refresh:
        raise HTTPException(status_code=401, detail="No refresh token")

    new_raw, user_id = rotate_refresh_token(raw_refresh, db)
    access_token = create_access_token(user_id)
    db.commit()

    _set_auth_cookies(response, access_token, new_raw)
    return {"message": "Token refreshed"}


@router.post("/logout")
async def logout(
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    revoke_all_user_tokens(current_user.id, db)
    db.commit()
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    return {"message": "Logged out"}


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)) -> User:
    return current_user
