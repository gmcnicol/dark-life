"""Create Reddit ingestion tables

Revision ID: 0001
Revises: 
Create Date: 2025-08-09
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "reddit_posts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("reddit_id", sa.Text(), nullable=False, unique=True),
        sa.Column("subreddit", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("author", sa.Text(), nullable=True),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("created_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_self", sa.Boolean(), nullable=False),
        sa.Column("selftext", sa.Text(), nullable=True),
        sa.Column("nsfw", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("language", sa.Text(), nullable=True),
        sa.Column("upvotes", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("num_comments", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("hash_title_body", sa.Text(), nullable=False),
        sa.Column("inserted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("subreddit", "hash_title_body", name="reddit_posts_subreddit_hash_title_body_key"),
    )
    op.create_index("ix_reddit_posts_subreddit", "reddit_posts", ["subreddit"], unique=False)
    op.create_index("ix_reddit_posts_created_utc", "reddit_posts", ["created_utc"], unique=False)
    op.create_index("ix_reddit_posts_hash_title_body", "reddit_posts", ["hash_title_body"], unique=False)

    op.create_table(
        "reddit_fetch_state",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("subreddit", sa.Text(), nullable=False, unique=True),
        sa.Column("last_fullname", sa.Text(), nullable=True),
        sa.Column("last_created_utc", sa.DateTime(timezone=True), nullable=True),
        sa.Column("backfill_earliest_utc", sa.DateTime(timezone=True), nullable=True),
        sa.Column("mode", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "reddit_rejections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("reddit_id", sa.Text(), nullable=False),
        sa.Column("subreddit", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade():
    op.drop_table("reddit_rejections")
    op.drop_table("reddit_fetch_state")
    op.drop_index("ix_reddit_posts_hash_title_body", table_name="reddit_posts")
    op.drop_index("ix_reddit_posts_created_utc", table_name="reddit_posts")
    op.drop_index("ix_reddit_posts_subreddit", table_name="reddit_posts")
    op.drop_table("reddit_posts")
