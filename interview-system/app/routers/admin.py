import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..auth import (Principal, current_user, hash_password, make_token, require_super, TOKEN_TTL,
                    verify_password)
from ..config import get_settings
from ..database import get_db
from ..models import Agency, Interview, Recruiter, utcnow

import secrets

router = APIRouter()
EMAIL = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"

# --- tiny in-memory brute-force throttle (per client+account, resets on restart) ---
_fails: dict[str, tuple[int, float]] = {}


def _throttled(k: str) -> bool:
    n, until = _fails.get(k, (0, 0.0))
    return n >= 5 and time.time() < until


def _fail(k: str) -> None:
    n, _ = _fails.get(k, (0, 0.0))
    _fails[k] = (n + 1, time.time() + 60)


class LoginIn(BaseModel):
    email: Optional[str] = Field(default=None, max_length=190)
    password: Optional[str] = Field(default=None, max_length=200)
    api_key: Optional[str] = Field(default=None, max_length=200)


class PasswordIn(BaseModel):
    current_password: str = Field(max_length=200)
    new_password: str = Field(min_length=8, max_length=200)


@router.post("/auth/login")
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)):
    ident = (body.email or "key").lower()
    k = f"{request.client.host if request.client else '?'}|{ident}"
    if _throttled(k):
        raise HTTPException(429, "Too many attempts - wait a minute and try again")
    if body.api_key:
        real = get_settings().admin_api_key
        if real and secrets.compare_digest(body.api_key, real):
            _fails.pop(k, None)
            return {"token": make_token("super_admin"), "role": "super_admin", "name": "Super admin",
                    "agency": None, "expires_in": TOKEN_TTL}
    elif body.email and body.password:
        rec = db.scalar(select(Recruiter).where(Recruiter.email == body.email.strip().lower()))
        if rec and verify_password(body.password, rec.password_hash):
            if not rec.active or not rec.agency.active:
                raise HTTPException(403, "This account or its agency is disabled")
            rec.last_login_at = utcnow()
            db.commit()
            _fails.pop(k, None)
            return {"token": make_token("recruiter", rec.id), "role": "recruiter", "name": rec.name,
                    "agency": rec.agency.name, "expires_in": TOKEN_TTL}
    _fail(k)
    raise HTTPException(401, "Invalid credentials")


@router.get("/auth/me")
def me(user: Principal = Depends(current_user), db: Session = Depends(get_db)):
    if user.is_super:
        return {"role": "super_admin", "name": "Super admin", "agency": None}
    rec = db.get(Recruiter, user.recruiter_id)
    return {"role": "recruiter", "name": rec.name, "email": rec.email, "agency": rec.agency.name}


@router.post("/auth/change-password")
def change_password(body: PasswordIn, user: Principal = Depends(current_user), db: Session = Depends(get_db)):
    if user.is_super:
        raise HTTPException(400, "Super admin uses ADMIN_API_KEY (change it in Secrets Manager)")
    rec = db.get(Recruiter, user.recruiter_id)
    if not verify_password(body.current_password, rec.password_hash):
        raise HTTPException(400, "Current password is wrong")
    rec.password_hash = hash_password(body.new_password)
    db.commit()
    return {"ok": True}


# ------------------------- super admin: agencies -------------------------
class AgencyIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    max_recruiters: int = Field(default=5, ge=1, le=500)


class AgencyPatch(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=120)
    max_recruiters: Optional[int] = Field(default=None, ge=1, le=500)
    active: Optional[bool] = None


def _active_count(db: Session, agency_id: int) -> int:
    return db.scalar(select(func.count()).select_from(Recruiter)
                     .where(Recruiter.agency_id == agency_id, Recruiter.active.is_(True))) or 0


def _agency_out(db: Session, a: Agency) -> dict:
    total = db.scalar(select(func.count()).select_from(Interview).where(Interview.agency_id == a.id)) or 0
    return {"id": a.id, "name": a.name, "max_recruiters": a.max_recruiters, "active": a.active,
            "active_recruiters": _active_count(db, a.id), "interviews": total, "created_at": a.created_at}


def _commit(db: Session, msg: str) -> None:
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, msg)


@router.post("/admin/agencies", dependencies=[Depends(require_super)])
def create_agency(body: AgencyIn, db: Session = Depends(get_db)):
    a = Agency(name=body.name.strip(), max_recruiters=body.max_recruiters)
    db.add(a)
    _commit(db, "An agency with this name already exists")
    return _agency_out(db, a)


@router.get("/admin/agencies", dependencies=[Depends(require_super)])
def list_agencies(db: Session = Depends(get_db)):
    return [_agency_out(db, a) for a in db.scalars(select(Agency).order_by(Agency.id.desc()))]


@router.patch("/admin/agencies/{agency_id}", dependencies=[Depends(require_super)])
def update_agency(agency_id: int, body: AgencyPatch, db: Session = Depends(get_db)):
    a = db.get(Agency, agency_id)
    if not a:
        raise HTTPException(404, "Agency not found")
    if body.max_recruiters is not None:
        if body.max_recruiters < _active_count(db, a.id):
            raise HTTPException(409, "Seat limit is below the number of active recruiters - deactivate some first")
        a.max_recruiters = body.max_recruiters
    if body.name is not None:
        a.name = body.name.strip()
    if body.active is not None:
        a.active = body.active
    _commit(db, "An agency with this name already exists")
    return _agency_out(db, a)


# ------------------------- super admin: recruiters -------------------------
class RecruiterIn(BaseModel):
    agency_id: int
    name: str = Field(min_length=1, max_length=120)
    email: str = Field(pattern=EMAIL, max_length=190)
    password: str = Field(min_length=8, max_length=200)


class RecruiterPatch(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    active: Optional[bool] = None
    password: Optional[str] = Field(default=None, min_length=8, max_length=200)


def _rec_out(r: Recruiter, interviews: int = 0) -> dict:
    return {"id": r.id, "agency_id": r.agency_id, "agency": r.agency.name, "name": r.name, "email": r.email,
            "active": r.active, "interviews": interviews, "last_login_at": r.last_login_at,
            "created_at": r.created_at}


def _seat_check(db: Session, a: Agency) -> None:
    if not a.active:
        raise HTTPException(409, "Agency is disabled")
    if _active_count(db, a.id) >= a.max_recruiters:
        raise HTTPException(409, f"Seat limit reached ({a.max_recruiters}) for {a.name}")


@router.post("/admin/recruiters", dependencies=[Depends(require_super)])
def create_recruiter(body: RecruiterIn, db: Session = Depends(get_db)):
    a = db.get(Agency, body.agency_id)
    if not a:
        raise HTTPException(404, "Agency not found")
    _seat_check(db, a)
    r = Recruiter(agency_id=a.id, name=body.name.strip(), email=body.email.strip().lower(),
                  password_hash=hash_password(body.password))
    db.add(r)
    _commit(db, "A recruiter with this email already exists")
    return _rec_out(r)


@router.get("/admin/recruiters", dependencies=[Depends(require_super)])
def list_recruiters(agency_id: Optional[int] = None, db: Session = Depends(get_db)):
    q = select(Recruiter).order_by(Recruiter.id.desc())
    if agency_id:
        q = q.where(Recruiter.agency_id == agency_id)
    counts = dict(db.execute(select(Interview.recruiter_id, func.count()).group_by(Interview.recruiter_id)).all())
    return [_rec_out(r, counts.get(r.id, 0)) for r in db.scalars(q)]


@router.patch("/admin/recruiters/{recruiter_id}", dependencies=[Depends(require_super)])
def update_recruiter(recruiter_id: int, body: RecruiterPatch, db: Session = Depends(get_db)):
    r = db.get(Recruiter, recruiter_id)
    if not r:
        raise HTTPException(404, "Recruiter not found")
    if body.active and not r.active:
        _seat_check(db, r.agency)
    if body.name is not None:
        r.name = body.name.strip()
    if body.active is not None:
        r.active = body.active
    if body.password:
        r.password_hash = hash_password(body.password)
    db.commit()
    return _rec_out(r)
