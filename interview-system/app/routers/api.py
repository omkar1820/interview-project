import secrets
from typing import List

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import get_db
from ..models import Candidate, Interview
from ..schemas import (DecisionIn, InterviewCreate, InterviewCreated, InterviewPublic, InterviewSummary,
                       ReportOut)

router = APIRouter()


def require_admin(x_api_key: str | None = Header(default=None)):
    key = get_settings().admin_api_key
    if key and not secrets.compare_digest(x_api_key or "", key):
        raise HTTPException(401, "Invalid or missing X-API-Key")


@router.post("/interviews", response_model=InterviewCreated, dependencies=[Depends(require_admin)])
def create_interview(body: InterviewCreate, request: Request, db: Session = Depends(get_db)):
    cand = db.scalar(select(Candidate).where(Candidate.email == body.email.lower()))
    if cand is None:
        cand = Candidate(name=body.name, email=body.email.lower())
        db.add(cand)
        db.flush()
    else:
        cand.name = body.name
    iv = Interview(candidate_id=cand.id, role=body.role,
                   num_questions=body.num_questions or get_settings().default_num_questions)
    db.add(iv)
    db.commit()
    base = str(request.base_url).rstrip("/")
    return InterviewCreated(interview_id=iv.id, access_token=iv.access_token,
                            candidate_url=f"{base}/interview?id={iv.id}&token={iv.access_token}")


@router.get("/interviews", response_model=List[InterviewSummary], dependencies=[Depends(require_admin)])
def list_interviews(db: Session = Depends(get_db)):
    rows = db.scalars(select(Interview).order_by(Interview.id.desc()).limit(200)).all()
    return [InterviewSummary(
        interview_id=i.id, candidate_name=i.candidate.name, email=i.candidate.email, role=i.role,
        status=i.status, overall_score=i.result.overall_score if i.result else None,
        recommendation=i.result.recommendation if i.result else None,
        recruiter_decision=i.result.recruiter_decision if i.result else None, created_at=i.created_at)
        for i in rows]


@router.get("/interviews/{interview_id}/report", response_model=ReportOut, dependencies=[Depends(require_admin)])
def report(interview_id: int, db: Session = Depends(get_db)):
    iv = db.get(Interview, interview_id)
    if not iv:
        raise HTTPException(404, "Interview not found")
    return ReportOut(interview_id=iv.id, candidate_name=iv.candidate.name, email=iv.candidate.email,
                     role=iv.role, status=iv.status, responses=iv.responses, result=iv.result)


@router.patch("/interviews/{interview_id}/decision", dependencies=[Depends(require_admin)])
def decide(interview_id: int, body: DecisionIn, db: Session = Depends(get_db)):
    iv = db.get(Interview, interview_id)
    if not iv or not iv.result:
        raise HTTPException(404, "Completed interview not found")
    iv.result.recruiter_decision, iv.result.recruiter_notes = body.decision, body.notes
    db.commit()
    return {"interview_id": iv.id, "recruiter_decision": body.decision}


@router.get("/interviews/{interview_id}/public", response_model=InterviewPublic)
def public_info(interview_id: int, token: str = Query(...), db: Session = Depends(get_db)):
    iv = db.get(Interview, interview_id)
    if not iv or not secrets.compare_digest(token, iv.access_token):
        raise HTTPException(404, "Interview not found")
    return InterviewPublic(candidate_name=iv.candidate.name, role=iv.role, status=iv.status,
                           num_questions=iv.num_questions, answered=len(iv.responses))
