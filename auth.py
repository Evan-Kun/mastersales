import bcrypt

from fastapi import Request, Depends
from fastapi.responses import RedirectResponse
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from sqlalchemy.orm import Session

from config import settings
from database.db import get_db
from database.models import User

# ── Password hashing (bcrypt) ────────────────────────────────────────────────


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


# ── Session cookie (signed, tamper-proof) ─────────────────────────────────────

SESSION_COOKIE = "mastersales_session"
SESSION_MAX_AGE = 60 * 60 * 24 * 7  # 7 days

_session_serializer = URLSafeTimedSerializer(settings.secret_key, salt="session")
_reset_serializer = URLSafeTimedSerializer(settings.secret_key, salt="password-reset")


def create_session_cookie(user_id: int) -> str:
    return _session_serializer.dumps({"uid": user_id})


def read_session_cookie(token: str) -> int | None:
    try:
        data = _session_serializer.loads(token, max_age=SESSION_MAX_AGE)
        return data.get("uid")
    except (BadSignature, SignatureExpired):
        return None


# ── Password reset tokens (valid 1 hour) ─────────────────────────────────────

RESET_TOKEN_MAX_AGE = 60 * 60  # 1 hour


def create_reset_token(email: str) -> str:
    return _reset_serializer.dumps({"email": email})


def verify_reset_token(token: str) -> str | None:
    try:
        data = _reset_serializer.loads(token, max_age=RESET_TOKEN_MAX_AGE)
        return data.get("email")
    except (BadSignature, SignatureExpired):
        return None


# ── Auth dependency ───────────────────────────────────────────────────────────

PUBLIC_PATHS = {"/login", "/signup", "/forgot-password", "/reset-password"}


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    user_id = read_session_cookie(token)
    if not user_id:
        return None
    return db.query(User).filter(User.id == user_id, User.is_active.is_(True)).first()


def require_auth(request: Request, db: Session = Depends(get_db)) -> User:
    """Dependency that redirects to /login if not authenticated."""
    user = get_current_user(request, db)
    if user is None:
        raise _AuthRedirect()
    return user


class _AuthRedirect(Exception):
    """Raised to trigger a redirect to the login page."""
    pass


def set_session_cookie(response: RedirectResponse, user_id: int) -> RedirectResponse:
    response.set_cookie(
        key=SESSION_COOKIE,
        value=create_session_cookie(user_id),
        max_age=SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
    )
    return response


def clear_session_cookie(response: RedirectResponse) -> RedirectResponse:
    response.delete_cookie(key=SESSION_COOKIE)
    return response
