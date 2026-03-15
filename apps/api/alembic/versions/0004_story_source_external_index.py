"""Add unique index on (source, external_id)"""

from alembic import op
from sqlalchemy import inspect

revision = "0004_story_source_external_index"
down_revision = "0003_job_lease_and_error_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    unique_constraints = {
        constraint["name"]
        for constraint in inspector.get_unique_constraints("story")
        if constraint.get("name")
    }
    indexes = {
        index["name"]
        for index in inspector.get_indexes("story")
        if index.get("name")
    }
    if "uq_story_source_external" in unique_constraints:
        op.drop_constraint("uq_story_source_external", "story", type_="unique")
    if "ix_story_source_external" not in indexes:
        op.create_index(
            "ix_story_source_external", "story", ["source", "external_id"], unique=True
        )


def downgrade() -> None:
    op.drop_index("ix_story_source_external", table_name="story")
    op.create_unique_constraint(
        "uq_story_source_external", "story", ["source", "external_id"]
    )
