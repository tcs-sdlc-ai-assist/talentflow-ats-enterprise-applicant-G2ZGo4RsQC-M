import logging
from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import COOKIE_NAME, SESSION_MAX_AGE, create_session_cookie
from app.middleware.auth_middleware import get_optional_user
from app.models.user import User
from app.services.auth_service import login_user, register_user
from app.services.audit_service import log_action

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

templates = Jinja2Templates(
    directory=str(Path(__file__).resolve().parent.parent / "templates")
)


@router.get("/login")
async def login_page(
    request: Request,
    user: User = Depends(get_optional_user),
) -> Response:
    """Render the login form. If already logged in, redirect to dashboard."""
    if user is not None:
        return RedirectResponse(url="/dashboard", status_code=303)

    return templates.TemplateResponse(
        request,
        "auth/login.html",
        context={"error": None},
    )


@router.post("/login")
async def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Authenticate user, set session cookie, and redirect based on role."""
    user = await login_user(db=db, username=username, password=password)

    if user is None:
        return templates.TemplateResponse(
            request,
            "auth/login.html",
            context={"error": "Invalid username or password."},
            status_code=400,
        )

    try:
        await log_action(
            db=db,
            user_id=user.id,
            username=user.username,
            action="LOGIN",
            entity_type="User",
            entity_id=user.id,
            details=f"User '{user.username}' logged in successfully",
        )
    except Exception:
        logger.exception("Failed to log audit for login")

    cookie_value = create_session_cookie(user_id=str(user.id), role=user.role)

    if user.role in ("System Admin", "HR Recruiter", "Admin", "HR", "Super Admin"):
        redirect_url = "/dashboard"
    elif user.role == "Hiring Manager":
        redirect_url = "/dashboard"
    elif user.role == "Interviewer":
        redirect_url = "/dashboard"
    else:
        redirect_url = "/dashboard"

    response = RedirectResponse(url=redirect_url, status_code=303)
    response.set_cookie(
        key=COOKIE_NAME,
        value=cookie_value,
        httponly=True,
        samesite="lax",
        max_age=SESSION_MAX_AGE,
    )

    logger.info("User '%s' (role=%s) logged in, redirecting to %s", user.username, user.role, redirect_url)
    return response


@router.get("/register")
async def register_page(
    request: Request,
    user: User = Depends(get_optional_user),
) -> Response:
    """Render the registration form. If already logged in, redirect to dashboard."""
    if user is not None:
        return RedirectResponse(url="/dashboard", status_code=303)

    return templates.TemplateResponse(
        request,
        "auth/register.html",
        context={"errors": None, "error": None, "form_data": None},
    )


@router.post("/register")
async def register_submit(
    request: Request,
    username: str = Form(...),
    full_name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Create a new user account and redirect to login page."""
    form_data = {
        "username": username,
        "full_name": full_name,
        "email": email,
    }

    errors: list[str] = []

    username_stripped = username.strip()
    if not username_stripped:
        errors.append("Username is required.")
    elif len(username_stripped) < 3:
        errors.append("Username must be at least 3 characters.")

    full_name_stripped = full_name.strip()
    if not full_name_stripped:
        errors.append("Full name is required.")

    email_stripped = email.strip()
    if not email_stripped:
        errors.append("Email is required.")

    if len(password) < 8:
        errors.append("Password must be at least 8 characters.")

    if password != confirm_password:
        errors.append("Passwords do not match.")

    if errors:
        return templates.TemplateResponse(
            request,
            "auth/register.html",
            context={"errors": errors, "error": None, "form_data": form_data},
            status_code=400,
        )

    try:
        new_user = await register_user(
            db=db,
            username=username_stripped,
            password=password,
            full_name=full_name_stripped,
            email=email_stripped,
            role="Interviewer",
        )
    except ValueError as e:
        return templates.TemplateResponse(
            request,
            "auth/register.html",
            context={"errors": None, "error": str(e), "form_data": form_data},
            status_code=400,
        )
    except Exception:
        logger.exception("Unexpected error during registration")
        return templates.TemplateResponse(
            request,
            "auth/register.html",
            context={
                "errors": None,
                "error": "An unexpected error occurred. Please try again.",
                "form_data": form_data,
            },
            status_code=500,
        )

    try:
        await log_action(
            db=db,
            user_id=new_user.id,
            username=new_user.username,
            action="CREATE",
            entity_type="User",
            entity_id=new_user.id,
            details=f"New user '{new_user.username}' registered with role '{new_user.role}'",
        )
    except Exception:
        logger.exception("Failed to log audit for registration")

    logger.info("New user registered: username=%s email=%s", new_user.username, new_user.email)

    return RedirectResponse(url="/auth/login", status_code=303)


@router.post("/logout")
async def logout(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_optional_user),
) -> Response:
    """Clear session cookie and redirect to landing page."""
    if user is not None:
        try:
            await log_action(
                db=db,
                user_id=user.id,
                username=user.username,
                action="LOGOUT",
                entity_type="User",
                entity_id=user.id,
                details=f"User '{user.username}' logged out",
            )
        except Exception:
            logger.exception("Failed to log audit for logout")

        logger.info("User '%s' logged out", user.username)

    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie(key=COOKIE_NAME)
    return response