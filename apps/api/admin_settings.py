from __future__ import annotations

import os

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlmodel import SQLModel, Session, select

from .db import get_session
from .models import StudioSetting
from .publishing import active_publish_platforms, configured_publish_platforms
from shared.config import settings

router = APIRouter(prefix="/admin/settings", tags=["admin-settings"])

ADMIN_TOKEN = os.getenv("API_AUTH_TOKEN") or os.getenv("ADMIN_API_TOKEN")
ACTIVE_PUBLISH_PLATFORMS_KEY = "active_publish_platforms"


def require_token(authorization: str = Header(...)) -> None:
    if not ADMIN_TOKEN or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")
    token = authorization.split(" ", 1)[1]
    if token != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")


class PublishPlatformSettingsRead(SQLModel):
    available_platforms: list[str]
    active_platforms: list[str]
    weekly_supported_platforms: list[str]
    short_slots_utc: list[str]


class PublishPlatformSettingsUpdate(SQLModel):
    active_platforms: list[str]


def _normalize_platforms(platforms: list[str]) -> list[str]:
    allowed = set(configured_publish_platforms())
    normalized: list[str] = []
    for platform in platforms:
        candidate = platform.strip().lower()
        if candidate and candidate in allowed and candidate not in normalized:
            normalized.append(candidate)
    return normalized


@router.get("/publish-platforms", response_model=PublishPlatformSettingsRead)
def get_publish_platform_settings(
    session: Session = Depends(get_session),
    _: None = Depends(require_token),
) -> PublishPlatformSettingsRead:
    available = configured_publish_platforms()
    return PublishPlatformSettingsRead(
        available_platforms=available,
        active_platforms=active_publish_platforms(session),
        weekly_supported_platforms=[platform for platform in ["youtube"] if platform in available],
        short_slots_utc=[slot.strip() for slot in settings.SHORTS_PUBLISH_SLOTS_UTC.split(",") if slot.strip()],
    )


@router.put("/publish-platforms", response_model=PublishPlatformSettingsRead)
def update_publish_platform_settings(
    payload: PublishPlatformSettingsUpdate,
    session: Session = Depends(get_session),
    _: None = Depends(require_token),
) -> PublishPlatformSettingsRead:
    platforms = _normalize_platforms(payload.active_platforms)
    if not platforms:
        raise HTTPException(status_code=400, detail="At least one active publish platform is required")

    setting = session.exec(select(StudioSetting).where(StudioSetting.key == ACTIVE_PUBLISH_PLATFORMS_KEY)).first()
    if not setting:
        setting = StudioSetting(key=ACTIVE_PUBLISH_PLATFORMS_KEY)
    setting.value = {"platforms": platforms}
    session.add(setting)
    session.commit()

    available = configured_publish_platforms()
    return PublishPlatformSettingsRead(
        available_platforms=available,
        active_platforms=active_publish_platforms(session),
        weekly_supported_platforms=[platform for platform in ["youtube"] if platform in available],
        short_slots_utc=[slot.strip() for slot in settings.SHORTS_PUBLISH_SLOTS_UTC.split(",") if slot.strip()],
    )


__all__ = ["router"]
