"""Stdlib-only auth: scrypt password hashes + HMAC-signed bearer tokens.

No new dependencies or secrets: the token signing key is derived from the existing ADMIN_API_KEY.
The ADMIN_API_KEY itself stays valid as the super-admin credential (X-API-Key header or login).
"""
import base64
import hashlib
import hmac
import json
import logging
import secrets
import time
from dataclasses import dataclass
from typing import Optional

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from .config import get_settings
from .database import get_db
from .models import Recruiter

log = logging.getLogger("auth")
TOKEN_TTL = 12 * 3600
_FALLBACK_KEY = secrets.token_bytes(32)  # only used when ADMIN_API_KEY is unset (dev)


def _signing_key() -> bytes:
    k = get_settings().admin_api_key
    return hashlib.sha256(b"interview-auth-v1:" + k.encode()).digest() if k else _FALLBACK_KEY


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return f"scrypt${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, salt, dk = stored.split("$")
        calc = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=2**14, r=8, p=1, dklen=32)
        return hmac.compare_digest(calc.hex(), dk)
    except Exception:
        return False


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def make_token(role: str, recruiter_id: Optional[int] = None) -> str:
    body = _b64(json.dumps({"r": role, "u": recruiter_id, "exp": int(time.time()) + TOKEN_TTL}).encode())
    sig = _b64(hmac.new(_signing_key(), body.encode(), hashlib.sha256).digest())
    return f"{body}.{sig}"


def verify_token(token: str) -> Optional[dict]:
    try:
        body, sig = token.split(".")
        good = _b64(hmac.new(_signing_key(), body.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(sig, good):
            return None
        data = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
        return data if data.get("exp", 0) > time.time() else None
    except Exception:
        return None


@dataclass
class Principal:
    role: str  # super_admin | recruiter
    recruiter_id: Optional[int] = None
    agency_id: Optional[int] = None

    @property
    def is_super(self) -> bool:
        return self.role == "super_admin"


def current_user(authorization: str | None = Header(default=None),
                 x_api_key: str | None = Header(default=None),
                 db: Session = Depends(get_db)) -> Principal:
    if authorization and authorization.lower().startswith("bearer "):
        data = verify_token(authorization[7:].strip())
        if not data:
            raise HTTPException(401, "Session expired - please sign in again")
        if data["r"] == "super_admin":
            return Principal("super_admin")
        rec = db.get(Recruiter, data["u"])
        if not rec or not rec.active or not rec.agency.active:
            raise HTTPException(401, "Account disabled")
        return Principal("recruiter", rec.id, rec.agency_id)
    key = get_settings().admin_api_key
    if not key:  # same behaviour as before: no key configured = open (local dev)
        return Principal("super_admin")
    if x_api_key and secrets.compare_digest(x_api_key, key):
        return Principal("super_admin")
    raise HTTPException(401, "Invalid or missing credentials")


def require_super(user: Principal = Depends(current_user)) -> Principal:
    if not user.is_super:
        raise HTTPException(403, "Super admin only")
    return user
