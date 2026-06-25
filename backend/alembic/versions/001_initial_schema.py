"""Initial database schema.

Revision ID: 001
Create Date: 2026-06-25
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "workspaces",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("role", sa.String(50), default="member"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "projects",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("jira_url", sa.String(500), nullable=False),
        sa.Column("jira_email", sa.String(255), nullable=False),
        sa.Column("jira_api_token", sa.String(500), nullable=False),
        sa.Column("jira_project_key", sa.String(50), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "sprints",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("jira_sprint_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("state", sa.String(50), default="active"),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("ended_at", sa.DateTime(), nullable=True),
        sa.Column("imported_at", sa.DateTime(), nullable=True),
        sa.Column("total_tickets", sa.Integer(), default=0),
        sa.Column("analysis_status", sa.String(50), default="pending"),
        sa.Column("analysis_data", sa.JSON(), nullable=True),
    )

    op.create_table(
        "tickets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("sprint_id", sa.Integer(), sa.ForeignKey("sprints.id"), nullable=False),
        sa.Column("key", sa.String(50), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("issue_type", sa.String(50), nullable=True),
        sa.Column("status", sa.String(50), nullable=True),
        sa.Column("priority", sa.String(50), nullable=True),
        sa.Column("assignee", sa.String(255), nullable=True),
        sa.Column("labels", sa.JSON(), nullable=True),
        sa.Column("story_points", sa.Integer(), nullable=True),
        sa.Column("acceptance_criteria", sa.JSON(), nullable=True),
        sa.Column("comments", sa.JSON(), nullable=True),
        sa.Column("analysis_data", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("tickets")
    op.drop_table("sprints")
    op.drop_table("projects")
    op.drop_table("users")
    op.drop_table("workspaces")
