import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.middleware.auth_middleware import get_current_user_required
from app.models.user import User
from app.services.dashboard_service import (
    get_hr_dashboard_data,
    get_interviewer_dashboard_data,
    get_manager_dashboard_data,
)

logger = logging.getLogger(__name__)

router = APIRouter()

templates = Jinja2Templates(
    directory=str(Path(__file__).resolve().parent.parent / "templates")
)


@router.get("/dashboard")
async def dashboard(
    request: Request,
    user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
):
    """Main dashboard endpoint. Renders role-specific dashboard data."""
    try:
        role = user.role

        if role in ("System Admin", "HR Recruiter", "Admin", "HR", "Super Admin"):
            data = await get_hr_dashboard_data(db)
            context = {
                "user": user,
                "role": role,
                "metrics": data["metrics"],
                "audit_logs": data["audit_logs"],
            }
            return templates.TemplateResponse(
                request, "dashboard/index.html", context=context
            )

        elif role == "Hiring Manager":
            data = await get_manager_dashboard_data(db, manager_id=user.id)
            context = {
                "user": user,
                "role": role,
                "my_jobs": data["my_jobs"],
                "pending_interviews": data["pending_interviews"],
            }
            return templates.TemplateResponse(
                request, "dashboard/index.html", context=context
            )

        elif role == "Interviewer":
            data = await get_interviewer_dashboard_data(db, interviewer_id=user.id)
            context = {
                "user": user,
                "role": role,
                "upcoming_interviews": data["upcoming_interviews"],
                "missing_feedback": data["missing_feedback"],
            }
            return templates.TemplateResponse(
                request, "dashboard/index.html", context=context
            )

        else:
            context = {
                "user": user,
                "role": role,
            }
            return templates.TemplateResponse(
                request, "dashboard/index.html", context=context
            )

    except Exception:
        logger.exception("Error loading dashboard for user %s", user.username)
        context = {
            "user": user,
            "role": user.role,
        }
        return templates.TemplateResponse(
            request, "dashboard/index.html", context=context
        )