# models.py
# Database tables: User (sign up karne waalon ki detail) aur AnalysisHistory (unki work/analysis history)

from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(150), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    history = relationship(
        "AnalysisHistory", back_populates="user", cascade="all, delete-orphan"
    )


class AnalysisHistory(Base):
    """Har user ke resume-analysis results yahan save honge -> 'work history'"""
    __tablename__ = "analysis_history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    job_description = Column(Text)
    candidate_name = Column(String(150))
    match_score = Column(Float)
    matching_skills = Column(Text)   # JSON string ke roop me store hoga
    missing_skills = Column(Text)    # JSON string ke roop me store hoga
    verdict = Column(Text)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="history")