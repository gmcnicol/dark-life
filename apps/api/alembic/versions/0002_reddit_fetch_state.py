"""Add reddit_fetch_state table."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

revision = "0002_reddit_fetch_state"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "reddit_fetch_state",
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True),
        sa.Column("subreddit", sa.Text(), nullable=False, unique=True),
        sa.Column("last_fullname", sa.Text(), nullable=True),
        sa.Column("last_created_utc", sa.DateTime(timezone=True), nullable=True),
        sa.Column("mode", sa.Text(), nullable=True),
        sa.Column("backfill_earliest_utc", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_table("reddit_fetch_state")
