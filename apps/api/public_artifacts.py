"""Signed public artifact delivery endpoints."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from sqlmodel import Session

from .db import engine
from .models import Release, RenderArtifact
from .publishing import resolve_public_video_path, resolve_release_artifact, verify_signature


router = APIRouter(prefix="/public", tags=["public-artifacts"])


def _file_response(path: Path) -> FileResponse:
    return FileResponse(path=path, media_type="video/mp4", filename=path.name)


@router.get("/artifacts/{artifact_id}")
def get_public_artifact(artifact_id: int, exp: int = Query(...), sig: str = Query(...)) -> FileResponse:
    verify_signature("artifact", artifact_id, exp, sig)
    with Session(engine) as session:
        artifact = session.get(RenderArtifact, artifact_id)
        if not artifact:
            raise HTTPException(status_code=404, detail="Artifact not found")
        return _file_response(resolve_public_video_path(artifact.video_path))


@router.get("/releases/{release_id}/asset")
def get_public_release_asset(release_id: int, exp: int = Query(...), sig: str = Query(...)) -> FileResponse:
    verify_signature("release", release_id, exp, sig)
    with Session(engine) as session:
        release = session.get(Release, release_id)
        if not release:
            raise HTTPException(status_code=404, detail="Release not found")
        artifact = resolve_release_artifact(session, release)
        if not artifact:
            raise HTTPException(status_code=404, detail="Artifact not found")
        return _file_response(resolve_public_video_path(artifact.video_path))
