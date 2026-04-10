import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.constants import ApplicationStatus, ALLOWED_APPLICATION_TRANSITIONS


class ApplicationCreate(BaseModel):
    job_id: uuid.UUID
    candidate_id: uuid.UUID
    cover_letter: Optional[str] = None
    resume_url: Optional[str] = None
    notes: Optional[str] = None


class ApplicationUpdate(BaseModel):
    cover_letter: Optional[str] = None
    resume_url: Optional[str] = None
    notes: Optional[str] = None


class ApplicationStatusUpdate(BaseModel):
    new_status: str

    @field_validator("new_status")
    @classmethod
    def status_must_be_valid(cls, v: str) -> str:
        stripped = v.strip()
        valid_statuses = {s.value for s in ApplicationStatus}
        if stripped not in valid_statuses:
            raise ValueError(
                f"Status must be one of: {', '.join(sorted(valid_statuses))}"
            )
        return stripped


class CandidateInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    first_name: str
    last_name: str
    email: str
    phone: Optional[str] = None


class JobInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    department: Optional[str] = None
    location: Optional[str] = None
    status: str


class ApplicationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    job_id: uuid.UUID
    candidate_id: str
    status: str
    cover_letter: Optional[str] = None
    resume_url: Optional[str] = None
    notes: Optional[str] = None
    applied_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    candidate: Optional[CandidateInfo] = None
    job: Optional[JobInfo] = None


class ApplicationListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    items: list[ApplicationResponse]
    total: int
    page: int = Field(ge=1, default=1)
    page_size: int = Field(ge=1, le=100, default=20)


class AuditLogCreate(BaseModel):
    user_id: uuid.UUID
    username: str
    action: str
    entity_type: str
    entity_id: Optional[str] = None
    details: Optional[str] = None