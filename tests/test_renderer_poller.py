from pathlib import Path

import sys
sys.path.append(str(Path(__file__).resolve().parents[1]))

from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine

from apps.api.models import Asset, Job, Story, StoryPart
from shared.config import settings
from services.renderer import poller


def test_poller_processes_job(tmp_path, monkeypatch):
    video_dir = tmp_path / "videos"
    monkeypatch.setattr(settings, "VIDEO_OUTPUT_DIR", video_dir)

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        story = Story(title="Test Story")
        session.add(story)
        session.commit()
        session.refresh(story)

        part = StoryPart(story_id=story.id, index=1, body_md="Hello world", est_seconds=5)
        session.add(part)

        asset = Asset(story_id=story.id, remote_url="http://example.com/img.jpg")
        session.add(asset)
        session.commit()
        session.refresh(asset)

        job = Job(
            story_id=story.id,
            kind="render_part",
            status="queued",
            payload={
                "story_id": story.id,
                "part_index": 1,
                "asset_ids": [asset.id],
            },
        )
        session.add(job)
        session.commit()
        job_id = job.id

    class DummyResponse:
        content = b"img"

        def raise_for_status(self):
            pass

    monkeypatch.setattr(poller.requests, "get", lambda url, timeout: DummyResponse())

    def fake_slideshow(args):
        story_id = args[args.index("--story_id") + 1]
        output_dir = Path(args[args.index("--output-dir") + 1])
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / f"{story_id}_final.mp4").write_bytes(b"vid")
        return 0

    monkeypatch.setattr(poller.create_slideshow, "main", fake_slideshow)
    monkeypatch.setattr(poller.voiceover, "_synth_with_pyttsx3", lambda engine, text, dest: False)
    monkeypatch.setattr(poller.voiceover, "_placeholder_audio", lambda text, dest: dest.write_bytes(b"a"))

    with Session(engine) as session:
        processed = poller.process_once(session)

    assert processed
    video_path = video_dir / "test-story_p01.mp4"
    assert video_path.exists()
    with Session(engine) as session:
        job = session.get(Job, job_id)
        assert job.status == "success"
