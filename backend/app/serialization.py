"""Shared database record serialization and bounded list queries."""

from sqlalchemy import select, func


def record(row, exclude=()):
    return {
        column.name: getattr(row, column.name)
        for column in row.__table__.columns
        if column.name not in {*exclude, "workspace_id"}
    }


def page(db, model, workspace, offset=0, limit=50, extra=()):
    query = select(model).where(model.workspace_id == workspace, *extra)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.scalars(
        query.order_by(model.created_at.desc(), model.id.desc()).offset(offset).limit(limit)
    ).all()
    return {"items": [record(r) for r in rows], "total": total, "offset": offset, "limit": limit}
