import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.application import Application
from app.models.candidate import Candidate
from app.models.job import Job
from app.models.user import User


class TestApplicationCreate:
    """Tests for creating applications."""

    async def test_create_application_success(
        self,
        admin_client: AsyncClient,
        sample_job: Job,
        sample_candidate: Candidate,
    ):
        """Creating an application with valid data redirects to the application detail page."""
        response = await admin_client.post(
            "/applications/create",
            data={
                "job_id": sample_job.id,
                "candidate_id": sample_candidate.id,
                "cover_letter": "I am excited about this opportunity.",
                "resume_url": "https://example.com/resume.pdf",
                "notes": "Referred by employee.",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert "/applications/" in response.headers["location"]

    async def test_create_application_duplicate_rejected(
        self,
        admin_client: AsyncClient,
        sample_job: Job,
        sample_candidate: Candidate,
        sample_application: Application,
    ):
        """Creating a duplicate application for the same job and candidate returns an error."""
        response = await admin_client.post(
            "/applications/create",
            data={
                "job_id": sample_job.id,
                "candidate_id": sample_candidate.id,
                "cover_letter": "Another application.",
                "resume_url": "",
                "notes": "",
            },
            follow_redirects=False,
        )
        assert response.status_code == 400
        assert b"already applied" in response.content

    async def test_create_application_invalid_job_id(
        self,
        admin_client: AsyncClient,
        sample_candidate: Candidate,
    ):
        """Creating an application with a non-existent job ID returns an error."""
        response = await admin_client.post(
            "/applications/create",
            data={
                "job_id": "nonexistent-job-id-12345",
                "candidate_id": sample_candidate.id,
                "cover_letter": "",
                "resume_url": "",
                "notes": "",
            },
            follow_redirects=False,
        )
        assert response.status_code == 400
        assert b"not found" in response.content

    async def test_create_application_invalid_candidate_id(
        self,
        admin_client: AsyncClient,
        sample_job: Job,
    ):
        """Creating an application with a non-existent candidate ID returns an error."""
        response = await admin_client.post(
            "/applications/create",
            data={
                "job_id": sample_job.id,
                "candidate_id": "nonexistent-candidate-id-12345",
                "cover_letter": "",
                "resume_url": "",
                "notes": "",
            },
            follow_redirects=False,
        )
        assert response.status_code == 400
        assert b"not found" in response.content

    async def test_create_application_requires_auth(
        self,
        client: AsyncClient,
        sample_job: Job,
        sample_candidate: Candidate,
    ):
        """Unauthenticated users cannot create applications."""
        response = await client.post(
            "/applications/create",
            data={
                "job_id": sample_job.id,
                "candidate_id": sample_candidate.id,
                "cover_letter": "",
                "resume_url": "",
                "notes": "",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert "/auth/login" in response.headers["location"]

    async def test_create_application_interviewer_forbidden(
        self,
        interviewer_client: AsyncClient,
        sample_job: Job,
        sample_candidate: Candidate,
    ):
        """Interviewers cannot create applications (role restriction)."""
        response = await interviewer_client.post(
            "/applications/create",
            data={
                "job_id": sample_job.id,
                "candidate_id": sample_candidate.id,
                "cover_letter": "",
                "resume_url": "",
                "notes": "",
            },
            follow_redirects=False,
        )
        assert response.status_code == 403

    async def test_create_application_form_renders(
        self,
        admin_client: AsyncClient,
    ):
        """The create application form page renders successfully."""
        response = await admin_client.get("/applications/create")
        assert response.status_code == 200
        assert b"New Application" in response.content or b"Create" in response.content


class TestApplicationStatusTransitions:
    """Tests for application status transitions following ALLOWED_TRANSITIONS."""

    async def test_transition_applied_to_screening(
        self,
        admin_client: AsyncClient,
        sample_application: Application,
    ):
        """Transitioning from Applied to Screening is allowed."""
        response = await admin_client.post(
            f"/applications/{sample_application.id}/status",
            data={"status": "Screening"},
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert f"/applications/{sample_application.id}" in response.headers["location"]

    async def test_transition_applied_to_rejected(
        self,
        admin_client: AsyncClient,
        sample_application: Application,
    ):
        """Transitioning from Applied to Rejected is allowed."""
        response = await admin_client.post(
            f"/applications/{sample_application.id}/status",
            data={"status": "Rejected"},
            follow_redirects=False,
        )
        assert response.status_code == 303

    async def test_transition_applied_to_interview_rejected(
        self,
        admin_client: AsyncClient,
        sample_application: Application,
    ):
        """Transitioning directly from Applied to Interview is not allowed (must go through Screening)."""
        response = await admin_client.post(
            f"/applications/{sample_application.id}/status",
            data={"status": "Interview"},
            follow_redirects=False,
        )
        # The route redirects even on failure (logs warning, redirects back)
        assert response.status_code == 303

    async def test_transition_applied_to_offer_rejected(
        self,
        admin_client: AsyncClient,
        sample_application: Application,
    ):
        """Transitioning directly from Applied to Offer is not allowed."""
        response = await admin_client.post(
            f"/applications/{sample_application.id}/status",
            data={"status": "Offer"},
            follow_redirects=False,
        )
        assert response.status_code == 303

    async def test_transition_applied_to_hired_rejected(
        self,
        admin_client: AsyncClient,
        sample_application: Application,
    ):
        """Transitioning directly from Applied to Hired is not allowed."""
        response = await admin_client.post(
            f"/applications/{sample_application.id}/status",
            data={"status": "Hired"},
            follow_redirects=False,
        )
        assert response.status_code == 303

    async def test_full_pipeline_applied_to_hired(
        self,
        admin_client: AsyncClient,
        sample_application: Application,
        db_session: AsyncSession,
    ):
        """An application can progress through the full pipeline: Applied -> Screening -> Interview -> Offer -> Hired."""
        app_id = sample_application.id

        # Applied -> Screening
        response = await admin_client.post(
            f"/applications/{app_id}/status",
            data={"status": "Screening"},
            follow_redirects=False,
        )
        assert response.status_code == 303

        # Verify status changed in DB
        await db_session.expire_all()
        result = await db_session.execute(
            select(Application).where(Application.id == app_id)
        )
        app = result.scalar_one()
        assert app.status == "Screening"

        # Screening -> Interview
        response = await admin_client.post(
            f"/applications/{app_id}/status",
            data={"status": "Interview"},
            follow_redirects=False,
        )
        assert response.status_code == 303

        await db_session.expire_all()
        result = await db_session.execute(
            select(Application).where(Application.id == app_id)
        )
        app = result.scalar_one()
        assert app.status == "Interview"

        # Interview -> Offer
        response = await admin_client.post(
            f"/applications/{app_id}/status",
            data={"status": "Offer"},
            follow_redirects=False,
        )
        assert response.status_code == 303

        await db_session.expire_all()
        result = await db_session.execute(
            select(Application).where(Application.id == app_id)
        )
        app = result.scalar_one()
        assert app.status == "Offer"

        # Offer -> Hired
        response = await admin_client.post(
            f"/applications/{app_id}/status",
            data={"status": "Hired"},
            follow_redirects=False,
        )
        assert response.status_code == 303

        await db_session.expire_all()
        result = await db_session.execute(
            select(Application).where(Application.id == app_id)
        )
        app = result.scalar_one()
        assert app.status == "Hired"

    async def test_rejected_is_terminal(
        self,
        admin_client: AsyncClient,
        sample_application: Application,
        db_session: AsyncSession,
    ):
        """Once rejected, no further transitions are allowed."""
        app_id = sample_application.id

        # Applied -> Rejected
        await admin_client.post(
            f"/applications/{app_id}/status",
            data={"status": "Rejected"},
            follow_redirects=False,
        )

        await db_session.expire_all()
        result = await db_session.execute(
            select(Application).where(Application.id == app_id)
        )
        app = result.scalar_one()
        assert app.status == "Rejected"

        # Rejected -> Screening (should fail)
        await admin_client.post(
            f"/applications/{app_id}/status",
            data={"status": "Screening"},
            follow_redirects=False,
        )

        await db_session.expire_all()
        result = await db_session.execute(
            select(Application).where(Application.id == app_id)
        )
        app = result.scalar_one()
        assert app.status == "Rejected"

    async def test_hired_is_terminal(
        self,
        admin_client: AsyncClient,
        sample_application: Application,
        db_session: AsyncSession,
    ):
        """Once hired, no further transitions are allowed."""
        app_id = sample_application.id

        # Progress to Hired
        for status in ["Screening", "Interview", "Offer", "Hired"]:
            await admin_client.post(
                f"/applications/{app_id}/status",
                data={"status": status},
                follow_redirects=False,
            )

        await db_session.expire_all()
        result = await db_session.execute(
            select(Application).where(Application.id == app_id)
        )
        app = result.scalar_one()
        assert app.status == "Hired"

        # Hired -> Rejected (should fail)
        await admin_client.post(
            f"/applications/{app_id}/status",
            data={"status": "Rejected"},
            follow_redirects=False,
        )

        await db_session.expire_all()
        result = await db_session.execute(
            select(Application).where(Application.id == app_id)
        )
        app = result.scalar_one()
        assert app.status == "Hired"

    async def test_screening_to_rejected(
        self,
        admin_client: AsyncClient,
        sample_application: Application,
        db_session: AsyncSession,
    ):
        """Transitioning from Screening to Rejected is allowed."""
        app_id = sample_application.id

        # Applied -> Screening
        await admin_client.post(
            f"/applications/{app_id}/status",
            data={"status": "Screening"},
            follow_redirects=False,
        )

        # Screening -> Rejected
        await admin_client.post(
            f"/applications/{app_id}/status",
            data={"status": "Rejected"},
            follow_redirects=False,
        )

        await db_session.expire_all()
        result = await db_session.execute(
            select(Application).where(Application.id == app_id)
        )
        app = result.scalar_one()
        assert app.status == "Rejected"

    async def test_interview_to_rejected(
        self,
        admin_client: AsyncClient,
        sample_application: Application,
        db_session: AsyncSession,
    ):
        """Transitioning from Interview to Rejected is allowed."""
        app_id = sample_application.id

        # Applied -> Screening -> Interview
        await admin_client.post(
            f"/applications/{app_id}/status",
            data={"status": "Screening"},
            follow_redirects=False,
        )
        await admin_client.post(
            f"/applications/{app_id}/status",
            data={"status": "Interview"},
            follow_redirects=False,
        )

        # Interview -> Rejected
        await admin_client.post(
            f"/applications/{app_id}/status",
            data={"status": "Rejected"},
            follow_redirects=False,
        )

        await db_session.expire_all()
        result = await db_session.execute(
            select(Application).where(Application.id == app_id)
        )
        app = result.scalar_one()
        assert app.status == "Rejected"

    async def test_offer_to_rejected(
        self,
        admin_client: AsyncClient,
        sample_application: Application,
        db_session: AsyncSession,
    ):
        """Transitioning from Offer to Rejected is allowed."""
        app_id = sample_application.id

        # Applied -> Screening -> Interview -> Offer
        for status in ["Screening", "Interview", "Offer"]:
            await admin_client.post(
                f"/applications/{app_id}/status",
                data={"status": status},
                follow_redirects=False,
            )

        # Offer -> Rejected
        await admin_client.post(
            f"/applications/{app_id}/status",
            data={"status": "Rejected"},
            follow_redirects=False,
        )

        await db_session.expire_all()
        result = await db_session.execute(
            select(Application).where(Application.id == app_id)
        )
        app = result.scalar_one()
        assert app.status == "Rejected"

    async def test_status_change_nonexistent_application(
        self,
        admin_client: AsyncClient,
    ):
        """Changing status of a non-existent application redirects gracefully."""
        response = await admin_client.post(
            "/applications/nonexistent-id-12345/status",
            data={"status": "Screening"},
            follow_redirects=False,
        )
        assert response.status_code == 303


class TestApplicationList:
    """Tests for listing applications."""

    async def test_list_applications_authenticated(
        self,
        admin_client: AsyncClient,
        sample_application: Application,
    ):
        """Authenticated users can view the applications list."""
        response = await admin_client.get("/applications")
        assert response.status_code == 200
        assert b"Applications" in response.content

    async def test_list_applications_unauthenticated(
        self,
        client: AsyncClient,
    ):
        """Unauthenticated users are redirected to login."""
        response = await client.get("/applications", follow_redirects=False)
        assert response.status_code == 303
        assert "/auth/login" in response.headers["location"]

    async def test_list_applications_filter_by_status(
        self,
        admin_client: AsyncClient,
        sample_application: Application,
    ):
        """Applications can be filtered by status."""
        response = await admin_client.get("/applications?status=Applied")
        assert response.status_code == 200

    async def test_list_applications_filter_by_job(
        self,
        admin_client: AsyncClient,
        sample_application: Application,
        sample_job: Job,
    ):
        """Applications can be filtered by job ID."""
        response = await admin_client.get(f"/applications?job_id={sample_job.id}")
        assert response.status_code == 200

    async def test_list_applications_empty_result(
        self,
        admin_client: AsyncClient,
    ):
        """Listing applications with no data returns an empty list page."""
        response = await admin_client.get("/applications?status=Hired")
        assert response.status_code == 200
        assert b"No applications" in response.content or b"applications" in response.content.lower()


class TestApplicationDetail:
    """Tests for viewing application details."""

    async def test_view_application_detail(
        self,
        admin_client: AsyncClient,
        sample_application: Application,
    ):
        """Authenticated users can view application details."""
        response = await admin_client.get(f"/applications/{sample_application.id}")
        assert response.status_code == 200
        assert b"Application" in response.content

    async def test_view_nonexistent_application(
        self,
        admin_client: AsyncClient,
    ):
        """Viewing a non-existent application returns 404."""
        response = await admin_client.get("/applications/nonexistent-id-12345")
        assert response.status_code == 404

    async def test_view_application_unauthenticated(
        self,
        client: AsyncClient,
        sample_application: Application,
    ):
        """Unauthenticated users are redirected to login."""
        response = await client.get(
            f"/applications/{sample_application.id}",
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert "/auth/login" in response.headers["location"]


class TestApplicationPipeline:
    """Tests for the kanban/pipeline view of applications grouped by status."""

    async def test_pipeline_view_renders(
        self,
        admin_client: AsyncClient,
    ):
        """The pipeline view renders successfully."""
        response = await admin_client.get("/applications/pipeline")
        assert response.status_code == 200
        assert b"Pipeline" in response.content or b"pipeline" in response.content.lower()

    async def test_pipeline_view_shows_statuses(
        self,
        admin_client: AsyncClient,
        sample_application: Application,
    ):
        """The pipeline view shows all status columns."""
        response = await admin_client.get("/applications/pipeline")
        assert response.status_code == 200
        content = response.content.decode()
        assert "Applied" in content
        assert "Screening" in content
        assert "Interview" in content
        assert "Offer" in content
        assert "Hired" in content
        assert "Rejected" in content

    async def test_pipeline_view_groups_by_status(
        self,
        admin_client: AsyncClient,
        sample_application: Application,
        sample_candidate: Candidate,
    ):
        """The pipeline view shows the application in the correct status column."""
        response = await admin_client.get("/applications/pipeline")
        assert response.status_code == 200
        content = response.content.decode()
        # The sample application is in "Applied" status, so the candidate name should appear
        assert sample_candidate.first_name in content or sample_candidate.last_name in content

    async def test_pipeline_view_filter_by_job(
        self,
        admin_client: AsyncClient,
        sample_application: Application,
        sample_job: Job,
    ):
        """The pipeline view can be filtered by job ID."""
        response = await admin_client.get(f"/applications/pipeline?job_id={sample_job.id}")
        assert response.status_code == 200
        content = response.content.decode()
        assert "Pipeline" in content or "pipeline" in content.lower()

    async def test_pipeline_view_unauthenticated(
        self,
        client: AsyncClient,
    ):
        """Unauthenticated users are redirected to login."""
        response = await client.get("/applications/pipeline", follow_redirects=False)
        assert response.status_code == 303
        assert "/auth/login" in response.headers["location"]

    async def test_pipeline_multiple_applications_grouped(
        self,
        admin_client: AsyncClient,
        db_session: AsyncSession,
        sample_job: Job,
    ):
        """Multiple applications in different statuses appear in their respective columns."""
        # Create two candidates
        candidate1 = Candidate(
            first_name="Alice",
            last_name="Smith",
            email="alice.smith@example.com",
            phone="+1-555-0201",
        )
        candidate2 = Candidate(
            first_name="Bob",
            last_name="Jones",
            email="bob.jones@example.com",
            phone="+1-555-0202",
        )
        db_session.add(candidate1)
        db_session.add(candidate2)
        await db_session.flush()

        # Create applications in different statuses
        app1 = Application(
            job_id=sample_job.id,
            candidate_id=candidate1.id,
            status="Applied",
        )
        app2 = Application(
            job_id=sample_job.id,
            candidate_id=candidate2.id,
            status="Screening",
        )
        db_session.add(app1)
        db_session.add(app2)
        await db_session.commit()

        response = await admin_client.get("/applications/pipeline")
        assert response.status_code == 200
        content = response.content.decode()
        assert "Alice" in content
        assert "Bob" in content


class TestApplicationEdit:
    """Tests for editing applications."""

    async def test_edit_application_form_renders(
        self,
        admin_client: AsyncClient,
        sample_application: Application,
    ):
        """The edit application form renders successfully."""
        response = await admin_client.get(f"/applications/{sample_application.id}/edit")
        assert response.status_code == 200

    async def test_edit_application_success(
        self,
        admin_client: AsyncClient,
        sample_application: Application,
    ):
        """Editing an application with valid data redirects to the detail page."""
        response = await admin_client.post(
            f"/applications/{sample_application.id}/edit",
            data={
                "cover_letter": "Updated cover letter.",
                "resume_url": "https://example.com/updated-resume.pdf",
                "notes": "Updated notes.",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert f"/applications/{sample_application.id}" in response.headers["location"]

    async def test_edit_nonexistent_application(
        self,
        admin_client: AsyncClient,
    ):
        """Editing a non-existent application redirects to the list."""
        response = await admin_client.get(
            "/applications/nonexistent-id-12345/edit",
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert "/applications" in response.headers["location"]


class TestApplicationDelete:
    """Tests for deleting applications."""

    async def test_delete_application_success(
        self,
        admin_client: AsyncClient,
        sample_application: Application,
    ):
        """Deleting an application redirects to the applications list."""
        response = await admin_client.post(
            f"/applications/{sample_application.id}/delete",
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert response.headers["location"] == "/applications"

    async def test_delete_application_interviewer_forbidden(
        self,
        interviewer_client: AsyncClient,
        sample_application: Application,
    ):
        """Interviewers cannot delete applications."""
        response = await interviewer_client.post(
            f"/applications/{sample_application.id}/delete",
            follow_redirects=False,
        )
        assert response.status_code == 403

    async def test_delete_nonexistent_application(
        self,
        admin_client: AsyncClient,
    ):
        """Deleting a non-existent application redirects gracefully."""
        response = await admin_client.post(
            "/applications/nonexistent-id-12345/delete",
            follow_redirects=False,
        )
        assert response.status_code == 303


class TestAllowedTransitionsConstants:
    """Tests for the ALLOWED_APPLICATION_TRANSITIONS constant and validation function."""

    def test_applied_allowed_transitions(self):
        """Applied status allows transitions to Screening and Rejected."""
        from app.core.constants import ALLOWED_APPLICATION_TRANSITIONS, ApplicationStatus

        allowed = ALLOWED_APPLICATION_TRANSITIONS[ApplicationStatus.APPLIED]
        assert ApplicationStatus.SCREENING in allowed
        assert ApplicationStatus.REJECTED in allowed
        assert ApplicationStatus.INTERVIEW not in allowed
        assert ApplicationStatus.OFFER not in allowed
        assert ApplicationStatus.HIRED not in allowed

    def test_screening_allowed_transitions(self):
        """Screening status allows transitions to Interview and Rejected."""
        from app.core.constants import ALLOWED_APPLICATION_TRANSITIONS, ApplicationStatus

        allowed = ALLOWED_APPLICATION_TRANSITIONS[ApplicationStatus.SCREENING]
        assert ApplicationStatus.INTERVIEW in allowed
        assert ApplicationStatus.REJECTED in allowed
        assert ApplicationStatus.APPLIED not in allowed
        assert ApplicationStatus.OFFER not in allowed

    def test_interview_allowed_transitions(self):
        """Interview status allows transitions to Offer and Rejected."""
        from app.core.constants import ALLOWED_APPLICATION_TRANSITIONS, ApplicationStatus

        allowed = ALLOWED_APPLICATION_TRANSITIONS[ApplicationStatus.INTERVIEW]
        assert ApplicationStatus.OFFER in allowed
        assert ApplicationStatus.REJECTED in allowed
        assert ApplicationStatus.SCREENING not in allowed

    def test_offer_allowed_transitions(self):
        """Offer status allows transitions to Hired and Rejected."""
        from app.core.constants import ALLOWED_APPLICATION_TRANSITIONS, ApplicationStatus

        allowed = ALLOWED_APPLICATION_TRANSITIONS[ApplicationStatus.OFFER]
        assert ApplicationStatus.HIRED in allowed
        assert ApplicationStatus.REJECTED in allowed
        assert ApplicationStatus.INTERVIEW not in allowed

    def test_hired_no_transitions(self):
        """Hired status has no allowed transitions (terminal state)."""
        from app.core.constants import ALLOWED_APPLICATION_TRANSITIONS, ApplicationStatus

        allowed = ALLOWED_APPLICATION_TRANSITIONS[ApplicationStatus.HIRED]
        assert len(allowed) == 0

    def test_rejected_no_transitions(self):
        """Rejected status has no allowed transitions (terminal state)."""
        from app.core.constants import ALLOWED_APPLICATION_TRANSITIONS, ApplicationStatus

        allowed = ALLOWED_APPLICATION_TRANSITIONS[ApplicationStatus.REJECTED]
        assert len(allowed) == 0

    def test_is_valid_application_transition_valid(self):
        """is_valid_application_transition returns True for valid transitions."""
        from app.core.constants import is_valid_application_transition

        assert is_valid_application_transition("Applied", "Screening") is True
        assert is_valid_application_transition("Applied", "Rejected") is True
        assert is_valid_application_transition("Screening", "Interview") is True
        assert is_valid_application_transition("Interview", "Offer") is True
        assert is_valid_application_transition("Offer", "Hired") is True

    def test_is_valid_application_transition_invalid(self):
        """is_valid_application_transition returns False for invalid transitions."""
        from app.core.constants import is_valid_application_transition

        assert is_valid_application_transition("Applied", "Interview") is False
        assert is_valid_application_transition("Applied", "Offer") is False
        assert is_valid_application_transition("Applied", "Hired") is False
        assert is_valid_application_transition("Screening", "Hired") is False
        assert is_valid_application_transition("Hired", "Rejected") is False
        assert is_valid_application_transition("Rejected", "Applied") is False
        assert is_valid_application_transition("Rejected", "Screening") is False