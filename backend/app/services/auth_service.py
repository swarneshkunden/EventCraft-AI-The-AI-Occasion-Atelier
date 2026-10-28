"""
Authentication service – password hashing and JWT handling.
Uses bcrypt for hashing and HS256 JWTs for tokens.
"""
import hashlib
import logging
import secrets
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.config.settings import get_settings
from app.models.models import RefreshToken, User

log = logging.getLogger(__name__)
settings = get_settings()

_bearer = HTTPBearer(auto_error=False)


# ── Password ──────────────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


# ── JWT access token ──────────────────────────────────────────────────────────

def create_access_token(user_id: str) -> str:
    expires = datetime.now(UTC) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload = {"sub": user_id, "exp": expires, "type": "access"}
    return jwt.encode(payload, settings.APP_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Raises jwt.PyJWTError on failure."""
    return jwt.decode(
        token,
        settings.APP_SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
    )


# ── Refresh token ─────────────────────────────────────────────────────────────

def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def create_refresh_token(user_id: str, db: Session) -> str:
    raw = secrets.token_urlsafe(48)
    token_hash = _hash_token(raw)
    expires = datetime.now(UTC) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    record = RefreshToken(user_id=user_id, token_hash=token_hash, expires_at=expires)
    db.add(record)
    db.flush()
    return raw


def rotate_refresh_token(raw: str, db: Session) -> tuple[str, str]:
    """Validates and rotates a refresh token. Returns (new_raw, user_id)."""
    token_hash = _hash_token(raw)
    record = (
        db.query(RefreshToken)
        .filter(RefreshToken.token_hash == token_hash, RefreshToken.revoked.is_(False))
        .first()
    )
    if not record or record.expires_at < datetime.now(UTC):
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    # Revoke old token, issue new one
    record.revoked = True
    new_raw = create_refresh_token(record.user_id, db)
    db.flush()
    return new_raw, record.user_id


def revoke_all_user_tokens(user_id: str, db: Session) -> None:
    db.query(RefreshToken).filter(
        RefreshToken.user_id == user_id, RefreshToken.revoked.is_(False)
    ).update({"revoked": True})


# ── Dependency: get current user ──────────────────────────────────────────────

async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    # Try Authorization header first, then httpOnly cookie
    token = credentials.credentials if credentials else request.cookies.get("access_token")

    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        payload = decode_access_token(token)
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token") from None
    if not isinstance(payload, dict) or payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    user_id = payload.get("sub")
    if not isinstance(user_id, str) or not user_id:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user = db.query(User).filter(User.id == user_id, User.is_active.is_(True)).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    # Make user_id available to middleware for rate limiting
    request.state.user_id = user.id
    return user
