import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.middleware.auth_middleware import get_current_user_required, require_role
from app.models.user import User
from app.services.job_service import (
    change_job_status,
    create_job,
    get_job,
    list_jobs,
    update_job,
)

logger = logging.getLogger(__name__)

router = APIRouter()

templates = Jinja2Templates(
    directory=str(Path(__file__).resolve().parent.parent / "templates")
)


@router.get("/jobs")
async def jobs_list_page(
    request: Request,
    user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
) -> Response:
    """List all jobs with optional status filter and pagination."""
    result = await list_jobs(
        db=db,
        page=page,
        page_size=page_size,
        status=status,
    )

    filters = {
        "status": status or "",
    }

    return templates.TemplateResponse(
        request,
        "jobs/list.html",
        context={
            "user": user,
            "jobs": result["items"],
            "total": result["total"],
            "current_page": result["page"],
            "total_pages": result["total_pages"],
            "filters": filters,
        },
    )


@router.get("/jobs/create")
async def job_create_form(
    request: Request,
    user: User = Depends(require_role("System Admin", "HR Recruiter")),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Render the create job form. Only System Admin and HR Recruiter can access."""
    managers = await _get_managers(db)

    return templates.TemplateResponse(
        request,
        "jobs/form.html",
        context={
            "user": user,
            "job": None,
            "managers": managers,
        },
    )


@router.post("/jobs/create")
async def job_create(
    request: Request,
    user: User = Depends(require_role("System Admin", "HR Recruiter")),
    db: AsyncSession = Depends(get_db),
    title: str = Form(...),
    department: str = Form(...),
    location: str = Form(...),
    job_type: str = Form(...),
    salary_min: Optional[str] = Form(None),
    salary_max: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    assigned_manager_id: Optional[str] = Form(None),
) -> Response:
    """Create a new job posting."""
    try:
        parsed_salary_min = _parse_salary(salary_min)
        parsed_salary_max = _parse_salary(salary_max)

        manager_id = assigned_manager_id if assigned_manager_id and assigned_manager_id.strip() else None

        job = await create_job(
            db=db,
            title=title.strip(),
            department=department.strip(),
            location=location.strip(),
            job_type=job_type.strip(),
            salary_min=parsed_salary_min,
            salary_max=parsed_salary_max,
            description=description.strip() if description else None,
            assigned_manager_id=manager_id,
            status="Draft",
            current_user=user,
        )

        logger.info("Job created by user %s: id=%s title=%s", user.username, job.id, job.title)
        return RedirectResponse(url=f"/jobs/{job.id}", status_code=303)

    except ValueError as e:
        logger.warning("Job creation failed: %s", str(e))
        managers = await _get_managers(db)
        return templates.TemplateResponse(
            request,
            "jobs/form.html",
            context={
                "user": user,
                "job": None,
                "managers": managers,
                "error": str(e),
            },
            status_code=400,
        )
    except Exception:
        logger.exception("Unexpected error creating job")
        managers = await _get_managers(db)
        return templates.TemplateResponse(
            request,
            "jobs/form.html",
            context={
                "user": user,
                "job": None,
                "managers": managers,
                "error": "An unexpected error occurred. Please try again.",
            },
            status_code=500,
        )


@router.get("/jobs/{job_id}")
async def job_detail_page(
    request: Request,
    job_id: str,
    user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """View job detail page."""
    job = await get_job(db=db, job_id=job_id)
    if job is None:
        return templates.TemplateResponse(
            request,
            "jobs/detail.html",
            context={
                "user": user,
                "job": None,
                "applications": [],
                "error": "Job not found.",
            },
            status_code=404,
        )

    applications = job.applications if job.applications else []

    return templates.TemplateResponse(
        request,
        "jobs/detail.html",
        context={
            "user": user,
            "job": job,
            "applications": applications,
        },
    )


@router.get("/jobs/{job_id}/edit")
async def job_edit_form(
    request: Request,
    job_id: str,
    user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Render the edit job form.

    Accessible to System Admin, HR Recruiter, and the assigned Hiring Manager.
    """
    job = await get_job(db=db, job_id=job_id)
    if job is None:
        return RedirectResponse(url="/jobs", status_code=303)

    if not _can_edit_job(user, job):
        logger.warning(
            "User %s (role=%s) attempted to edit job %s without permission",
            user.username,
            user.role,
            job_id,
        )
        return RedirectResponse(url=f"/jobs/{job_id}", status_code=303)

    managers = await _get_managers(db)

    return templates.TemplateResponse(
        request,
        "jobs/form.html",
        context={
            "user": user,
            "job": job,
            "managers": managers,
        },
    )


@router.post("/jobs/{job_id}/edit")
async def job_update(
    request: Request,
    job_id: str,
    user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
    title: str = Form(...),
    department: str = Form(...),
    location: str = Form(...),
    job_type: str = Form(...),
    salary_min: Optional[str] = Form(None),
    salary_max: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    assigned_manager_id: Optional[str] = Form(None),
    status: Optional[str] = Form(None),
) -> Response:
    """Update an existing job posting."""
    job = await get_job(db=db, job_id=job_id)
    if job is None:
        return RedirectResponse(url="/jobs", status_code=303)

    if not _can_edit_job(user, job):
        logger.warning(
            "User %s (role=%s) attempted to update job %s without permission",
            user.username,
            user.role,
            job_id,
        )
        return RedirectResponse(url=f"/jobs/{job_id}", status_code=303)

    try:
        parsed_salary_min = _parse_salary(salary_min)
        parsed_salary_max = _parse_salary(salary_max)

        manager_id = assigned_manager_id if assigned_manager_id and assigned_manager_id.strip() else None

        updated_job = await update_job(
            db=db,
            job_id=job_id,
            title=title.strip(),
            department=department.strip(),
            location=location.strip(),
            job_type=job_type.strip(),
            salary_min=parsed_salary_min,
            salary_max=parsed_salary_max,
            description=description.strip() if description else None,
            assigned_manager_id=manager_id,
            status=status.strip() if status else None,
            current_user=user,
        )

        if updated_job is None:
            return RedirectResponse(url="/jobs", status_code=303)

        logger.info("Job updated by user %s: id=%s", user.username, job_id)
        return RedirectResponse(url=f"/jobs/{job_id}", status_code=303)

    except ValueError as e:
        logger.warning("Job update failed for %s: %s", job_id, str(e))
        managers = await _get_managers(db)
        return templates.TemplateResponse(
            request,
            "jobs/form.html",
            context={
                "user": user,
                "job": job,
                "managers": managers,
                "error": str(e),
            },
            status_code=400,
        )
    except Exception:
        logger.exception("Unexpected error updating job %s", job_id)
        managers = await _get_managers(db)
        return templates.TemplateResponse(
            request,
            "jobs/form.html",
            context={
                "user": user,
                "job": job,
                "managers": managers,
                "error": "An unexpected error occurred. Please try again.",
            },
            status_code=500,
        )


@router.post("/jobs/{job_id}/status")
async def job_status_change(
    request: Request,
    job_id: str,
    user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
    status: str = Form(...),
) -> Response:
    """Change the status of a job posting.

    Accessible to System Admin, HR Recruiter, and the assigned Hiring Manager.
    """
    job = await get_job(db=db, job_id=job_id)
    if job is None:
        return RedirectResponse(url="/jobs", status_code=303)

    if not _can_edit_job(user, job):
        logger.warning(
            "User %s (role=%s) attempted to change status of job %s without permission",
            user.username,
            user.role,
            job_id,
        )
        return RedirectResponse(url=f"/jobs/{job_id}", status_code=303)

    new_status = status.strip()
    if not new_status:
        return RedirectResponse(url=f"/jobs/{job_id}", status_code=303)

    result = await change_job_status(
        db=db,
        job_id=job_id,
        new_status=new_status,
        current_user=user,
    )

    if not result["success"]:
        logger.warning(
            "Job status change failed for %s: %s",
            job_id,
            result.get("error", "Unknown error"),
        )

    return RedirectResponse(url=f"/jobs/{job_id}", status_code=303)


def _can_edit_job(user: User, job) -> bool:
    """Check if a user has permission to edit a job.

    System Admin and HR Recruiter can edit any job.
    Hiring Manager can edit jobs assigned to them.
    """
    if user.role in ("System Admin", "HR Recruiter"):
        return True

    if user.role == "Hiring Manager" and job.assigned_manager_id == user.id:
        return True

    return False


def _parse_salary(value: Optional[str]) -> Optional[float]:
    """Parse a salary string to float, returning None for empty/invalid values."""
    if value is None or not value.strip():
        return None
    try:
        parsed = float(value.strip())
        if parsed < 0:
            return None
        return parsed
    except (ValueError, TypeError):
        return None


async def _get_managers(db: AsyncSession) -> list[User]:
    """Get all active users who can be assigned as hiring managers."""
    result = await db.execute(
        select(User)
        .where(
            User.is_active == True,
            User.role.in_(["System Admin", "HR Recruiter", "Hiring Manager"]),
        )
        .order_by(User.full_name.asc())
    )
    return list(result.scalars().all())