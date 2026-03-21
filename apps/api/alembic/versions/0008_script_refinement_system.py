"""Add script refinement system tables and variant-aware columns."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0008_script_refinement"
down_revision = "0007_publish_jobs"
branch_labels = None
depends_on = None


def _has_table(inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _columns(inspector, table_name: str) -> set[str]:
    if not _has_table(inspector, table_name):
        return set()
    return {column["name"] for column in inspector.get_columns(table_name)}


def _add_column_if_missing(inspector, table_name: str, column: sa.Column) -> None:
    if column.name not in _columns(inspector, table_name):
        op.add_column(table_name, column)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if not _has_table(inspector, "storyconcept"):
        op.create_table(
            "storyconcept",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("story_id", sa.Integer(), sa.ForeignKey("story.id"), nullable=False),
            sa.Column("concept_key", sa.Text(), nullable=False),
            sa.Column("concept_label", sa.Text(), nullable=False),
            sa.Column("anomaly_type", sa.Text(), nullable=False, server_default="unknown"),
            sa.Column("object_focus", sa.Text(), nullable=True),
            sa.Column("specificity", sa.Text(), nullable=False, server_default="mixed"),
            sa.Column("extraction_metadata", sa.JSON(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )

    if not _has_table(inspector, "scriptbatch"):
        op.create_table(
            "scriptbatch",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("story_id", sa.Integer(), sa.ForeignKey("story.id"), nullable=False),
            sa.Column("concept_id", sa.Integer(), sa.ForeignKey("storyconcept.id"), nullable=True),
            sa.Column("status", sa.Text(), nullable=False, server_default="queued"),
            sa.Column("candidate_count", sa.Integer(), nullable=False, server_default="20"),
            sa.Column("shortlisted_count", sa.Integer(), nullable=False, server_default="3"),
            sa.Column("template_version", sa.Text(), nullable=False, server_default="template_v1"),
            sa.Column("prompt_version", sa.Text(), nullable=False, server_default="gen_prompt_v1"),
            sa.Column("critic_version", sa.Text(), nullable=False, server_default="critic_v1"),
            sa.Column("selection_policy_version", sa.Text(), nullable=False, server_default="selection_policy_v1"),
            sa.Column("analyst_version", sa.Text(), nullable=False, server_default="analyst_v1"),
            sa.Column("model_name", sa.Text(), nullable=False, server_default="gpt-4.1-mini"),
            sa.Column("temperature", sa.Float(), nullable=False, server_default="1.0"),
            sa.Column("config", sa.JSON(), nullable=True),
            sa.Column("result", sa.JSON(), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )

    if not _has_table(inspector, "promptversion"):
        op.create_table(
            "promptversion",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("kind", sa.Text(), nullable=False),
            sa.Column("version_label", sa.Text(), nullable=False),
            sa.Column("status", sa.Text(), nullable=False, server_default="draft"),
            sa.Column("body", sa.Text(), nullable=False),
            sa.Column("config", sa.JSON(), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.UniqueConstraint("kind", "version_label"),
        )

    if not _has_table(inspector, "metricssnapshot"):
        op.create_table(
            "metricssnapshot",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("release_id", sa.Integer(), sa.ForeignKey("release.id"), nullable=True),
            sa.Column("story_id", sa.Integer(), sa.ForeignKey("story.id"), nullable=False),
            sa.Column("script_version_id", sa.Integer(), sa.ForeignKey("scriptversion.id"), nullable=False),
            sa.Column("story_part_id", sa.Integer(), sa.ForeignKey("storypart.id"), nullable=True),
            sa.Column("window_hours", sa.Integer(), nullable=False),
            sa.Column("source", sa.Text(), nullable=False, server_default="youtube"),
            sa.Column("metrics", sa.JSON(), nullable=False),
            sa.Column("derived_metrics", sa.JSON(), nullable=True),
            sa.Column("captured_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )

    if not _has_table(inspector, "analysisreport"):
        op.create_table(
            "analysisreport",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("batch_id", sa.Integer(), sa.ForeignKey("scriptbatch.id"), nullable=True),
            sa.Column("story_id", sa.Integer(), sa.ForeignKey("story.id"), nullable=False),
            sa.Column("concept_id", sa.Integer(), sa.ForeignKey("storyconcept.id"), nullable=True),
            sa.Column("analyst_version", sa.Text(), nullable=False, server_default="analyst_v1"),
            sa.Column("status", sa.Text(), nullable=False, server_default="draft"),
            sa.Column("summary", sa.Text(), nullable=False, server_default=""),
            sa.Column("insights", sa.JSON(), nullable=True),
            sa.Column("recommendations", sa.JSON(), nullable=True),
            sa.Column("prompt_proposals", sa.JSON(), nullable=True),
            sa.Column("metrics_window_hours", sa.Integer(), nullable=False, server_default="72"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )

    scriptversion_additions = [
        sa.Column("batch_id", sa.Integer(), nullable=True),
        sa.Column("concept_id", sa.Integer(), nullable=True),
        sa.Column("template_version", sa.Text(), nullable=False, server_default="template_v1"),
        sa.Column("critic_version", sa.Text(), nullable=False, server_default="critic_v1"),
        sa.Column("selection_policy_version", sa.Text(), nullable=False, server_default="selection_policy_v1"),
        sa.Column("temperature", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("selection_state", sa.Text(), nullable=False, server_default="draft"),
        sa.Column("critic_scores", sa.JSON(), nullable=True),
        sa.Column("performance_metrics", sa.JSON(), nullable=True),
        sa.Column("derived_metrics", sa.JSON(), nullable=True),
        sa.Column("generation_metadata", sa.JSON(), nullable=True),
        sa.Column("critic_rank", sa.Integer(), nullable=True),
        sa.Column("performance_rank", sa.Integer(), nullable=True),
    ]
    for column in scriptversion_additions:
        _add_column_if_missing(inspector, "scriptversion", column)

    storypart_additions = [
        sa.Column("episode_type", sa.Text(), nullable=False, server_default="entry"),
        sa.Column("hook", sa.Text(), nullable=False, server_default=""),
        sa.Column("lines", sa.JSON(), nullable=True),
        sa.Column("loop_line", sa.Text(), nullable=False, server_default=""),
        sa.Column("features", sa.JSON(), nullable=True),
        sa.Column("critic_scores", sa.JSON(), nullable=True),
        sa.Column("performance_metrics", sa.JSON(), nullable=True),
        sa.Column("derived_metrics", sa.JSON(), nullable=True),
        sa.Column("critic_rank", sa.Integer(), nullable=True),
        sa.Column("performance_rank", sa.Integer(), nullable=True),
    ]
    for column in storypart_additions:
        _add_column_if_missing(inspector, "storypart", column)

    _add_column_if_missing(inspector, "renderartifact", sa.Column("script_version_id", sa.Integer(), nullable=True))
    _add_column_if_missing(inspector, "release", sa.Column("script_version_id", sa.Integer(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if _has_table(inspector, "analysisreport"):
        op.drop_table("analysisreport")
    if _has_table(inspector, "metricssnapshot"):
        op.drop_table("metricssnapshot")
    if _has_table(inspector, "promptversion"):
        op.drop_table("promptversion")
    if _has_table(inspector, "scriptbatch"):
        op.drop_table("scriptbatch")
    if _has_table(inspector, "storyconcept"):
        op.drop_table("storyconcept")

    for table_name, column_name in [
        ("release", "script_version_id"),
        ("renderartifact", "script_version_id"),
        ("storypart", "performance_rank"),
        ("storypart", "critic_rank"),
        ("storypart", "derived_metrics"),
        ("storypart", "performance_metrics"),
        ("storypart", "critic_scores"),
        ("storypart", "features"),
        ("storypart", "loop_line"),
        ("storypart", "lines"),
        ("storypart", "hook"),
        ("storypart", "episode_type"),
        ("scriptversion", "performance_rank"),
        ("scriptversion", "critic_rank"),
        ("scriptversion", "generation_metadata"),
        ("scriptversion", "derived_metrics"),
        ("scriptversion", "performance_metrics"),
        ("scriptversion", "critic_scores"),
        ("scriptversion", "selection_state"),
        ("scriptversion", "temperature"),
        ("scriptversion", "selection_policy_version"),
        ("scriptversion", "critic_version"),
        ("scriptversion", "template_version"),
        ("scriptversion", "concept_id"),
        ("scriptversion", "batch_id"),
    ]:
        if _has_table(inspector, table_name) and column_name in _columns(inspector, table_name):
            op.drop_column(table_name, column_name)
