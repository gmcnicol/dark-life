"""Add publish jobs, release state fields, and public publishing metadata."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0007_publish_jobs"
down_revision = "0006_asset_bundle_part_map"
branch_labels = None
depends_on = None


def _has_table(inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _has_column(inspector, table_name: str, column_name: str) -> bool:
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if _has_table(inspector, "release"):
        additions = [
            ("publish_status", sa.Column("publish_status", sa.Text(), nullable=False, server_default="draft")),
            ("approval_status", sa.Column("approval_status", sa.Text(), nullable=False, server_default="pending")),
            ("delivery_mode", sa.Column("delivery_mode", sa.Text(), nullable=False, server_default="automated")),
            ("platform_video_id", sa.Column("platform_video_id", sa.Text(), nullable=True)),
            ("publish_at", sa.Column("publish_at", sa.DateTime(timezone=True), nullable=True)),
            ("approved_at", sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True)),
            ("last_error", sa.Column("last_error", sa.Text(), nullable=True)),
            ("attempt_count", sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0")),
            ("provider_metadata", sa.Column("provider_metadata", sa.JSON(), nullable=True)),
        ]
        for name, column in additions:
            if not _has_column(inspector, "release", name):
                op.add_column("release", column)
        op.execute("UPDATE release SET publish_status = status WHERE publish_status IS NULL OR publish_status = 'draft'")

    if not _has_table(inspector, "publishjob"):
        op.create_table(
            "publishjob",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("release_id", sa.Integer(), sa.ForeignKey("release.id"), nullable=False),
            sa.Column("platform", sa.Text(), nullable=False),
            sa.Column("status", sa.Text(), nullable=False, server_default="queued"),
            sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("not_before", sa.DateTime(timezone=True), nullable=True),
            sa.Column("correlation_id", sa.Text(), nullable=True),
            sa.Column("payload", sa.JSON(), nullable=True),
            sa.Column("result", sa.JSON(), nullable=True),
            sa.Column("error_class", sa.Text(), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("stderr_snippet", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.UniqueConstraint("release_id"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if _has_table(inspector, "publishjob"):
        op.drop_table("publishjob")
    if _has_table(inspector, "release"):
        for column_name in [
            "provider_metadata",
            "attempt_count",
            "last_error",
            "approved_at",
            "publish_at",
            "platform_video_id",
            "delivery_mode",
            "approval_status",
            "publish_status",
        ]:
            if _has_column(inspector, "release", column_name):
                op.drop_column("release", column_name)
