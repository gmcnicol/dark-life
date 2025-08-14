"""Add unique index on (source, external_id)"""

from alembic import op

revision = "0004_story_source_external_index"
down_revision = "0003_job_lease_and_error_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("uq_story_source_external", "story", type_="unique")
    op.create_index(
        "ix_story_source_external", "story", ["source", "external_id"], unique=True
    )


def downgrade() -> None:
    op.drop_index("ix_story_source_external", table_name="story")
    op.create_unique_constraint(
        "uq_story_source_external", "story", ["source", "external_id"]
    )
