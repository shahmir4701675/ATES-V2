"""Administrator audit trail with actor, action and local-time filtering."""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import Query, Request
from sqlalchemy import func, select

from backend.api.errors import problem
from backend.api.master import require_role
from backend.services.exports import KARACHI


def as_utc(stamp):
    return stamp.replace(tzinfo=stamp.tzinfo or KARACHI).astimezone(UTC).replace(tzinfo=None)


def register_audit(app, Current):
    @app.get("/audit", tags=["Audit trail"])
    def audit_log(request: Request, context: Current, username: Annotated[str, Query(max_length=40)] = "",
                  action: Annotated[str, Query(max_length=40)] = "", from_time: datetime | None = None,
                  to_time: datetime | None = None, page: Annotated[int, Query(ge=1, le=100_000)] = 1):
        connection, actor, _ = context
        require_role(actor, "Administrator")
        store = request.app.state.store
        logs = store["audit_logs"]
        users = store["users"]
        query = select(logs, users.c.username).outerjoin(users)
        if username:
            query = query.where(users.c.username == username)
        if action:
            query = query.where(logs.c.action == action)
        if from_time:
            query = query.where(logs.c.created_at >= as_utc(from_time))
        if to_time:
            query = query.where(logs.c.created_at <= as_utc(to_time))
        if from_time and to_time and as_utc(from_time) > as_utc(to_time):
            raise problem(422, "Choose an end time after the start time.", "to_time")
        total = connection.scalar(select(func.count()).select_from(query.subquery()))
        rows = connection.execute(query.order_by(logs.c.created_at.desc(), logs.c.log_id.desc())
                                  .limit(25).offset((page - 1) * 25)).mappings().all()
        return {"total": total, "page": page, "items": [
            {**row, "created_at": row["created_at"].replace(tzinfo=UTC).isoformat()} for row in rows
        ]}

