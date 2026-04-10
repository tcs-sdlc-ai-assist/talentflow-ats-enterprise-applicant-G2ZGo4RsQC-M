import logging
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.application import Application
from app.models.candidate import Candidate
from app.models.interview import Interview, InterviewFeedback
from app.models.job import Job
from app.models.user import User
from app.services.audit_service import log_action

logger = logging.getLogger(__name__)


async def schedule_interview(
    db: AsyncSession,
    application_id: str,
    interviewer_id: str,
    scheduled_at: datetime,
    current_user_id: Optional[str] = None,
    current_username: Optional[str] = None,
) -> Interview:
    """Schedule a new interview for an application."""
    result = await db.execute(
        select(Application).where(Application.id == application_id)
    )
    application = result.scalar_one_or_none()
    if application is None:
        raise ValueError(f"Application with id '{application_id}' not found")

    result = await db.execute(
        select(User).where(User.id == interviewer_id, User.is_active == True)
    )
    interviewer = result.scalar_one_or_none()
    if interviewer is None:
        raise ValueError(f"Interviewer with id '{interviewer_id}' not found or inactive")

    interview = Interview(
        application_id=application_id,
        interviewer_id=interviewer_id,
        scheduled_at=scheduled_at,
        status="Scheduled",
    )
    db.add(interview)
    await db.flush()

    try:
        await log_action(
            db=db,
            user_id=current_user_id,
            username=current_username,
            action="CREATE",
            entity_type="Interview",
            entity_id=interview.id,
            details=f"Scheduled interview for application {application_id} with interviewer {interviewer_id} at {scheduled_at.isoformat()}",
        )
    except Exception:
        logger.exception("Failed to log audit for interview scheduling")

    logger.info(
        "Interview scheduled: id=%s application_id=%s interviewer_id=%s scheduled_at=%s",
        interview.id,
        application_id,
        interviewer_id,
        scheduled_at.isoformat(),
    )

    return interview


async def submit_feedback(
    db: AsyncSession,
    interview_id: str,
    interviewer_id: str,
    rating: int,
    feedback: str,
    current_user_id: Optional[str] = None,
    current_username: Optional[str] = None,
) -> InterviewFeedback:
    """Submit feedback for an interview. Rating must be 1-5."""
    if not (1 <= rating <= 5):
        raise ValueError("Rating must be between 1 and 5")

    feedback_text = feedback.strip()
    if not feedback_text:
        raise ValueError("Feedback text must not be blank")

    result = await db.execute(
        select(Interview).where(Interview.id == interview_id)
    )
    interview = result.scalar_one_or_none()
    if interview is None:
        raise ValueError(f"Interview with id '{interview_id}' not found")

    existing_result = await db.execute(
        select(InterviewFeedback).where(
            InterviewFeedback.interview_id == interview_id,
            InterviewFeedback.interviewer_id == interviewer_id,
        )
    )
    existing_feedback = existing_result.scalar_one_or_none()
    if existing_feedback is not None:
        raise ValueError("Feedback has already been submitted for this interview by this interviewer")

    interview_feedback = InterviewFeedback(
        interview_id=interview_id,
        interviewer_id=interviewer_id,
        rating=rating,
        feedback=feedback_text,
    )
    db.add(interview_feedback)

    interview.rating = rating
    interview.feedback = feedback_text
    interview.status = "Completed"
    interview.updated_at = datetime.now(timezone.utc)

    await db.flush()

    try:
        await log_action(
            db=db,
            user_id=current_user_id,
            username=current_username,
            action="CREATE",
            entity_type="InterviewFeedback",
            entity_id=interview_feedback.id,
            details=f"Submitted feedback for interview {interview_id} with rating {rating}/5",
        )
    except Exception:
        logger.exception("Failed to log audit for feedback submission")

    logger.info(
        "Feedback submitted: interview_id=%s interviewer_id=%s rating=%d",
        interview_id,
        interviewer_id,
        rating,
    )

    return interview_feedback


async def list_interviews(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 20,
    status: Optional[str] = None,
    job_id: Optional[str] = None,
    interviewer_id: Optional[str] = None,
    application_id: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
) -> dict[str, Any]:
    """List interviews with pagination and filtering."""
    conditions = []

    if status:
        conditions.append(Interview.status == status)

    if interviewer_id:
        conditions.append(Interview.interviewer_id == interviewer_id)

    if application_id:
        conditions.append(Interview.application_id == application_id)

    if date_from:
        conditions.append(Interview.scheduled_at >= date_from)

    if date_to:
        conditions.append(Interview.scheduled_at <= date_to)

    if job_id:
        conditions.append(Application.job_id == job_id)

    if page < 1:
        page = 1
    if page_size < 1:
        page_size = 20
    if page_size > 100:
        page_size = 100

    count_query = select(func.count(Interview.id))
    if job_id:
        count_query = count_query.join(Application, Interview.application_id == Application.id)
    if conditions:
        count_query = count_query.where(and_(*conditions))

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    total_pages = max(1, (total + page_size - 1) // page_size)
    offset = (page - 1) * page_size

    query = (
        select(Interview)
        .options(
            selectinload(Interview.application).selectinload(Application.candidate),
            selectinload(Interview.application).selectinload(Application.job),
            selectinload(Interview.interviewer),
        )
    )

    if job_id:
        query = query.join(Application, Interview.application_id == Application.id)

    if conditions:
        query = query.where(and_(*conditions))

    query = query.order_by(Interview.scheduled_at.desc()).offset(offset).limit(page_size)

    result = await db.execute(query)
    interviews = list(result.scalars().all())

    return {
        "items": interviews,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


async def get_interviews_for_user(
    db: AsyncSession,
    interviewer_id: str,
    page: int = 1,
    page_size: int = 20,
    status: Optional[str] = None,
    feedback_status: Optional[str] = None,
) -> dict[str, Any]:
    """Get interviews assigned to a specific interviewer."""
    conditions = [Interview.interviewer_id == interviewer_id]

    if status:
        conditions.append(Interview.status == status)

    if page < 1:
        page = 1
    if page_size < 1:
        page_size = 20
    if page_size > 100:
        page_size = 100

    count_query = (
        select(func.count(Interview.id))
        .where(and_(*conditions))
    )
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    total_pages = max(1, (total + page_size - 1) // page_size)
    offset = (page - 1) * page_size

    query = (
        select(Interview)
        .where(and_(*conditions))
        .options(
            selectinload(Interview.application).selectinload(Application.candidate),
            selectinload(Interview.application).selectinload(Application.job),
            selectinload(Interview.interviewer),
        )
        .order_by(Interview.scheduled_at.desc())
        .offset(offset)
        .limit(page_size)
    )

    result = await db.execute(query)
    interviews = list(result.scalars().all())

    enriched_interviews = []
    for interview in interviews:
        feedback_result = await db.execute(
            select(func.count(InterviewFeedback.id)).where(
                InterviewFeedback.interview_id == interview.id,
                InterviewFeedback.interviewer_id == interviewer_id,
            )
        )
        feedback_count = feedback_result.scalar() or 0
        interview.has_feedback = feedback_count > 0
        enriched_interviews.append(interview)

    if feedback_status == "pending":
        enriched_interviews = [i for i in enriched_interviews if not i.has_feedback]
    elif feedback_status == "submitted":
        enriched_interviews = [i for i in enriched_interviews if i.has_feedback]

    return {
        "items": enriched_interviews,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


async def get_interview(
    db: AsyncSession,
    interview_id: str,
) -> Optional[Interview]:
    """Get a single interview by ID with all related data."""
    result = await db.execute(
        select(Interview)
        .where(Interview.id == interview_id)
        .options(
            selectinload(Interview.application).selectinload(Application.candidate),
            selectinload(Interview.application).selectinload(Application.job),
            selectinload(Interview.interviewer),
        )
    )
    interview = result.scalar_one_or_none()
    return interview


async def get_interview_feedbacks(
    db: AsyncSession,
    interview_id: str,
) -> list[InterviewFeedback]:
    """Get all feedback entries for a specific interview."""
    result = await db.execute(
        select(InterviewFeedback)
        .where(InterviewFeedback.interview_id == interview_id)
        .order_by(InterviewFeedback.created_at.desc())
    )
    return list(result.scalars().all())


async def update_interview_status(
    db: AsyncSession,
    interview_id: str,
    new_status: str,
    current_user_id: Optional[str] = None,
    current_username: Optional[str] = None,
) -> Interview:
    """Update the status of an interview."""
    valid_statuses = {"Scheduled", "Completed", "Cancelled", "No Show", "In Progress"}
    if new_status not in valid_statuses:
        raise ValueError(f"Invalid status '{new_status}'. Must be one of: {', '.join(sorted(valid_statuses))}")

    result = await db.execute(
        select(Interview).where(Interview.id == interview_id)
    )
    interview = result.scalar_one_or_none()
    if interview is None:
        raise ValueError(f"Interview with id '{interview_id}' not found")

    old_status = interview.status
    interview.status = new_status
    interview.updated_at = datetime.now(timezone.utc)

    await db.flush()

    try:
        await log_action(
            db=db,
            user_id=current_user_id,
            username=current_username,
            action="STATUS_CHANGE",
            entity_type="Interview",
            entity_id=interview_id,
            details=f"Interview status changed from '{old_status}' to '{new_status}'",
        )
    except Exception:
        logger.exception("Failed to log audit for interview status change")

    logger.info(
        "Interview status updated: id=%s old_status=%s new_status=%s",
        interview_id,
        old_status,
        new_status,
    )

    return interview


async def cancel_interview(
    db: AsyncSession,
    interview_id: str,
    current_user_id: Optional[str] = None,
    current_username: Optional[str] = None,
) -> Interview:
    """Cancel a scheduled interview."""
    return await update_interview_status(
        db=db,
        interview_id=interview_id,
        new_status="Cancelled",
        current_user_id=current_user_id,
        current_username=current_username,
    )