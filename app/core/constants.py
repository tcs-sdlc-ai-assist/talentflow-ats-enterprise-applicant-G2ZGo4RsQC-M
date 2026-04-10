from enum import Enum


class UserRole(str, Enum):
    SYSTEM_ADMIN = "System Admin"
    HR_RECRUITER = "HR Recruiter"
    HIRING_MANAGER = "Hiring Manager"
    INTERVIEWER = "Interviewer"


class JobStatus(str, Enum):
    DRAFT = "Draft"
    PUBLISHED = "Published"
    CLOSED = "Closed"


class ApplicationStatus(str, Enum):
    APPLIED = "Applied"
    SCREENING = "Screening"
    INTERVIEW = "Interview"
    OFFER = "Offer"
    HIRED = "Hired"
    REJECTED = "Rejected"


ALLOWED_APPLICATION_TRANSITIONS: dict[str, list[str]] = {
    ApplicationStatus.APPLIED: [ApplicationStatus.SCREENING, ApplicationStatus.REJECTED],
    ApplicationStatus.SCREENING: [ApplicationStatus.INTERVIEW, ApplicationStatus.REJECTED],
    ApplicationStatus.INTERVIEW: [ApplicationStatus.OFFER, ApplicationStatus.REJECTED],
    ApplicationStatus.OFFER: [ApplicationStatus.HIRED, ApplicationStatus.REJECTED],
    ApplicationStatus.HIRED: [],
    ApplicationStatus.REJECTED: [],
}

ALLOWED_JOB_TRANSITIONS: dict[str, list[str]] = {
    JobStatus.DRAFT: [JobStatus.PUBLISHED],
    JobStatus.PUBLISHED: [JobStatus.CLOSED],
    JobStatus.CLOSED: [],
}


def is_valid_application_transition(current_status: str, new_status: str) -> bool:
    allowed = ALLOWED_APPLICATION_TRANSITIONS.get(current_status, [])
    return new_status in allowed


def is_valid_job_transition(current_status: str, new_status: str) -> bool:
    allowed = ALLOWED_JOB_TRANSITIONS.get(current_status, [])
    return new_status in allowed