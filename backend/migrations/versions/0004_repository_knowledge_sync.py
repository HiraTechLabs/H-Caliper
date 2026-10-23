"""Add durable repository sync status and derived knowledge snapshots."""

import sqlalchemy as sa
from alembic import op

revision = "0004_repository_knowledge_sync"
down_revision = "0003_project_credentials"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "project_syncs",
        sa.Column(
            "project_id",
            sa.Uuid(),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("source_url", sa.String(length=2048), nullable=False),
        sa.Column("branch", sa.String(length=255), nullable=False),
        sa.Column("revision", sa.String(length=64), nullable=True),
        sa.Column("attempted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.CheckConstraint(
            "status IN ('running', 'synchronized', 'stale', 'failed')",
            name="ck_project_sync_status",
        ),
    )
    op.create_table(
        "knowledge_files",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "project_id",
            sa.Uuid(),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("path", sa.String(length=2048), nullable=False),
        sa.Column("revision", sa.String(length=64), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "path", name="uq_knowledge_project_path"),
    )
    op.create_index("ix_knowledge_project_revision", "knowledge_files", ["project_id", "revision"])


def downgrade() -> None:
    op.drop_index("ix_knowledge_project_revision", table_name="knowledge_files")
    op.drop_table("knowledge_files")
    op.drop_table("project_syncs")
