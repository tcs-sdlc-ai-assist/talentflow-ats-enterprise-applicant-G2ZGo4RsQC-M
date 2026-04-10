import logging
from datetime import datetime
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
from app.services.interview_service import (
    get_interview,
    get_interview_feedbacks,
    get_interviews_for_user,
    list_interviews,
    schedule_interview,
    submit_feedback,
    update_interview_status,
    cancel_interview,
)
from app.services.application_service import get_application, list_applications
from app.services.job_service import get_all_jobs

logger = logging.getLogger(__name__)

router = APIRouter()

templates = Jinja2Templates(
    directory=str(Path(__file__).resolve().parent.parent / "templates")
)


@router.get("/interviews")
async def interviews_list(
    request: Request,
    user: User = Depends(
        require_role("System Admin", "HR Recruiter", "Hiring Manager")
    ),
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    job_id: Optional[str] = Query(None),
    interviewer_id: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
) -> Response:
    """List all interviews. Accessible to System Admin, HR Recruiter, Hiring Manager."""
    parsed_date_from = None
    parsed_date_to = None

    if date_from:
        try:
            parsed_date_from = datetime.strptime(date_from, "%Y-%m-%d")
        except ValueError:
            logger.warning("Invalid date_from format: %s", date_from)

    if date_to:
        try:
            parsed_date_to = datetime.strptime(date_to, "%Y-%m-%d").replace(
                hour=23, minute=59, second=59
            )
        except ValueError:
            logger.warning("Invalid date_to format: %s", date_to)

    result = await list_interviews(
        db=db,
        page=page,
        page_size=page_size,
        status=status,
        job_id=job_id,
        interviewer_id=interviewer_id,
        date_from=parsed_date_from,
        date_to=parsed_date_to,
    )

    jobs = await get_all_jobs(db)

    interviewers_result = await db.execute(
        select(User).where(User.is_active == True).order_by(User.full_name.asc())
    )
    interviewers = list(interviewers_result.scalars().all())

    enriched_interviews = []
    for interview in result["items"]:
        candidate = None
        job = None
        if interview.application:
            candidate = interview.application.candidate
            job = interview.application.job
        interview.candidate = candidate
        interview.job = job
        enriched_interviews.append(interview)

    filters = {
        "status": status or "",
        "job_id": job_id or "",
        "interviewer_id": interviewer_id or "",
        "date_from": date_from or "",
        "date_to": date_to or "",
    }

    return templates.TemplateResponse(
        request,
        "interviews/list.html",
        context={
            "user": user,
            "interviews": enriched_interviews,
            "jobs": jobs,
            "interviewers": interviewers,
            "filters": filters,
            "current_page": result["page"],
            "total_pages": result["total_pages"],
            "total_count": result["total"],
        },
    )


@router.get("/interviews/my")
async def my_interviews(
    request: Request,
    user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    feedback_status: Optional[str] = Query(None),
) -> Response:
    """List interviews assigned to the current user as interviewer."""
    result = await get_interviews_for_user(
        db=db,
        interviewer_id=user.id,
        page=page,
        page_size=page_size,
        status=status,
        feedback_status=feedback_status,
    )

    filters = {
        "status": status or "",
        "feedback_status": feedback_status or "",
    }

    return templates.TemplateResponse(
        request,
        "interviews/my.html",
        context={
            "user": user,
            "interviews": result["items"],
            "filters": filters,
            "current_page": result["page"],
            "total_pages": result["total_pages"],
            "total_count": result["total"],
        },
    )


@router.get("/interviews/create")
async def schedule_interview_form(
    request: Request,
    user: User = Depends(
        require_role("System Admin", "HR Recruiter", "Hiring Manager")
    ),
    db: AsyncSession = Depends(get_db),
    application_id: Optional[str] = Query(None),
) -> Response:
    """Render the interview scheduling form."""
    applications_result = await list_applications(db=db, page=1, page_size=200)
    applications = applications_result["items"]

    interviewers_result = await db.execute(
        select(User).where(User.is_active == True).order_by(User.full_name.asc())
    )
    interviewers = list(interviewers_result.scalars().all())

    selected_application = None
    if application_id:
        selected_application = await get_application(db, application_id)

    return templates.TemplateResponse(
        request,
        "interviews/schedule_form.html",
        context={
            "user": user,
            "applications": applications,
            "interviewers": interviewers,
            "selected_application": selected_application,
            "application_id": application_id or "",
            "error": None,
        },
    )


@router.post("/interviews/create")
async def schedule_interview_submit(
    request: Request,
    user: User = Depends(
        require_role("System Admin", "HR Recruiter", "Hiring Manager")
    ),
    db: AsyncSession = Depends(get_db),
    application_id: str = Form(...),
    interviewer_id: str = Form(...),
    scheduled_at: str = Form(...),
) -> Response:
    """Handle interview scheduling form submission."""
    try:
        parsed_scheduled_at = datetime.strptime(scheduled_at, "%Y-%m-%dT%H:%M")
    except ValueError:
        try:
            parsed_scheduled_at = datetime.strptime(scheduled_at, "%Y-%m-%d %H:%M")
        except ValueError:
            applications_result = await list_applications(db=db, page=1, page_size=200)
            interviewers_result = await db.execute(
                select(User)
                .where(User.is_active == True)
                .order_by(User.full_name.asc())
            )
            interviewers = list(interviewers_result.scalars().all())

            return templates.TemplateResponse(
                request,
                "interviews/schedule_form.html",
                context={
                    "user": user,
                    "applications": applications_result["items"],
                    "interviewers": interviewers,
                    "selected_application": None,
                    "application_id": application_id,
                    "error": "Invalid date/time format. Please use the date picker.",
                },
                status_code=400,
            )

    try:
        interview = await schedule_interview(
            db=db,
            application_id=application_id,
            interviewer_id=interviewer_id,
            scheduled_at=parsed_scheduled_at,
            current_user_id=user.id,
            current_username=user.username,
        )
        return RedirectResponse(
            url=f"/interviews/{interview.id}", status_code=303
        )
    except ValueError as e:
        applications_result = await list_applications(db=db, page=1, page_size=200)
        interviewers_result = await db.execute(
            select(User)
            .where(User.is_active == True)
            .order_by(User.full_name.asc())
        )
        interviewers = list(interviewers_result.scalars().all())

        return templates.TemplateResponse(
            request,
            "interviews/schedule_form.html",
            context={
                "user": user,
                "applications": applications_result["items"],
                "interviewers": interviewers,
                "selected_application": None,
                "application_id": application_id,
                "error": str(e),
            },
            status_code=400,
        )


@router.get("/interviews/{interview_id}")
async def interview_detail(
    request: Request,
    interview_id: str,
    user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """View interview details."""
    interview = await get_interview(db, interview_id)
    if interview is None:
        return templates.TemplateResponse(
            request,
            "interviews/list.html",
            context={
                "user": user,
                "interviews": [],
                "jobs": [],
                "interviewers": [],
                "filters": {},
                "current_page": 1,
                "total_pages": 1,
                "total_count": 0,
                "error": f"Interview with id '{interview_id}' not found.",
            },
            status_code=404,
        )

    feedbacks = await get_interview_feedbacks(db, interview_id)

    candidate = None
    job = None
    if interview.application:
        candidate = interview.application.candidate
        job = interview.application.job

    interview.candidate = candidate
    interview.job = job

    return templates.TemplateResponse(
        request,
        "interviews/detail.html",
        context={
            "user": user,
            "interview": interview,
            "feedbacks": feedbacks,
            "candidate": candidate,
            "job": job,
        },
    )


@router.get("/interviews/{interview_id}/feedback")
async def feedback_form(
    request: Request,
    interview_id: str,
    user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Render the feedback submission form for an interview."""
    interview = await get_interview(db, interview_id)
    if interview is None:
        return RedirectResponse(url="/interviews/my", status_code=303)

    candidate = None
    job = None
    if interview.application:
        candidate = interview.application.candidate
        job = interview.application.job

    interview.candidate = candidate
    interview.job = job

    existing_feedbacks = await get_interview_feedbacks(db, interview_id)

    user_has_submitted = any(
        fb.interviewer_id == user.id for fb in existing_feedbacks
    )

    return templates.TemplateResponse(
        request,
        "interviews/feedback_form.html",
        context={
            "user": user,
            "interview": interview,
            "candidate": candidate,
            "job": job,
            "feedbacks": existing_feedbacks,
            "user_has_submitted": user_has_submitted,
            "error": None,
            "success": None,
        },
    )


@router.post("/interviews/{interview_id}/feedback")
async def submit_feedback_handler(
    request: Request,
    interview_id: str,
    user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
    rating: int = Form(...),
    feedback: str = Form(...),
) -> Response:
    """Handle feedback form submission."""
    interview = await get_interview(db, interview_id)
    if interview is None:
        return RedirectResponse(url="/interviews/my", status_code=303)

    candidate = None
    job = None
    if interview.application:
        candidate = interview.application.candidate
        job = interview.application.job

    interview.candidate = candidate
    interview.job = job

    try:
        await submit_feedback(
            db=db,
            interview_id=interview_id,
            interviewer_id=user.id,
            rating=rating,
            feedback=feedback,
            current_user_id=user.id,
            current_username=user.username,
        )

        existing_feedbacks = await get_interview_feedbacks(db, interview_id)

        return templates.TemplateResponse(
            request,
            "interviews/feedback_form.html",
            context={
                "user": user,
                "interview": interview,
                "candidate": candidate,
                "job": job,
                "feedbacks": existing_feedbacks,
                "user_has_submitted": True,
                "error": None,
                "success": "Feedback submitted successfully!",
            },
        )
    except ValueError as e:
        existing_feedbacks = await get_interview_feedbacks(db, interview_id)
        user_has_submitted = any(
            fb.interviewer_id == user.id for fb in existing_feedbacks
        )

        return templates.TemplateResponse(
            request,
            "interviews/feedback_form.html",
            context={
                "user": user,
                "interview": interview,
                "candidate": candidate,
                "job": job,
                "feedbacks": existing_feedbacks,
                "user_has_submitted": user_has_submitted,
                "error": str(e),
                "success": None,
            },
            status_code=400,
        )


@router.post("/interviews/{interview_id}/cancel")
async def cancel_interview_handler(
    request: Request,
    interview_id: str,
    user: User = Depends(
        require_role("System Admin", "HR Recruiter", "Hiring Manager")
    ),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Cancel a scheduled interview."""
    try:
        await cancel_interview(
            db=db,
            interview_id=interview_id,
            current_user_id=user.id,
            current_username=user.username,
        )
        return RedirectResponse(
            url=f"/interviews/{interview_id}", status_code=303
        )
    except ValueError as e:
        logger.warning(
            "Failed to cancel interview %s: %s", interview_id, str(e)
        )
        return RedirectResponse(url="/interviews", status_code=303)


@router.post("/interviews/{interview_id}/status")
async def update_status_handler(
    request: Request,
    interview_id: str,
    user: User = Depends(
        require_role("System Admin", "HR Recruiter", "Hiring Manager")
    ),
    db: AsyncSession = Depends(get_db),
    status: str = Form(...),
) -> Response:
    """Update interview status."""
    try:
        await update_interview_status(
            db=db,
            interview_id=interview_id,
            new_status=status,
            current_user_id=user.id,
            current_username=user.username,
        )
        return RedirectResponse(
            url=f"/interviews/{interview_id}", status_code=303
        )
    except ValueError as e:
        logger.warning(
            "Failed to update interview %s status: %s",
            interview_id,
            str(e),
        )
        return RedirectResponse(
            url=f"/interviews/{interview_id}", status_code=303
        )