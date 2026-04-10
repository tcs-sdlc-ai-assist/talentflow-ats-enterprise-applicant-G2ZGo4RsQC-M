import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.candidate import Candidate, candidate_skills
from app.models.skill import Skill

logger = logging.getLogger(__name__)


async def _get_or_create_skills(
    db: AsyncSession, skill_names: list[str]
) -> list[Skill]:
    """Get existing skills or create new ones by name.

    Deduplicates by lowercase comparison. Returns a list of Skill objects.
    """
    if not skill_names:
        return []

    cleaned: dict[str, str] = {}
    for name in skill_names:
        stripped = name.strip()
        if stripped:
            lower = stripped.lower()
            if lower not in cleaned:
                cleaned[lower] = stripped

    if not cleaned:
        return []

    result = await db.execute(
        select(Skill).where(func.lower(Skill.name).in_(list(cleaned.keys())))
    )
    existing_skills = list(result.scalars().all())
    existing_map = {skill.name.lower(): skill for skill in existing_skills}

    skills: list[Skill] = []
    for lower_name, display_name in cleaned.items():
        if lower_name in existing_map:
            skills.append(existing_map[lower_name])
        else:
            new_skill = Skill(name=display_name)
            db.add(new_skill)
            await db.flush()
            skills.append(new_skill)
            existing_map[lower_name] = new_skill

    return skills


async def create_candidate(
    db: AsyncSession,
    first_name: str,
    last_name: str,
    email: str,
    phone: Optional[str] = None,
    resume_text: Optional[str] = None,
    skill_names: Optional[list[str]] = None,
) -> Candidate:
    """Create a new candidate with optional skill tags.

    Args:
        db: Async database session.
        first_name: Candidate's first name.
        last_name: Candidate's last name.
        email: Candidate's email address (must be unique).
        phone: Optional phone number.
        resume_text: Optional resume text content.
        skill_names: Optional list of skill name strings to associate.

    Returns:
        The newly created Candidate object with skills loaded.

    Raises:
        ValueError: If a candidate with the given email already exists.
    """
    existing = await db.execute(
        select(Candidate).where(func.lower(Candidate.email) == email.lower().strip())
    )
    if existing.scalar_one_or_none() is not None:
        raise ValueError(f"A candidate with email '{email}' already exists.")

    candidate = Candidate(
        first_name=first_name.strip(),
        last_name=last_name.strip(),
        email=email.strip(),
        phone=phone.strip() if phone else None,
        resume_text=resume_text,
    )
    db.add(candidate)
    await db.flush()

    if skill_names:
        skills = await _get_or_create_skills(db, skill_names)
        candidate.skills = skills
        await db.flush()

    logger.info(
        "Created candidate: %s %s (%s) with %d skills",
        candidate.first_name,
        candidate.last_name,
        candidate.email,
        len(candidate.skills) if candidate.skills else 0,
    )

    return candidate


async def update_candidate(
    db: AsyncSession,
    candidate_id: str,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    resume_text: Optional[str] = None,
    skill_names: Optional[list[str]] = None,
) -> Optional[Candidate]:
    """Update an existing candidate's information and/or skills.

    Args:
        db: Async database session.
        candidate_id: The UUID of the candidate to update.
        first_name: New first name (if provided).
        last_name: New last name (if provided).
        email: New email (if provided, must be unique).
        phone: New phone number (if provided).
        resume_text: New resume text (if provided).
        skill_names: New list of skill names (replaces existing skills if provided).

    Returns:
        The updated Candidate object, or None if not found.

    Raises:
        ValueError: If the new email is already taken by another candidate.
    """
    result = await db.execute(
        select(Candidate)
        .where(Candidate.id == candidate_id)
        .options(selectinload(Candidate.skills))
    )
    candidate = result.scalar_one_or_none()
    if candidate is None:
        return None

    if email is not None:
        clean_email = email.strip().lower()
        if clean_email != candidate.email.lower():
            existing = await db.execute(
                select(Candidate).where(
                    func.lower(Candidate.email) == clean_email,
                    Candidate.id != candidate_id,
                )
            )
            if existing.scalar_one_or_none() is not None:
                raise ValueError(f"A candidate with email '{email}' already exists.")
            candidate.email = email.strip()

    if first_name is not None:
        candidate.first_name = first_name.strip()
    if last_name is not None:
        candidate.last_name = last_name.strip()
    if phone is not None:
        candidate.phone = phone.strip() if phone else None
    if resume_text is not None:
        candidate.resume_text = resume_text

    if skill_names is not None:
        skills = await _get_or_create_skills(db, skill_names)
        candidate.skills = skills

    candidate.updated_at = datetime.utcnow()
    await db.flush()

    logger.info(
        "Updated candidate: %s (id=%s)",
        candidate.email,
        candidate.id,
    )

    return candidate


async def get_candidate(
    db: AsyncSession,
    candidate_id: str,
) -> Optional[Candidate]:
    """Get a single candidate by ID with skills eagerly loaded.

    Args:
        db: Async database session.
        candidate_id: The UUID of the candidate.

    Returns:
        The Candidate object or None if not found.
    """
    result = await db.execute(
        select(Candidate)
        .where(Candidate.id == candidate_id)
        .options(
            selectinload(Candidate.skills),
            selectinload(Candidate.applications),
        )
    )
    return result.scalar_one_or_none()


async def list_candidates(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """List all candidates with pagination.

    Args:
        db: Async database session.
        page: Page number (1-based).
        page_size: Number of results per page.

    Returns:
        Dict with 'items', 'total', 'page', 'page_size', 'total_pages'.
    """
    if page < 1:
        page = 1
    if page_size < 1:
        page_size = 20
    if page_size > 100:
        page_size = 100

    count_query = select(func.count()).select_from(Candidate)
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    total_pages = max(1, (total + page_size - 1) // page_size)
    offset = (page - 1) * page_size

    query = (
        select(Candidate)
        .options(selectinload(Candidate.skills))
        .order_by(Candidate.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    result = await db.execute(query)
    candidates = list(result.scalars().all())

    return {
        "items": candidates,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


async def search_candidates(
    db: AsyncSession,
    query: Optional[str] = None,
    skills: Optional[list[str]] = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """Search candidates by name, email, or skills.

    Args:
        db: Async database session.
        query: Free-text search string (matches first_name, last_name, email).
        skills: List of skill names to filter by (candidates must have ALL listed skills).
        page: Page number (1-based).
        page_size: Number of results per page.

    Returns:
        Dict with 'items', 'total', 'page', 'page_size', 'total_pages'.
    """
    if page < 1:
        page = 1
    if page_size < 1:
        page_size = 20
    if page_size > 100:
        page_size = 100

    base_query = select(Candidate)
    count_base = select(func.count(func.distinct(Candidate.id)))

    if query:
        search_term = f"%{query.strip()}%"
        text_filter = or_(
            Candidate.first_name.ilike(search_term),
            Candidate.last_name.ilike(search_term),
            Candidate.email.ilike(search_term),
        )
        base_query = base_query.where(text_filter)
        count_base = count_base.where(text_filter)

    if skills:
        cleaned_skills = [s.strip().lower() for s in skills if s.strip()]
        if cleaned_skills:
            for skill_name in cleaned_skills:
                skill_subquery = (
                    select(candidate_skills.c.candidate_id)
                    .join(Skill, Skill.id == candidate_skills.c.skill_id)
                    .where(func.lower(Skill.name) == skill_name)
                )
                base_query = base_query.where(Candidate.id.in_(skill_subquery))
                count_base = count_base.where(Candidate.id.in_(skill_subquery))

    total_result = await db.execute(count_base)
    total = total_result.scalar() or 0

    total_pages = max(1, (total + page_size - 1) // page_size)
    offset = (page - 1) * page_size

    final_query = (
        base_query
        .options(selectinload(Candidate.skills))
        .order_by(Candidate.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    result = await db.execute(final_query)
    candidates = list(result.scalars().unique().all())

    return {
        "items": candidates,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


async def delete_candidate(
    db: AsyncSession,
    candidate_id: str,
) -> bool:
    """Delete a candidate by ID.

    Args:
        db: Async database session.
        candidate_id: The UUID of the candidate to delete.

    Returns:
        True if the candidate was deleted, False if not found.
    """
    result = await db.execute(
        select(Candidate)
        .where(Candidate.id == candidate_id)
        .options(selectinload(Candidate.skills))
    )
    candidate = result.scalar_one_or_none()
    if candidate is None:
        return False

    candidate.skills = []
    await db.flush()

    await db.delete(candidate)
    await db.flush()

    logger.info("Deleted candidate: id=%s", candidate_id)
    return True


async def get_all_skill_names(db: AsyncSession) -> list[str]:
    """Get all distinct skill names for filter dropdowns.

    Args:
        db: Async database session.

    Returns:
        Sorted list of unique skill name strings.
    """
    result = await db.execute(
        select(Skill.name).distinct().order_by(Skill.name)
    )
    return [row[0] for row in result.all() if row[0]]