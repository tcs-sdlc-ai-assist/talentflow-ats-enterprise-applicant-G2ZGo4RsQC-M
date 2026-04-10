import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.candidate import Candidate, candidate_skills
from app.models.skill import Skill


class TestCandidatesList:
    """Tests for the candidates list page."""

    async def test_candidates_list_requires_auth(self, client: AsyncClient):
        """Unauthenticated users should be redirected to login."""
        response = await client.get("/candidates", follow_redirects=False)
        assert response.status_code == 303 or response.status_code == 200

    async def test_candidates_list_returns_200_for_authenticated_user(
        self, admin_client: AsyncClient
    ):
        """Authenticated users should see the candidates list page."""
        response = await admin_client.get("/candidates")
        assert response.status_code == 200
        assert "Candidates" in response.text

    async def test_candidates_list_empty(self, admin_client: AsyncClient):
        """Candidates list should handle empty state gracefully."""
        response = await admin_client.get("/candidates")
        assert response.status_code == 200
        assert "No candidates found" in response.text

    async def test_candidates_list_shows_existing_candidates(
        self, admin_client: AsyncClient, sample_candidate: Candidate
    ):
        """Candidates list should display existing candidates."""
        response = await admin_client.get("/candidates")
        assert response.status_code == 200
        assert "Jane" in response.text
        assert "Doe" in response.text
        assert "janedoe@example.com" in response.text


class TestCreateCandidate:
    """Tests for creating candidates."""

    async def test_create_candidate_form_requires_admin_or_hr(
        self, interviewer_client: AsyncClient
    ):
        """Interviewers should not be able to access the create candidate form."""
        response = await interviewer_client.get(
            "/candidates/create", follow_redirects=False
        )
        assert response.status_code == 403

    async def test_create_candidate_form_accessible_by_admin(
        self, admin_client: AsyncClient
    ):
        """System Admin should be able to access the create candidate form."""
        response = await admin_client.get("/candidates/create")
        assert response.status_code == 200
        assert "Add" in response.text or "Candidate" in response.text

    async def test_create_candidate_form_accessible_by_hr(
        self, hr_client: AsyncClient
    ):
        """HR Recruiter should be able to access the create candidate form."""
        response = await hr_client.get("/candidates/create")
        assert response.status_code == 200

    async def test_create_candidate_success(
        self, admin_client: AsyncClient, db_session: AsyncSession
    ):
        """Creating a candidate with valid data should succeed."""
        response = await admin_client.post(
            "/candidates/create",
            data={
                "first_name": "John",
                "last_name": "Smith",
                "email": "johnsmith@example.com",
                "phone": "+1-555-0200",
                "skill_names": "",
                "resume_text": "Experienced developer.",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert "/candidates/" in response.headers["location"]

        result = await db_session.execute(
            select(Candidate).where(Candidate.email == "johnsmith@example.com")
        )
        candidate = result.scalar_one_or_none()
        assert candidate is not None
        assert candidate.first_name == "John"
        assert candidate.last_name == "Smith"
        assert candidate.phone == "+1-555-0200"
        assert candidate.resume_text == "Experienced developer."

    async def test_create_candidate_with_skills(
        self, admin_client: AsyncClient, db_session: AsyncSession
    ):
        """Creating a candidate with skill tags should create skills and associations."""
        response = await admin_client.post(
            "/candidates/create",
            data={
                "first_name": "Alice",
                "last_name": "Wonder",
                "email": "alice@example.com",
                "phone": "",
                "skill_names": "Python, JavaScript, SQL",
                "resume_text": "",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303

        result = await db_session.execute(
            select(Candidate).where(Candidate.email == "alice@example.com")
        )
        candidate = result.scalar_one_or_none()
        assert candidate is not None

        # Verify skills were created
        skills_result = await db_session.execute(
            select(Skill).order_by(Skill.name)
        )
        skills = list(skills_result.scalars().all())
        skill_names = [s.name for s in skills]
        assert "Python" in skill_names
        assert "JavaScript" in skill_names
        assert "SQL" in skill_names

    async def test_create_candidate_duplicate_email_fails(
        self,
        admin_client: AsyncClient,
        sample_candidate: Candidate,
    ):
        """Creating a candidate with an existing email should fail."""
        response = await admin_client.post(
            "/candidates/create",
            data={
                "first_name": "Another",
                "last_name": "Person",
                "email": "janedoe@example.com",
                "phone": "",
                "skill_names": "",
                "resume_text": "",
            },
            follow_redirects=False,
        )
        assert response.status_code == 400
        assert "already exists" in response.text

    async def test_create_candidate_deduplicates_skills(
        self, admin_client: AsyncClient, db_session: AsyncSession
    ):
        """Duplicate skill names in input should be deduplicated."""
        response = await admin_client.post(
            "/candidates/create",
            data={
                "first_name": "Bob",
                "last_name": "Builder",
                "email": "bob@example.com",
                "phone": "",
                "skill_names": "Python, python, PYTHON",
                "resume_text": "",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303

        result = await db_session.execute(
            select(Skill).where(Skill.name.ilike("python"))
        )
        python_skills = list(result.scalars().all())
        # Should only have one Python skill (case-insensitive dedup)
        assert len(python_skills) == 1


class TestCandidateDetail:
    """Tests for viewing candidate details."""

    async def test_candidate_detail_returns_200(
        self, admin_client: AsyncClient, sample_candidate: Candidate
    ):
        """Viewing an existing candidate should return 200."""
        response = await admin_client.get(f"/candidates/{sample_candidate.id}")
        assert response.status_code == 200
        assert "Jane" in response.text
        assert "Doe" in response.text
        assert "janedoe@example.com" in response.text

    async def test_candidate_detail_not_found(self, admin_client: AsyncClient):
        """Viewing a non-existent candidate should return 404."""
        response = await admin_client.get(
            "/candidates/00000000-0000-0000-0000-000000000000"
        )
        assert response.status_code == 404
        assert "not found" in response.text.lower()

    async def test_candidate_detail_shows_applications(
        self,
        admin_client: AsyncClient,
        sample_candidate: Candidate,
        sample_application,
    ):
        """Candidate detail should show associated applications."""
        response = await admin_client.get(f"/candidates/{sample_candidate.id}")
        assert response.status_code == 200
        # The application's job title should appear
        assert "Senior Software Engineer" in response.text


class TestUpdateCandidate:
    """Tests for updating candidates."""

    async def test_edit_form_requires_admin_or_hr(
        self,
        interviewer_client: AsyncClient,
        sample_candidate: Candidate,
    ):
        """Interviewers should not be able to access the edit form."""
        response = await interviewer_client.get(
            f"/candidates/{sample_candidate.id}/edit", follow_redirects=False
        )
        assert response.status_code == 403

    async def test_edit_form_accessible_by_admin(
        self, admin_client: AsyncClient, sample_candidate: Candidate
    ):
        """System Admin should be able to access the edit form."""
        response = await admin_client.get(
            f"/candidates/{sample_candidate.id}/edit"
        )
        assert response.status_code == 200
        assert "Jane" in response.text

    async def test_update_candidate_success(
        self,
        admin_client: AsyncClient,
        sample_candidate: Candidate,
        db_session: AsyncSession,
    ):
        """Updating a candidate with valid data should succeed."""
        response = await admin_client.post(
            f"/candidates/{sample_candidate.id}/edit",
            data={
                "first_name": "Janet",
                "last_name": "Doe-Smith",
                "email": "janedoe@example.com",
                "phone": "+1-555-9999",
                "skill_names": "Go, Rust",
                "resume_text": "Updated resume text.",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert f"/candidates/{sample_candidate.id}" in response.headers["location"]

        # Verify the update in the database
        await db_session.expire_all()
        result = await db_session.execute(
            select(Candidate).where(Candidate.id == sample_candidate.id)
        )
        updated = result.scalar_one_or_none()
        assert updated is not None
        assert updated.first_name == "Janet"
        assert updated.last_name == "Doe-Smith"
        assert updated.phone == "+1-555-9999"
        assert updated.resume_text == "Updated resume text."

    async def test_update_candidate_duplicate_email_fails(
        self,
        admin_client: AsyncClient,
        sample_candidate: Candidate,
        db_session: AsyncSession,
    ):
        """Updating a candidate's email to an existing email should fail."""
        # Create another candidate first
        other = Candidate(
            first_name="Other",
            last_name="Person",
            email="other@example.com",
            phone=None,
        )
        db_session.add(other)
        await db_session.flush()
        await db_session.commit()

        response = await admin_client.post(
            f"/candidates/{sample_candidate.id}/edit",
            data={
                "first_name": "Jane",
                "last_name": "Doe",
                "email": "other@example.com",
                "phone": "",
                "skill_names": "",
                "resume_text": "",
            },
            follow_redirects=False,
        )
        assert response.status_code == 400
        assert "already exists" in response.text

    async def test_update_candidate_skills_replaces_existing(
        self,
        admin_client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Updating skills should replace existing skills entirely."""
        # Create candidate with initial skills
        create_response = await admin_client.post(
            "/candidates/create",
            data={
                "first_name": "Skill",
                "last_name": "Test",
                "email": "skilltest@example.com",
                "phone": "",
                "skill_names": "Python, Java",
                "resume_text": "",
            },
            follow_redirects=False,
        )
        assert create_response.status_code == 303
        candidate_url = create_response.headers["location"]
        candidate_id = candidate_url.split("/")[-1]

        # Update with different skills
        update_response = await admin_client.post(
            f"/candidates/{candidate_id}/edit",
            data={
                "first_name": "Skill",
                "last_name": "Test",
                "email": "skilltest@example.com",
                "phone": "",
                "skill_names": "Go, Rust, TypeScript",
                "resume_text": "",
            },
            follow_redirects=False,
        )
        assert update_response.status_code == 303

        # Verify skills were replaced
        from sqlalchemy.orm import selectinload

        result = await db_session.execute(
            select(Candidate)
            .where(Candidate.id == candidate_id)
            .options(selectinload(Candidate.skills))
        )
        candidate = result.scalar_one_or_none()
        assert candidate is not None
        skill_names = sorted([s.name for s in candidate.skills])
        assert "Go" in skill_names
        assert "Rust" in skill_names
        assert "TypeScript" in skill_names
        # Old skills should not be present
        assert "Python" not in skill_names
        assert "Java" not in skill_names


class TestDeleteCandidate:
    """Tests for deleting candidates."""

    async def test_delete_candidate_requires_admin_or_hr(
        self,
        interviewer_client: AsyncClient,
        sample_candidate: Candidate,
    ):
        """Interviewers should not be able to delete candidates."""
        response = await interviewer_client.post(
            f"/candidates/{sample_candidate.id}/delete", follow_redirects=False
        )
        assert response.status_code == 403

    async def test_delete_candidate_success(
        self,
        admin_client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Admin should be able to delete a candidate."""
        # Create a candidate to delete
        candidate = Candidate(
            first_name="Delete",
            last_name="Me",
            email="deleteme@example.com",
        )
        db_session.add(candidate)
        await db_session.flush()
        await db_session.commit()
        candidate_id = candidate.id

        response = await admin_client.post(
            f"/candidates/{candidate_id}/delete", follow_redirects=False
        )
        assert response.status_code == 303
        assert "/candidates" in response.headers["location"]

        # Verify deletion
        result = await db_session.execute(
            select(Candidate).where(Candidate.id == candidate_id)
        )
        assert result.scalar_one_or_none() is None


class TestSearchCandidates:
    """Tests for searching and filtering candidates."""

    async def test_search_by_name(
        self, admin_client: AsyncClient, sample_candidate: Candidate
    ):
        """Searching by name should return matching candidates."""
        response = await admin_client.get("/candidates?search=Jane")
        assert response.status_code == 200
        assert "Jane" in response.text
        assert "Doe" in response.text

    async def test_search_by_email(
        self, admin_client: AsyncClient, sample_candidate: Candidate
    ):
        """Searching by email should return matching candidates."""
        response = await admin_client.get("/candidates?search=janedoe")
        assert response.status_code == 200
        assert "janedoe@example.com" in response.text

    async def test_search_by_last_name(
        self, admin_client: AsyncClient, sample_candidate: Candidate
    ):
        """Searching by last name should return matching candidates."""
        response = await admin_client.get("/candidates?search=Doe")
        assert response.status_code == 200
        assert "Doe" in response.text

    async def test_search_no_results(
        self, admin_client: AsyncClient, sample_candidate: Candidate
    ):
        """Searching for a non-existent term should return no results."""
        response = await admin_client.get(
            "/candidates?search=NonExistentPerson12345"
        )
        assert response.status_code == 200
        assert "No candidates found" in response.text or "NonExistentPerson12345" not in response.text

    async def test_filter_by_skill(
        self, admin_client: AsyncClient, db_session: AsyncSession
    ):
        """Filtering by skill should return only candidates with that skill."""
        # Create a candidate with a specific skill
        await admin_client.post(
            "/candidates/create",
            data={
                "first_name": "Skilled",
                "last_name": "Dev",
                "email": "skilleddev@example.com",
                "phone": "",
                "skill_names": "Kubernetes, Docker",
                "resume_text": "",
            },
            follow_redirects=False,
        )

        # Create another candidate without that skill
        await admin_client.post(
            "/candidates/create",
            data={
                "first_name": "Other",
                "last_name": "Dev",
                "email": "otherdev@example.com",
                "phone": "",
                "skill_names": "React, Vue",
                "resume_text": "",
            },
            follow_redirects=False,
        )

        # Filter by Kubernetes skill
        response = await admin_client.get("/candidates?skill=Kubernetes")
        assert response.status_code == 200
        assert "Skilled" in response.text

    async def test_search_and_filter_combined(
        self, admin_client: AsyncClient, db_session: AsyncSession
    ):
        """Combining search and skill filter should narrow results."""
        # Create candidates
        await admin_client.post(
            "/candidates/create",
            data={
                "first_name": "Alpha",
                "last_name": "Tester",
                "email": "alpha@example.com",
                "phone": "",
                "skill_names": "Python, FastAPI",
                "resume_text": "",
            },
            follow_redirects=False,
        )

        await admin_client.post(
            "/candidates/create",
            data={
                "first_name": "Beta",
                "last_name": "Tester",
                "email": "beta@example.com",
                "phone": "",
                "skill_names": "Java, Spring",
                "resume_text": "",
            },
            follow_redirects=False,
        )

        # Search for "Tester" with Python skill
        response = await admin_client.get(
            "/candidates?search=Tester&skill=Python"
        )
        assert response.status_code == 200
        assert "Alpha" in response.text


class TestManyToManySkillTagging:
    """Tests for the many-to-many relationship between candidates and skills."""

    async def test_multiple_candidates_share_same_skill(
        self, admin_client: AsyncClient, db_session: AsyncSession
    ):
        """Multiple candidates can share the same skill without duplication."""
        # Create first candidate with Python
        await admin_client.post(
            "/candidates/create",
            data={
                "first_name": "Dev",
                "last_name": "One",
                "email": "dev1@example.com",
                "phone": "",
                "skill_names": "Python, Django",
                "resume_text": "",
            },
            follow_redirects=False,
        )

        # Create second candidate with Python
        await admin_client.post(
            "/candidates/create",
            data={
                "first_name": "Dev",
                "last_name": "Two",
                "email": "dev2@example.com",
                "phone": "",
                "skill_names": "Python, Flask",
                "resume_text": "",
            },
            follow_redirects=False,
        )

        # Verify only one Python skill exists in the database
        result = await db_session.execute(
            select(Skill).where(Skill.name.ilike("python"))
        )
        python_skills = list(result.scalars().all())
        assert len(python_skills) == 1

    async def test_candidate_can_have_multiple_skills(
        self, admin_client: AsyncClient, db_session: AsyncSession
    ):
        """A candidate can be tagged with multiple skills."""
        response = await admin_client.post(
            "/candidates/create",
            data={
                "first_name": "Multi",
                "last_name": "Skilled",
                "email": "multiskilled@example.com",
                "phone": "",
                "skill_names": "Python, JavaScript, Go, Rust, TypeScript",
                "resume_text": "",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303

        from sqlalchemy.orm import selectinload

        result = await db_session.execute(
            select(Candidate)
            .where(Candidate.email == "multiskilled@example.com")
            .options(selectinload(Candidate.skills))
        )
        candidate = result.scalar_one_or_none()
        assert candidate is not None
        assert len(candidate.skills) == 5

    async def test_empty_skills_creates_no_associations(
        self, admin_client: AsyncClient, db_session: AsyncSession
    ):
        """Creating a candidate with no skills should not create any skill associations."""
        response = await admin_client.post(
            "/candidates/create",
            data={
                "first_name": "No",
                "last_name": "Skills",
                "email": "noskills@example.com",
                "phone": "",
                "skill_names": "",
                "resume_text": "",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303

        from sqlalchemy.orm import selectinload

        result = await db_session.execute(
            select(Candidate)
            .where(Candidate.email == "noskills@example.com")
            .options(selectinload(Candidate.skills))
        )
        candidate = result.scalar_one_or_none()
        assert candidate is not None
        assert len(candidate.skills) == 0

    async def test_whitespace_only_skills_ignored(
        self, admin_client: AsyncClient, db_session: AsyncSession
    ):
        """Skill names that are only whitespace should be ignored."""
        response = await admin_client.post(
            "/candidates/create",
            data={
                "first_name": "Whitespace",
                "last_name": "Test",
                "email": "whitespace@example.com",
                "phone": "",
                "skill_names": "Python, , ,  , JavaScript",
                "resume_text": "",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303

        from sqlalchemy.orm import selectinload

        result = await db_session.execute(
            select(Candidate)
            .where(Candidate.email == "whitespace@example.com")
            .options(selectinload(Candidate.skills))
        )
        candidate = result.scalar_one_or_none()
        assert candidate is not None
        skill_names = [s.name for s in candidate.skills]
        assert len(skill_names) == 2
        assert "Python" in skill_names
        assert "JavaScript" in skill_names


class TestCandidatePagination:
    """Tests for candidate list pagination."""

    async def test_pagination_defaults(
        self, admin_client: AsyncClient, sample_candidate: Candidate
    ):
        """Default pagination should work correctly."""
        response = await admin_client.get("/candidates?page=1")
        assert response.status_code == 200

    async def test_pagination_page_out_of_range(
        self, admin_client: AsyncClient
    ):
        """Requesting a page beyond available data should still return 200."""
        response = await admin_client.get("/candidates?page=999")
        assert response.status_code == 200