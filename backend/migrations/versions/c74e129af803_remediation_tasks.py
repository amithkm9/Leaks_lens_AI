"""Remediation ownership, deadlines, verification, and append-only history."""

from alembic import op
import sqlalchemy as sa

revision = "c74e129af803"
down_revision = "a821f47d62bc"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "remediation_tasks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.Column("workspace_id", sa.String(36), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("incident_id", sa.String(36), sa.ForeignKey("incidents.id"), nullable=False),
        sa.Column("analysis_revision", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("owner_id", sa.String(36), sa.ForeignKey("users.id")),
        sa.Column("due_date", sa.String(10)),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("action_taken", sa.Text(), nullable=False),
        sa.Column("evidence_ids", sa.JSON(), nullable=False),
        sa.Column("verification_method", sa.String(40)),
        sa.Column("verification_notes", sa.Text(), nullable=False),
        sa.Column("verified_by", sa.String(36), sa.ForeignKey("users.id")),
        sa.Column("verified_at", sa.String(40)),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.String(40), nullable=False),
    )
    op.create_index("ix_remediation_tasks_workspace_id", "remediation_tasks", ["workspace_id"])
    op.create_index("ix_remediation_tasks_incident_id", "remediation_tasks", ["incident_id"])
    op.create_index("ix_remediation_tasks_queue", "remediation_tasks", ["workspace_id", "status", "due_date"])
    op.create_table(
        "remediation_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.Column("workspace_id", sa.String(36), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("task_id", sa.String(36), sa.ForeignKey("remediation_tasks.id"), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.UniqueConstraint("task_id", "revision"),
    )
    op.create_index("ix_remediation_events_workspace_id", "remediation_events", ["workspace_id"])
    op.create_index("ix_remediation_events_task_id", "remediation_events", ["task_id"])


def downgrade():
    if op.get_bind().scalar(sa.text("SELECT COUNT(*) FROM remediation_tasks")):
        raise RuntimeError("Remediation tasks exist; restore a pre-upgrade backup to preserve the audit trail")
    op.drop_table("remediation_events")
    op.drop_table("remediation_tasks")
