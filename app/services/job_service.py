import logging
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.constants import JobStatus, is_valid_job_transition
from app.models.job import Job
from app.models.user import User
from app.services.audit_service import log_action

logger = logging.getLogger(__name__)


async def create_job(
    db: AsyncSession,
    title: str,
    department: str,
    location: str,
    job_type: str,
    description: Optional[str] = None,
    salary_min: Optional[float] = None,
    salary_max: Optional[float] = None,
    assigned_manager_id: Optional[str] = None,
    status: str = "Draft",
    current_user: Optional[User] = None,
) -> Job:
    """Create a new job posting."""
    job = Job(
        title=title,
        department=department,
        location=location,
        job_type=job_type,
        description=description,
        salary_min=salary_min,
        salary_max=salary_max,
        assigned_manager_id=assigned_manager_id,
        status=status,
    )
    db.add(job)
    await db.flush()
    await db.refresh(job)

    if current_user:
        await log_action(
            db=db,
            user_id=current_user.id,
            username=current_user.username,
            action="CREATE",
            entity_type="Job",
            entity_id=job.id,
            details=f"Created job: {title}",
        )

    logger.info("Job created: id=%s title=%s", job.id, title)
    return job


async def update_job(
    db: AsyncSession,
    job_id: str,
    title: Optional[str] = None,
    department: Optional[str] = None,
    location: Optional[str] = None,
    job_type: Optional[str] = None,
    description: Optional[str] = None,
    salary_min: Optional[float] = None,
    salary_max: Optional[float] = None,
    assigned_manager_id: Optional[str] = None,
    status: Optional[str] = None,
    current_user: Optional[User] = None,
) -> Optional[Job]:
    """Update an existing job posting."""
    result = await db.execute(
        select(Job)
        .where(Job.id == job_id)
        .options(selectinload(Job.assigned_manager))
    )
    job = result.scalar_one_or_none()
    if job is None:
        return None

    changes: list[str] = []

    if title is not None and title != job.title:
        changes.append(f"title: '{job.title}' → '{title}'")
        job.title = title
    if department is not None and department != job.department:
        changes.append(f"department: '{job.department}' → '{department}'")
        job.department = department
    if location is not None and location != job.location:
        changes.append(f"location: '{job.location}' → '{location}'")
        job.location = location
    if job_type is not None and job_type != job.job_type:
        changes.append(f"job_type: '{job.job_type}' → '{job_type}'")
        job.job_type = job_type
    if description is not None:
        job.description = description
    if salary_min is not None:
        job.salary_min = salary_min
    if salary_max is not None:
        job.salary_max = salary_max
    if assigned_manager_id is not None:
        job.assigned_manager_id = assigned_manager_id if assigned_manager_id else None
    if status is not None and status != job.status:
        changes.append(f"status: '{job.status}' → '{status}'")
        job.status = status

    job.updated_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(job)

    if current_user and changes:
        await log_action(
            db=db,
            user_id=current_user.id,
            username=current_user.username,
            action="UPDATE",
            entity_type="Job",
            entity_id=job.id,
            details=f"Updated job: {', '.join(changes)}",
        )

    logger.info("Job updated: id=%s changes=%s", job_id, changes)
    return job


async def change_job_status(
    db: AsyncSession,
    job_id: str,
    new_status: str,
    current_user: Optional[User] = None,
) -> dict[str, Any]:
    """Change job status enforcing allowed transitions.

    Returns a dict with 'success' (bool), 'job' (Job or None), and 'error' (str or None).
    """
    result = await db.execute(
        select(Job)
        .where(Job.id == job_id)
        .options(selectinload(Job.assigned_manager))
    )
    job = result.scalar_one_or_none()
    if job is None:
        return {"success": False, "job": None, "error": "Job not found"}

    old_status = job.status

    if old_status == new_status:
        return {"success": True, "job": job, "error": None}

    if not is_valid_job_transition(old_status, new_status):
        error_msg = (
            f"Invalid status transition from '{old_status}' to '{new_status}'. "
            f"Allowed transitions from '{old_status}': "
            f"{', '.join(get_allowed_transitions(old_status)) or 'none'}"
        )
        logger.warning(
            "Invalid job status transition: job_id=%s from=%s to=%s",
            job_id,
            old_status,
            new_status,
        )
        return {"success": False, "job": job, "error": error_msg}

    job.status = new_status
    job.updated_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(job)

    if current_user:
        await log_action(
            db=db,
            user_id=current_user.id,
            username=current_user.username,
            action="STATUS_CHANGE",
            entity_type="Job",
            entity_id=job.id,
            details=f"Job status changed from '{old_status}' to '{new_status}'",
        )

    logger.info(
        "Job status changed: id=%s from=%s to=%s", job_id, old_status, new_status
    )
    return {"success": True, "job": job, "error": None}


def get_allowed_transitions(current_status: str) -> list[str]:
    """Get allowed status transitions for a given job status."""
    from app.core.constants import ALLOWED_JOB_TRANSITIONS

    return ALLOWED_JOB_TRANSITIONS.get(current_status, [])


async def get_job(
    db: AsyncSession,
    job_id: str,
) -> Optional[Job]:
    """Get a single job by ID with related data."""
    result = await db.execute(
        select(Job)
        .where(Job.id == job_id)
        .options(
            selectinload(Job.assigned_manager),
            selectinload(Job.applications),
        )
    )
    return result.scalar_one_or_none()


async def list_jobs(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 20,
    status: Optional[str] = None,
    manager_id: Optional[str] = None,
    search: Optional[str] = None,
) -> dict[str, Any]:
    """List jobs with pagination and filtering."""
    query = select(Job).options(selectinload(Job.assigned_manager))
    count_query = select(func.count(Job.id))

    if status:
        query = query.where(Job.status == status)
        count_query = count_query.where(Job.status == status)

    if manager_id:
        query = query.where(Job.assigned_manager_id == manager_id)
        count_query = count_query.where(Job.assigned_manager_id == manager_id)

    if search:
        search_filter = f"%{search}%"
        query = query.where(
            Job.title.ilike(search_filter)
            | Job.department.ilike(search_filter)
            | Job.location.ilike(search_filter)
        )
        count_query = count_query.where(
            Job.title.ilike(search_filter)
            | Job.department.ilike(search_filter)
            | Job.location.ilike(search_filter)
        )

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    if page < 1:
        page = 1
    if page_size < 1:
        page_size = 20
    if page_size > 100:
        page_size = 100

    total_pages = max(1, (total + page_size - 1) // page_size)
    offset = (page - 1) * page_size

    query = query.order_by(Job.created_at.desc()).offset(offset).limit(page_size)
    result = await db.execute(query)
    jobs = list(result.scalars().all())

    return {
        "items": jobs,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


async def get_published_jobs(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 50,
) -> dict[str, Any]:
    """Get published jobs for the public job board."""
    query = (
        select(Job)
        .where(Job.status == JobStatus.PUBLISHED.value)
        .options(selectinload(Job.assigned_manager))
    )
    count_query = select(func.count(Job.id)).where(
        Job.status == JobStatus.PUBLISHED.value
    )

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    if page < 1:
        page = 1
    if page_size < 1:
        page_size = 20
    if page_size > 100:
        page_size = 100

    total_pages = max(1, (total + page_size - 1) // page_size)
    offset = (page - 1) * page_size

    query = query.order_by(Job.created_at.desc()).offset(offset).limit(page_size)
    result = await db.execute(query)
    jobs = list(result.scalars().all())

    return {
        "items": jobs,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


async def get_all_jobs(db: AsyncSession) -> list[Job]:
    """Get all jobs (for dropdowns/selects)."""
    result = await db.execute(
        select(Job).order_by(Job.title.asc())
    )
    return list(result.scalars().all())


async def get_jobs_by_manager(
    db: AsyncSession,
    manager_id: str,
) -> list[Job]:
    """Get all jobs assigned to a specific manager."""
    result = await db.execute(
        select(Job)
        .where(Job.assigned_manager_id == manager_id)
        .options(
            selectinload(Job.assigned_manager),
            selectinload(Job.applications),
        )
        .order_by(Job.created_at.desc())
    )
    return list(result.scalars().all())


async def delete_job(
    db: AsyncSession,
    job_id: str,
    current_user: Optional[User] = None,
) -> bool:
    """Delete a job posting. Returns True if deleted, False if not found."""
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if job is None:
        return False

    job_title = job.title
    await db.delete(job)
    await db.flush()

    if current_user:
        await log_action(
            db=db,
            user_id=current_user.id,
            username=current_user.username,
            action="DELETE",
            entity_type="Job",
            entity_id=job_id,
            details=f"Deleted job: {job_title}",
        )

    logger.info("Job deleted: id=%s title=%s", job_id, job_title)
    return True