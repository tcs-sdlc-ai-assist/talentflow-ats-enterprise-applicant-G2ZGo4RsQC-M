import logging
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.application import Application
from app.models.audit_log import AuditLog
from app.models.candidate import Candidate
from app.models.interview import Interview, InterviewFeedback
from app.models.job import Job
from app.models.user import User

logger = logging.getLogger(__name__)


async def get_hr_dashboard_data(db: AsyncSession) -> dict[str, Any]:
    """Get dashboard data for Admin/HR roles.

    Returns total jobs, candidates, applications, applications by status,
    scheduled interviews count, and recent audit logs.
    """
    total_jobs_result = await db.execute(select(func.count(Job.id)))
    total_jobs = total_jobs_result.scalar() or 0

    total_candidates_result = await db.execute(select(func.count(Candidate.id)))
    total_candidates = total_candidates_result.scalar() or 0

    total_applications_result = await db.execute(select(func.count(Application.id)))
    total_applications = total_applications_result.scalar() or 0

    scheduled_interviews_result = await db.execute(
        select(func.count(Interview.id)).where(Interview.status == "Scheduled")
    )
    scheduled_interviews = scheduled_interviews_result.scalar() or 0

    applications_by_status_result = await db.execute(
        select(Application.status, func.count(Application.id))
        .group_by(Application.status)
        .order_by(Application.status)
    )
    applications_by_status = [
        {"status": row[0], "count": row[1]}
        for row in applications_by_status_result.all()
    ]

    audit_logs_result = await db.execute(
        select(AuditLog)
        .options(selectinload(AuditLog.actor))
        .order_by(AuditLog.created_at.desc())
        .limit(10)
    )
    recent_audit_logs = list(audit_logs_result.scalars().all())

    metrics = {
        "total_jobs": total_jobs,
        "total_candidates": total_candidates,
        "total_applications": total_applications,
        "scheduled_interviews": scheduled_interviews,
        "applications_by_status": applications_by_status,
    }

    return {
        "metrics": metrics,
        "audit_logs": recent_audit_logs,
    }


async def get_manager_dashboard_data(
    db: AsyncSession, manager_id: str
) -> dict[str, Any]:
    """Get dashboard data for Hiring Manager role.

    Returns the manager's assigned jobs and pending interviews
    for applications on those jobs.
    """
    my_jobs_result = await db.execute(
        select(Job)
        .where(Job.assigned_manager_id == manager_id)
        .options(selectinload(Job.applications))
        .order_by(Job.created_at.desc())
    )
    my_jobs = list(my_jobs_result.scalars().all())

    job_ids = [job.id for job in my_jobs]

    pending_interviews: list[dict[str, Any]] = []
    if job_ids:
        interviews_result = await db.execute(
            select(Interview)
            .join(Application, Interview.application_id == Application.id)
            .where(
                Application.job_id.in_(job_ids),
                Interview.status.in_(["Scheduled"]),
            )
            .options(
                selectinload(Interview.application).selectinload(Application.candidate),
                selectinload(Interview.application).selectinload(Application.job),
                selectinload(Interview.interviewer),
            )
            .order_by(Interview.scheduled_at.asc())
            .limit(20)
        )
        interviews = list(interviews_result.scalars().all())

        for interview in interviews:
            candidate_name = "Unknown Candidate"
            job_title = "Unknown Position"

            if interview.application:
                if interview.application.candidate:
                    candidate = interview.application.candidate
                    candidate_name = f"{candidate.first_name} {candidate.last_name}"
                if interview.application.job:
                    job_title = interview.application.job.title

            pending_interviews.append(
                {
                    "id": interview.id,
                    "candidate_name": candidate_name,
                    "job_title": job_title,
                    "scheduled_at": interview.scheduled_at,
                    "status": interview.status,
                    "interview_type": getattr(interview, "interview_type", None),
                    "interviewer": interview.interviewer,
                }
            )

    return {
        "my_jobs": my_jobs,
        "pending_interviews": pending_interviews,
    }


async def get_interviewer_dashboard_data(
    db: AsyncSession, interviewer_id: str
) -> dict[str, Any]:
    """Get dashboard data for Interviewer role.

    Returns upcoming interviews assigned to the interviewer
    and interviews that are missing feedback.
    """
    upcoming_result = await db.execute(
        select(Interview)
        .where(
            Interview.interviewer_id == interviewer_id,
            Interview.status.in_(["Scheduled"]),
        )
        .options(
            selectinload(Interview.application).selectinload(Application.candidate),
            selectinload(Interview.application).selectinload(Application.job),
        )
        .order_by(Interview.scheduled_at.asc())
        .limit(20)
    )
    upcoming_interviews_raw = list(upcoming_result.scalars().all())

    upcoming_interviews: list[dict[str, Any]] = []
    for interview in upcoming_interviews_raw:
        candidate_name = "Unknown Candidate"
        job_title = "Unknown Position"

        if interview.application:
            if interview.application.candidate:
                candidate = interview.application.candidate
                candidate_name = f"{candidate.first_name} {candidate.last_name}"
            if interview.application.job:
                job_title = interview.application.job.title

        upcoming_interviews.append(
            {
                "id": interview.id,
                "candidate_name": candidate_name,
                "job_title": job_title,
                "scheduled_at": interview.scheduled_at,
                "status": interview.status,
                "interview_type": getattr(interview, "interview_type", None),
                "location": getattr(interview, "location", None),
            }
        )

    completed_interviews_result = await db.execute(
        select(Interview)
        .where(
            Interview.interviewer_id == interviewer_id,
            Interview.status == "Completed",
        )
        .options(
            selectinload(Interview.application).selectinload(Application.candidate),
            selectinload(Interview.application).selectinload(Application.job),
        )
        .order_by(Interview.scheduled_at.desc())
        .limit(50)
    )
    completed_interviews = list(completed_interviews_result.scalars().all())

    missing_feedback: list[dict[str, Any]] = []
    for interview in completed_interviews:
        feedback_result = await db.execute(
            select(func.count(InterviewFeedback.id)).where(
                InterviewFeedback.interview_id == interview.id,
                InterviewFeedback.interviewer_id == interviewer_id,
            )
        )
        feedback_count = feedback_result.scalar() or 0

        if feedback_count == 0:
            candidate_name = "Unknown Candidate"
            job_title = "Unknown Position"

            if interview.application:
                if interview.application.candidate:
                    candidate = interview.application.candidate
                    candidate_name = f"{candidate.first_name} {candidate.last_name}"
                if interview.application.job:
                    job_title = interview.application.job.title

            missing_feedback.append(
                {
                    "id": interview.id,
                    "candidate_name": candidate_name,
                    "job_title": job_title,
                    "scheduled_at": interview.scheduled_at,
                    "status": interview.status,
                }
            )

    return {
        "upcoming_interviews": upcoming_interviews,
        "missing_feedback": missing_feedback,
    }


async def get_audit_logs_paginated(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 25,
    user_filter: Optional[str] = None,
    action_filter: Optional[str] = None,
    entity_type_filter: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> dict[str, Any]:
    """Get paginated and filtered audit logs."""
    query = select(AuditLog).options(selectinload(AuditLog.actor))
    count_query = select(func.count(AuditLog.id))

    if user_filter:
        query = query.join(User, AuditLog.user_id == User.id, isouter=True).where(
            User.full_name.ilike(f"%{user_filter}%")
            | User.username.ilike(f"%{user_filter}%")
        )
        count_query = count_query.join(
            User, AuditLog.user_id == User.id, isouter=True
        ).where(
            User.full_name.ilike(f"%{user_filter}%")
            | User.username.ilike(f"%{user_filter}%")
        )

    if action_filter:
        query = query.where(AuditLog.action == action_filter)
        count_query = count_query.where(AuditLog.action == action_filter)

    if entity_type_filter:
        query = query.where(AuditLog.entity_type == entity_type_filter)
        count_query = count_query.where(AuditLog.entity_type == entity_type_filter)

    if date_from:
        try:
            dt_from = datetime.strptime(date_from, "%Y-%m-%d").replace(
                tzinfo=timezone.utc
            )
            query = query.where(AuditLog.created_at >= dt_from)
            count_query = count_query.where(AuditLog.created_at >= dt_from)
        except ValueError:
            logger.warning("Invalid date_from format: %s", date_from)

    if date_to:
        try:
            dt_to = datetime.strptime(date_to, "%Y-%m-%d").replace(
                hour=23, minute=59, second=59, tzinfo=timezone.utc
            )
            query = query.where(AuditLog.created_at <= dt_to)
            count_query = count_query.where(AuditLog.created_at <= dt_to)
        except ValueError:
            logger.warning("Invalid date_to format: %s", date_to)

    total_result = await db.execute(count_query)
    total_count = total_result.scalar() or 0

    total_pages = max(1, (total_count + page_size - 1) // page_size)
    offset = (page - 1) * page_size

    query = query.order_by(AuditLog.created_at.desc()).offset(offset).limit(page_size)
    result = await db.execute(query)
    audit_logs = list(result.scalars().all())

    action_options_result = await db.execute(
        select(AuditLog.action).distinct().order_by(AuditLog.action)
    )
    action_options = [row[0] for row in action_options_result.all() if row[0]]

    entity_type_options_result = await db.execute(
        select(AuditLog.entity_type).distinct().order_by(AuditLog.entity_type)
    )
    entity_type_options = [
        row[0] for row in entity_type_options_result.all() if row[0]
    ]

    return {
        "audit_logs": audit_logs,
        "total_count": total_count,
        "total_pages": total_pages,
        "current_page": page,
        "page_size": page_size,
        "action_options": action_options,
        "entity_type_options": entity_type_options,
    }