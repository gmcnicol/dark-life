import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine, select

from apps.api.db import get_session
import apps.api.admin_settings as admin_settings_api
import apps.api.main as main
from apps.api.models import StudioSetting
from shared.config import settings


@pytest.fixture(name="client")
def client_fixture(monkeypatch: pytest.MonkeyPatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    def get_test_session():
        with Session(engine) as session:
            yield session

    monkeypatch.setattr(main, "init_db", lambda: None)
    monkeypatch.setattr(main, "engine", engine)
    monkeypatch.setattr(admin_settings_api, "ADMIN_TOKEN", "local-admin")
    monkeypatch.setattr(settings, "ACTIVE_PUBLISH_PLATFORMS", "youtube")
    main.app.dependency_overrides[get_session] = get_test_session
    with TestClient(main.app) as client:
        yield client, engine
    main.app.dependency_overrides.clear()


def _auth_headers() -> dict[str, str]:
    return {"Authorization": "Bearer local-admin"}


def test_publish_platform_settings_are_clamped_by_config(client):
    client, engine = client

    res = client.get("/admin/settings/publish-platforms", headers=_auth_headers())
    assert res.status_code == 200
    assert res.json()["available_platforms"] == ["youtube"]
    assert res.json()["active_platforms"] == ["youtube"]

    updated = client.put(
        "/admin/settings/publish-platforms",
        json={"active_platforms": ["youtube", "instagram", "tiktok"]},
        headers=_auth_headers(),
    )
    assert updated.status_code == 200
    assert updated.json()["available_platforms"] == ["youtube"]
    assert updated.json()["active_platforms"] == ["youtube"]

    with Session(engine) as session:
        setting = session.exec(select(StudioSetting).where(StudioSetting.key == "active_publish_platforms")).first()
        assert setting is not None
        assert setting.value == {"platforms": ["youtube"]}
