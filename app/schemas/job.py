import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator


class JobCreate(BaseModel):
    title: str
    department: str
    location: str
    job_type: str
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    description: Optional[str] = None
    assigned_manager_id: Optional[uuid.UUID] = None

    @field_validator("title")
    @classmethod
    def title_must_not_be_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Title must not be empty")
        return v.strip()

    @field_validator("department")
    @classmethod
    def department_must_not_be_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Department must not be empty")
        return v.strip()

    @field_validator("location")
    @classmethod
    def location_must_not_be_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Location must not be empty")
        return v.strip()

    @field_validator("job_type")
    @classmethod
    def job_type_must_be_valid(cls, v: str) -> str:
        valid_types = {"full-time", "part-time", "contract", "internship", "temporary"}
        if v.strip().lower() not in valid_types:
            raise ValueError(f"Job type must be one of: {', '.join(sorted(valid_types))}")
        return v.strip().lower()

    @field_validator("salary_max")
    @classmethod
    def salary_max_must_be_gte_min(cls, v: Optional[float], info) -> Optional[float]:
        if v is not None:
            salary_min = info.data.get("salary_min")
            if salary_min is not None and v < salary_min:
                raise ValueError("salary_max must be greater than or equal to salary_min")
        return v


class JobUpdate(BaseModel):
    title: Optional[str] = None
    department: Optional[str] = None
    location: Optional[str] = None
    job_type: Optional[str] = None
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    description: Optional[str] = None
    assigned_manager_id: Optional[uuid.UUID] = None

    @field_validator("title")
    @classmethod
    def title_must_not_be_empty(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not v.strip():
            raise ValueError("Title must not be empty")
        return v.strip() if v is not None else v

    @field_validator("department")
    @classmethod
    def department_must_not_be_empty(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not v.strip():
            raise ValueError("Department must not be empty")
        return v.strip() if v is not None else v

    @field_validator("location")
    @classmethod
    def location_must_not_be_empty(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not v.strip():
            raise ValueError("Location must not be empty")
        return v.strip() if v is not None else v

    @field_validator("job_type")
    @classmethod
    def job_type_must_be_valid(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            valid_types = {"full-time", "part-time", "contract", "internship", "temporary"}
            if v.strip().lower() not in valid_types:
                raise ValueError(f"Job type must be one of: {', '.join(sorted(valid_types))}")
            return v.strip().lower()
        return v

    @field_validator("salary_max")
    @classmethod
    def salary_max_must_be_gte_min(cls, v: Optional[float], info) -> Optional[float]:
        if v is not None:
            salary_min = info.data.get("salary_min")
            if salary_min is not None and v < salary_min:
                raise ValueError("salary_max must be greater than or equal to salary_min")
        return v


class JobStatusUpdate(BaseModel):
    new_status: str

    @field_validator("new_status")
    @classmethod
    def status_must_be_valid(cls, v: str) -> str:
        valid_statuses = {"draft", "open", "closed", "on_hold", "archived"}
        if v.strip().lower() not in valid_statuses:
            raise ValueError(f"Status must be one of: {', '.join(sorted(valid_statuses))}")
        return v.strip().lower()


class AssignedManagerInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: Optional[str] = None


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    department: str
    location: str
    job_type: str
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    description: Optional[str] = None
    status: str
    assigned_manager_id: Optional[uuid.UUID] = None
    assigned_manager: Optional[AssignedManagerInfo] = None
    created_at: datetime
    updated_at: datetime


class JobListResponse(BaseModel):
    items: list[JobResponse]
    total: int
    page: int
    size: int
    pages: int