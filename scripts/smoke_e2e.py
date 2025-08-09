from __future__ import annotations

"""End-to-end smoke test for the Dark Life pipeline.

This script exercises the happy path of the system:

* create a story
* fetch images and mark the first three as selected
* split the story into ~60 second parts
* enqueue render jobs for each part
* poll until all jobs succeed
* verify expected output files exist
* optionally run the uploader in dry-run mode

The API base URL defaults to ``http://localhost:8000`` but can be overridden
with the ``API_BASE_URL`` environment variable or ``--api-base`` CLI flag.
"""

import os
import time
from pathlib import Path
from typing import Dict, List

import requests
import typer

APP = typer.Typer(add_completion=False)

API_BASE_DEFAULT = os.environ.get("API_BASE_URL", "http://localhost:8000")


def _create_story(api_base: str) -> Dict:
    """Create a sample story and return the response JSON."""
    body = "This is a smoke test story. " * 40
    resp = requests.post(
        f"{api_base}/stories",
        json={"title": f"Smoke Test {int(time.time())}", "body_md": body},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def _fetch_and_select_images(api_base: str, story_id: int) -> None:
    """Fetch images for the story and select the first three."""
    resp = requests.post(f"{api_base}/stories/{story_id}/fetch-images", timeout=30)
    resp.raise_for_status()
    assets = resp.json()
    if len(assets) < 3:
        raise RuntimeError("fetched fewer than 3 images")
    for rank, asset in enumerate(assets[:3]):
        resp = requests.patch(
            f"{api_base}/stories/{story_id}/images/{asset['id']}",
            json={"selected": True, "rank": rank},
            timeout=10,
        )
        resp.raise_for_status()


def _split_story(api_base: str, story_id: int) -> List[Dict]:
    resp = requests.post(
        f"{api_base}/stories/{story_id}/split",
        params={"target_seconds": 60},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def _enqueue_series(api_base: str, story_id: int) -> List[Dict]:
    resp = requests.post(f"{api_base}/stories/{story_id}/enqueue-series", timeout=10)
    resp.raise_for_status()
    data = resp.json()
    return data.get("jobs", [])


def _poll_jobs(api_base: str, jobs: List[Dict], timeout: int = 300) -> None:
    """Poll job statuses until all succeed or timeout (seconds)."""
    deadline = time.time() + timeout
    statuses: Dict[int, str] = {job["id"]: "queued" for job in jobs}
    while time.time() < deadline and any(s != "success" for s in statuses.values()):
        for job in jobs:
            job_id = job["id"]
            if statuses[job_id] == "success":
                continue
            resp = requests.get(f"{api_base}/jobs/{job_id}", timeout=10)
            resp.raise_for_status()
            statuses[job_id] = resp.json().get("status", "")
        if any(s != "success" for s in statuses.values()):
            time.sleep(5)
    if any(s != "success" for s in statuses.values()):
        raise RuntimeError(f"jobs incomplete: {statuses}")


def _verify_outputs(story_id: int, jobs: List[Dict]) -> None:
    video_dir = Path("output/videos")
    manifest_dir = Path("output/manifest")
    missing: List[str] = []
    for job in jobs:
        part_index = job.get("part_index")
        video_file = video_dir / f"{story_id}_p{part_index:02d}.mp4"
        manifest_file = manifest_dir / f"{story_id}_p{part_index:02d}.json"
        if not video_file.exists():
            missing.append(str(video_file))
        if not manifest_file.exists():
            missing.append(str(manifest_file))
    if missing:
        raise FileNotFoundError("missing outputs: " + ", ".join(missing))


@APP.command()
def run(
    api_base: str = typer.Option(API_BASE_DEFAULT, "--api-base", help="API base URL"),
    uploader: bool = typer.Option(
        False, "--uploader", help="Run uploader in dry-run mode", is_flag=True
    ),
) -> None:
    """Execute the end-to-end smoke test."""
    story = _create_story(api_base)
    story_id = story["id"]
    _fetch_and_select_images(api_base, story_id)
    _split_story(api_base, story_id)
    jobs = _enqueue_series(api_base, story_id)
    if not jobs:
        raise RuntimeError("no jobs enqueued")
    _poll_jobs(api_base, jobs)
    _verify_outputs(story_id, jobs)
    if uploader:
        from video_uploader.cron_upload import run as uploader_run

        uploader_run(limit=1, dry_run=True)
    typer.echo(f"Smoke test succeeded for story {story_id}")


if __name__ == "__main__":  # pragma: no cover
    APP()
