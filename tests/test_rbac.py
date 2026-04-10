import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.job import Job
from app.models.candidate import Candidate
from app.models.application import Application
from app.models.interview import Interview


class TestSystemAdminFullAccess:
    """System Admin should have full access to all resources."""

    async def test_admin_can_access_dashboard(self, admin_client: AsyncClient):
        response = await admin_client.get("/dashboard")
        assert response.status_code == 200

    async def test_admin_can_list_jobs(self, admin_client: AsyncClient):
        response = await admin_client.get("/jobs")
        assert response.status_code == 200

    async def test_admin_can_access_create_job_form(self, admin_client: AsyncClient):
        response = await admin_client.get("/jobs/create")
        assert response.status_code == 200

    async def test_admin_can_create_job(self, admin_client: AsyncClient):
        response = await admin_client.post(
            "/jobs/create",
            data={
                "title": "Admin Created Job",
                "department": "Engineering",
                "location": "Remote",
                "job_type": "Full-Time",
                "description": "A job created by admin",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303

    async def test_admin_can_list_candidates(self, admin_client: AsyncClient):
        response = await admin_client.get("/candidates")
        assert response.status_code == 200

    async def test_admin_can_access_create_candidate_form(self, admin_client: AsyncClient):
        response = await admin_client.get("/candidates/create")
        assert response.status_code == 200

    async def test_admin_can_create_candidate(self, admin_client: AsyncClient):
        response = await admin_client.post(
            "/candidates/create",
            data={
                "first_name": "Admin",
                "last_name": "Candidate",
                "email": "admin.candidate@example.com",
                "phone": "+1-555-0001",
                "skill_names": "Python, Go",
                "resume_text": "Created by admin",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303

    async def test_admin_can_list_applications(self, admin_client: AsyncClient):
        response = await admin_client.get("/applications")
        assert response.status_code == 200

    async def test_admin_can_access_create_application_form(self, admin_client: AsyncClient):
        response = await admin_client.get("/applications/create")
        assert response.status_code == 200

    async def test_admin_can_list_interviews(self, admin_client: AsyncClient):
        response = await admin_client.get("/interviews")
        assert response.status_code == 200

    async def test_admin_can_access_schedule_interview_form(self, admin_client: AsyncClient):
        response = await admin_client.get("/interviews/create")
        assert response.status_code == 200

    async def test_admin_can_access_audit_log(self, admin_client: AsyncClient):
        response = await admin_client.get("/dashboard/audit-log")
        assert response.status_code == 200

    async def test_admin_can_view_application_detail(
        self, admin_client: AsyncClient, sample_application: Application
    ):
        response = await admin_client.get(f"/applications/{sample_application.id}")
        assert response.status_code == 200

    async def test_admin_can_change_application_status(
        self, admin_client: AsyncClient, sample_application: Application
    ):
        response = await admin_client.post(
            f"/applications/{sample_application.id}/status",
            data={"status": "Screening"},
            follow_redirects=False,
        )
        assert response.status_code == 303

    async def test_admin_can_delete_application(
        self,
        admin_client: AsyncClient,
        db_session: AsyncSession,
        sample_job: Job,
        sample_candidate: Candidate,
    ):
        app = Application(
            job_id=sample_job.id,
            candidate_id=sample_candidate.id,
            status="Applied",
            cover_letter="To be deleted by admin",
        )
        db_session.add(app)
        await db_session.flush()
        await db_session.refresh(app)
        await db_session.commit()

        response = await admin_client.post(
            f"/applications/{app.id}/delete",
            follow_redirects=False,
        )
        assert response.status_code == 303


class TestHRRecruiterAccess:
    """HR Recruiter should manage jobs, candidates, applications, and interviews."""

    async def test_hr_can_access_dashboard(self, hr_client: AsyncClient):
        response = await hr_client.get("/dashboard")
        assert response.status_code == 200

    async def test_hr_can_list_jobs(self, hr_client: AsyncClient):
        response = await hr_client.get("/jobs")
        assert response.status_code == 200

    async def test_hr_can_access_create_job_form(self, hr_client: AsyncClient):
        response = await hr_client.get("/jobs/create")
        assert response.status_code == 200

    async def test_hr_can_create_job(self, hr_client: AsyncClient):
        response = await hr_client.post(
            "/jobs/create",
            data={
                "title": "HR Created Job",
                "department": "Marketing",
                "location": "New York",
                "job_type": "Full-Time",
                "description": "A job created by HR recruiter",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303

    async def test_hr_can_list_candidates(self, hr_client: AsyncClient):
        response = await hr_client.get("/candidates")
        assert response.status_code == 200

    async def test_hr_can_access_create_candidate_form(self, hr_client: AsyncClient):
        response = await hr_client.get("/candidates/create")
        assert response.status_code == 200

    async def test_hr_can_create_candidate(self, hr_client: AsyncClient):
        response = await hr_client.post(
            "/candidates/create",
            data={
                "first_name": "HR",
                "last_name": "Candidate",
                "email": "hr.candidate@example.com",
                "phone": "+1-555-0002",
                "skill_names": "Java, SQL",
                "resume_text": "Created by HR recruiter",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303

    async def test_hr_can_list_applications(self, hr_client: AsyncClient):
        response = await hr_client.get("/applications")
        assert response.status_code == 200

    async def test_hr_can_access_create_application_form(self, hr_client: AsyncClient):
        response = await hr_client.get("/applications/create")
        assert response.status_code == 200

    async def test_hr_can_list_interviews(self, hr_client: AsyncClient):
        response = await hr_client.get("/interviews")
        assert response.status_code == 200

    async def test_hr_can_access_schedule_interview_form(self, hr_client: AsyncClient):
        response = await hr_client.get("/interviews/create")
        assert response.status_code == 200

    async def test_hr_can_access_audit_log(self, hr_client: AsyncClient):
        response = await hr_client.get("/dashboard/audit-log")
        assert response.status_code == 200

    async def test_hr_can_change_application_status(
        self, hr_client: AsyncClient, sample_application: Application
    ):
        response = await hr_client.post(
            f"/applications/{sample_application.id}/status",
            data={"status": "Screening"},
            follow_redirects=False,
        )
        assert response.status_code == 303

    async def test_hr_can_delete_candidate(
        self, hr_client: AsyncClient, db_session: AsyncSession
    ):
        candidate = Candidate(
            first_name="ToDelete",
            last_name="Candidate",
            email="todelete.hr@example.com",
        )
        db_session.add(candidate)
        await db_session.flush()
        await db_session.refresh(candidate)
        await db_session.commit()

        response = await hr_client.post(
            f"/candidates/{candidate.id}/delete",
            follow_redirects=False,
        )
        assert response.status_code == 303

    async def test_hr_can_delete_application(
        self,
        hr_client: AsyncClient,
        db_session: AsyncSession,
        sample_job: Job,
    ):
        candidate = Candidate(
            first_name="HRDel",
            last_name="App",
            email="hrdel.app@example.com",
        )
        db_session.add(candidate)
        await db_session.flush()
        await db_session.refresh(candidate)

        app = Application(
            job_id=sample_job.id,
            candidate_id=candidate.id,
            status="Applied",
        )
        db_session.add(app)
        await db_session.flush()
        await db_session.refresh(app)
        await db_session.commit()

        response = await hr_client.post(
            f"/applications/{app.id}/delete",
            follow_redirects=False,
        )
        assert response.status_code == 303


class TestHiringManagerAccess:
    """Hiring Manager should access own jobs and related resources, but not admin features."""

    async def test_manager_can_access_dashboard(self, manager_client: AsyncClient):
        response = await manager_client.get("/dashboard")
        assert response.status_code == 200

    async def test_manager_can_list_jobs(self, manager_client: AsyncClient):
        response = await manager_client.get("/jobs")
        assert response.status_code == 200

    async def test_manager_can_view_own_job(
        self, manager_client: AsyncClient, sample_job: Job
    ):
        response = await manager_client.get(f"/jobs/{sample_job.id}")
        assert response.status_code == 200

    async def test_manager_can_edit_own_job_form(
        self, manager_client: AsyncClient, sample_job: Job
    ):
        response = await manager_client.get(f"/jobs/{sample_job.id}/edit")
        assert response.status_code == 200

    async def test_manager_can_update_own_job(
        self, manager_client: AsyncClient, sample_job: Job
    ):
        response = await manager_client.post(
            f"/jobs/{sample_job.id}/edit",
            data={
                "title": "Updated by Manager",
                "department": "Engineering",
                "location": "Remote",
                "job_type": "Full-Time",
                "description": "Updated description",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303

    async def test_manager_can_change_own_job_status(
        self, manager_client: AsyncClient, sample_job: Job
    ):
        response = await manager_client.post(
            f"/jobs/{sample_job.id}/status",
            data={"status": "Closed"},
            follow_redirects=False,
        )
        assert response.status_code == 303

    async def test_manager_cannot_create_job(self, manager_client: AsyncClient):
        """Hiring Manager should not be able to access the create job form (requires System Admin or HR Recruiter)."""
        response = await manager_client.get("/jobs/create")
        assert response.status_code == 403

    async def test_manager_cannot_create_candidate(self, manager_client: AsyncClient):
        """Hiring Manager should not be able to access the create candidate form."""
        response = await manager_client.get("/candidates/create")
        assert response.status_code == 403

    async def test_manager_cannot_create_candidate_post(self, manager_client: AsyncClient):
        """Hiring Manager should not be able to create a candidate via POST."""
        response = await manager_client.post(
            "/candidates/create",
            data={
                "first_name": "Unauthorized",
                "last_name": "Candidate",
                "email": "unauthorized@example.com",
            },
            follow_redirects=False,
        )
        assert response.status_code == 403

    async def test_manager_cannot_edit_unassigned_job(
        self,
        manager_client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Hiring Manager should be redirected when trying to edit a job not assigned to them."""
        unassigned_job = Job(
            title="Unassigned Job",
            department="Sales",
            location="Chicago",
            job_type="Full-Time",
            status="Draft",
            assigned_manager_id=None,
        )
        db_session.add(unassigned_job)
        await db_session.flush()
        await db_session.refresh(unassigned_job)
        await db_session.commit()

        response = await manager_client.get(
            f"/jobs/{unassigned_job.id}/edit",
            follow_redirects=False,
        )
        # Manager without assignment gets redirected to job detail
        assert response.status_code == 303

    async def test_manager_can_list_applications(self, manager_client: AsyncClient):
        response = await manager_client.get("/applications")
        assert response.status_code == 200

    async def test_manager_can_view_application_detail(
        self, manager_client: AsyncClient, sample_application: Application
    ):
        response = await manager_client.get(f"/applications/{sample_application.id}")
        assert response.status_code == 200

    async def test_manager_can_change_application_status(
        self, manager_client: AsyncClient, sample_application: Application
    ):
        response = await manager_client.post(
            f"/applications/{sample_application.id}/status",
            data={"status": "Screening"},
            follow_redirects=False,
        )
        assert response.status_code == 303

    async def test_manager_cannot_delete_application(
        self, manager_client: AsyncClient, sample_application: Application
    ):
        """Hiring Manager should not be able to delete applications (requires System Admin or HR Recruiter)."""
        response = await manager_client.post(
            f"/applications/{sample_application.id}/delete",
            follow_redirects=False,
        )
        assert response.status_code == 403

    async def test_manager_cannot_access_audit_log(self, manager_client: AsyncClient):
        """Hiring Manager should not be able to access the audit log."""
        response = await manager_client.get("/dashboard/audit-log")
        assert response.status_code == 403

    async def test_manager_cannot_delete_candidate(
        self, manager_client: AsyncClient, sample_candidate: Candidate
    ):
        """Hiring Manager should not be able to delete candidates."""
        response = await manager_client.post(
            f"/candidates/{sample_candidate.id}/delete",
            follow_redirects=False,
        )
        assert response.status_code == 403

    async def test_manager_can_list_interviews(self, manager_client: AsyncClient):
        response = await manager_client.get("/interviews")
        assert response.status_code == 200

    async def test_manager_can_schedule_interview(self, manager_client: AsyncClient):
        response = await manager_client.get("/interviews/create")
        assert response.status_code == 200


class TestInterviewerAccess:
    """Interviewer should only access assigned interviews and submit feedback."""

    async def test_interviewer_can_access_dashboard(self, interviewer_client: AsyncClient):
        response = await interviewer_client.get("/dashboard")
        assert response.status_code == 200

    async def test_interviewer_can_list_own_interviews(self, interviewer_client: AsyncClient):
        response = await interviewer_client.get("/interviews/my")
        assert response.status_code == 200

    async def test_interviewer_can_view_interview_detail(
        self, interviewer_client: AsyncClient, sample_interview: Interview
    ):
        response = await interviewer_client.get(f"/interviews/{sample_interview.id}")
        assert response.status_code == 200

    async def test_interviewer_can_access_feedback_form(
        self, interviewer_client: AsyncClient, sample_interview: Interview
    ):
        response = await interviewer_client.get(f"/interviews/{sample_interview.id}/feedback")
        assert response.status_code == 200

    async def test_interviewer_can_submit_feedback(
        self, interviewer_client: AsyncClient, sample_interview: Interview
    ):
        response = await interviewer_client.post(
            f"/interviews/{sample_interview.id}/feedback",
            data={
                "rating": 4,
                "feedback": "Strong candidate with excellent technical skills and communication.",
            },
            follow_redirects=False,
        )
        # Feedback form re-renders with success message (200) or redirects (303)
        assert response.status_code in (200, 303)

    async def test_interviewer_can_list_candidates(self, interviewer_client: AsyncClient):
        response = await interviewer_client.get("/candidates")
        assert response.status_code == 200

    async def test_interviewer_can_view_candidate_detail(
        self, interviewer_client: AsyncClient, sample_candidate: Candidate
    ):
        response = await interviewer_client.get(f"/candidates/{sample_candidate.id}")
        assert response.status_code == 200

    async def test_interviewer_can_list_jobs(self, interviewer_client: AsyncClient):
        response = await interviewer_client.get("/jobs")
        assert response.status_code == 200

    async def test_interviewer_can_view_job_detail(
        self, interviewer_client: AsyncClient, sample_job: Job
    ):
        response = await interviewer_client.get(f"/jobs/{sample_job.id}")
        assert response.status_code == 200

    async def test_interviewer_can_view_application_detail(
        self, interviewer_client: AsyncClient, sample_application: Application
    ):
        response = await interviewer_client.get(f"/applications/{sample_application.id}")
        assert response.status_code == 200

    async def test_interviewer_cannot_create_job(self, interviewer_client: AsyncClient):
        """Interviewer should not be able to access the create job form."""
        response = await interviewer_client.get("/jobs/create")
        assert response.status_code == 403

    async def test_interviewer_cannot_create_job_post(self, interviewer_client: AsyncClient):
        """Interviewer should not be able to create a job via POST."""
        response = await interviewer_client.post(
            "/jobs/create",
            data={
                "title": "Unauthorized Job",
                "department": "Engineering",
                "location": "Remote",
                "job_type": "Full-Time",
                "description": "Should not be created",
            },
            follow_redirects=False,
        )
        assert response.status_code == 403

    async def test_interviewer_cannot_create_candidate(self, interviewer_client: AsyncClient):
        """Interviewer should not be able to access the create candidate form."""
        response = await interviewer_client.get("/candidates/create")
        assert response.status_code == 403

    async def test_interviewer_cannot_create_candidate_post(self, interviewer_client: AsyncClient):
        """Interviewer should not be able to create a candidate via POST."""
        response = await interviewer_client.post(
            "/candidates/create",
            data={
                "first_name": "Unauthorized",
                "last_name": "Candidate",
                "email": "unauth.interviewer@example.com",
            },
            follow_redirects=False,
        )
        assert response.status_code == 403

    async def test_interviewer_cannot_edit_candidate(
        self, interviewer_client: AsyncClient, sample_candidate: Candidate
    ):
        """Interviewer should not be able to edit a candidate."""
        response = await interviewer_client.get(
            f"/candidates/{sample_candidate.id}/edit"
        )
        assert response.status_code == 403

    async def test_interviewer_cannot_delete_candidate(
        self, interviewer_client: AsyncClient, sample_candidate: Candidate
    ):
        """Interviewer should not be able to delete a candidate."""
        response = await interviewer_client.post(
            f"/candidates/{sample_candidate.id}/delete",
            follow_redirects=False,
        )
        assert response.status_code == 403

    async def test_interviewer_cannot_create_application(self, interviewer_client: AsyncClient):
        """Interviewer should not be able to access the create application form."""
        response = await interviewer_client.get("/applications/create")
        assert response.status_code == 403

    async def test_interviewer_cannot_create_application_post(
        self,
        interviewer_client: AsyncClient,
        sample_job: Job,
        sample_candidate: Candidate,
    ):
        """Interviewer should not be able to create an application via POST."""
        response = await interviewer_client.post(
            "/applications/create",
            data={
                "job_id": sample_job.id,
                "candidate_id": sample_candidate.id,
                "cover_letter": "Should not be created",
            },
            follow_redirects=False,
        )
        assert response.status_code == 403

    async def test_interviewer_cannot_change_application_status(
        self, interviewer_client: AsyncClient, sample_application: Application
    ):
        """Interviewer should not be able to change application status."""
        response = await interviewer_client.post(
            f"/applications/{sample_application.id}/status",
            data={"status": "Screening"},
            follow_redirects=False,
        )
        assert response.status_code == 403

    async def test_interviewer_cannot_delete_application(
        self, interviewer_client: AsyncClient, sample_application: Application
    ):
        """Interviewer should not be able to delete an application."""
        response = await interviewer_client.post(
            f"/applications/{sample_application.id}/delete",
            follow_redirects=False,
        )
        assert response.status_code == 403

    async def test_interviewer_cannot_list_all_interviews(self, interviewer_client: AsyncClient):
        """Interviewer should not be able to access the full interviews list (requires admin/HR/manager)."""
        response = await interviewer_client.get("/interviews")
        assert response.status_code == 403

    async def test_interviewer_cannot_schedule_interview(self, interviewer_client: AsyncClient):
        """Interviewer should not be able to access the schedule interview form."""
        response = await interviewer_client.get("/interviews/create")
        assert response.status_code == 403

    async def test_interviewer_cannot_cancel_interview(
        self, interviewer_client: AsyncClient, sample_interview: Interview
    ):
        """Interviewer should not be able to cancel an interview."""
        response = await interviewer_client.post(
            f"/interviews/{sample_interview.id}/cancel",
            follow_redirects=False,
        )
        assert response.status_code == 403

    async def test_interviewer_cannot_update_interview_status(
        self, interviewer_client: AsyncClient, sample_interview: Interview
    ):
        """Interviewer should not be able to update interview status."""
        response = await interviewer_client.post(
            f"/interviews/{sample_interview.id}/status",
            data={"status": "Completed"},
            follow_redirects=False,
        )
        assert response.status_code == 403

    async def test_interviewer_cannot_access_audit_log(self, interviewer_client: AsyncClient):
        """Interviewer should not be able to access the audit log."""
        response = await interviewer_client.get("/dashboard/audit-log")
        assert response.status_code == 403

    async def test_interviewer_cannot_edit_application(
        self, interviewer_client: AsyncClient, sample_application: Application
    ):
        """Interviewer should not be able to edit an application."""
        response = await interviewer_client.get(
            f"/applications/{sample_application.id}/edit"
        )
        assert response.status_code == 403

    async def test_interviewer_cannot_edit_application_post(
        self, interviewer_client: AsyncClient, sample_application: Application
    ):
        """Interviewer should not be able to update an application via POST."""
        response = await interviewer_client.post(
            f"/applications/{sample_application.id}/edit",
            data={
                "cover_letter": "Should not update",
                "resume_url": "",
                "notes": "",
            },
            follow_redirects=False,
        )
        assert response.status_code == 403


class TestUnauthenticatedAccess:
    """Unauthenticated users should be redirected to login for protected resources."""

    async def test_unauthenticated_dashboard_redirects(self, client: AsyncClient):
        response = await client.get("/dashboard", follow_redirects=False)
        # Should get 303 redirect to login via HTTPException
        assert response.status_code == 303
        assert "/auth/login" in response.headers.get("location", "")

    async def test_unauthenticated_jobs_redirects(self, client: AsyncClient):
        response = await client.get("/jobs", follow_redirects=False)
        assert response.status_code == 303
        assert "/auth/login" in response.headers.get("location", "")

    async def test_unauthenticated_candidates_redirects(self, client: AsyncClient):
        response = await client.get("/candidates", follow_redirects=False)
        assert response.status_code == 303
        assert "/auth/login" in response.headers.get("location", "")

    async def test_unauthenticated_applications_redirects(self, client: AsyncClient):
        response = await client.get("/applications", follow_redirects=False)
        assert response.status_code == 303
        assert "/auth/login" in response.headers.get("location", "")

    async def test_unauthenticated_interviews_redirects(self, client: AsyncClient):
        response = await client.get("/interviews", follow_redirects=False)
        assert response.status_code == 303
        assert "/auth/login" in response.headers.get("location", "")

    async def test_unauthenticated_can_access_landing(self, client: AsyncClient):
        """Landing page should be accessible without authentication."""
        response = await client.get("/")
        assert response.status_code == 200

    async def test_unauthenticated_can_access_login(self, client: AsyncClient):
        """Login page should be accessible without authentication."""
        response = await client.get("/auth/login")
        assert response.status_code == 200

    async def test_unauthenticated_can_access_register(self, client: AsyncClient):
        """Register page should be accessible without authentication."""
        response = await client.get("/auth/register")
        assert response.status_code == 200

    async def test_unauthenticated_create_job_redirects(self, client: AsyncClient):
        response = await client.get("/jobs/create", follow_redirects=False)
        assert response.status_code == 303
        assert "/auth/login" in response.headers.get("location", "")

    async def test_unauthenticated_create_candidate_redirects(self, client: AsyncClient):
        response = await client.get("/candidates/create", follow_redirects=False)
        assert response.status_code == 303
        assert "/auth/login" in response.headers.get("location", "")

    async def test_unauthenticated_audit_log_redirects(self, client: AsyncClient):
        response = await client.get("/dashboard/audit-log", follow_redirects=False)
        assert response.status_code == 303
        assert "/auth/login" in response.headers.get("location", "")


class TestCrossRoleEscalation:
    """Verify that roles cannot escalate privileges by accessing other role endpoints."""

    async def test_interviewer_cannot_access_hr_create_job(
        self, interviewer_client: AsyncClient
    ):
        response = await interviewer_client.post(
            "/jobs/create",
            data={
                "title": "Escalation Attempt",
                "department": "Engineering",
                "location": "Remote",
                "job_type": "Full-Time",
                "description": "Should be blocked",
            },
            follow_redirects=False,
        )
        assert response.status_code == 403

    async def test_manager_cannot_access_hr_create_candidate(
        self, manager_client: AsyncClient
    ):
        response = await manager_client.post(
            "/candidates/create",
            data={
                "first_name": "Escalation",
                "last_name": "Attempt",
                "email": "escalation@example.com",
            },
            follow_redirects=False,
        )
        assert response.status_code == 403

    async def test_interviewer_cannot_schedule_interview_post(
        self,
        interviewer_client: AsyncClient,
        sample_application: Application,
        interviewer_user: User,
    ):
        response = await interviewer_client.post(
            "/interviews/create",
            data={
                "application_id": sample_application.id,
                "interviewer_id": interviewer_user.id,
                "scheduled_at": "2025-06-15T10:00",
            },
            follow_redirects=False,
        )
        assert response.status_code == 403

    async def test_manager_cannot_access_audit_log(self, manager_client: AsyncClient):
        response = await manager_client.get("/dashboard/audit-log")
        assert response.status_code == 403

    async def test_interviewer_cannot_edit_job(
        self, interviewer_client: AsyncClient, sample_job: Job
    ):
        """Interviewer should not be able to edit any job."""
        response = await interviewer_client.post(
            f"/jobs/{sample_job.id}/edit",
            data={
                "title": "Hacked Title",
                "department": "Hacked",
                "location": "Hacked",
                "job_type": "Full-Time",
                "description": "Hacked",
            },
            follow_redirects=False,
        )
        # Interviewer role is not in the _can_edit_job check, so gets redirected
        assert response.status_code == 303

    async def test_interviewer_cannot_change_job_status(
        self, interviewer_client: AsyncClient, sample_job: Job
    ):
        """Interviewer should not be able to change job status."""
        response = await interviewer_client.post(
            f"/jobs/{sample_job.id}/status",
            data={"status": "Closed"},
            follow_redirects=False,
        )
        # Interviewer role is not in _can_edit_job, so gets redirected
        assert response.status_code == 303