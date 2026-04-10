import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response
from fastapi.templating import Jinja2Templates
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.middleware.auth_middleware import require_role
from app.models.user import User
from app.services.dashboard_service import get_audit_logs_paginated

logger = logging.getLogger(__name__)

router = APIRouter()

templates = Jinja2Templates(
    directory=str(Path(__file__).resolve().parent.parent / "templates")
)


@router.get("/audit-log")
async def audit_log_page(
    request: Request,
    user: User = Depends(require_role("System Admin", "HR Recruiter")),
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    user_filter: Optional[str] = Query(None, alias="user"),
    action: Optional[str] = Query(None),
    entity_type: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
) -> Response:
    """Render the paginated, filterable audit log page.

    Accessible only to System Admin and HR Recruiter roles.
    """
    result = await get_audit_logs_paginated(
        db=db,
        page=page,
        page_size=page_size,
        user_filter=user_filter,
        action_filter=action,
        entity_type_filter=entity_type,
        date_from=date_from,
        date_to=date_to,
    )

    filters = {
        "user": user_filter or "",
        "action": action or "",
        "entity_type": entity_type or "",
        "date_from": date_from or "",
        "date_to": date_to or "",
    }

    return templates.TemplateResponse(
        request,
        "dashboard/audit_log.html",
        context={
            "user": user,
            "audit_logs": result["audit_logs"],
            "total_count": result["total_count"],
            "total_pages": result["total_pages"],
            "current_page": result["current_page"],
            "page_size": result["page_size"],
            "action_options": result["action_options"],
            "entity_type_options": result["entity_type_options"],
            "filters": filters,
        },
    )