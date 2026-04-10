import logging
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import func, select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.application import Application
from app.models.candidate import Candidate
from app.models.job import Job
from app.core.constants import ApplicationStatus, ALLOWED_APPLICATION_TRANSITIONS, is_valid_application_transition
from app.services.audit_service import log_action

logger = logging.getLogger(__name__)


async def create_application(
    db: AsyncSession,
    job_id: str,
    candidate_id: str,
    cover_letter: Optional[str] = None,
    resume_url: Optional[str] = None,
    notes: Optional[str] = None,
    user_id: Optional[str] = None,
    username: Optional[str] = None,
) -> Application:
    """Create a new application for a candidate to a job."""
    # Verify job exists
    job_result = await db.execute(select(Job).where(Job.id == job_id))
    job = job_result.scalar_one_or_none()
    if job is None:
        raise ValueError(f"Job with id '{job_id}' not found")

    # Verify candidate exists
    candidate_result = await db.execute(select(Candidate).where(Candidate.id == candidate_id))
    candidate = candidate_result.scalar_one_or_none()
    if candidate is None:
        raise ValueError(f"Candidate with id '{candidate_id}' not found")

    # Check for duplicate application
    existing_result = await db.execute(
        select(Application).where(
            Application.job_id == job_id,
            Application.candidate_id == candidate_id,
        )
    )
    existing = existing_result.scalar_one_or_none()
    if existing is not None:
        raise ValueError("This candidate has already applied for this job")

    now = datetime.now(timezone.utc)
    application = Application(
        job_id=job_id,
        candidate_id=candidate_id,
        status=ApplicationStatus.APPLIED.value,
        cover_letter=cover_letter,
        resume_url=resume_url,
        notes=notes,
        applied_at=now,
        created_at=now,
        updated_at=now,
    )
    db.add(application)
    await db.flush()

    try:
        await log_action(
            db=db,
            user_id=user_id,
            username=username,
            action="CREATE",
            entity_type="Application",
            entity_id=application.id,
            details=f"Application created for candidate '{candidate_id}' to job '{job_id}'",
        )
    except Exception:
        logger.exception("Failed to log audit for application creation")

    logger.info(
        "Application created: id=%s job_id=%s candidate_id=%s",
        application.id,
        job_id,
        candidate_id,
    )
    return application


async def get_application(
    db: AsyncSession,
    application_id: str,
) -> Optional[Application]:
    """Get a single application by ID with related job and candidate."""
    result = await db.execute(
        select(Application)
        .where(Application.id == application_id)
        .options(
            selectinload(Application.job),
            selectinload(Application.candidate).selectinload(Candidate.skills),
            selectinload(Application.interviews),
        )
    )
    return result.scalar_one_or_none()


async def list_applications(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 20,
    status: Optional[str] = None,
    job_id: Optional[str] = None,
    candidate_id: Optional[str] = None,
) -> dict[str, Any]:
    """List applications with optional filters and pagination."""
    conditions = []

    if status:
        conditions.append(Application.status == status)
    if job_id:
        conditions.append(Application.job_id == job_id)
    if candidate_id:
        conditions.append(Application.candidate_id == candidate_id)

    where_clause = and_(*conditions) if conditions else True

    # Count total
    count_query = select(func.count()).select_from(Application).where(where_clause)
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Pagination
    if page < 1:
        page = 1
    if page_size < 1:
        page_size = 20
    if page_size > 100:
        page_size = 100

    total_pages = max(1, (total + page_size - 1) // page_size)
    offset = (page - 1) * page_size

    # Fetch applications
    query = (
        select(Application)
        .where(where_clause)
        .options(
            selectinload(Application.job),
            selectinload(Application.candidate),
        )
        .order_by(Application.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    result = await db.execute(query)
    applications = list(result.scalars().all())

    return {
        "items": applications,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


async def change_application_status(
    db: AsyncSession,
    application_id: str,
    new_status: str,
    user_id: Optional[str] = None,
    username: Optional[str] = None,
) -> Application:
    """Change the status of an application, enforcing allowed transitions."""
    result = await db.execute(
        select(Application)
        .where(Application.id == application_id)
        .options(
            selectinload(Application.job),
            selectinload(Application.candidate),
        )
    )
    application = result.scalar_one_or_none()
    if application is None:
        raise ValueError(f"Application with id '{application_id}' not found")

    old_status = application.status

    # Validate the transition
    if not is_valid_application_transition(old_status, new_status):
        allowed = ALLOWED_APPLICATION_TRANSITIONS.get(old_status, [])
        allowed_str = ", ".join(allowed) if allowed else "none"
        raise ValueError(
            f"Cannot transition from '{old_status}' to '{new_status}'. "
            f"Allowed transitions from '{old_status}': {allowed_str}"
        )

    application.status = new_status
    application.updated_at = datetime.now(timezone.utc)
    await db.flush()

    try:
        await log_action(
            db=db,
            user_id=user_id,
            username=username,
            action="STATUS_CHANGE",
            entity_type="Application",
            entity_id=application.id,
            details=f"Status changed from '{old_status}' to '{new_status}'",
        )
    except Exception:
        logger.exception("Failed to log audit for application status change")

    logger.info(
        "Application status changed: id=%s from=%s to=%s",
        application_id,
        old_status,
        new_status,
    )
    return application


async def update_application(
    db: AsyncSession,
    application_id: str,
    cover_letter: Optional[str] = None,
    resume_url: Optional[str] = None,
    notes: Optional[str] = None,
    user_id: Optional[str] = None,
    username: Optional[str] = None,
) -> Application:
    """Update application fields (cover letter, resume URL, notes)."""
    result = await db.execute(
        select(Application)
        .where(Application.id == application_id)
        .options(
            selectinload(Application.job),
            selectinload(Application.candidate),
        )
    )
    application = result.scalar_one_or_none()
    if application is None:
        raise ValueError(f"Application with id '{application_id}' not found")

    updated_fields = []
    if cover_letter is not None:
        application.cover_letter = cover_letter
        updated_fields.append("cover_letter")
    if resume_url is not None:
        application.resume_url = resume_url
        updated_fields.append("resume_url")
    if notes is not None:
        application.notes = notes
        updated_fields.append("notes")

    if updated_fields:
        application.updated_at = datetime.now(timezone.utc)
        await db.flush()

        try:
            await log_action(
                db=db,
                user_id=user_id,
                username=username,
                action="UPDATE",
                entity_type="Application",
                entity_id=application.id,
                details=f"Updated fields: {', '.join(updated_fields)}",
            )
        except Exception:
            logger.exception("Failed to log audit for application update")

    return application


async def delete_application(
    db: AsyncSession,
    application_id: str,
    user_id: Optional[str] = None,
    username: Optional[str] = None,
) -> bool:
    """Delete an application by ID."""
    result = await db.execute(
        select(Application).where(Application.id == application_id)
    )
    application = result.scalar_one_or_none()
    if application is None:
        raise ValueError(f"Application with id '{application_id}' not found")

    await db.delete(application)
    await db.flush()

    try:
        await log_action(
            db=db,
            user_id=user_id,
            username=username,
            action="DELETE",
            entity_type="Application",
            entity_id=application_id,
            details=f"Application deleted (job_id={application.job_id}, candidate_id={application.candidate_id})",
        )
    except Exception:
        logger.exception("Failed to log audit for application deletion")

    logger.info("Application deleted: id=%s", application_id)
    return True


async def get_applications_by_job(
    db: AsyncSession,
    job_id: Optional[str] = None,
) -> dict[str, list[dict[str, Any]]]:
    """Get applications grouped by status for kanban/pipeline view.

    Returns a dict keyed by status with lists of application summary dicts.
    """
    statuses = [
        ApplicationStatus.APPLIED.value,
        ApplicationStatus.SCREENING.value,
        ApplicationStatus.INTERVIEW.value,
        ApplicationStatus.OFFER.value,
        ApplicationStatus.HIRED.value,
        ApplicationStatus.REJECTED.value,
    ]

    pipeline: dict[str, list[dict[str, Any]]] = {status: [] for status in statuses}

    conditions = []
    if job_id:
        conditions.append(Application.job_id == job_id)

    where_clause = and_(*conditions) if conditions else True

    query = (
        select(Application)
        .where(where_clause)
        .options(
            selectinload(Application.job),
            selectinload(Application.candidate),
        )
        .order_by(Application.applied_at.desc())
    )
    result = await db.execute(query)
    applications = list(result.scalars().all())

    for app in applications:
        candidate_name = "Unknown Candidate"
        if app.candidate:
            candidate_name = f"{app.candidate.first_name} {app.candidate.last_name}"

        job_title = "Unknown Position"
        if app.job:
            job_title = app.job.title

        applied_at_str = None
        if app.applied_at:
            applied_at_str = app.applied_at.strftime("%b %d, %Y")

        app_summary = {
            "id": app.id,
            "candidate_name": candidate_name,
            "candidate_id": app.candidate_id,
            "job_title": job_title,
            "job_id": app.job_id,
            "status": app.status,
            "applied_at": applied_at_str,
        }

        status_key = app.status
        if status_key in pipeline:
            pipeline[status_key].append(app_summary)
        else:
            # If status doesn't match known statuses, put in Applied
            pipeline[ApplicationStatus.APPLIED.value].append(app_summary)

    return pipeline


async def get_applications_for_candidate(
    db: AsyncSession,
    candidate_id: str,
) -> list[Application]:
    """Get all applications for a specific candidate."""
    result = await db.execute(
        select(Application)
        .where(Application.candidate_id == candidate_id)
        .options(
            selectinload(Application.job),
        )
        .order_by(Application.created_at.desc())
    )
    return list(result.scalars().all())


async def get_application_status_counts(
    db: AsyncSession,
    job_id: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Get application counts grouped by status, optionally filtered by job."""
    query = (
        select(Application.status, func.count(Application.id))
        .group_by(Application.status)
        .order_by(Application.status)
    )

    if job_id:
        query = query.where(Application.job_id == job_id)

    result = await db.execute(query)
    return [
        {"status": row[0], "count": row[1]}
        for row in result.all()
    ]