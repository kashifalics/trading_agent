"""BOOTSTRAP_API_KEY gives a hosted deployment its owner key at startup (no shell access needed)."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.security import OWNER_EMAIL, ensure_bootstrap_user
from app.database.models import User
from app.main import create_app


@pytest.fixture()
def secured(engine, monkeypatch):
    monkeypatch.setenv("AUTH_REQUIRED", "true")
    monkeypatch.setenv("BOOTSTRAP_API_KEY", "ati_first-key")
    get_settings.cache_clear()
    yield monkeypatch
    get_settings.cache_clear()


def test_startup_creates_the_owner_and_only_that_key_works(secured):
    with TestClient(create_app()) as c:
        assert c.get("/api/v1/paper/account").status_code == 401
        assert c.get("/api/v1/paper/account", headers={"X-API-Key": "ati_wrong"}).status_code == 401
        assert c.get("/api/v1/paper/account", headers={"X-API-Key": "ati_first-key"}).status_code == 200


def test_bootstrap_is_idempotent_and_rotates_the_key(secured, session):
    assert ensure_bootstrap_user(session) is True
    assert ensure_bootstrap_user(session) is False  # every later start is a no-op
    secured.setenv("BOOTSTRAP_API_KEY", "ati_second-key")
    get_settings.cache_clear()
    assert ensure_bootstrap_user(session) is True  # a new key replaces the old one
    assert session.scalar(select(func.count(User.id)).where(User.email == OWNER_EMAIL)) == 1
    secured.delenv("BOOTSTRAP_API_KEY")
    get_settings.cache_clear()
    assert ensure_bootstrap_user(session) is False  # unset: nothing happens
