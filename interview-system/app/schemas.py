from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class InterviewCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=190)
    role: str = Field(min_length=2, max_length=120)
    num_questions: Optional[int] = Field(default=None, ge=1, le=15)


class InterviewCreated(BaseModel):
    interview_id: int
    access_token: str
    candidate_url: str


class InterviewPublic(BaseModel):
    candidate_name: str
    role: str
    status: str
    num_questions: int
    answered: int


class InterviewSummary(BaseModel):
    interview_id: int
    candidate_name: str
    email: str
    role: str
    status: str
    overall_score: Optional[float] = None
    recommendation: Optional[str] = None
    recruiter_decision: Optional[str] = None
    created_at: datetime


class ResponseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    order_no: int
    question_text: str
    answer_text: str
    technical_score: float
    relevance_score: float
    problem_solving_score: float
    communication_score: float
    overall_score: float
    feedback: str


class ResultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    overall_score: float
    technical_score: float
    relevance_score: float
    problem_solving_score: float
    communication_score: float
    strengths: str
    improvements: str
    recommendation: str
    recruiter_decision: Optional[str] = None
    recruiter_notes: Optional[str] = None


class ReportOut(BaseModel):
    interview_id: int
    candidate_name: str
    email: str
    role: str
    status: str
    responses: List[ResponseOut]
    result: Optional[ResultOut] = None
    disclaimer: str = "AI provides decision support; final hiring decisions remain with human recruiters."


class DecisionIn(BaseModel):
    decision: str = Field(pattern="^(advance|hold|reject)$")
    notes: Optional[str] = Field(default=None, max_length=2000)
