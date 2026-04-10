import logging
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.middleware.auth_middleware import get_optional_user
from app.models.user import User
from app.services.job_service import get_published_jobs

logger = logging.getLogger(__name__)

router = APIRouter()

templates = Jinja2Templates(
    directory=str(Path(__file__).resolve().parent.parent / "templates")
)


@router.get("/")
async def landing_page(
    request: Request,
    user: User = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    """Landing page with published job listings and login/dashboard CTA."""
    try:
        jobs_data = await get_published_jobs(db, page=1, page_size=50)
        jobs = jobs_data.get("items", [])
    except Exception:
        logger.exception("Error fetching published jobs for landing page")
        jobs = []

    return templates.TemplateResponse(
        request,
        "landing.html",
        context={
            "user": user,
            "jobs": jobs,
        },
    )