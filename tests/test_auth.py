import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import COOKIE_NAME
from app.models.user import User


class TestRegistration:
    """Tests for user registration flow."""

    async def test_register_page_renders(self, client: AsyncClient):
        """GET /auth/register returns the registration form."""
        response = await client.get("/auth/register")
        assert response.status_code == 200
        assert "Create your account" in response.text

    async def test_register_creates_user_with_interviewer_role(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Successful registration creates a user with the Interviewer role."""
        response = await client.post(
            "/auth/register",
            data={
                "username": "newuser",
                "full_name": "New User",
                "email": "newuser@example.com",
                "password": "securepass123",
                "confirm_password": "securepass123",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert response.headers["location"] == "/auth/login"

        result = await db_session.execute(
            select(User).where(User.username == "newuser")
        )
        user = result.scalar_one_or_none()
        assert user is not None
        assert user.role == "Interviewer"
        assert user.full_name == "New User"
        assert user.email == "newuser@example.com"
        assert user.is_active is True

    async def test_register_rejects_duplicate_username(
        self, client: AsyncClient, admin_user: User
    ):
        """Registration with an existing username returns an error."""
        response = await client.post(
            "/auth/register",
            data={
                "username": admin_user.username,
                "full_name": "Duplicate User",
                "email": "unique@example.com",
                "password": "securepass123",
                "confirm_password": "securepass123",
            },
            follow_redirects=False,
        )
        assert response.status_code == 400
        assert "already taken" in response.text

    async def test_register_rejects_duplicate_email(
        self, client: AsyncClient, admin_user: User
    ):
        """Registration with an existing email returns an error."""
        response = await client.post(
            "/auth/register",
            data={
                "username": "uniqueuser",
                "full_name": "Duplicate Email User",
                "email": admin_user.email,
                "password": "securepass123",
                "confirm_password": "securepass123",
            },
            follow_redirects=False,
        )
        assert response.status_code == 400
        assert "already registered" in response.text

    async def test_register_rejects_password_mismatch(self, client: AsyncClient):
        """Registration with mismatched passwords returns an error."""
        response = await client.post(
            "/auth/register",
            data={
                "username": "mismatchuser",
                "full_name": "Mismatch User",
                "email": "mismatch@example.com",
                "password": "securepass123",
                "confirm_password": "differentpass456",
            },
            follow_redirects=False,
        )
        assert response.status_code == 400
        assert "Passwords do not match" in response.text

    async def test_register_rejects_short_password(self, client: AsyncClient):
        """Registration with a password shorter than 8 characters returns an error."""
        response = await client.post(
            "/auth/register",
            data={
                "username": "shortpwuser",
                "full_name": "Short Password User",
                "email": "shortpw@example.com",
                "password": "short",
                "confirm_password": "short",
            },
            follow_redirects=False,
        )
        assert response.status_code == 400
        assert "at least 8 characters" in response.text

    async def test_register_rejects_short_username(self, client: AsyncClient):
        """Registration with a username shorter than 3 characters returns an error."""
        response = await client.post(
            "/auth/register",
            data={
                "username": "ab",
                "full_name": "Short Username",
                "email": "shortun@example.com",
                "password": "securepass123",
                "confirm_password": "securepass123",
            },
            follow_redirects=False,
        )
        assert response.status_code == 400
        assert "at least 3 characters" in response.text

    async def test_register_redirects_authenticated_user_to_dashboard(
        self, admin_client: AsyncClient
    ):
        """Authenticated users visiting /auth/register are redirected to /dashboard."""
        response = await admin_client.get(
            "/auth/register", follow_redirects=False
        )
        assert response.status_code == 303
        assert response.headers["location"] == "/dashboard"


class TestLogin:
    """Tests for user login flow."""

    async def test_login_page_renders(self, client: AsyncClient):
        """GET /auth/login returns the login form."""
        response = await client.get("/auth/login")
        assert response.status_code == 200
        assert "Sign in to TalentFlow ATS" in response.text

    async def test_login_with_valid_credentials_sets_session_cookie(
        self, client: AsyncClient, admin_user: User
    ):
        """Successful login sets a session cookie and redirects to dashboard."""
        response = await client.post(
            "/auth/login",
            data={
                "username": "testadmin",
                "password": "adminpass123",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert response.headers["location"] == "/dashboard"

        cookies = response.cookies
        assert COOKIE_NAME in cookies

    async def test_login_with_invalid_password_fails(
        self, client: AsyncClient, admin_user: User
    ):
        """Login with wrong password returns an error."""
        response = await client.post(
            "/auth/login",
            data={
                "username": "testadmin",
                "password": "wrongpassword",
            },
            follow_redirects=False,
        )
        assert response.status_code == 400
        assert "Invalid username or password" in response.text

    async def test_login_with_nonexistent_user_fails(self, client: AsyncClient):
        """Login with a username that doesn't exist returns an error."""
        response = await client.post(
            "/auth/login",
            data={
                "username": "nonexistentuser",
                "password": "somepassword123",
            },
            follow_redirects=False,
        )
        assert response.status_code == 400
        assert "Invalid username or password" in response.text

    async def test_login_redirects_authenticated_user_to_dashboard(
        self, admin_client: AsyncClient
    ):
        """Authenticated users visiting /auth/login are redirected to /dashboard."""
        response = await admin_client.get(
            "/auth/login", follow_redirects=False
        )
        assert response.status_code == 303
        assert response.headers["location"] == "/dashboard"

    async def test_login_system_admin_redirects_to_dashboard(
        self, client: AsyncClient, admin_user: User
    ):
        """System Admin login redirects to /dashboard."""
        response = await client.post(
            "/auth/login",
            data={
                "username": "testadmin",
                "password": "adminpass123",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert response.headers["location"] == "/dashboard"

    async def test_login_hr_recruiter_redirects_to_dashboard(
        self, client: AsyncClient, hr_recruiter_user: User
    ):
        """HR Recruiter login redirects to /dashboard."""
        response = await client.post(
            "/auth/login",
            data={
                "username": "testrecruiter",
                "password": "recruiterpass123",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert response.headers["location"] == "/dashboard"

    async def test_login_hiring_manager_redirects_to_dashboard(
        self, client: AsyncClient, hiring_manager_user: User
    ):
        """Hiring Manager login redirects to /dashboard."""
        response = await client.post(
            "/auth/login",
            data={
                "username": "testhiringmgr",
                "password": "managerpass123",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert response.headers["location"] == "/dashboard"

    async def test_login_interviewer_redirects_to_dashboard(
        self, client: AsyncClient, interviewer_user: User
    ):
        """Interviewer login redirects to /dashboard."""
        response = await client.post(
            "/auth/login",
            data={
                "username": "testinterviewer",
                "password": "interviewerpass123",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert response.headers["location"] == "/dashboard"


class TestLogout:
    """Tests for user logout flow."""

    async def test_logout_clears_session_cookie(
        self, admin_client: AsyncClient
    ):
        """POST /auth/logout clears the session cookie and redirects to landing."""
        response = await admin_client.post(
            "/auth/logout", follow_redirects=False
        )
        assert response.status_code == 303
        assert response.headers["location"] == "/"

        set_cookie_header = response.headers.get("set-cookie", "")
        assert COOKIE_NAME in set_cookie_header
        assert 'Max-Age=0' in set_cookie_header or '="";' in set_cookie_header or 'expires=' in set_cookie_header.lower()

    async def test_logout_without_session_redirects_to_landing(
        self, client: AsyncClient
    ):
        """POST /auth/logout without a session still redirects to landing page."""
        response = await client.post(
            "/auth/logout", follow_redirects=False
        )
        assert response.status_code == 303
        assert response.headers["location"] == "/"


class TestSessionProtection:
    """Tests for session-based access control."""

    async def test_dashboard_requires_authentication(self, client: AsyncClient):
        """Unauthenticated access to /dashboard redirects to login."""
        response = await client.get("/dashboard", follow_redirects=False)
        assert response.status_code == 303
        assert "/auth/login" in response.headers["location"]

    async def test_jobs_requires_authentication(self, client: AsyncClient):
        """Unauthenticated access to /jobs redirects to login."""
        response = await client.get("/jobs", follow_redirects=False)
        assert response.status_code == 303
        assert "/auth/login" in response.headers["location"]

    async def test_candidates_requires_authentication(self, client: AsyncClient):
        """Unauthenticated access to /candidates redirects to login."""
        response = await client.get("/candidates", follow_redirects=False)
        assert response.status_code == 303
        assert "/auth/login" in response.headers["location"]

    async def test_applications_requires_authentication(self, client: AsyncClient):
        """Unauthenticated access to /applications redirects to login."""
        response = await client.get("/applications", follow_redirects=False)
        assert response.status_code == 303
        assert "/auth/login" in response.headers["location"]

    async def test_authenticated_user_can_access_dashboard(
        self, admin_client: AsyncClient
    ):
        """Authenticated user can access /dashboard."""
        response = await admin_client.get("/dashboard")
        assert response.status_code == 200
        assert "Dashboard" in response.text

    async def test_authenticated_user_can_access_jobs(
        self, admin_client: AsyncClient
    ):
        """Authenticated user can access /jobs."""
        response = await admin_client.get("/jobs")
        assert response.status_code == 200

    async def test_invalid_session_cookie_redirects_to_login(
        self, client: AsyncClient
    ):
        """A request with a tampered/invalid session cookie redirects to login."""
        client.cookies.set(COOKIE_NAME, "invalid-cookie-value")
        response = await client.get("/dashboard", follow_redirects=False)
        assert response.status_code == 303
        assert "/auth/login" in response.headers["location"]


class TestRoleBasedAccess:
    """Tests for role-based access control on protected routes."""

    async def test_interviewer_cannot_create_job(
        self, interviewer_client: AsyncClient
    ):
        """Interviewer role cannot access job creation form (requires System Admin or HR Recruiter)."""
        response = await interviewer_client.get(
            "/jobs/create", follow_redirects=False
        )
        assert response.status_code == 403

    async def test_admin_can_create_job(self, admin_client: AsyncClient):
        """System Admin can access job creation form."""
        response = await admin_client.get("/jobs/create")
        assert response.status_code == 200

    async def test_hr_recruiter_can_create_job(self, hr_client: AsyncClient):
        """HR Recruiter can access job creation form."""
        response = await hr_client.get("/jobs/create")
        assert response.status_code == 200

    async def test_interviewer_cannot_create_candidate(
        self, interviewer_client: AsyncClient
    ):
        """Interviewer role cannot access candidate creation form."""
        response = await interviewer_client.get(
            "/candidates/create", follow_redirects=False
        )
        assert response.status_code == 403

    async def test_interviewer_cannot_access_audit_log(
        self, interviewer_client: AsyncClient
    ):
        """Interviewer role cannot access the audit log page."""
        response = await interviewer_client.get(
            "/dashboard/audit-log", follow_redirects=False
        )
        assert response.status_code == 403

    async def test_admin_can_access_audit_log(self, admin_client: AsyncClient):
        """System Admin can access the audit log page."""
        response = await admin_client.get("/dashboard/audit-log")
        assert response.status_code == 200

    async def test_hiring_manager_cannot_create_candidate(
        self, manager_client: AsyncClient
    ):
        """Hiring Manager role cannot access candidate creation form (requires System Admin or HR Recruiter)."""
        response = await manager_client.get(
            "/candidates/create", follow_redirects=False
        )
        assert response.status_code == 403


class TestLandingPage:
    """Tests for the public landing page."""

    async def test_landing_page_accessible_without_auth(
        self, client: AsyncClient
    ):
        """The landing page is accessible without authentication."""
        response = await client.get("/")
        assert response.status_code == 200
        assert "TalentFlow ATS" in response.text

    async def test_landing_page_shows_login_link_for_guests(
        self, client: AsyncClient
    ):
        """The landing page shows a login link for unauthenticated users."""
        response = await client.get("/")
        assert response.status_code == 200
        assert "Login" in response.text or "Employee Portal Login" in response.text

    async def test_landing_page_shows_dashboard_link_for_authenticated(
        self, admin_client: AsyncClient
    ):
        """The landing page shows a dashboard link for authenticated users."""
        response = await admin_client.get("/")
        assert response.status_code == 200
        assert "Dashboard" in response.text or "Go to Dashboard" in response.text