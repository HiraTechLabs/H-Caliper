"""Persist Ollama endpoint validation and discovered model identifiers."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0006_ollama_provider"
down_revision = "0005_durable_task_runner"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ollama_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("endpoint_url", sa.String(length=512), nullable=False),
        sa.Column("selected_model_id", sa.String(length=256), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column(
            "models", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"
        ),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("id = 1", name="ck_ollama_settings_singleton"),
        sa.CheckConstraint(
            "status IN ('not_configured', 'configured', 'reachable', 'failed')",
            name="ck_ollama_settings_status",
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("ollama_settings")
