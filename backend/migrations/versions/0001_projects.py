"""Create the projects table."""

import sqlalchemy as sa
from alembic import op

revision = "0001_projects"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.String(length=2000), nullable=False, server_default=""),
        sa.Column("repository_url", sa.String(length=2048), nullable=True),
        sa.Column("default_branch", sa.String(length=255), nullable=False, server_default="main"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("length(trim(name)) > 0", name="ck_projects_name_not_blank"),
    )
    op.create_index("ix_projects_name", "projects", ["name"])


def downgrade() -> None:
    op.drop_index("ix_projects_name", table_name="projects")
    op.drop_table("projects")
