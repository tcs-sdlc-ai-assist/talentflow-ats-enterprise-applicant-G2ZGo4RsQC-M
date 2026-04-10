import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog

logger = logging.getLogger(__name__)


async def log_action(
    db: AsyncSession,
    user_id: Optional[str],
    username: Optional[str],
    action: str,
    entity_type: str,
    entity_id: Optional[str] = None,
    details: Optional[str] = None,
) -> AuditLog:
    """Create an audit log entry."""
    try:
        audit_log = AuditLog(
            user_id=user_id,
            username=username,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details,
        )
        db.add(audit_log)
        await db.flush()
        logger.info(
            "Audit log created: user=%s action=%s entity_type=%s entity_id=%s",
            username or user_id,
            action,
            entity_type,
            entity_id,
        )
        return audit_log
    except Exception:
        logger.exception("Failed to create audit log entry")
        raise


async def get_audit_logs(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 20,
    user_id: Optional[str] = None,
    username: Optional[str] = None,
    action: Optional[str] = None,
    entity_type: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
) -> dict:
    """Get audit logs with pagination and filtering."""
    conditions = []

    if user_id:
        conditions.append(AuditLog.user_id == user_id)

    if username:
        conditions.append(AuditLog.username.ilike(f"%{username}%"))

    if action:
        conditions.append(AuditLog.action == action)

    if entity_type:
        conditions.append(AuditLog.entity_type == entity_type)

    if date_from:
        conditions.append(AuditLog.created_at >= date_from)

    if date_to:
        conditions.append(AuditLog.created_at <= date_to)

    where_clause = and_(*conditions) if conditions else True

    # Count total
    count_query = select(func.count()).select_from(AuditLog).where(where_clause)
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Calculate pagination
    if page < 1:
        page = 1
    if page_size < 1:
        page_size = 20
    if page_size > 100:
        page_size = 100

    total_pages = max(1, (total + page_size - 1) // page_size)
    offset = (page - 1) * page_size

    # Fetch logs
    query = (
        select(AuditLog)
        .where(where_clause)
        .order_by(AuditLog.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    result = await db.execute(query)
    logs = result.scalars().all()

    return {
        "items": logs,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


async def get_recent_audit_logs(
    db: AsyncSession,
    limit: int = 10,
) -> list[AuditLog]:
    """Get the most recent audit log entries."""
    query = (
        select(AuditLog)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_distinct_actions(db: AsyncSession) -> list[str]:
    """Get all distinct action values for filter dropdowns."""
    query = select(AuditLog.action).distinct().order_by(AuditLog.action)
    result = await db.execute(query)
    return [row[0] for row in result.all() if row[0]]


async def get_distinct_entity_types(db: AsyncSession) -> list[str]:
    """Get all distinct entity_type values for filter dropdowns."""
    query = select(AuditLog.entity_type).distinct().order_by(AuditLog.entity_type)
    result = await db.execute(query)
    return [row[0] for row in result.all() if row[0]]