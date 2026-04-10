from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator


class SkillResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str


class CandidateCreate(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    phone: Optional[str] = None
    resume_text: Optional[str] = None
    skill_names: list[str] = []

    @field_validator("first_name", "last_name")
    @classmethod
    def name_must_not_be_empty(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("must not be empty")
        return stripped

    @field_validator("skill_names")
    @classmethod
    def deduplicate_skills(cls, v: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for name in v:
            stripped = name.strip()
            if not stripped:
                continue
            lower = stripped.lower()
            if lower not in seen:
                seen.add(lower)
                result.append(stripped)
        return result


class CandidateUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    resume_text: Optional[str] = None
    skill_names: Optional[list[str]] = None

    @field_validator("first_name", "last_name")
    @classmethod
    def name_must_not_be_empty(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        stripped = v.strip()
        if not stripped:
            raise ValueError("must not be empty")
        return stripped

    @field_validator("skill_names")
    @classmethod
    def deduplicate_skills(cls, v: Optional[list[str]]) -> Optional[list[str]]:
        if v is None:
            return v
        seen: set[str] = set()
        result: list[str] = []
        for name in v:
            stripped = name.strip()
            if not stripped:
                continue
            lower = stripped.lower()
            if lower not in seen:
                seen.add(lower)
                result.append(stripped)
        return result


class CandidateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    first_name: str
    last_name: str
    email: str
    phone: Optional[str] = None
    resume_text: Optional[str] = None
    skills: list[SkillResponse] = []
    created_at: datetime
    updated_at: datetime


class CandidateSearch(BaseModel):
    query: Optional[str] = None
    skills: list[str] = []
    skip: int = 0
    limit: int = 20

    @field_validator("limit")
    @classmethod
    def limit_must_be_reasonable(cls, v: int) -> int:
        if v < 1:
            raise ValueError("limit must be at least 1")
        if v > 100:
            return 100
        return v

    @field_validator("skip")
    @classmethod
    def skip_must_be_non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("skip must be non-negative")
        return v