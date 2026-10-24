"""Persist repository synchronization work for the in-process task runner."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0005_durable_task_runner"
down_revision = "0004_repository_knowledge_sync"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tasks",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "project_id",
            sa.Uuid(),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(length=48), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.CheckConstraint("kind IN ('repository_sync')", name="ck_tasks_supported_kind"),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'failed')",
            name="ck_tasks_status",
        ),
    )
    op.create_index("ix_tasks_claim", "tasks", ["status", "created_at"])
    op.create_index("ix_tasks_project", "tasks", ["project_id", "created_at"])
    op.drop_constraint("ck_project_sync_status", "project_syncs", type_="check")
    op.create_check_constraint(
        "ck_project_sync_status",
        "project_syncs",
        "status IN ('queued', 'running', 'synchronized', 'stale', 'failed')",
    )
    op.add_column("project_syncs", sa.Column("task_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_project_syncs_task_id_tasks",
        "project_syncs",
        "tasks",
        ["task_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_unique_constraint("uq_project_syncs_task_id", "project_syncs", ["task_id"])


def downgrade() -> None:
    op.drop_constraint("uq_project_syncs_task_id", "project_syncs", type_="unique")
    op.drop_constraint("fk_project_syncs_task_id_tasks", "project_syncs", type_="foreignkey")
    op.drop_column("project_syncs", "task_id")
    op.drop_constraint("ck_project_sync_status", "project_syncs", type_="check")
    op.create_check_constraint(
        "ck_project_sync_status",
        "project_syncs",
        "status IN ('running', 'synchronized', 'stale', 'failed')",
    )
    op.drop_index("ix_tasks_project", table_name="tasks")
    op.drop_index("ix_tasks_claim", table_name="tasks")
    op.drop_table("tasks")
