"""Initial database tables."""

from alembic import op
from sqlmodel import SQLModel

from apps.api import models  # noqa: F401
from apps.api import reddit_admin

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    SQLModel.metadata.create_all(bind)
    reddit_admin.reddit_fetch_state.create(bind)


def downgrade() -> None:
    bind = op.get_bind()
    reddit_admin.reddit_fetch_state.drop(bind)
    SQLModel.metadata.drop_all(bind)
