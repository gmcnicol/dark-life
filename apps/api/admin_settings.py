from __future__ import annotations

import os

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlmodel import SQLModel, Session, select

from .db import get_session
from .models import StudioSetting
from .publishing import (
    SHORT_PUBLISH_SCHEDULE_KEY,
    active_publish_platforms,
    active_short_schedule_cron_utc,
    configured_publish_platforms,
    derived_short_slots_per_day,
    derived_short_slots_utc,
    describe_short_schedule_cron,
)
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
    short_slots_per_day: int
    short_schedule_cron_utc: str | None = None
    short_schedule_summary: str | None = None


class PublishPlatformSettingsUpdate(SQLModel):
    active_platforms: list[str] | None = None
    short_schedule_cron_utc: str | None = None


def _normalize_platforms(platforms: list[str]) -> list[str]:
    allowed = set(configured_publish_platforms())
    normalized: list[str] = []
    for platform in platforms:
        candidate = platform.strip().lower()
        if candidate and candidate in allowed and candidate not in normalized:
            normalized.append(candidate)
    return normalized


def _build_publish_settings_read(session: Session) -> PublishPlatformSettingsRead:
    cron_utc = active_short_schedule_cron_utc(session)
    return PublishPlatformSettingsRead(
        available_platforms=configured_publish_platforms(),
        active_platforms=active_publish_platforms(session),
        weekly_supported_platforms=[platform for platform in ["youtube"] if platform in configured_publish_platforms()],
        short_slots_utc=derived_short_slots_utc(session),
        short_slots_per_day=derived_short_slots_per_day(session),
        short_schedule_cron_utc=cron_utc,
        short_schedule_summary=describe_short_schedule_cron(cron_utc) if cron_utc else None,
    )


@router.get("/publish-platforms", response_model=PublishPlatformSettingsRead)
def get_publish_platform_settings(
    session: Session = Depends(get_session),
    _: None = Depends(require_token),
) -> PublishPlatformSettingsRead:
    return _build_publish_settings_read(session)


@router.put("/publish-platforms", response_model=PublishPlatformSettingsRead)
def update_publish_platform_settings(
    payload: PublishPlatformSettingsUpdate,
    session: Session = Depends(get_session),
    _: None = Depends(require_token),
) -> PublishPlatformSettingsRead:
    if payload.active_platforms is not None:
        platforms = _normalize_platforms(payload.active_platforms)
        if not platforms:
            raise HTTPException(status_code=400, detail="At least one active publish platform is required")

        setting = session.exec(select(StudioSetting).where(StudioSetting.key == ACTIVE_PUBLISH_PLATFORMS_KEY)).first()
        if not setting:
            setting = StudioSetting(key=ACTIVE_PUBLISH_PLATFORMS_KEY)
        setting.value = {"platforms": platforms}
        session.add(setting)

    if payload.short_schedule_cron_utc is not None:
        cron_utc = payload.short_schedule_cron_utc.strip()
        if not cron_utc:
            cron_utc = None
        if cron_utc:
            try:
                describe_short_schedule_cron(cron_utc)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
        schedule_setting = session.exec(select(StudioSetting).where(StudioSetting.key == SHORT_PUBLISH_SCHEDULE_KEY)).first()
        if cron_utc:
            if not schedule_setting:
                schedule_setting = StudioSetting(key=SHORT_PUBLISH_SCHEDULE_KEY)
            schedule_setting.value = {"cron_utc": cron_utc}
            session.add(schedule_setting)
        elif schedule_setting:
            session.delete(schedule_setting)

    session.commit()
    return _build_publish_settings_read(session)


__all__ = ["router"]
