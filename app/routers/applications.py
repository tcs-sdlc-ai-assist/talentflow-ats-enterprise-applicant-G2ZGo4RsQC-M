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
from app.models.job import Job
from app.models.candidate import Candidate
from app.models.user import User
from app.services.application_service import (
    change_application_status,
    create_application,
    delete_application,
    get_application,
    get_applications_by_job,
    list_applications,
    update_application,
)
from app.services.job_service import get_all_jobs

logger = logging.getLogger(__name__)

router = APIRouter()

templates = Jinja2Templates(
    directory=str(Path(__file__).resolve().parent.parent / "templates")
)


@router.get("/applications")
async def applications_list(
    request: Request,
    user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    job_id: Optional[str] = Query(None),
) -> Response:
    """List all applications with optional filters and pagination."""
    result = await list_applications(
        db=db,
        page=page,
        page_size=page_size,
        status=status,
        job_id=job_id,
    )

    jobs_list = await get_all_jobs(db)

    status_options = [
        "Applied",
        "Screening",
        "Interview",
        "Offer",
        "Hired",
        "Rejected",
    ]

    filters = {
        "status": status or "",
        "job_id": job_id or "",
    }

    return templates.TemplateResponse(
        request,
        "applications/list.html",
        context={
            "user": user,
            "applications": result["items"],
            "total": result["total"],
            "current_page": result["page"],
            "page_size": result["page_size"],
            "total_pages": result["total_pages"],
            "status_options": status_options,
            "jobs": jobs_list,
            "filters": filters,
        },
    )


@router.get("/applications/pipeline")
async def applications_pipeline(
    request: Request,
    user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
    job_id: Optional[str] = Query(None),
) -> Response:
    """Kanban/pipeline view of applications grouped by status."""
    pipeline = await get_applications_by_job(db=db, job_id=job_id)

    job_filter = None
    if job_id:
        job_result = await db.execute(select(Job).where(Job.id == job_id))
        job = job_result.scalar_one_or_none()
        if job:
            job_filter = job.title

    return templates.TemplateResponse(
        request,
        "applications/pipeline.html",
        context={
            "user": user,
            "pipeline": pipeline,
            "job_filter": job_filter,
            "job_id": job_id or "",
        },
    )


@router.get("/applications/create")
async def application_create_form(
    request: Request,
    user: User = Depends(
        require_role("System Admin", "HR Recruiter", "Hiring Manager")
    ),
    db: AsyncSession = Depends(get_db),
    job_id: Optional[str] = Query(None),
    candidate_id: Optional[str] = Query(None),
) -> Response:
    """Render the create application form."""
    jobs_result = await db.execute(select(Job).order_by(Job.title.asc()))
    jobs = list(jobs_result.scalars().all())

    candidates_result = await db.execute(
        select(Candidate).order_by(Candidate.last_name.asc(), Candidate.first_name.asc())
    )
    candidates = list(candidates_result.scalars().all())

    return templates.TemplateResponse(
        request,
        "applications/create.html",
        context={
            "user": user,
            "jobs": jobs,
            "candidates": candidates,
            "selected_job_id": job_id or "",
            "selected_candidate_id": candidate_id or "",
            "error": None,
        },
    )


@router.post("/applications/create")
async def application_create(
    request: Request,
    user: User = Depends(
        require_role("System Admin", "HR Recruiter", "Hiring Manager")
    ),
    db: AsyncSession = Depends(get_db),
    job_id: str = Form(...),
    candidate_id: str = Form(...),
    cover_letter: str = Form(""),
    resume_url: str = Form(""),
    notes: str = Form(""),
) -> Response:
    """Create a new application."""
    try:
        application = await create_application(
            db=db,
            job_id=job_id,
            candidate_id=candidate_id,
            cover_letter=cover_letter if cover_letter.strip() else None,
            resume_url=resume_url if resume_url.strip() else None,
            notes=notes if notes.strip() else None,
            user_id=user.id,
            username=user.username,
        )
        return RedirectResponse(
            url=f"/applications/{application.id}",
            status_code=303,
        )
    except ValueError as e:
        logger.warning("Application creation failed: %s", str(e))

        jobs_result = await db.execute(select(Job).order_by(Job.title.asc()))
        jobs = list(jobs_result.scalars().all())

        candidates_result = await db.execute(
            select(Candidate).order_by(
                Candidate.last_name.asc(), Candidate.first_name.asc()
            )
        )
        candidates = list(candidates_result.scalars().all())

        return templates.TemplateResponse(
            request,
            "applications/create.html",
            context={
                "user": user,
                "jobs": jobs,
                "candidates": candidates,
                "selected_job_id": job_id,
                "selected_candidate_id": candidate_id,
                "error": str(e),
            },
            status_code=400,
        )
    except Exception:
        logger.exception("Unexpected error creating application")

        jobs_result = await db.execute(select(Job).order_by(Job.title.asc()))
        jobs = list(jobs_result.scalars().all())

        candidates_result = await db.execute(
            select(Candidate).order_by(
                Candidate.last_name.asc(), Candidate.first_name.asc()
            )
        )
        candidates = list(candidates_result.scalars().all())

        return templates.TemplateResponse(
            request,
            "applications/create.html",
            context={
                "user": user,
                "jobs": jobs,
                "candidates": candidates,
                "selected_job_id": job_id,
                "selected_candidate_id": candidate_id,
                "error": "An unexpected error occurred. Please try again.",
            },
            status_code=500,
        )


@router.get("/applications/{application_id}")
async def application_detail(
    request: Request,
    application_id: str,
    user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """View application detail page."""
    application = await get_application(db=db, application_id=application_id)

    if application is None:
        return templates.TemplateResponse(
            request,
            "applications/detail.html",
            context={
                "user": user,
                "application": None,
                "interviews": [],
                "error": "Application not found.",
            },
            status_code=404,
        )

    interviews = application.interviews if application.interviews else []

    return templates.TemplateResponse(
        request,
        "applications/detail.html",
        context={
            "user": user,
            "application": application,
            "interviews": interviews,
        },
    )


@router.get("/applications/{application_id}/edit")
async def application_edit_form(
    request: Request,
    application_id: str,
    user: User = Depends(
        require_role("System Admin", "HR Recruiter", "Hiring Manager")
    ),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Render the edit application form."""
    application = await get_application(db=db, application_id=application_id)

    if application is None:
        return RedirectResponse(url="/applications", status_code=303)

    return templates.TemplateResponse(
        request,
        "applications/edit.html",
        context={
            "user": user,
            "application": application,
            "error": None,
        },
    )


@router.post("/applications/{application_id}/edit")
async def application_edit(
    request: Request,
    application_id: str,
    user: User = Depends(
        require_role("System Admin", "HR Recruiter", "Hiring Manager")
    ),
    db: AsyncSession = Depends(get_db),
    cover_letter: str = Form(""),
    resume_url: str = Form(""),
    notes: str = Form(""),
) -> Response:
    """Update an existing application."""
    try:
        application = await update_application(
            db=db,
            application_id=application_id,
            cover_letter=cover_letter if cover_letter.strip() else None,
            resume_url=resume_url if resume_url.strip() else None,
            notes=notes if notes.strip() else None,
            user_id=user.id,
            username=user.username,
        )
        return RedirectResponse(
            url=f"/applications/{application.id}",
            status_code=303,
        )
    except ValueError as e:
        logger.warning("Application update failed: %s", str(e))

        application = await get_application(db=db, application_id=application_id)

        return templates.TemplateResponse(
            request,
            "applications/edit.html",
            context={
                "user": user,
                "application": application,
                "error": str(e),
            },
            status_code=400,
        )
    except Exception:
        logger.exception("Unexpected error updating application %s", application_id)

        application = await get_application(db=db, application_id=application_id)

        return templates.TemplateResponse(
            request,
            "applications/edit.html",
            context={
                "user": user,
                "application": application,
                "error": "An unexpected error occurred. Please try again.",
            },
            status_code=500,
        )


@router.post("/applications/{application_id}/status")
async def application_change_status(
    request: Request,
    application_id: str,
    user: User = Depends(
        require_role("System Admin", "HR Recruiter", "Hiring Manager")
    ),
    db: AsyncSession = Depends(get_db),
    status: str = Form(...),
) -> Response:
    """Change the status of an application."""
    try:
        await change_application_status(
            db=db,
            application_id=application_id,
            new_status=status,
            user_id=user.id,
            username=user.username,
        )
        return RedirectResponse(
            url=f"/applications/{application_id}",
            status_code=303,
        )
    except ValueError as e:
        logger.warning(
            "Application status change failed: app_id=%s error=%s",
            application_id,
            str(e),
        )
        return RedirectResponse(
            url=f"/applications/{application_id}",
            status_code=303,
        )
    except Exception:
        logger.exception(
            "Unexpected error changing application status: %s", application_id
        )
        return RedirectResponse(
            url=f"/applications/{application_id}",
            status_code=303,
        )


@router.post("/applications/{application_id}/delete")
async def application_delete(
    request: Request,
    application_id: str,
    user: User = Depends(
        require_role("System Admin", "HR Recruiter")
    ),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Delete an application."""
    try:
        await delete_application(
            db=db,
            application_id=application_id,
            user_id=user.id,
            username=user.username,
        )
        return RedirectResponse(url="/applications", status_code=303)
    except ValueError as e:
        logger.warning(
            "Application deletion failed: app_id=%s error=%s",
            application_id,
            str(e),
        )
        return RedirectResponse(
            url=f"/applications/{application_id}",
            status_code=303,
        )
    except Exception:
        logger.exception(
            "Unexpected error deleting application: %s", application_id
        )
        return RedirectResponse(
            url=f"/applications/{application_id}",
            status_code=303,
        )