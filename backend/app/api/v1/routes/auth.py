from fastapi import APIRouter, Depends

from app.core.config import get_settings
from app.core.security import DEV_USER_EMAIL, get_current_user
from app.database.models import User

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/status")
def auth_status(user: User = Depends(get_current_user)) -> dict:
    """Confirms that the request is authenticated (a wrong or missing key gets 401 before this runs). Used by the Settings page to
    verify a key. Returns nothing about the user beyond the fact that the key works."""
    s = get_settings()
    return {"authenticated": True, "auth_required": s.auth_required, "mode": "analysis_only",
            "key_used": user.email != DEV_USER_EMAIL}
