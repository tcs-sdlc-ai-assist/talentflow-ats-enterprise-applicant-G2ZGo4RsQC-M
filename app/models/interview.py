import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, Text, func
from sqlalchemy.orm import relationship

from app.core.database import Base


class Interview(Base):
    __tablename__ = "interviews"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    application_id = Column(String(36), ForeignKey("applications.id"), nullable=False)
    interviewer_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    scheduled_at = Column(DateTime, nullable=True)
    rating = Column(Integer, nullable=True)
    feedback = Column(Text, nullable=True)
    status = Column(String(50), nullable=False, default="Scheduled")
    created_at = Column(DateTime, nullable=False, server_default=func.now(), default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), default=datetime.utcnow, onupdate=datetime.utcnow)

    application = relationship("Application", back_populates="interviews", lazy="selectin")
    interviewer = relationship("User", back_populates="interviews", lazy="selectin")

    def __repr__(self):
        return f"<Interview(id={self.id}, application_id={self.application_id}, status={self.status})>"


class InterviewFeedback(Base):
    __tablename__ = "interview_feedbacks"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    interview_id = Column(String(36), ForeignKey("interviews.id"), nullable=False)
    interviewer_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    rating = Column(Integer, nullable=False)
    feedback = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now(), default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), default=datetime.utcnow, onupdate=datetime.utcnow)

    interview = relationship("Interview", backref="feedbacks", lazy="selectin")

    def __repr__(self):
        return f"<InterviewFeedback(id={self.id}, interview_id={self.interview_id}, rating={self.rating})>"