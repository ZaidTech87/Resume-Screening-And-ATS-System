# schemas.py
# Request/Response validation ke liye Pydantic models

from pydantic import BaseModel, EmailStr
from datetime import datetime


class SignupRequest(BaseModel):
    name: str
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: int
    name: str
    email: str
    created_at: datetime

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class HistoryItem(BaseModel):
    id: int
    candidate_name: str | None = None
    match_score: float | None = None
    matching_skills: list[str] = []
    missing_skills: list[str] = []
    verdict: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True