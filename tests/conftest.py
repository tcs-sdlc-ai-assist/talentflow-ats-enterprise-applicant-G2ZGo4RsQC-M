import asyncio
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base, get_db
from app.core.security import hash_password, create_session_cookie, COOKIE_NAME
from app.main import app
from app.models.user import User
from app.models.job import Job
from app.models.candidate import Candidate, candidate_skills
from app.models.skill import Skill
from app.models.application import Application
from app.models.interview import Interview, InterviewFeedback
from app.models.audit_log import AuditLog


TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
    future=True,
)

test_async_session = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
    async with test_async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="session")
def event_loop():
    """Create a single event loop for the entire test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(autouse=True)
async def setup_database():
    """Create all tables before each test and drop them after."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a test database session."""
    async with test_async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Provide an unauthenticated async HTTP test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


async def _create_user(
    db: AsyncSession,
    username: str,
    password: str,
    full_name: str,
    email: str,
    role: str,
) -> User:
    """Helper to create a user in the test database."""
    hashed = hash_password(password)
    user = User(
        username=username,
        hashed_password=hashed,
        full_name=full_name,
        email=email,
        role=role,
        is_active=True,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


@pytest_asyncio.fixture
async def admin_user(db_session: AsyncSession) -> User:
    """Create a System Admin user."""
    user = await _create_user(
        db=db_session,
        username="testadmin",
        password="adminpass123",
        full_name="Test Admin",
        email="testadmin@talentflow.test",
        role="System Admin",
    )
    await db_session.commit()
    return user


@pytest_asyncio.fixture
async def hr_recruiter_user(db_session: AsyncSession) -> User:
    """Create an HR Recruiter user."""
    user = await _create_user(
        db=db_session,
        username="testrecruiter",
        password="recruiterpass123",
        full_name="Test Recruiter",
        email="testrecruiter@talentflow.test",
        role="HR Recruiter",
    )
    await db_session.commit()
    return user


@pytest_asyncio.fixture
async def hiring_manager_user(db_session: AsyncSession) -> User:
    """Create a Hiring Manager user."""
    user = await _create_user(
        db=db_session,
        username="testhiringmgr",
        password="managerpass123",
        full_name="Test Hiring Manager",
        email="testhiringmgr@talentflow.test",
        role="Hiring Manager",
    )
    await db_session.commit()
    return user


@pytest_asyncio.fixture
async def interviewer_user(db_session: AsyncSession) -> User:
    """Create an Interviewer user."""
    user = await _create_user(
        db=db_session,
        username="testinterviewer",
        password="interviewerpass123",
        full_name="Test Interviewer",
        email="testinterviewer@talentflow.test",
        role="Interviewer",
    )
    await db_session.commit()
    return user


def _make_session_cookie(user: User) -> dict[str, str]:
    """Generate a session cookie dict for the given user."""
    cookie_value = create_session_cookie(user_id=str(user.id), role=user.role)
    return {COOKIE_NAME: cookie_value}


@pytest_asyncio.fixture
async def admin_client(admin_user: User) -> AsyncGenerator[AsyncClient, None]:
    """Provide an authenticated async HTTP test client for System Admin."""
    cookies = _make_session_cookie(admin_user)
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://testserver",
        cookies=cookies,
    ) as ac:
        yield ac


@pytest_asyncio.fixture
async def hr_client(hr_recruiter_user: User) -> AsyncGenerator[AsyncClient, None]:
    """Provide an authenticated async HTTP test client for HR Recruiter."""
    cookies = _make_session_cookie(hr_recruiter_user)
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://testserver",
        cookies=cookies,
    ) as ac:
        yield ac


@pytest_asyncio.fixture
async def manager_client(hiring_manager_user: User) -> AsyncGenerator[AsyncClient, None]:
    """Provide an authenticated async HTTP test client for Hiring Manager."""
    cookies = _make_session_cookie(hiring_manager_user)
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://testserver",
        cookies=cookies,
    ) as ac:
        yield ac


@pytest_asyncio.fixture
async def interviewer_client(interviewer_user: User) -> AsyncGenerator[AsyncClient, None]:
    """Provide an authenticated async HTTP test client for Interviewer."""
    cookies = _make_session_cookie(interviewer_user)
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://testserver",
        cookies=cookies,
    ) as ac:
        yield ac


@pytest_asyncio.fixture
async def sample_job(db_session: AsyncSession, hiring_manager_user: User) -> Job:
    """Create a sample job for testing."""
    job = Job(
        title="Senior Software Engineer",
        department="Engineering",
        location="Remote",
        job_type="Full-Time",
        salary_min=100000.0,
        salary_max=150000.0,
        description="We are looking for a senior software engineer.",
        status="Published",
        assigned_manager_id=hiring_manager_user.id,
    )
    db_session.add(job)
    await db_session.flush()
    await db_session.refresh(job)
    await db_session.commit()
    return job


@pytest_asyncio.fixture
async def sample_candidate(db_session: AsyncSession) -> Candidate:
    """Create a sample candidate for testing."""
    candidate = Candidate(
        first_name="Jane",
        last_name="Doe",
        email="janedoe@example.com",
        phone="+1-555-0100",
        resume_text="Experienced software engineer with 10 years of experience.",
    )
    db_session.add(candidate)
    await db_session.flush()
    await db_session.refresh(candidate)
    await db_session.commit()
    return candidate


@pytest_asyncio.fixture
async def sample_application(
    db_session: AsyncSession,
    sample_job: Job,
    sample_candidate: Candidate,
) -> Application:
    """Create a sample application for testing."""
    application = Application(
        job_id=sample_job.id,
        candidate_id=sample_candidate.id,
        status="Applied",
        cover_letter="I am very interested in this position.",
        notes="Strong candidate from referral.",
    )
    db_session.add(application)
    await db_session.flush()
    await db_session.refresh(application)
    await db_session.commit()
    return application


@pytest_asyncio.fixture
async def sample_interview(
    db_session: AsyncSession,
    sample_application: Application,
    interviewer_user: User,
) -> Interview:
    """Create a sample interview for testing."""
    from datetime import datetime, timezone, timedelta

    scheduled_time = datetime.now(timezone.utc) + timedelta(days=3)
    interview = Interview(
        application_id=sample_application.id,
        interviewer_id=interviewer_user.id,
        scheduled_at=scheduled_time,
        status="Scheduled",
    )
    db_session.add(interview)
    await db_session.flush()
    await db_session.refresh(interview)
    await db_session.commit()
    return interview