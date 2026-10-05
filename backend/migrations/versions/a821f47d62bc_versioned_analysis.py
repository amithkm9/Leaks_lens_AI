"""Preserve document analyses and bind evidence and decisions to revisions."""

import uuid
from alembic import op
import sqlalchemy as sa

revision = "a821f47d62bc"
down_revision = "7b42a8c91d03"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "documents", sa.Column("analysis_revision", sa.Integer(), nullable=False, server_default="0")
    )
    op.add_column("scan_jobs", sa.Column("analysis_request", sa.JSON(), nullable=False, server_default="{}"))
    for table in ("evidence", "findings", "reviews", "investigations"):
        op.add_column(table, sa.Column("analysis_revision", sa.Integer(), nullable=False, server_default="1"))
    op.add_column(
        "investigations", sa.Column("scope_snapshot", sa.JSON(), nullable=False, server_default="{}")
    )
    analyses = op.create_table(
        "document_analyses",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.Column("workspace_id", sa.String(36), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("document_id", sa.String(36), sa.ForeignKey("documents.id"), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.String(36), sa.ForeignKey("scan_jobs.id"), nullable=True),
        sa.Column("requested_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("input_name", sa.String(300), nullable=False),
        sa.Column("versions", sa.JSON(), nullable=False),
        sa.Column("organization_snapshot", sa.JSON(), nullable=False),
        sa.Column("redaction_status", sa.String(30), nullable=False),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("redacted_text", sa.Text(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("attribution", sa.JSON(), nullable=False),
        sa.Column("policy", sa.JSON(), nullable=False),
        sa.Column("related", sa.JSON(), nullable=False),
        sa.UniqueConstraint("document_id", "revision"),
        sa.UniqueConstraint("document_id", "job_id"),
    )
    op.create_index("ix_document_analyses_document_id", "document_analyses", ["document_id"])
    op.create_index("ix_document_analyses_workspace_id", "document_analyses", ["workspace_id"])
    bind = op.get_bind()
    metadata = sa.MetaData()
    documents = sa.Table("documents", metadata, autoload_with=bind)
    incidents = sa.Table("incidents", metadata, autoload_with=bind)
    for doc in bind.execute(sa.select(documents)).mappings():
        case = (
            bind.execute(sa.select(incidents).where(incidents.c.document_id == doc["id"])).mappings().first()
        )
        bind.execute(
            analyses.insert().values(
                id=str(uuid.uuid4()),
                created_at=doc["created_at"],
                workspace_id=doc["workspace_id"],
                document_id=doc["id"],
                revision=1,
                job_id=None,
                requested_by=None,
                reason="Migrated historical analysis; original pipeline/profile provenance was not recorded",
                input_name=doc["name"],
                versions={"legacy": True},
                organization_snapshot=[],
                redaction_status="restricted",
                category=doc["category"],
                redacted_text=doc["redacted_text"],
                metadata_json=doc["metadata_json"],
                summary=case["summary"] if case else "Historical document",
                attribution=case["attribution"] if case else [],
                policy=case["policy"] if case else {},
                related=case["related"] if case else [],
            )
        )
    bind.execute(documents.update().values(analysis_revision=1))


def downgrade():
    bind = op.get_bind()
    # A downgrade cannot represent multiple analyses. Refuse instead of silently
    # mixing historical findings into the old single-analysis application.
    count = bind.scalar(sa.text("SELECT COUNT(*) FROM document_analyses WHERE revision > 1"))
    if count:
        raise RuntimeError("Versioned analyses exist; restore a pre-upgrade backup with its matching code")
    op.drop_table("document_analyses")
    op.drop_column("investigations", "scope_snapshot")
    for table in ("evidence", "findings", "reviews", "investigations"):
        op.drop_column(table, "analysis_revision")
    op.drop_column("scan_jobs", "analysis_request")
    op.drop_column("documents", "analysis_revision")
