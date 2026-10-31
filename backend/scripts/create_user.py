"""Create (or rotate) a platform user and print a NEW API key once. The key is stored only as an HMAC hash.

Usage (from backend/, with DATABASE_URL and APP_SECRET_KEY set exactly as the running service has them):
    python scripts/create_user.py you@example.com
"""
import os
import sys

sys.path.insert(0, os.getcwd())

from sqlalchemy import select  # noqa: E402

from app.core.security import hash_api_key, new_api_key  # noqa: E402
from app.database.models import User  # noqa: E402
from app.database.session import session_scope  # noqa: E402


def main(email: str) -> None:
    key = new_api_key()
    with session_scope() as s:
        user = s.scalar(select(User).where(User.email == email))
        if user is None:
            user = User(email=email, is_active=True)
            s.add(user)
        user.api_key_hash = hash_api_key(key)
    print(f"user: {email}\nAPI key (shown once, send as X-API-Key): {key}")


if __name__ == "__main__":
    if len(sys.argv) != 2 or "@" not in sys.argv[1]:
        sys.exit("usage: python scripts/create_user.py you@example.com")
    main(sys.argv[1])
