"""Add single administrator credentials and revocable sessions."""

import sqlalchemy as sa
from alembic import op

revision = "0002_single_admin_auth"
down_revision = "0001_projects"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "admin_credential",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("password_hash", sa.String(512), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("id = 1", name="ck_admin_credential_singleton"),
    )
    op.create_table(
        "admin_sessions",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_admin_sessions_expires_at", "admin_sessions", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_admin_sessions_expires_at", table_name="admin_sessions")
    op.drop_table("admin_sessions")
    op.drop_table("admin_credential")
