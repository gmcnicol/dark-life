"""Run the uploader once. Useful for cron jobs."""

from services.uploader.upload_youtube import run as upload_once


def main() -> None:
    """Upload the next rendered part to YouTube."""
    upload_once(dry_run=False)


if __name__ == "__main__":
    main()
