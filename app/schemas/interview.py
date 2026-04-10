import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class InterviewCreate(BaseModel):
    application_id: uuid.UUID
    interviewer_id: uuid.UUID
    scheduled_at: datetime


class InterviewUpdate(BaseModel):
    scheduled_at: Optional[datetime] = None
    status: Optional[str] = None


class InterviewerInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    full_name: str
    email: str


class ApplicationInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: str
    candidate_id: uuid.UUID


class InterviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    application_id: uuid.UUID
    interviewer_id: uuid.UUID
    scheduled_at: datetime
    status: str
    feedback: Optional[str] = None
    rating: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    interviewer: Optional[InterviewerInfo] = None
    application: Optional[ApplicationInfo] = None


class InterviewListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    items: list[InterviewResponse]
    total: int


class FeedbackSubmit(BaseModel):
    rating: int = Field(..., ge=1, le=5, description="Rating from 1 to 5")
    feedback: str = Field(..., min_length=1, max_length=5000, description="Feedback text")

    @field_validator("feedback")
    @classmethod
    def feedback_not_blank(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Feedback text must not be blank")
        return stripped