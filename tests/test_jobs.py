import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import Job
from app.models.user import User


class TestJobCreation:
    """Tests for creating job postings."""

    async def test_create_job_form_accessible_by_admin(
        self, admin_client: AsyncClient
    ):
        """System Admin can access the create job form."""
        response = await admin_client.get("/jobs/create")
        assert response.status_code == 200
        assert "Create" in response.text

    async def test_create_job_form_accessible_by_hr_recruiter(
        self, hr_client: AsyncClient
    ):
        """HR Recruiter can access the create job form."""
        response = await hr_client.get("/jobs/create")
        assert response.status_code == 200
        assert "Create" in response.text

    async def test_create_job_with_all_fields(
        self,
        admin_client: AsyncClient,
        hiring_manager_user: User,
    ):
        """Create a job with all fields populated."""
        response = await admin_client.post(
            "/jobs/create",
            data={
                "title": "Backend Engineer",
                "department": "Engineering",
                "location": "New York, NY",
                "job_type": "Full-Time",
                "salary_min": "90000",
                "salary_max": "140000",
                "description": "We need a backend engineer with Python experience.",
                "assigned_manager_id": str(hiring_manager_user.id),
            },
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert "/jobs/" in response.headers["location"]

    async def test_create_job_minimal_fields(
        self, admin_client: AsyncClient
    ):
        """Create a job with only required fields."""
        response = await admin_client.post(
            "/jobs/create",
            data={
                "title": "QA Tester",
                "department": "Quality Assurance",
                "location": "Remote",
                "job_type": "Contract",
                "salary_min": "",
                "salary_max": "",
                "description": "",
                "assigned_manager_id": "",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert "/jobs/" in response.headers["location"]

    async def test_create_job_persists_in_database(
        self,
        admin_client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Created job is persisted in the database with correct values."""
        await admin_client.post(
            "/jobs/create",
            data={
                "title": "Data Scientist",
                "department": "Data",
                "location": "San Francisco, CA",
                "job_type": "Full-Time",
                "salary_min": "120000",
                "salary_max": "180000",
                "description": "Looking for a data scientist.",
                "assigned_manager_id": "",
            },
            follow_redirects=False,
        )

        result = await db_session.execute(
            select(Job).where(Job.title == "Data Scientist")
        )
        job = result.scalar_one_or_none()
        assert job is not None
        assert job.department == "Data"
        assert job.location == "San Francisco, CA"
        assert job.job_type == "Full-Time"
        assert job.salary_min == 120000.0
        assert job.salary_max == 180000.0
        assert job.status == "Draft"

    async def test_create_job_default_status_is_draft(
        self,
        admin_client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Newly created jobs default to Draft status."""
        await admin_client.post(
            "/jobs/create",
            data={
                "title": "DevOps Engineer",
                "department": "Infrastructure",
                "location": "Remote",
                "job_type": "Full-Time",
                "salary_min": "",
                "salary_max": "",
                "description": "DevOps role.",
                "assigned_manager_id": "",
            },
            follow_redirects=False,
        )

        result = await db_session.execute(
            select(Job).where(Job.title == "DevOps Engineer")
        )
        job = result.scalar_one_or_none()
        assert job is not None
        assert job.status == "Draft"

    async def test_create_job_blocked_for_interviewer(
        self, interviewer_client: AsyncClient
    ):
        """Interviewer role cannot access the create job form."""
        response = await interviewer_client.get(
            "/jobs/create", follow_redirects=False
        )
        assert response.status_code == 403

    async def test_create_job_blocked_for_hiring_manager(
        self, manager_client: AsyncClient
    ):
        """Hiring Manager role cannot access the create job form."""
        response = await manager_client.get(
            "/jobs/create", follow_redirects=False
        )
        assert response.status_code == 403

    async def test_create_job_blocked_for_unauthenticated(
        self, client: AsyncClient
    ):
        """Unauthenticated users are redirected to login."""
        response = await client.get("/jobs/create", follow_redirects=False)
        assert response.status_code == 303
        assert "/auth/login" in response.headers["location"]


class TestJobEditing:
    """Tests for editing job postings."""

    async def test_edit_job_form_accessible_by_admin(
        self, admin_client: AsyncClient, sample_job: Job
    ):
        """System Admin can access the edit job form."""
        response = await admin_client.get(f"/jobs/{sample_job.id}/edit")
        assert response.status_code == 200
        assert sample_job.title in response.text

    async def test_edit_job_form_accessible_by_hr_recruiter(
        self, hr_client: AsyncClient, sample_job: Job
    ):
        """HR Recruiter can access the edit job form."""
        response = await hr_client.get(f"/jobs/{sample_job.id}/edit")
        assert response.status_code == 200
        assert sample_job.title in response.text

    async def test_edit_job_form_accessible_by_assigned_manager(
        self, manager_client: AsyncClient, sample_job: Job
    ):
        """Hiring Manager assigned to the job can access the edit form."""
        response = await manager_client.get(f"/jobs/{sample_job.id}/edit")
        assert response.status_code == 200
        assert sample_job.title in response.text

    async def test_edit_job_updates_fields(
        self,
        admin_client: AsyncClient,
        sample_job: Job,
        db_session: AsyncSession,
    ):
        """Editing a job updates the fields in the database."""
        response = await admin_client.post(
            f"/jobs/{sample_job.id}/edit",
            data={
                "title": "Updated Title",
                "department": "Updated Department",
                "location": "Updated Location",
                "job_type": "Part-Time",
                "salary_min": "80000",
                "salary_max": "110000",
                "description": "Updated description.",
                "assigned_manager_id": "",
                "status": sample_job.status,
            },
            follow_redirects=False,
        )
        assert response.status_code == 303

        await db_session.expire_all()
        result = await db_session.execute(
            select(Job).where(Job.id == sample_job.id)
        )
        updated_job = result.scalar_one_or_none()
        assert updated_job is not None
        assert updated_job.title == "Updated Title"
        assert updated_job.department == "Updated Department"
        assert updated_job.location == "Updated Location"
        assert updated_job.job_type == "Part-Time"

    async def test_edit_job_redirects_for_unassigned_manager(
        self,
        db_session: AsyncSession,
        manager_client: AsyncClient,
    ):
        """Hiring Manager NOT assigned to a job is redirected away from edit."""
        unassigned_job = Job(
            title="Unassigned Job",
            department="Other",
            location="Remote",
            job_type="Full-Time",
            status="Draft",
            assigned_manager_id=None,
        )
        db_session.add(unassigned_job)
        await db_session.flush()
        await db_session.refresh(unassigned_job)
        await db_session.commit()

        response = await manager_client.get(
            f"/jobs/{unassigned_job.id}/edit", follow_redirects=False
        )
        assert response.status_code == 303
        assert f"/jobs/{unassigned_job.id}" in response.headers["location"]

    async def test_edit_nonexistent_job_redirects(
        self, admin_client: AsyncClient
    ):
        """Editing a nonexistent job redirects to jobs list."""
        response = await admin_client.get(
            "/jobs/nonexistent-id/edit", follow_redirects=False
        )
        assert response.status_code == 303
        assert "/jobs" in response.headers["location"]

    async def test_edit_job_blocked_for_interviewer(
        self, interviewer_client: AsyncClient, sample_job: Job
    ):
        """Interviewer cannot edit a job (redirected because _can_edit_job fails)."""
        response = await interviewer_client.get(
            f"/jobs/{sample_job.id}/edit", follow_redirects=False
        )
        assert response.status_code == 303


class TestJobStatusTransitions:
    """Tests for job status transitions (Draft → Published → Closed)."""

    async def test_transition_draft_to_published(
        self,
        admin_client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Job can transition from Draft to Published."""
        job = Job(
            title="Draft Job",
            department="Engineering",
            location="Remote",
            job_type="Full-Time",
            status="Draft",
        )
        db_session.add(job)
        await db_session.flush()
        await db_session.refresh(job)
        await db_session.commit()

        response = await admin_client.post(
            f"/jobs/{job.id}/status",
            data={"status": "Published"},
            follow_redirects=False,
        )
        assert response.status_code == 303

        await db_session.expire_all()
        result = await db_session.execute(select(Job).where(Job.id == job.id))
        updated_job = result.scalar_one_or_none()
        assert updated_job is not None
        assert updated_job.status == "Published"

    async def test_transition_published_to_closed(
        self,
        admin_client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Job can transition from Published to Closed."""
        job = Job(
            title="Published Job",
            department="Engineering",
            location="Remote",
            job_type="Full-Time",
            status="Published",
        )
        db_session.add(job)
        await db_session.flush()
        await db_session.refresh(job)
        await db_session.commit()

        response = await admin_client.post(
            f"/jobs/{job.id}/status",
            data={"status": "Closed"},
            follow_redirects=False,
        )
        assert response.status_code == 303

        await db_session.expire_all()
        result = await db_session.execute(select(Job).where(Job.id == job.id))
        updated_job = result.scalar_one_or_none()
        assert updated_job is not None
        assert updated_job.status == "Closed"

    async def test_invalid_transition_draft_to_closed(
        self,
        admin_client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Job cannot transition directly from Draft to Closed."""
        job = Job(
            title="Draft Job No Skip",
            department="Engineering",
            location="Remote",
            job_type="Full-Time",
            status="Draft",
        )
        db_session.add(job)
        await db_session.flush()
        await db_session.refresh(job)
        await db_session.commit()

        response = await admin_client.post(
            f"/jobs/{job.id}/status",
            data={"status": "Closed"},
            follow_redirects=False,
        )
        assert response.status_code == 303

        await db_session.expire_all()
        result = await db_session.execute(select(Job).where(Job.id == job.id))
        updated_job = result.scalar_one_or_none()
        assert updated_job is not None
        assert updated_job.status == "Draft"

    async def test_invalid_transition_closed_to_published(
        self,
        admin_client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Job cannot transition from Closed back to Published."""
        job = Job(
            title="Closed Job",
            department="Engineering",
            location="Remote",
            job_type="Full-Time",
            status="Closed",
        )
        db_session.add(job)
        await db_session.flush()
        await db_session.refresh(job)
        await db_session.commit()

        response = await admin_client.post(
            f"/jobs/{job.id}/status",
            data={"status": "Published"},
            follow_redirects=False,
        )
        assert response.status_code == 303

        await db_session.expire_all()
        result = await db_session.execute(select(Job).where(Job.id == job.id))
        updated_job = result.scalar_one_or_none()
        assert updated_job is not None
        assert updated_job.status == "Closed"

    async def test_status_change_by_assigned_manager(
        self,
        manager_client: AsyncClient,
        sample_job: Job,
        db_session: AsyncSession,
    ):
        """Assigned Hiring Manager can change job status."""
        assert sample_job.status == "Published"

        response = await manager_client.post(
            f"/jobs/{sample_job.id}/status",
            data={"status": "Closed"},
            follow_redirects=False,
        )
        assert response.status_code == 303

        await db_session.expire_all()
        result = await db_session.execute(
            select(Job).where(Job.id == sample_job.id)
        )
        updated_job = result.scalar_one_or_none()
        assert updated_job is not None
        assert updated_job.status == "Closed"


class TestJobListing:
    """Tests for job listing and detail pages."""

    async def test_jobs_list_page_accessible_by_authenticated_user(
        self, admin_client: AsyncClient
    ):
        """Authenticated users can access the jobs list page."""
        response = await admin_client.get("/jobs")
        assert response.status_code == 200
        assert "Jobs" in response.text

    async def test_jobs_list_shows_created_jobs(
        self, admin_client: AsyncClient, sample_job: Job
    ):
        """Jobs list page shows existing jobs."""
        response = await admin_client.get("/jobs")
        assert response.status_code == 200
        assert sample_job.title in response.text

    async def test_jobs_list_filter_by_status(
        self,
        admin_client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Jobs list can be filtered by status."""
        draft_job = Job(
            title="Filterable Draft Job",
            department="Engineering",
            location="Remote",
            job_type="Full-Time",
            status="Draft",
        )
        published_job = Job(
            title="Filterable Published Job",
            department="Engineering",
            location="Remote",
            job_type="Full-Time",
            status="Published",
        )
        db_session.add(draft_job)
        db_session.add(published_job)
        await db_session.flush()
        await db_session.commit()

        response = await admin_client.get("/jobs?status=Draft")
        assert response.status_code == 200
        assert "Filterable Draft Job" in response.text
        assert "Filterable Published Job" not in response.text

    async def test_job_detail_page(
        self, admin_client: AsyncClient, sample_job: Job
    ):
        """Job detail page shows job information."""
        response = await admin_client.get(f"/jobs/{sample_job.id}")
        assert response.status_code == 200
        assert sample_job.title in response.text
        assert sample_job.department in response.text

    async def test_job_detail_nonexistent_returns_404(
        self, admin_client: AsyncClient
    ):
        """Requesting a nonexistent job returns 404."""
        response = await admin_client.get("/jobs/nonexistent-uuid")
        assert response.status_code == 404

    async def test_jobs_list_blocked_for_unauthenticated(
        self, client: AsyncClient
    ):
        """Unauthenticated users are redirected to login."""
        response = await client.get("/jobs", follow_redirects=False)
        assert response.status_code == 303
        assert "/auth/login" in response.headers["location"]


class TestPublishedJobsOnLandingPage:
    """Tests for published jobs appearing on the public landing page."""

    async def test_landing_page_shows_published_jobs(
        self,
        client: AsyncClient,
        sample_job: Job,
    ):
        """Published jobs appear on the public landing page."""
        assert sample_job.status == "Published"
        response = await client.get("/")
        assert response.status_code == 200
        assert sample_job.title in response.text

    async def test_landing_page_hides_draft_jobs(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Draft jobs do not appear on the public landing page."""
        draft_job = Job(
            title="Secret Draft Job XYZ",
            department="Engineering",
            location="Remote",
            job_type="Full-Time",
            status="Draft",
        )
        db_session.add(draft_job)
        await db_session.flush()
        await db_session.commit()

        response = await client.get("/")
        assert response.status_code == 200
        assert "Secret Draft Job XYZ" not in response.text

    async def test_landing_page_hides_closed_jobs(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Closed jobs do not appear on the public landing page."""
        closed_job = Job(
            title="Closed Position ABC",
            department="Engineering",
            location="Remote",
            job_type="Full-Time",
            status="Closed",
        )
        db_session.add(closed_job)
        await db_session.flush()
        await db_session.commit()

        response = await client.get("/")
        assert response.status_code == 200
        assert "Closed Position ABC" not in response.text

    async def test_landing_page_accessible_without_auth(
        self, client: AsyncClient
    ):
        """Landing page is accessible without authentication."""
        response = await client.get("/")
        assert response.status_code == 200
        assert "TalentFlow" in response.text


class TestHiringManagerJobAccess:
    """Tests for Hiring Manager job visibility and access control."""

    async def test_hiring_manager_can_view_assigned_job_detail(
        self, manager_client: AsyncClient, sample_job: Job
    ):
        """Hiring Manager can view detail of a job assigned to them."""
        response = await manager_client.get(f"/jobs/{sample_job.id}")
        assert response.status_code == 200
        assert sample_job.title in response.text

    async def test_hiring_manager_can_view_unassigned_job_detail(
        self,
        manager_client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Hiring Manager can view detail of any job (read access)."""
        other_job = Job(
            title="Other Team Job",
            department="Marketing",
            location="Chicago",
            job_type="Full-Time",
            status="Published",
            assigned_manager_id=None,
        )
        db_session.add(other_job)
        await db_session.flush()
        await db_session.refresh(other_job)
        await db_session.commit()

        response = await manager_client.get(f"/jobs/{other_job.id}")
        assert response.status_code == 200
        assert "Other Team Job" in response.text

    async def test_hiring_manager_cannot_edit_unassigned_job(
        self,
        manager_client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Hiring Manager cannot edit a job not assigned to them."""
        other_job = Job(
            title="Not My Job",
            department="Sales",
            location="Remote",
            job_type="Full-Time",
            status="Draft",
            assigned_manager_id=None,
        )
        db_session.add(other_job)
        await db_session.flush()
        await db_session.refresh(other_job)
        await db_session.commit()

        response = await manager_client.get(
            f"/jobs/{other_job.id}/edit", follow_redirects=False
        )
        assert response.status_code == 303
        assert f"/jobs/{other_job.id}" in response.headers["location"]

    async def test_hiring_manager_cannot_change_status_of_unassigned_job(
        self,
        manager_client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Hiring Manager cannot change status of a job not assigned to them."""
        other_job = Job(
            title="Not My Job Status",
            department="Sales",
            location="Remote",
            job_type="Full-Time",
            status="Draft",
            assigned_manager_id=None,
        )
        db_session.add(other_job)
        await db_session.flush()
        await db_session.refresh(other_job)
        await db_session.commit()

        response = await manager_client.post(
            f"/jobs/{other_job.id}/status",
            data={"status": "Published"},
            follow_redirects=False,
        )
        assert response.status_code == 303

        await db_session.expire_all()
        result = await db_session.execute(
            select(Job).where(Job.id == other_job.id)
        )
        job = result.scalar_one_or_none()
        assert job is not None
        assert job.status == "Draft"


class TestUnauthorizedAccess:
    """Tests for unauthorized access to job management endpoints."""

    async def test_unauthenticated_cannot_create_job(
        self, client: AsyncClient
    ):
        """Unauthenticated users cannot create jobs."""
        response = await client.post(
            "/jobs/create",
            data={
                "title": "Unauthorized Job",
                "department": "Engineering",
                "location": "Remote",
                "job_type": "Full-Time",
                "salary_min": "",
                "salary_max": "",
                "description": "",
                "assigned_manager_id": "",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert "/auth/login" in response.headers["location"]

    async def test_unauthenticated_cannot_edit_job(
        self, client: AsyncClient, sample_job: Job
    ):
        """Unauthenticated users cannot edit jobs."""
        response = await client.get(
            f"/jobs/{sample_job.id}/edit", follow_redirects=False
        )
        assert response.status_code == 303
        assert "/auth/login" in response.headers["location"]

    async def test_unauthenticated_cannot_change_job_status(
        self, client: AsyncClient, sample_job: Job
    ):
        """Unauthenticated users cannot change job status."""
        response = await client.post(
            f"/jobs/{sample_job.id}/status",
            data={"status": "Closed"},
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert "/auth/login" in response.headers["location"]

    async def test_interviewer_cannot_create_job_post(
        self, interviewer_client: AsyncClient
    ):
        """Interviewer cannot submit the create job form."""
        response = await interviewer_client.post(
            "/jobs/create",
            data={
                "title": "Interviewer Job",
                "department": "Engineering",
                "location": "Remote",
                "job_type": "Full-Time",
                "salary_min": "",
                "salary_max": "",
                "description": "",
                "assigned_manager_id": "",
            },
            follow_redirects=False,
        )
        assert response.status_code == 403

    async def test_unauthenticated_cannot_view_job_detail(
        self, client: AsyncClient, sample_job: Job
    ):
        """Unauthenticated users cannot view job detail pages."""
        response = await client.get(
            f"/jobs/{sample_job.id}", follow_redirects=False
        )
        assert response.status_code == 303
        assert "/auth/login" in response.headers["location"]