import logging
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import COOKIE_NAME, decode_session_cookie
from app.models.user import User

logger = logging.getLogger(__name__)


async def get_optional_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """Get the current user from session cookie if present, otherwise return None.
    
    Use this dependency for pages accessible to both guests and logged-in users.
    """
    cookie_value = request.cookies.get(COOKIE_NAME)
    if not cookie_value:
        return None

    session_data = decode_session_cookie(cookie_value)
    if session_data is None:
        return None

    user_id = session_data.get("user_id")
    if not user_id:
        return None

    try:
        result = await db.execute(
            select(User).where(User.id == user_id, User.is_active == True)
        )
        user = result.scalar_one_or_none()
        return user
    except Exception:
        logger.exception("Error fetching user from session in get_optional_user")
        return None


async def get_current_user_required(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    """Get the current authenticated user or redirect to login page.
    
    Use this dependency for pages that require authentication.
    Redirects to /auth/login if no valid session is found.
    """
    cookie_value = request.cookies.get(COOKIE_NAME)
    if not cookie_value:
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": "/auth/login"},
        )

    session_data = decode_session_cookie(cookie_value)
    if session_data is None:
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": "/auth/login"},
        )

    user_id = session_data.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": "/auth/login"},
        )

    try:
        result = await db.execute(
            select(User).where(User.id == user_id, User.is_active == True)
        )
        user = result.scalar_one_or_none()
    except Exception:
        logger.exception("Error fetching user from session in get_current_user_required")
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": "/auth/login"},
        )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": "/auth/login"},
        )

    return user


def require_role(*allowed_roles: str):
    """Dependency factory that checks the current user's role against allowed roles.
    
    Usage:
        @router.get("/admin", dependencies=[Depends(require_role("System Admin"))])
        async def admin_page(...):
            ...
    
    Or as a parameter dependency:
        async def admin_page(user: User = Depends(require_role("System Admin", "HR Recruiter"))):
            ...
    
    Raises:
        HTTPException 403 if the user's role is not in the allowed roles.
        Redirects to /auth/login if no valid session.
    """

    async def role_checker(
        request: Request,
        db: AsyncSession = Depends(get_db),
    ) -> User:
        user = await get_current_user_required(request=request, db=db)

        if user.role not in allowed_roles:
            logger.warning(
                "User %s (role=%s) attempted to access resource requiring roles %s",
                user.username,
                user.role,
                allowed_roles,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required role(s): {', '.join(allowed_roles)}. Your role: {user.role}.",
            )

        return user

    return role_checker


def inject_user_context(user: Optional[User]) -> dict:
    """Build template context dict with user and role information.
    
    Use this to inject user data into Jinja2 template context.
    
    Args:
        user: The current user or None for guests.
    
    Returns:
        Dict with 'user' and 'role' keys for template rendering.
    """
    if user is None:
        return {"user": None, "role": None}

    return {
        "user": user,
        "role": user.role,
    }