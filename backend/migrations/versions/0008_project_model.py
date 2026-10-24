"""Persist a model selection per project."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_project_model"
down_revision: str | None = "0007_opencode_provider"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "project_model_settings",
        sa.Column(
            "project_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("provider_type", sa.String(32), nullable=False),
        sa.Column("provider_id", sa.String(128), nullable=False),
        sa.Column("model_id", sa.String(256), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "provider_type IN ('ollama', 'opencode')", name="ck_project_model_provider_type"
        ),
    )


def downgrade() -> None:
    op.drop_table("project_model_settings")
