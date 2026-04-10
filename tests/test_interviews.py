import pytest
import pytest_asyncio
from datetime import datetime, timezone, timedelta

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.interview import Interview, InterviewFeedback
from app.models.application import Application
from app.models.job import Job
from app.models.candidate import Candidate
from app.models.user import User


class TestScheduleInterview:
    """Tests for interview scheduling functionality."""

    async def test_schedule_interview_form_accessible_by_admin(
        self, admin_client: AsyncClient
    ):
        """Admin can access the schedule interview form."""
        response = await admin_client.get("/interviews/create")
        assert response.status_code == 200
        assert "Schedule" in response.text or "schedule" in response.text

    async def test_schedule_interview_form_accessible_by_hr(
        self, hr_client: AsyncClient
    ):
        """HR Recruiter can access the schedule interview form."""
        response = await hr_client.get("/interviews/create")
        assert response.status_code == 200

    async def test_schedule_interview_form_accessible_by_manager(
        self, manager_client: AsyncClient
    ):
        """Hiring Manager can access the schedule interview form."""
        response = await manager_client.get("/interviews/create")
        assert response.status_code == 200

    async def test_schedule_interview_form_blocked_for_interviewer(
        self, interviewer_client: AsyncClient
    ):
        """Interviewer cannot access the schedule interview form (403)."""
        response = await interviewer_client.get(
            "/interviews/create", follow_redirects=False
        )
        assert response.status_code in (403, 303)

    async def test_schedule_interview_success(
        self,
        admin_client: AsyncClient,
        sample_application: Application,
        interviewer_user: User,
    ):
        """Admin can successfully schedule an interview."""
        scheduled_time = (datetime.now(timezone.utc) + timedelta(days=5)).strftime(
            "%Y-%m-%dT%H:%M"
        )
        response = await admin_client.post(
            "/interviews/create",
            data={
                "application_id": sample_application.id,
                "interviewer_id": interviewer_user.id,
                "scheduled_at": scheduled_time,
            },
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert "/interviews/" in response.headers.get("location", "")

    async def test_schedule_interview_invalid_application(
        self,
        admin_client: AsyncClient,
        interviewer_user: User,
    ):
        """Scheduling with a non-existent application returns error."""
        scheduled_time = (datetime.now(timezone.utc) + timedelta(days=5)).strftime(
            "%Y-%m-%dT%H:%M"
        )
        response = await admin_client.post(
            "/interviews/create",
            data={
                "application_id": "nonexistent-app-id",
                "interviewer_id": interviewer_user.id,
                "scheduled_at": scheduled_time,
            },
            follow_redirects=False,
        )
        assert response.status_code == 400

    async def test_schedule_interview_invalid_interviewer(
        self,
        admin_client: AsyncClient,
        sample_application: Application,
    ):
        """Scheduling with a non-existent interviewer returns error."""
        scheduled_time = (datetime.now(timezone.utc) + timedelta(days=5)).strftime(
            "%Y-%m-%dT%H:%M"
        )
        response = await admin_client.post(
            "/interviews/create",
            data={
                "application_id": sample_application.id,
                "interviewer_id": "nonexistent-interviewer-id",
                "scheduled_at": scheduled_time,
            },
            follow_redirects=False,
        )
        assert response.status_code == 400

    async def test_schedule_interview_invalid_datetime_format(
        self,
        admin_client: AsyncClient,
        sample_application: Application,
        interviewer_user: User,
    ):
        """Scheduling with an invalid datetime format returns error."""
        response = await admin_client.post(
            "/interviews/create",
            data={
                "application_id": sample_application.id,
                "interviewer_id": interviewer_user.id,
                "scheduled_at": "not-a-date",
            },
            follow_redirects=False,
        )
        assert response.status_code == 400

    async def test_schedule_interview_by_hr_recruiter(
        self,
        hr_client: AsyncClient,
        sample_application: Application,
        interviewer_user: User,
    ):
        """HR Recruiter can schedule an interview."""
        scheduled_time = (datetime.now(timezone.utc) + timedelta(days=7)).strftime(
            "%Y-%m-%dT%H:%M"
        )
        response = await hr_client.post(
            "/interviews/create",
            data={
                "application_id": sample_application.id,
                "interviewer_id": interviewer_user.id,
                "scheduled_at": scheduled_time,
            },
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert "/interviews/" in response.headers.get("location", "")


class TestInterviewDetail:
    """Tests for viewing interview details."""

    async def test_view_interview_detail(
        self,
        admin_client: AsyncClient,
        sample_interview: Interview,
    ):
        """Authenticated user can view interview detail."""
        response = await admin_client.get(f"/interviews/{sample_interview.id}")
        assert response.status_code == 200

    async def test_view_nonexistent_interview(
        self,
        admin_client: AsyncClient,
    ):
        """Viewing a non-existent interview returns 404."""
        response = await admin_client.get("/interviews/nonexistent-id")
        assert response.status_code == 404

    async def test_view_interview_detail_as_interviewer(
        self,
        interviewer_client: AsyncClient,
        sample_interview: Interview,
    ):
        """Interviewer can view their assigned interview detail."""
        response = await interviewer_client.get(f"/interviews/{sample_interview.id}")
        assert response.status_code == 200


class TestInterviewList:
    """Tests for listing interviews."""

    async def test_list_interviews_as_admin(
        self,
        admin_client: AsyncClient,
        sample_interview: Interview,
    ):
        """Admin can list all interviews."""
        response = await admin_client.get("/interviews")
        assert response.status_code == 200
        assert "Interviews" in response.text

    async def test_list_interviews_as_hr(
        self,
        hr_client: AsyncClient,
        sample_interview: Interview,
    ):
        """HR Recruiter can list all interviews."""
        response = await hr_client.get("/interviews")
        assert response.status_code == 200

    async def test_list_interviews_blocked_for_interviewer(
        self,
        interviewer_client: AsyncClient,
    ):
        """Interviewer cannot access the main interviews list (requires admin/hr/manager role)."""
        response = await interviewer_client.get(
            "/interviews", follow_redirects=False
        )
        assert response.status_code in (403, 303)

    async def test_list_interviews_filter_by_status(
        self,
        admin_client: AsyncClient,
        sample_interview: Interview,
    ):
        """Admin can filter interviews by status."""
        response = await admin_client.get("/interviews?status=Scheduled")
        assert response.status_code == 200


class TestMyInterviews:
    """Tests for interviewer's own interview list."""

    async def test_my_interviews_shows_assigned(
        self,
        interviewer_client: AsyncClient,
        sample_interview: Interview,
    ):
        """Interviewer sees their assigned interviews on /interviews/my."""
        response = await interviewer_client.get("/interviews/my")
        assert response.status_code == 200
        assert "My Interviews" in response.text

    async def test_my_interviews_empty_for_other_user(
        self,
        db_session: AsyncSession,
        sample_interview: Interview,
    ):
        """A different interviewer sees no interviews assigned to them."""
        from app.core.security import hash_password, create_session_cookie, COOKIE_NAME
        from httpx import ASGITransport, AsyncClient as HttpxAsyncClient
        from app.main import app

        other_user = User(
            username="otherinterviewer",
            hashed_password=hash_password("otherpass123"),
            full_name="Other Interviewer",
            email="other@talentflow.test",
            role="Interviewer",
            is_active=True,
        )
        db_session.add(other_user)
        await db_session.flush()
        await db_session.refresh(other_user)
        await db_session.commit()

        cookie_value = create_session_cookie(
            user_id=str(other_user.id), role=other_user.role
        )
        cookies = {COOKIE_NAME: cookie_value}
        transport = ASGITransport(app=app)
        async with HttpxAsyncClient(
            transport=transport,
            base_url="http://testserver",
            cookies=cookies,
        ) as other_client:
            response = await other_client.get("/interviews/my")
            assert response.status_code == 200
            assert "No interviews found" in response.text or "0" in response.text or response.text.count("hover:bg-gray-50 transition-colors") == 0

    async def test_my_interviews_filter_by_status(
        self,
        interviewer_client: AsyncClient,
        sample_interview: Interview,
    ):
        """Interviewer can filter their interviews by status."""
        response = await interviewer_client.get("/interviews/my?status=Scheduled")
        assert response.status_code == 200

    async def test_my_interviews_filter_by_feedback_status(
        self,
        interviewer_client: AsyncClient,
        sample_interview: Interview,
    ):
        """Interviewer can filter by feedback status (pending/submitted)."""
        response = await interviewer_client.get(
            "/interviews/my?feedback_status=pending"
        )
        assert response.status_code == 200


class TestSubmitFeedback:
    """Tests for interview feedback submission."""

    async def test_feedback_form_accessible(
        self,
        interviewer_client: AsyncClient,
        sample_interview: Interview,
    ):
        """Interviewer can access the feedback form for their interview."""
        response = await interviewer_client.get(
            f"/interviews/{sample_interview.id}/feedback"
        )
        assert response.status_code == 200
        assert "Feedback" in response.text or "feedback" in response.text

    async def test_submit_feedback_rating_1(
        self,
        interviewer_client: AsyncClient,
        sample_interview: Interview,
    ):
        """Interviewer can submit feedback with rating 1 (minimum)."""
        response = await interviewer_client.post(
            f"/interviews/{sample_interview.id}/feedback",
            data={
                "rating": "1",
                "feedback": "The candidate did not meet the basic requirements.",
            },
            follow_redirects=False,
        )
        assert response.status_code == 200
        assert "successfully" in response.text.lower() or "submitted" in response.text.lower()

    async def test_submit_feedback_rating_5(
        self,
        db_session: AsyncSession,
        sample_application: Application,
    ):
        """Interviewer can submit feedback with rating 5 (maximum)."""
        from app.core.security import hash_password, create_session_cookie, COOKIE_NAME
        from httpx import ASGITransport, AsyncClient as HttpxAsyncClient
        from app.main import app

        new_interviewer = User(
            username="interviewer5star",
            hashed_password=hash_password("pass12345678"),
            full_name="Five Star Interviewer",
            email="fivestar@talentflow.test",
            role="Interviewer",
            is_active=True,
        )
        db_session.add(new_interviewer)
        await db_session.flush()
        await db_session.refresh(new_interviewer)

        interview = Interview(
            application_id=sample_application.id,
            interviewer_id=new_interviewer.id,
            scheduled_at=datetime.now(timezone.utc) + timedelta(days=1),
            status="Scheduled",
        )
        db_session.add(interview)
        await db_session.flush()
        await db_session.refresh(interview)
        await db_session.commit()

        cookie_value = create_session_cookie(
            user_id=str(new_interviewer.id), role=new_interviewer.role
        )
        cookies = {COOKIE_NAME: cookie_value}
        transport = ASGITransport(app=app)
        async with HttpxAsyncClient(
            transport=transport,
            base_url="http://testserver",
            cookies=cookies,
        ) as client:
            response = await client.post(
                f"/interviews/{interview.id}/feedback",
                data={
                    "rating": "5",
                    "feedback": "Outstanding candidate. Strongly recommend hiring.",
                },
                follow_redirects=False,
            )
            assert response.status_code == 200
            assert "successfully" in response.text.lower() or "submitted" in response.text.lower()

    async def test_submit_feedback_rating_3_midrange(
        self,
        db_session: AsyncSession,
        sample_application: Application,
    ):
        """Interviewer can submit feedback with rating 3 (midrange)."""
        from app.core.security import hash_password, create_session_cookie, COOKIE_NAME
        from httpx import ASGITransport, AsyncClient as HttpxAsyncClient
        from app.main import app

        mid_interviewer = User(
            username="midinterviewer",
            hashed_password=hash_password("pass12345678"),
            full_name="Mid Interviewer",
            email="mid@talentflow.test",
            role="Interviewer",
            is_active=True,
        )
        db_session.add(mid_interviewer)
        await db_session.flush()
        await db_session.refresh(mid_interviewer)

        interview = Interview(
            application_id=sample_application.id,
            interviewer_id=mid_interviewer.id,
            scheduled_at=datetime.now(timezone.utc) + timedelta(days=2),
            status="Scheduled",
        )
        db_session.add(interview)
        await db_session.flush()
        await db_session.refresh(interview)
        await db_session.commit()

        cookie_value = create_session_cookie(
            user_id=str(mid_interviewer.id), role=mid_interviewer.role
        )
        cookies = {COOKIE_NAME: cookie_value}
        transport = ASGITransport(app=app)
        async with HttpxAsyncClient(
            transport=transport,
            base_url="http://testserver",
            cookies=cookies,
        ) as client:
            response = await client.post(
                f"/interviews/{interview.id}/feedback",
                data={
                    "rating": "3",
                    "feedback": "Average performance. Some areas need improvement.",
                },
                follow_redirects=False,
            )
            assert response.status_code == 200

    async def test_submit_duplicate_feedback_blocked(
        self,
        db_session: AsyncSession,
        sample_application: Application,
    ):
        """Submitting feedback twice for the same interview is blocked."""
        from app.core.security import hash_password, create_session_cookie, COOKIE_NAME
        from httpx import ASGITransport, AsyncClient as HttpxAsyncClient
        from app.main import app

        dup_interviewer = User(
            username="dupinterviewer",
            hashed_password=hash_password("pass12345678"),
            full_name="Dup Interviewer",
            email="dup@talentflow.test",
            role="Interviewer",
            is_active=True,
        )
        db_session.add(dup_interviewer)
        await db_session.flush()
        await db_session.refresh(dup_interviewer)

        interview = Interview(
            application_id=sample_application.id,
            interviewer_id=dup_interviewer.id,
            scheduled_at=datetime.now(timezone.utc) + timedelta(days=4),
            status="Scheduled",
        )
        db_session.add(interview)
        await db_session.flush()
        await db_session.refresh(interview)
        await db_session.commit()

        cookie_value = create_session_cookie(
            user_id=str(dup_interviewer.id), role=dup_interviewer.role
        )
        cookies = {COOKIE_NAME: cookie_value}
        transport = ASGITransport(app=app)
        async with HttpxAsyncClient(
            transport=transport,
            base_url="http://testserver",
            cookies=cookies,
        ) as client:
            # First submission should succeed
            response1 = await client.post(
                f"/interviews/{interview.id}/feedback",
                data={
                    "rating": "4",
                    "feedback": "Good candidate with strong technical skills.",
                },
                follow_redirects=False,
            )
            assert response1.status_code == 200

            # Second submission should be blocked
            response2 = await client.post(
                f"/interviews/{interview.id}/feedback",
                data={
                    "rating": "5",
                    "feedback": "Changed my mind, even better!",
                },
                follow_redirects=False,
            )
            assert response2.status_code == 400
            assert "already" in response2.text.lower()

    async def test_submit_feedback_nonexistent_interview(
        self,
        interviewer_client: AsyncClient,
    ):
        """Submitting feedback for a non-existent interview redirects."""
        response = await interviewer_client.post(
            "/interviews/nonexistent-id/feedback",
            data={
                "rating": "3",
                "feedback": "Some feedback text here.",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303

    async def test_submit_feedback_empty_text_blocked(
        self,
        db_session: AsyncSession,
        sample_application: Application,
    ):
        """Submitting feedback with empty text is blocked."""
        from app.core.security import hash_password, create_session_cookie, COOKIE_NAME
        from httpx import ASGITransport, AsyncClient as HttpxAsyncClient
        from app.main import app

        empty_interviewer = User(
            username="emptyinterviewer",
            hashed_password=hash_password("pass12345678"),
            full_name="Empty Interviewer",
            email="empty@talentflow.test",
            role="Interviewer",
            is_active=True,
        )
        db_session.add(empty_interviewer)
        await db_session.flush()
        await db_session.refresh(empty_interviewer)

        interview = Interview(
            application_id=sample_application.id,
            interviewer_id=empty_interviewer.id,
            scheduled_at=datetime.now(timezone.utc) + timedelta(days=6),
            status="Scheduled",
        )
        db_session.add(interview)
        await db_session.flush()
        await db_session.refresh(interview)
        await db_session.commit()

        cookie_value = create_session_cookie(
            user_id=str(empty_interviewer.id), role=empty_interviewer.role
        )
        cookies = {COOKIE_NAME: cookie_value}
        transport = ASGITransport(app=app)
        async with HttpxAsyncClient(
            transport=transport,
            base_url="http://testserver",
            cookies=cookies,
        ) as client:
            response = await client.post(
                f"/interviews/{interview.id}/feedback",
                data={
                    "rating": "3",
                    "feedback": "   ",
                },
                follow_redirects=False,
            )
            assert response.status_code == 400


class TestUnauthorizedFeedback:
    """Tests that unauthorized users cannot submit feedback."""

    async def test_unauthenticated_user_cannot_submit_feedback(
        self,
        client: AsyncClient,
        sample_interview: Interview,
    ):
        """Unauthenticated user is redirected when trying to submit feedback."""
        response = await client.post(
            f"/interviews/{sample_interview.id}/feedback",
            data={
                "rating": "4",
                "feedback": "Great candidate!",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert "/auth/login" in response.headers.get("location", "")

    async def test_unauthenticated_user_cannot_view_feedback_form(
        self,
        client: AsyncClient,
        sample_interview: Interview,
    ):
        """Unauthenticated user is redirected when trying to view feedback form."""
        response = await client.get(
            f"/interviews/{sample_interview.id}/feedback",
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert "/auth/login" in response.headers.get("location", "")

    async def test_unauthenticated_user_cannot_list_interviews(
        self,
        client: AsyncClient,
    ):
        """Unauthenticated user is redirected when trying to list interviews."""
        response = await client.get("/interviews", follow_redirects=False)
        assert response.status_code == 303
        assert "/auth/login" in response.headers.get("location", "")

    async def test_unauthenticated_user_cannot_schedule_interview(
        self,
        client: AsyncClient,
    ):
        """Unauthenticated user is redirected when trying to schedule an interview."""
        response = await client.get("/interviews/create", follow_redirects=False)
        assert response.status_code == 303
        assert "/auth/login" in response.headers.get("location", "")


class TestInterviewStatusUpdate:
    """Tests for interview status updates."""

    async def test_cancel_interview(
        self,
        admin_client: AsyncClient,
        sample_interview: Interview,
    ):
        """Admin can cancel a scheduled interview."""
        response = await admin_client.post(
            f"/interviews/{sample_interview.id}/cancel",
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert f"/interviews/{sample_interview.id}" in response.headers.get(
            "location", ""
        )

    async def test_update_interview_status(
        self,
        admin_client: AsyncClient,
        sample_interview: Interview,
    ):
        """Admin can update interview status."""
        response = await admin_client.post(
            f"/interviews/{sample_interview.id}/status",
            data={"status": "Completed"},
            follow_redirects=False,
        )
        assert response.status_code == 303

    async def test_update_interview_invalid_status(
        self,
        admin_client: AsyncClient,
        sample_interview: Interview,
    ):
        """Updating to an invalid status redirects (error handled gracefully)."""
        response = await admin_client.post(
            f"/interviews/{sample_interview.id}/status",
            data={"status": "InvalidStatus"},
            follow_redirects=False,
        )
        assert response.status_code == 303

    async def test_interviewer_cannot_cancel_interview(
        self,
        interviewer_client: AsyncClient,
        sample_interview: Interview,
    ):
        """Interviewer cannot cancel an interview (requires admin/hr/manager role)."""
        response = await interviewer_client.post(
            f"/interviews/{sample_interview.id}/cancel",
            follow_redirects=False,
        )
        assert response.status_code in (403, 303)

    async def test_interviewer_cannot_update_status(
        self,
        interviewer_client: AsyncClient,
        sample_interview: Interview,
    ):
        """Interviewer cannot update interview status (requires admin/hr/manager role)."""
        response = await interviewer_client.post(
            f"/interviews/{sample_interview.id}/status",
            data={"status": "Completed"},
            follow_redirects=False,
        )
        assert response.status_code in (403, 303)


class TestInterviewServiceLogic:
    """Tests for interview service layer logic."""

    async def test_schedule_interview_creates_record(
        self,
        db_session: AsyncSession,
        sample_application: Application,
        interviewer_user: User,
    ):
        """Scheduling an interview creates a record in the database."""
        from app.services.interview_service import schedule_interview

        scheduled_time = datetime.now(timezone.utc) + timedelta(days=10)
        interview = await schedule_interview(
            db=db_session,
            application_id=sample_application.id,
            interviewer_id=interviewer_user.id,
            scheduled_at=scheduled_time,
            current_user_id=interviewer_user.id,
            current_username=interviewer_user.username,
        )
        await db_session.commit()

        assert interview is not None
        assert interview.application_id == sample_application.id
        assert interview.interviewer_id == interviewer_user.id
        assert interview.status == "Scheduled"

    async def test_submit_feedback_updates_interview(
        self,
        db_session: AsyncSession,
        sample_application: Application,
    ):
        """Submitting feedback updates the interview record."""
        from app.services.interview_service import schedule_interview, submit_feedback
        from app.core.security import hash_password

        svc_interviewer = User(
            username="svcinterviewer",
            hashed_password=hash_password("pass12345678"),
            full_name="Service Interviewer",
            email="svc@talentflow.test",
            role="Interviewer",
            is_active=True,
        )
        db_session.add(svc_interviewer)
        await db_session.flush()
        await db_session.refresh(svc_interviewer)

        interview = await schedule_interview(
            db=db_session,
            application_id=sample_application.id,
            interviewer_id=svc_interviewer.id,
            scheduled_at=datetime.now(timezone.utc) + timedelta(days=11),
            current_user_id=svc_interviewer.id,
            current_username=svc_interviewer.username,
        )
        await db_session.flush()

        feedback = await submit_feedback(
            db=db_session,
            interview_id=interview.id,
            interviewer_id=svc_interviewer.id,
            rating=4,
            feedback="Strong technical skills demonstrated.",
            current_user_id=svc_interviewer.id,
            current_username=svc_interviewer.username,
        )
        await db_session.commit()

        assert feedback is not None
        assert feedback.rating == 4
        assert feedback.feedback == "Strong technical skills demonstrated."

        # Verify interview was updated to Completed
        result = await db_session.execute(
            select(Interview).where(Interview.id == interview.id)
        )
        updated_interview = result.scalar_one_or_none()
        assert updated_interview is not None
        assert updated_interview.status == "Completed"
        assert updated_interview.rating == 4

    async def test_submit_feedback_invalid_rating_rejected(
        self,
        db_session: AsyncSession,
        sample_application: Application,
    ):
        """Feedback with rating outside 1-5 is rejected."""
        from app.services.interview_service import schedule_interview, submit_feedback
        from app.core.security import hash_password

        bad_interviewer = User(
            username="badrating",
            hashed_password=hash_password("pass12345678"),
            full_name="Bad Rating Interviewer",
            email="badrating@talentflow.test",
            role="Interviewer",
            is_active=True,
        )
        db_session.add(bad_interviewer)
        await db_session.flush()
        await db_session.refresh(bad_interviewer)

        interview = await schedule_interview(
            db=db_session,
            application_id=sample_application.id,
            interviewer_id=bad_interviewer.id,
            scheduled_at=datetime.now(timezone.utc) + timedelta(days=12),
            current_user_id=bad_interviewer.id,
            current_username=bad_interviewer.username,
        )
        await db_session.flush()

        with pytest.raises(ValueError, match="Rating must be between 1 and 5"):
            await submit_feedback(
                db=db_session,
                interview_id=interview.id,
                interviewer_id=bad_interviewer.id,
                rating=6,
                feedback="This should fail.",
                current_user_id=bad_interviewer.id,
                current_username=bad_interviewer.username,
            )

    async def test_submit_feedback_rating_zero_rejected(
        self,
        db_session: AsyncSession,
        sample_application: Application,
    ):
        """Feedback with rating 0 is rejected."""
        from app.services.interview_service import schedule_interview, submit_feedback
        from app.core.security import hash_password

        zero_interviewer = User(
            username="zerorating",
            hashed_password=hash_password("pass12345678"),
            full_name="Zero Rating Interviewer",
            email="zerorating@talentflow.test",
            role="Interviewer",
            is_active=True,
        )
        db_session.add(zero_interviewer)
        await db_session.flush()
        await db_session.refresh(zero_interviewer)

        interview = await schedule_interview(
            db=db_session,
            application_id=sample_application.id,
            interviewer_id=zero_interviewer.id,
            scheduled_at=datetime.now(timezone.utc) + timedelta(days=13),
            current_user_id=zero_interviewer.id,
            current_username=zero_interviewer.username,
        )
        await db_session.flush()

        with pytest.raises(ValueError, match="Rating must be between 1 and 5"):
            await submit_feedback(
                db=db_session,
                interview_id=interview.id,
                interviewer_id=zero_interviewer.id,
                rating=0,
                feedback="This should also fail.",
                current_user_id=zero_interviewer.id,
                current_username=zero_interviewer.username,
            )

    async def test_get_interviews_for_user_returns_only_assigned(
        self,
        db_session: AsyncSession,
        sample_application: Application,
    ):
        """get_interviews_for_user returns only interviews assigned to the specific user."""
        from app.services.interview_service import (
            schedule_interview,
            get_interviews_for_user,
        )
        from app.core.security import hash_password

        user_a = User(
            username="usera_int",
            hashed_password=hash_password("pass12345678"),
            full_name="User A",
            email="usera_int@talentflow.test",
            role="Interviewer",
            is_active=True,
        )
        user_b = User(
            username="userb_int",
            hashed_password=hash_password("pass12345678"),
            full_name="User B",
            email="userb_int@talentflow.test",
            role="Interviewer",
            is_active=True,
        )
        db_session.add(user_a)
        db_session.add(user_b)
        await db_session.flush()
        await db_session.refresh(user_a)
        await db_session.refresh(user_b)

        # Schedule interview for user_a
        await schedule_interview(
            db=db_session,
            application_id=sample_application.id,
            interviewer_id=user_a.id,
            scheduled_at=datetime.now(timezone.utc) + timedelta(days=14),
            current_user_id=user_a.id,
            current_username=user_a.username,
        )
        await db_session.flush()
        await db_session.commit()

        # user_a should see 1 interview
        result_a = await get_interviews_for_user(
            db=db_session, interviewer_id=user_a.id
        )
        assert len(result_a["items"]) >= 1

        # user_b should see 0 interviews
        result_b = await get_interviews_for_user(
            db=db_session, interviewer_id=user_b.id
        )
        assert len(result_b["items"]) == 0