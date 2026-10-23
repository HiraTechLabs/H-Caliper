"""Add project-scoped credential references and lifecycle metadata."""

import sqlalchemy as sa
from alembic import op

revision = "0003_project_credentials"
down_revision = "0002_single_admin_auth"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "credentials",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column(
            "username", sa.String(length=255), nullable=False, server_default="x-access-token"
        ),
        sa.Column("secret_ref", sa.Uuid(), nullable=False),
        sa.Column("cleanup_secret_ref", sa.Uuid(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="configured"),
        sa.Column("deletion_pending", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("length(trim(name)) > 0", name="ck_credentials_name_not_blank"),
        sa.CheckConstraint("kind IN ('https_token')", name="ck_credentials_supported_kind"),
        sa.CheckConstraint(
            "status IN ('configured', 'reachable', 'validated', 'authenticated', 'failed', 'deleting')",
            name="ck_credentials_status",
        ),
        sa.UniqueConstraint("project_id", "name", name="uq_credentials_project_name"),
    )
    op.create_index("ix_credentials_project", "credentials", ["project_id"])
    op.create_index("ix_credentials_cleanup", "credentials", ["cleanup_secret_ref"])


def downgrade() -> None:
    op.drop_index("ix_credentials_cleanup", table_name="credentials")
    op.drop_index("ix_credentials_project", table_name="credentials")
    op.drop_table("credentials")
