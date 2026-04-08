"""Add studio settings table."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0009_studio_settings"
down_revision = "0008_script_refinement"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "studiosetting" in inspector.get_table_names():
        return
    op.create_table(
        "studiosetting",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(), nullable=False),
        sa.Column("value", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("key"),
    )
    op.create_index("ix_studiosetting_key", "studiosetting", ["key"], unique=True)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "studiosetting" not in inspector.get_table_names():
        return
    indexes = {index["name"] for index in inspector.get_indexes("studiosetting")}
    if "ix_studiosetting_key" in indexes:
        op.drop_index("ix_studiosetting_key", table_name="studiosetting")
    op.drop_table("studiosetting")
