"""Source lifecycle, audit history, and scan configuration snapshots."""

from datetime import datetime, timezone
import uuid
from alembic import op
import sqlalchemy as sa

revision = "7b42a8c91d03"
down_revision = "1e1084787a6a"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("sources", sa.Column("revision", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("sources", sa.Column("archived_at", sa.String(40), nullable=True))
    op.add_column("scan_jobs", sa.Column("source_snapshot", sa.JSON(), nullable=False, server_default="{}"))
    op.add_column(
        "source_occurrences",
        sa.Column("access_context", sa.String(30), nullable=False, server_default="supplied"),
    )
    events = op.create_table(
        "source_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.Column("workspace_id", sa.String(36), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("source_id", sa.String(36), sa.ForeignKey("sources.id"), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("action", sa.String(30), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.UniqueConstraint("source_id", "revision"),
    )
    op.create_index("ix_source_events_source_id", "source_events", ["source_id"])
    op.create_index("ix_source_events_workspace_id", "source_events", ["workspace_id"])
    sources = sa.table(
        "sources",
        *[
            sa.column(name, kind)
            for name, kind in [
                ("id", sa.String),
                ("workspace_id", sa.String),
                ("name", sa.String),
                ("kind", sa.String),
                ("config", sa.JSON),
                ("access_context", sa.String),
            ]
        ],
    )
    occurrences = sa.table("source_occurrences", sa.column("source_id"), sa.column("access_context"))
    jobs = sa.table(
        "scan_jobs", sa.column("source_id"), sa.column("status"), sa.column("source_snapshot", sa.JSON)
    )
    bind = op.get_bind()
    timestamp = datetime.now(timezone.utc).isoformat()
    for source in bind.execute(sa.select(sources)).mappings():
        captured = {k: source[k] for k in ("name", "kind", "config", "access_context")}
        captured.update(revision=1, archived_at=None)
        bind.execute(
            events.insert().values(
                id=str(uuid.uuid4()),
                created_at=timestamp,
                workspace_id=source["workspace_id"],
                source_id=source["id"],
                user_id=None,
                action="migrated",
                revision=1,
                snapshot=captured,
            )
        )
        bind.execute(
            occurrences.update()
            .where(occurrences.c.source_id == source["id"])
            .values(access_context=source["access_context"])
        )
        # Only pending work can truthfully capture this configuration for execution.
        # Historical completed jobs retain an empty snapshot (unknown original revision).
        bind.execute(
            jobs.update()
            .where(jobs.c.source_id == source["id"], jobs.c.status.in_(["queued", "running"]))
            .values(source_snapshot=captured)
        )


def downgrade():
    op.drop_table("source_events")
    op.drop_column("source_occurrences", "access_context")
    op.drop_column("scan_jobs", "source_snapshot")
    op.drop_column("sources", "archived_at")
    op.drop_column("sources", "revision")
