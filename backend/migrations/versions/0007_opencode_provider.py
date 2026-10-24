"""Persist OpenCode auth profile reference and model selection."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0007_opencode_provider"
down_revision = "0006_ollama_provider"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "opencode_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("auth_secret_ref", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("selected_provider_id", sa.String(length=128), nullable=True),
        sa.Column("selected_model_id", sa.String(length=256), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("id = 1", name="ck_opencode_settings_singleton"),
        sa.CheckConstraint(
            "status IN ('not_configured', 'configured', 'connected', 'failed')",
            name="ck_opencode_settings_status",
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("opencode_settings")
