"""Add image_urls column to reddit_posts

Revision ID: 0002
Revises: 0001
Create Date: 2025-08-09
"""

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("reddit_posts", sa.Column("image_urls", sa.JSON(), nullable=True))


def downgrade():
    op.drop_column("reddit_posts", "image_urls")
