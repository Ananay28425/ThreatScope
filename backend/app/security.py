"""Credential hashing, persisted browser sessions, quotas, and explicit access checks."""
import hashlib
import json
import secrets
import time
from datetime import timedelta

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from fastapi import HTTPException, Request
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from backend.app.tables import Credential, Incident, Organization, Participation, RateBucket, Session, User
from common.contracts import aware, utcnow

PASSWORDS = PasswordHasher()
DUMMY_HASH = PASSWORDS.hash(secrets.token_urlsafe(24))
COOKIE = "threatscope_session"


def hash_token(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def digest(body: dict) -> str:
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def verify_password(encoded: str, password: str) -> bool:
    try:
        return PASSWORDS.verify(encoded, password)
    except VerificationError:
        return False


async def quota(db, key: str, limit: int) -> None:
    """Atomically count requests across API processes; caller commits rejected attempts."""
    insert = pg_insert if db.bind.dialect.name == "postgresql" else sqlite_insert
    stmt = insert(RateBucket).values(key=key, minute=int(time.time() // 60), count=1)
    stmt = stmt.on_conflict_do_update(
        index_elements=["key", "minute"], set_={"count": RateBucket.count + 1}
    ).returning(RateBucket.count)
    count = (await db.execute(stmt)).scalar_one()
    if count > limit:
        await db.commit()
        raise HTTPException(429, "rate_limit", headers={"Retry-After": "60"})


async def node_identity(request: Request, db) -> Organization:
    key = request.headers.get("x-api-key", "")
    if not 16 <= len(key) <= 256:
        raise HTTPException(401, "invalid_node_credential")
    credential = (await db.execute(select(Credential).where(Credential.key_hash == hash_token(key)))).scalar_one_or_none()
    if not credential or not credential.active or aware(credential.expires_at) <= utcnow():
        raise HTTPException(401, "invalid_node_credential")
    org = await db.get(Organization, credential.org_id)
    if not org or not org.active:
        raise HTTPException(401, "inactive_organization")
    await quota(db, "org:" + org.id, request.app.state.settings.ingest_per_minute)
    return org


async def actor_from_token(db, token: str | None):
    if not token or len(token) > 128:
        return None, None
    session = await db.get(Session, hash_token(token))
    if not session or aware(session.expires_at) <= utcnow():
        return None, None
    user = await db.get(User, session.user_id)
    if not user or not user.active or user.role not in {"admin", "coordinator", "analyst"}:
        return None, None
    if user.role == "analyst":
        org = await db.get(Organization, user.org_id) if user.org_id else None
        if not org or not org.active:
            return None, None
    return user, session


async def actor(request: Request, db) -> User:
    user, session = await actor_from_token(db, request.cookies.get(COOKIE))
    if user is None:
        raise HTTPException(401, "authentication_required")
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        origin = request.headers.get("origin")
        csrf = request.headers.get("x-csrf-token", "")
        if origin not in request.app.state.settings.origins or not secrets.compare_digest(csrf, session.csrf):
            raise HTTPException(403, "csrf_or_origin_rejected")
    return user


async def authorize_incident(db, user: User, incident_id: str) -> Incident:
    incident = await db.get(Incident, incident_id)
    if incident is None:
        raise HTTPException(404, "incident_not_found")
    if user.role not in {"admin", "coordinator"}:
        participant = await db.get(Participation, (incident_id, user.org_id))
        if not participant:
            raise HTTPException(404, "incident_not_found")
    return incident


def new_session(user_id: str, hours: int) -> tuple[str, Session]:
    token = secrets.token_urlsafe(32)
    return token, Session(
        token_hash=hash_token(token), user_id=user_id, csrf=secrets.token_urlsafe(32),
        expires_at=utcnow() + timedelta(hours=hours),
    )

