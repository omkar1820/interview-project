import secrets
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import Principal, current_user
from ..config import get_settings
from ..database import get_db
from ..models import Agency, Candidate, Interview, Recruiter
from ..schemas import (DecisionIn, InterviewCreate, InterviewCreated, InterviewPublic, InterviewSummary,
                       ReportOut)

router = APIRouter()


def owned_interview(db: Session, interview_id: int, user: Principal) -> Interview:
    """Super admin sees everything; a recruiter only the interviews they created."""
    iv = db.get(Interview, interview_id)
    if not iv or (not user.is_super and iv.recruiter_id != user.recruiter_id):
        raise HTTPException(404, "Interview not found")
    return iv


@router.post("/interviews", response_model=InterviewCreated)
def create_interview(body: InterviewCreate, request: Request, db: Session = Depends(get_db),
                     user: Principal = Depends(current_user)):
    cand = db.scalar(select(Candidate).where(Candidate.email == body.email.lower()))
    if cand is None:
        cand = Candidate(name=body.name, email=body.email.lower())
        db.add(cand)
        db.flush()
    else:
        cand.name = body.name
    iv = Interview(candidate_id=cand.id, role=body.role,
                   num_questions=body.num_questions or get_settings().default_num_questions,
                   recruiter_id=user.recruiter_id, agency_id=user.agency_id)
    db.add(iv)
    db.commit()
    base = str(request.base_url).rstrip("/")
    return InterviewCreated(interview_id=iv.id, access_token=iv.access_token,
                            candidate_url=f"{base}/interview?id={iv.id}&token={iv.access_token}")


@router.get("/interviews", response_model=List[InterviewSummary])
def list_interviews(db: Session = Depends(get_db), user: Principal = Depends(current_user)):
    q = select(Interview).order_by(Interview.id.desc()).limit(200)
    if not user.is_super:
        q = q.where(Interview.recruiter_id == user.recruiter_id)
    rows = db.scalars(q).all()
    rec = {r.id: r.name for r in db.scalars(select(Recruiter))} if user.is_super else {}
    ag = {a.id: a.name for a in db.scalars(select(Agency))} if user.is_super else {}
    return [InterviewSummary(
        interview_id=i.id, candidate_name=i.candidate.name, email=i.candidate.email, role=i.role,
        status=i.status, overall_score=i.result.overall_score if i.result else None,
        recommendation=i.result.recommendation if i.result else None,
        recruiter_decision=i.result.recruiter_decision if i.result else None,
        recruiter_name=rec.get(i.recruiter_id), agency_name=ag.get(i.agency_id), created_at=i.created_at)
        for i in rows]


@router.get("/interviews/{interview_id}/report", response_model=ReportOut)
def report(interview_id: int, db: Session = Depends(get_db), user: Principal = Depends(current_user)):
    iv = owned_interview(db, interview_id, user)
    return ReportOut(interview_id=iv.id, candidate_name=iv.candidate.name, email=iv.candidate.email,
                     role=iv.role, status=iv.status, responses=iv.responses, result=iv.result)


@router.get("/interviews/{interview_id}/transcript", response_class=PlainTextResponse)
def transcript(interview_id: int, db: Session = Depends(get_db), user: Principal = Depends(current_user)):
    iv = owned_interview(db, interview_id, user)
    out = [f"Interview #{iv.id} - {iv.candidate.name} ({iv.candidate.email}) - {iv.role}", ""]
    for r in iv.responses:
        out += [f"Q{r.order_no}: {r.question_text}", f"A: {r.answer_text}", f"Score {r.overall_score:.1f} - {r.feedback}", ""]
    if iv.result:
        out += [f"Overall {iv.result.overall_score:.1f} - {iv.result.recommendation}"]
    return "\n".join(out)


@router.patch("/interviews/{interview_id}/decision")
def decide(interview_id: int, body: DecisionIn, db: Session = Depends(get_db),
           user: Principal = Depends(current_user)):
    iv = owned_interview(db, interview_id, user)
    if not iv.result:
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
