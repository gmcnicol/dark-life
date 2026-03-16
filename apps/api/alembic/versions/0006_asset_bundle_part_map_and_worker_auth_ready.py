"""Add explicit asset bundle part mapping."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0006_asset_bundle_part_map"
down_revision = "0005_production_workflow_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("assetbundle")}
    if "part_asset_map" not in columns:
        op.add_column(
            "assetbundle",
            sa.Column("part_asset_map", sa.JSON(), nullable=False, server_default="[]"),
        )


def downgrade() -> None:
    op.drop_column("assetbundle", "part_asset_map")
