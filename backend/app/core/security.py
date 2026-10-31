import hashlib
import hmac
import secrets

from fastapi import Depends, Header
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import AuthError
from app.database.models.user import User
from app.database.session import get_session

DEV_USER_EMAIL = "local-dev@localhost"


def hash_api_key(key: str) -> str:
    secret = get_settings().app_secret_key.encode()
    return hmac.new(secret, key.encode(), hashlib.sha256).hexdigest()


def new_api_key() -> str:
    return "ati_" + secrets.token_urlsafe(32)


def get_current_user(
    x_api_key: str | None = Header(default=None),
    session: Session = Depends(get_session),
) -> User:
    """Server-side authentication.

    AUTH_REQUIRED=false (local dev) maps anonymous calls to one local user; otherwise an
    X-API-Key header is mandatory. Every owned resource is filtered by user.id.
    """
    if x_api_key:
        user = session.scalar(select(User).where(User.api_key_hash == hash_api_key(x_api_key)))
        if not user or not user.is_active:
            raise AuthError("Invalid API key")
        return user
    if get_settings().auth_required:
        raise AuthError("API key required")
    user = session.scalar(select(User).where(User.email == DEV_USER_EMAIL))
    if not user:
        user = User(email=DEV_USER_EMAIL, is_active=True)
        session.add(user)
        session.commit()
    return user
