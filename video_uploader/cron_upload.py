"""Upload rendered story parts to platforms."""

from __future__ import annotations

from sqlmodel import Session, create_engine
import typer

from apps.api.models import Upload
from apps.api.uploads import next_part_ready_for_upload
from shared.config import settings
from . import upload_youtube

app = typer.Typer(add_completion=False)


@app.command()
def run(
    limit: int = typer.Option(1, "--limit", help="Maximum number of parts to upload"),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Print actions without uploading", is_flag=True
    ),
) -> None:
    """Upload the next rendered parts to YouTube."""
    engine = create_engine(settings.DATABASE_URL, echo=False)
    uploaded = 0
    with Session(engine) as session:
        while uploaded < limit:
            result = next_part_ready_for_upload(session, platform="youtube")
            if not result:
                print("No parts ready for upload")
                break
            job, story = result
            payload = job.payload or {}
            part_index = payload.get("part_index")
            if part_index is None:
                print("Job missing part_index; skipping")
                break
            video_path = settings.VIDEO_OUTPUT_DIR / f"{story.id}_p{part_index:02d}.mp4"
            if not video_path.exists():
                print(f"Video file not found: {video_path}")
                break
            title = f"{story.title} — Part {part_index}"
            if dry_run:
                print(
                    f"[DRY RUN] Would upload {video_path} to YouTube with title '{title}'"
                )
            else:
                video_id = upload_youtube.upload(
                    video_path,
                    title,
                    settings.YOUTUBE_CLIENT_SECRETS_FILE,
                    settings.YOUTUBE_TOKEN_FILE,
                )
                if not video_id:
                    print("Upload failed; stopping")
                    break
                session.add(
                    Upload(
                        story_id=story.id,
                        part_index=part_index,
                        platform="youtube",
                        platform_video_id=video_id,
                    )
                )
                session.commit()
                print(f"Uploaded https://youtu.be/{video_id}")
            uploaded += 1


if __name__ == "__main__":  # pragma: no cover
    app()
