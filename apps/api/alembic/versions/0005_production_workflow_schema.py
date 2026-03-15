"""Add production workflow entities and canonical renderer columns."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0005_production_workflow_schema"
down_revision = "0004_story_source_external_index"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    def has_table(name: str) -> bool:
        return inspector.has_table(name)

    def columns(name: str) -> set[str]:
        return {column["name"] for column in inspector.get_columns(name)} if has_table(name) else set()

    def add_column_if_missing(table_name: str, column: sa.Column) -> None:
        if column.name not in columns(table_name):
            op.add_column(table_name, column)

    add_column_if_missing("story", sa.Column("active_script_version_id", sa.Integer(), nullable=True))
    add_column_if_missing("story", sa.Column("active_asset_bundle_id", sa.Integer(), nullable=True))
    add_column_if_missing("story", sa.Column("narration_notes", sa.Text(), nullable=True))

    add_column_if_missing("storypart", sa.Column("script_version_id", sa.Integer(), nullable=True))
    add_column_if_missing("storypart", sa.Column("asset_bundle_id", sa.Integer(), nullable=True))
    add_column_if_missing("storypart", sa.Column("source_text", sa.Text(), nullable=False, server_default=""))
    add_column_if_missing("storypart", sa.Column("script_text", sa.Text(), nullable=False, server_default=""))
    add_column_if_missing("storypart", sa.Column("approved", sa.Boolean(), nullable=False, server_default=sa.true()))
    add_column_if_missing("storypart", sa.Column("notes", sa.Text(), nullable=True))

    add_column_if_missing("asset", sa.Column("local_path", sa.Text(), nullable=True))
    add_column_if_missing("asset", sa.Column("source", sa.Text(), nullable=False, server_default="local"))
    add_column_if_missing("asset", sa.Column("duration_ms", sa.Integer(), nullable=True))
    add_column_if_missing("asset", sa.Column("width", sa.Integer(), nullable=True))
    add_column_if_missing("asset", sa.Column("height", sa.Integer(), nullable=True))
    add_column_if_missing("asset", sa.Column("orientation", sa.Text(), nullable=True))
    add_column_if_missing("asset", sa.Column("file_hash", sa.Text(), nullable=True))
    add_column_if_missing("asset", sa.Column("rating", sa.Integer(), nullable=True))
    add_column_if_missing("asset", sa.Column("attribution", sa.Text(), nullable=True))
    add_column_if_missing("asset", sa.Column("tags", sa.JSON(), nullable=True))

    add_column_if_missing("jobs", sa.Column("story_part_id", sa.Integer(), nullable=True))
    add_column_if_missing("jobs", sa.Column("compilation_id", sa.Integer(), nullable=True))
    add_column_if_missing("jobs", sa.Column("script_version_id", sa.Integer(), nullable=True))
    add_column_if_missing("jobs", sa.Column("asset_bundle_id", sa.Integer(), nullable=True))
    add_column_if_missing("jobs", sa.Column("render_preset_id", sa.Integer(), nullable=True))
    add_column_if_missing("jobs", sa.Column("variant", sa.Text(), nullable=False, server_default="short"))
    add_column_if_missing("jobs", sa.Column("correlation_id", sa.Text(), nullable=True))

    if not has_table("scriptversion"):
        op.create_table(
            "scriptversion",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("story_id", sa.Integer(), sa.ForeignKey("story.id"), nullable=False),
            sa.Column("source_text", sa.Text(), nullable=False),
            sa.Column("hook", sa.Text(), nullable=False, server_default=""),
            sa.Column("narration_text", sa.Text(), nullable=False),
            sa.Column("outro", sa.Text(), nullable=False, server_default=""),
            sa.Column("model_name", sa.Text(), nullable=False, server_default="rule_based"),
            sa.Column("prompt_version", sa.Text(), nullable=False, server_default="v1"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )

    if not has_table("assetbundle"):
        op.create_table(
            "assetbundle",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("story_id", sa.Integer(), sa.ForeignKey("story.id"), nullable=False),
            sa.Column("name", sa.Text(), nullable=False),
            sa.Column("variant", sa.Text(), nullable=False, server_default="short"),
            sa.Column("asset_ids", sa.JSON(), nullable=False),
            sa.Column("music_policy", sa.Text(), nullable=False, server_default="first"),
            sa.Column("music_track", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )

    if not has_table("renderpreset"):
        op.create_table(
            "renderpreset",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("slug", sa.Text(), nullable=False),
            sa.Column("name", sa.Text(), nullable=False),
            sa.Column("variant", sa.Text(), nullable=False),
            sa.Column("width", sa.Integer(), nullable=False),
            sa.Column("height", sa.Integer(), nullable=False),
            sa.Column("fps", sa.Integer(), nullable=False),
            sa.Column("burn_subtitles", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("target_min_seconds", sa.Integer(), nullable=False, server_default="45"),
            sa.Column("target_max_seconds", sa.Integer(), nullable=False, server_default="60"),
            sa.Column("music_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("music_gain_db", sa.Float(), nullable=False, server_default="-3"),
            sa.Column("ducking_db", sa.Float(), nullable=False, server_default="-12"),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )

    if not has_table("renderartifact"):
        op.create_table(
            "renderartifact",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id"), nullable=True),
            sa.Column("story_id", sa.Integer(), sa.ForeignKey("story.id"), nullable=False),
            sa.Column("story_part_id", sa.Integer(), sa.ForeignKey("storypart.id"), nullable=True),
            sa.Column("compilation_id", sa.Integer(), nullable=True),
            sa.Column("variant", sa.Text(), nullable=False, server_default="short"),
            sa.Column("video_path", sa.Text(), nullable=False),
            sa.Column("subtitle_path", sa.Text(), nullable=True),
            sa.Column("waveform_path", sa.Text(), nullable=True),
            sa.Column("bytes", sa.Integer(), nullable=True),
            sa.Column("duration_ms", sa.Integer(), nullable=True),
            sa.Column("metadata", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )

    if not has_table("compilation"):
        op.create_table(
            "compilation",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("story_id", sa.Integer(), sa.ForeignKey("story.id"), nullable=False),
            sa.Column("title", sa.Text(), nullable=False),
            sa.Column("status", sa.Text(), nullable=False, server_default="approved"),
            sa.Column("script_version_id", sa.Integer(), sa.ForeignKey("scriptversion.id"), nullable=True),
            sa.Column("render_preset_id", sa.Integer(), sa.ForeignKey("renderpreset.id"), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("render_artifact_id", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )

    if not has_table("release"):
        op.create_table(
            "release",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("story_id", sa.Integer(), sa.ForeignKey("story.id"), nullable=False),
            sa.Column("story_part_id", sa.Integer(), sa.ForeignKey("storypart.id"), nullable=True),
            sa.Column("compilation_id", sa.Integer(), sa.ForeignKey("compilation.id"), nullable=True),
            sa.Column("render_artifact_id", sa.Integer(), sa.ForeignKey("renderartifact.id"), nullable=True),
            sa.Column("platform", sa.Text(), nullable=False),
            sa.Column("variant", sa.Text(), nullable=False, server_default="short"),
            sa.Column("title", sa.Text(), nullable=False),
            sa.Column("description", sa.Text(), nullable=False, server_default=""),
            sa.Column("hashtags", sa.JSON(), nullable=True),
            sa.Column("status", sa.Text(), nullable=False, server_default="draft"),
            sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )


def downgrade() -> None:
    op.drop_table("release")
    op.drop_table("compilation")
    op.drop_table("renderartifact")
    op.drop_table("renderpreset")
    op.drop_table("assetbundle")
    op.drop_table("scriptversion")

    op.drop_column("jobs", "correlation_id")
    op.drop_column("jobs", "variant")
    op.drop_column("jobs", "render_preset_id")
    op.drop_column("jobs", "asset_bundle_id")
    op.drop_column("jobs", "script_version_id")
    op.drop_column("jobs", "compilation_id")
    op.drop_column("jobs", "story_part_id")

    op.drop_column("asset", "tags")
    op.drop_column("asset", "attribution")
    op.drop_column("asset", "rating")
    op.drop_column("asset", "file_hash")
    op.drop_column("asset", "orientation")
    op.drop_column("asset", "height")
    op.drop_column("asset", "width")
    op.drop_column("asset", "duration_ms")
    op.drop_column("asset", "source")
    op.drop_column("asset", "local_path")

    op.drop_column("storypart", "notes")
    op.drop_column("storypart", "approved")
    op.drop_column("storypart", "script_text")
    op.drop_column("storypart", "source_text")
    op.drop_column("storypart", "asset_bundle_id")
    op.drop_column("storypart", "script_version_id")

    op.drop_column("story", "narration_notes")
    op.drop_column("story", "active_asset_bundle_id")
    op.drop_column("story", "active_script_version_id")
