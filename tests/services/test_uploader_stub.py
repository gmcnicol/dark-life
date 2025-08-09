import pytest
from sqlmodel import SQLModel, Session, create_engine
from sqlalchemy.pool import StaticPool

from apps.api.models import Story, Job
from shared.config import settings
from video_uploader import cron_upload


def test_cron_upload_dry_run(tmp_path, monkeypatch, capsys):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        story = Story(title="Test Story", status="approved")
        session.add(story)
        session.commit()
        session.refresh(story)
        story_id = story.id
        job = Job(
            story_id=story_id,
            kind="render_part",
            status="success",
            payload={"story_id": story_id, "part_index": 1},
        )
        session.add(job)
        session.commit()

    video_dir = tmp_path / "videos"
    video_dir.mkdir()
    (video_dir / f"{story_id}_p01.mp4").write_text("video")
    monkeypatch.setattr(settings, "VIDEO_OUTPUT_DIR", video_dir)

    monkeypatch.setattr(cron_upload, "create_engine", lambda url, echo=False: engine)

    cron_upload.run(limit=1, dry_run=True)
    captured = capsys.readouterr()
    assert "DRY RUN" in captured.out
