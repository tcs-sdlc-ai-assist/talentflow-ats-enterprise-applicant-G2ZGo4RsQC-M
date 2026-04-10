import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.middleware.auth_middleware import get_current_user_required, get_optional_user, require_role
from app.models.user import User
from app.services.candidate_service import (
    create_candidate,
    delete_candidate,
    get_all_skill_names,
    get_candidate,
    list_candidates,
    search_candidates,
    update_candidate,
)
from app.services.application_service import get_applications_for_candidate
from app.services.audit_service import log_action

logger = logging.getLogger(__name__)

router = APIRouter()

templates = Jinja2Templates(
    directory=str(Path(__file__).resolve().parent.parent / "templates")
)


@router.get("/candidates")
async def candidates_list(
    request: Request,
    user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    search: Optional[str] = Query(None),
    skill: Optional[str] = Query(None),
) -> Response:
    """List candidates with optional search and skill filter."""
    skills_list = []
    if skill:
        skills_list = [skill]

    if search or skills_list:
        result = await search_candidates(
            db=db,
            query=search,
            skills=skills_list if skills_list else None,
            page=page,
            page_size=20,
        )
    else:
        result = await list_candidates(
            db=db,
            page=page,
            page_size=20,
        )

    all_skills = await get_all_skill_names(db)

    candidates = result["items"]
    # Convert skill objects to skill name strings for template display
    candidates_for_template = []
    for c in candidates:
        skill_names = []
        if c.skills:
            skill_names = [s.name for s in c.skills]
        c._skill_names = skill_names
        candidates_for_template.append(c)

    return templates.TemplateResponse(
        request,
        "candidates/list.html",
        context={
            "user": user,
            "candidates": candidates_for_template,
            "skills": all_skills,
            "search": search or "",
            "skill_filter": skill or "",
            "page": result["page"],
            "total_pages": result["total_pages"],
            "total": result["total"],
        },
    )


@router.get("/candidates/create")
async def candidates_create_form(
    request: Request,
    user: User = Depends(require_role("System Admin", "HR Recruiter")),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Render the create candidate form."""
    return templates.TemplateResponse(
        request,
        "candidates/form.html",
        context={
            "user": user,
            "candidate": None,
            "error": None,
            "skill_names": "",
        },
    )


@router.post("/candidates/create")
async def candidates_create(
    request: Request,
    user: User = Depends(require_role("System Admin", "HR Recruiter")),
    db: AsyncSession = Depends(get_db),
    first_name: str = Form(...),
    last_name: str = Form(...),
    email: str = Form(...),
    phone: str = Form(""),
    skill_names: str = Form(""),
    resume_text: str = Form(""),
) -> Response:
    """Create a new candidate."""
    parsed_skills = []
    if skill_names and skill_names.strip():
        parsed_skills = [s.strip() for s in skill_names.split(",") if s.strip()]

    try:
        candidate = await create_candidate(
            db=db,
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone=phone if phone else None,
            resume_text=resume_text if resume_text else None,
            skill_names=parsed_skills if parsed_skills else None,
        )

        try:
            await log_action(
                db=db,
                user_id=user.id,
                username=user.username,
                action="CREATE",
                entity_type="Candidate",
                entity_id=candidate.id,
                details=f"Created candidate: {first_name} {last_name} ({email})",
            )
        except Exception:
            logger.exception("Failed to log audit for candidate creation")

        return RedirectResponse(
            url=f"/candidates/{candidate.id}",
            status_code=303,
        )

    except ValueError as e:
        logger.warning("Candidate creation failed: %s", str(e))
        return templates.TemplateResponse(
            request,
            "candidates/form.html",
            context={
                "user": user,
                "candidate": None,
                "error": str(e),
                "skill_names": skill_names,
            },
            status_code=400,
        )
    except Exception:
        logger.exception("Unexpected error creating candidate")
        return templates.TemplateResponse(
            request,
            "candidates/form.html",
            context={
                "user": user,
                "candidate": None,
                "error": "An unexpected error occurred. Please try again.",
                "skill_names": skill_names,
            },
            status_code=500,
        )


@router.get("/candidates/{candidate_id}")
async def candidates_detail(
    request: Request,
    candidate_id: str,
    user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """View candidate detail page."""
    candidate = await get_candidate(db=db, candidate_id=candidate_id)
    if candidate is None:
        return templates.TemplateResponse(
            request,
            "candidates/list.html",
            context={
                "user": user,
                "candidates": [],
                "skills": [],
                "search": "",
                "skill_filter": "",
                "page": 1,
                "total_pages": 1,
                "total": 0,
                "error": f"Candidate with ID '{candidate_id}' not found.",
            },
            status_code=404,
        )

    applications = await get_applications_for_candidate(db=db, candidate_id=candidate_id)

    return templates.TemplateResponse(
        request,
        "candidates/detail.html",
        context={
            "user": user,
            "candidate": candidate,
            "applications": applications,
        },
    )


@router.get("/candidates/{candidate_id}/edit")
async def candidates_edit_form(
    request: Request,
    candidate_id: str,
    user: User = Depends(require_role("System Admin", "HR Recruiter")),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Render the edit candidate form."""
    candidate = await get_candidate(db=db, candidate_id=candidate_id)
    if candidate is None:
        return RedirectResponse(url="/candidates", status_code=303)

    skill_names_str = ""
    if candidate.skills:
        skill_names_str = ", ".join(s.name for s in candidate.skills)

    return templates.TemplateResponse(
        request,
        "candidates/form.html",
        context={
            "user": user,
            "candidate": candidate,
            "error": None,
            "skill_names": skill_names_str,
        },
    )


@router.post("/candidates/{candidate_id}/edit")
async def candidates_update(
    request: Request,
    candidate_id: str,
    user: User = Depends(require_role("System Admin", "HR Recruiter")),
    db: AsyncSession = Depends(get_db),
    first_name: str = Form(...),
    last_name: str = Form(...),
    email: str = Form(...),
    phone: str = Form(""),
    skill_names: str = Form(""),
    resume_text: str = Form(""),
) -> Response:
    """Update an existing candidate."""
    parsed_skills = []
    if skill_names and skill_names.strip():
        parsed_skills = [s.strip() for s in skill_names.split(",") if s.strip()]

    try:
        candidate = await update_candidate(
            db=db,
            candidate_id=candidate_id,
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone=phone if phone else None,
            resume_text=resume_text if resume_text else None,
            skill_names=parsed_skills,
        )

        if candidate is None:
            return RedirectResponse(url="/candidates", status_code=303)

        try:
            await log_action(
                db=db,
                user_id=user.id,
                username=user.username,
                action="UPDATE",
                entity_type="Candidate",
                entity_id=candidate_id,
                details=f"Updated candidate: {first_name} {last_name} ({email})",
            )
        except Exception:
            logger.exception("Failed to log audit for candidate update")

        return RedirectResponse(
            url=f"/candidates/{candidate_id}",
            status_code=303,
        )

    except ValueError as e:
        logger.warning("Candidate update failed: %s", str(e))
        existing_candidate = await get_candidate(db=db, candidate_id=candidate_id)
        return templates.TemplateResponse(
            request,
            "candidates/form.html",
            context={
                "user": user,
                "candidate": existing_candidate,
                "error": str(e),
                "skill_names": skill_names,
            },
            status_code=400,
        )
    except Exception:
        logger.exception("Unexpected error updating candidate")
        existing_candidate = await get_candidate(db=db, candidate_id=candidate_id)
        return templates.TemplateResponse(
            request,
            "candidates/form.html",
            context={
                "user": user,
                "candidate": existing_candidate,
                "error": "An unexpected error occurred. Please try again.",
                "skill_names": skill_names,
            },
            status_code=500,
        )


@router.post("/candidates/{candidate_id}/delete")
async def candidates_delete(
    request: Request,
    candidate_id: str,
    user: User = Depends(require_role("System Admin", "HR Recruiter")),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Delete a candidate."""
    try:
        candidate = await get_candidate(db=db, candidate_id=candidate_id)
        candidate_name = ""
        if candidate:
            candidate_name = f"{candidate.first_name} {candidate.last_name}"

        deleted = await delete_candidate(db=db, candidate_id=candidate_id)

        if deleted:
            try:
                await log_action(
                    db=db,
                    user_id=user.id,
                    username=user.username,
                    action="DELETE",
                    entity_type="Candidate",
                    entity_id=candidate_id,
                    details=f"Deleted candidate: {candidate_name}",
                )
            except Exception:
                logger.exception("Failed to log audit for candidate deletion")

        return RedirectResponse(url="/candidates", status_code=303)

    except Exception:
        logger.exception("Error deleting candidate %s", candidate_id)
        return RedirectResponse(url="/candidates", status_code=303)