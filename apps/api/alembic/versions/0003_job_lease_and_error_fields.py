"""Add lease and error tracking fields to jobs."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0003_job_lease_and_error_fields"
down_revision = "0002_reddit_fetch_state"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing = {column["name"] for column in inspector.get_columns("jobs")}

    if "lease_expires_at" not in existing:
        op.add_column(
            "jobs",
            sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        )
    if "retries" not in existing:
        op.add_column(
            "jobs", sa.Column("retries", sa.Integer(), server_default="0", nullable=False)
        )
    if "error_class" not in existing:
        op.add_column("jobs", sa.Column("error_class", sa.Text(), nullable=True))
    if "error_message" not in existing:
        op.add_column("jobs", sa.Column("error_message", sa.Text(), nullable=True))
    if "stderr_snippet" not in existing:
        op.add_column("jobs", sa.Column("stderr_snippet", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("jobs", "stderr_snippet")
    op.drop_column("jobs", "error_message")
    op.drop_column("jobs", "error_class")
    op.drop_column("jobs", "retries")
    op.drop_column("jobs", "lease_expires_at")
