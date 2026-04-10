import uuid
from datetime import datetime

from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Table
from sqlalchemy.orm import relationship

from app.core.database import Base


candidate_skills = Table(
    "candidate_skills",
    Base.metadata,
    Column("candidate_id", String(36), ForeignKey("candidates.id"), primary_key=True),
    Column("skill_id", String(36), ForeignKey("skills.id"), primary_key=True),
)


class Candidate(Base):
    __tablename__ = "candidates"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    phone = Column(String(50), nullable=True)
    resume_text = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    skills = relationship(
        "Skill",
        secondary=candidate_skills,
        back_populates="candidates",
        lazy="selectin",
    )
    applications = relationship(
        "Application",
        back_populates="candidate",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Candidate {self.first_name} {self.last_name} ({self.email})>"