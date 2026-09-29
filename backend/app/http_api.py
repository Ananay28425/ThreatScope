"""Versioned API: durable ingestion, scoped incident views, and audited evidence changes."""
import asyncio
import secrets
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.exc import IntegrityError

from backend.app.correlation import bump, evaluate
from backend.app.security import (
    COOKIE,
    DUMMY_HASH,
    actor,
    authorize_incident,
    digest,
    hash_token,
    new_session,
    node_identity,
    quota,
    verify_password,
)
from backend.app.snapshots import snapshot
from backend.app.tables import (
    Audit,
    Credential,
    Evidence,
    EvidenceHistory,
    EvidenceRequest,
    Explanation,
    Incident,
    Organization,
    Participation,
    Session,
    Signal,
    User,
)
from common.contracts import (
    CATALOGUE,
    EvidenceResponse,
    EvidenceRevision,
    LoginIn,
    SignalIn,
    WorkflowIn,
    aware,
    utcnow,
)

router = APIRouter(prefix="/api/v1")


async def session_dependency(request: Request):
    async with request.app.state.database.sessions() as session:
        yield session


@router.post("/auth/login")
async def login(body: LoginIn, request: Request, response: Response, db=Depends(session_dependency)):
    if request.headers.get("origin") not in request.app.state.settings.origins:
        raise HTTPException(403, "origin_rejected")
    address = request.client.host if request.client else "unknown"
    await quota(db, "login:" + hash_token(address), request.app.state.settings.login_per_minute)
    user = (await db.execute(select(User).where(User.email == body.email.strip().lower()))).scalar_one_or_none()
    valid = await asyncio.to_thread(verify_password, user.password_hash if user else DUMMY_HASH, body.password)
    if not valid or not user or not user.active:
        await db.commit()  # Failed attempts also consume the distributed quota.
        raise HTTPException(401, "invalid_credentials")
    # Rotate a previous browser session instead of keeping unlimited sessions on repeated login.
    previous = await db.get(Session, hash_token(request.cookies.get(COOKIE, "")))
    if previous:
        await db.delete(previous)
    token, session = new_session(user.id, request.app.state.settings.session_hours)
    db.add(session)
    db.add(Audit(actor_id=user.id, action="login", resource_id=None))
    await db.commit()
    response.set_cookie(
        COOKIE, token, httponly=True, secure=request.app.state.settings.cookie_secure,
        samesite="strict", path="/", max_age=request.app.state.settings.session_hours * 3600,
    )
    return {"user": {"id": user.id, "email": user.email, "role": user.role}, "csrf": session.csrf}


@router.get("/auth/me")
async def me(request: Request, db=Depends(session_dependency)):
    user = await actor(request, db)
    session = await db.get(Session, hash_token(request.cookies[COOKIE]))
    return {"user": {"id": user.id, "email": user.email, "role": user.role}, "csrf": session.csrf}


@router.post("/auth/logout")
async def logout(request: Request, response: Response, db=Depends(session_dependency)):
    await actor(request, db)
    session = await db.get(Session, hash_token(request.cookies[COOKIE]))
    await db.delete(session)
    await db.commit()
    response.delete_cookie(COOKIE, path="/")
    return {"status": "signed_out"}


@router.post("/signals", status_code=202)
async def ingest(body: SignalIn, request: Request, db=Depends(session_dependency)):
    org = await node_identity(request, db)
    now = utcnow()
    if body.observation_end > now + timedelta(seconds=60) or body.observation_end < now - timedelta(hours=24):
        raise HTTPException(422, "observation_time_out_of_bounds")
    payload = body.model_dump(mode="json")
    body_digest = digest(payload)
    existing = (await db.execute(select(Signal).where(
        Signal.org_id == org.id,
        or_(Signal.external_id == str(body.signal_id), Signal.snapshot_id == str(body.snapshot_id)),
    ))).scalars().all()
    if existing:
        if len(existing) != 1 or existing[0].digest != body_digest:
            raise HTTPException(409, "signal_identity_conflict")
        await db.commit()
        return {"status": "accepted", "signal_id": body.signal_id, "duplicate": True}
    record = Signal(
        org_id=org.id, external_id=str(body.signal_id), snapshot_id=str(body.snapshot_id),
        digest=body_digest, family=body.family, score=body.anomaly_score,
        provenance_group=org.provenance_group, observed_end=body.observation_end, body=payload,
    )
    db.add(record)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        existing = (await db.execute(select(Signal).where(
            Signal.org_id == org.id, Signal.snapshot_id == str(body.snapshot_id),
        ))).scalar_one_or_none()
        if existing and existing.digest == body_digest:
            return {"status": "accepted", "signal_id": body.signal_id, "duplicate": True}
        raise HTTPException(409, "signal_identity_conflict") from None
    return {"status": "accepted", "signal_id": body.signal_id, "duplicate": False}


@router.get("/agent/requests")
async def agent_requests(request: Request, db=Depends(session_dependency)):
    org = await node_identity(request, db)
    rows = (await db.execute(select(EvidenceRequest).where(
        EvidenceRequest.org_id == org.id, EvidenceRequest.status == "pending",
        EvidenceRequest.deadline > utcnow(),
    ).order_by(EvidenceRequest.id).limit(32))).scalars().all()
    await db.commit()
    return {"schema_version": 1, "requests": [
        {"request_id": r.id, "snapshot_id": r.snapshot_id, "entry": r.entry,
         "recipient": r.recipient, "deadline": aware(r.deadline).isoformat(), "schema_version": 1}
        for r in rows
    ]}


@router.post("/agent/responses")
async def evidence_response(body: EvidenceResponse, request: Request, db=Depends(session_dependency)):
    org = await node_identity(request, db)
    req = await db.get(EvidenceRequest, str(body.request_id))
    if not req or req.org_id != org.id:
        raise HTTPException(404, "request_not_found")
    incident = (await db.execute(select(Incident).where(
        Incident.id == req.incident_id
    ).with_for_update())).scalar_one()
    await db.refresh(req)  # Re-read after acquiring the incident lock.
    if req.snapshot_id != str(body.snapshot_id) or req.entry != body.entry:
        raise HTTPException(409, "request_binding_mismatch")
    payload = body.model_dump(mode="json")
    response_digest = digest(payload)
    if req.response_digest:
        if not secrets.compare_digest(req.response_digest, response_digest):
            raise HTTPException(409, "response_identity_conflict")
        await db.commit()
        return {"status": "recorded", "duplicate": True}
    if req.status != "pending" or aware(req.deadline) <= utcnow():
        raise HTTPException(409, "request_closed")
    req.response_digest, req.response, req.status = response_digest, payload, body.status
    if body.status != "denied":
        if await db.get(Evidence, str(body.evidence_id)):
            raise HTTPException(409, "evidence_identity_conflict")
        evidence = Evidence(
            id=str(body.evidence_id), request_id=req.id, incident_id=incident.id,
            org_id=org.id, entry=body.entry, value=body.value, version=1, active=True,
            policy_version=body.policy_version, cost=body.cost,
        )
        db.add(evidence)
        db.add(EvidenceHistory(evidence_id=evidence.id, version=1, body=payload))
    db.add(Audit(actor_id=org.id, action="evidence_" + body.status, resource_id=req.id))
    await db.flush()
    await evaluate(db, incident, request.app.state.settings, force_change=True)
    await db.commit()
    return {"status": "recorded", "duplicate": False}


@router.post("/agent/evidence/{evidence_id}/revise")
async def revise_evidence(evidence_id: str, body: EvidenceRevision, request: Request, db=Depends(session_dependency)):
    org = await node_identity(request, db)
    evidence = await db.get(Evidence, evidence_id)
    if not evidence or evidence.org_id != org.id:
        raise HTTPException(404, "evidence_not_found")
    incident = (await db.execute(select(Incident).where(
        Incident.id == evidence.incident_id
    ).with_for_update())).scalar_one()
    await db.refresh(evidence)
    if body.version != evidence.version:
        raise HTTPException(409, "evidence_version_conflict")
    if not body.withdraw and body.value not in CATALOGUE[evidence.entry]["values"]:
        raise HTTPException(422, "invalid_catalogue_value")
    evidence.version += 1
    evidence.active = not body.withdraw
    if body.value is not None:
        evidence.value = body.value
    db.add(EvidenceHistory(
        evidence_id=evidence.id, version=evidence.version,
        body={"value": evidence.value, "active": evidence.active, "version": evidence.version},
    ))
    db.add(Audit(actor_id=org.id, action="evidence_revision", resource_id=evidence.id))
    await db.flush()
    await evaluate(db, incident, request.app.state.settings, force_change=True)
    await db.commit()
    return {"id": evidence.id, "version": evidence.version, "active": evidence.active}


@router.get("/incidents")
async def incidents(request: Request, db=Depends(session_dependency), limit: int = 50):
    user = await actor(request, db)
    if not 1 <= limit <= 100:
        raise HTTPException(422, "limit_out_of_bounds")
    query = select(Incident)
    if user.role == "analyst":
        query = query.join(Participation).where(Participation.org_id == user.org_id)
    rows = (await db.execute(query.order_by(Incident.updated_at.desc()).limit(limit))).scalars().all()
    return {"incidents": [await snapshot(db, user, i.id) for i in rows]}


@router.get("/incidents/{incident_id}")
async def incident_detail(incident_id: str, request: Request, db=Depends(session_dependency)):
    return await snapshot(db, await actor(request, db), incident_id)


@router.patch("/incidents/{incident_id}/workflow")
async def workflow(incident_id: str, body: WorkflowIn, request: Request, db=Depends(session_dependency)):
    user = await actor(request, db)
    await authorize_incident(db, user, incident_id)
    if user.role not in {"admin", "coordinator"}:
        raise HTTPException(403, "coordinator_required")
    incident = (await db.execute(select(Incident).where(Incident.id == incident_id).with_for_update())).scalar_one()
    if incident.workflow != body.status:
        incident.workflow = body.status
        await bump(db, incident)
        db.add(Audit(actor_id=user.id, action="workflow_" + body.status, resource_id=incident.id))
    await db.commit()
    return await snapshot(db, user, incident_id)


@router.post("/incidents/{incident_id}/explanations", status_code=202)
async def create_explanation(incident_id: str, request: Request, db=Depends(session_dependency)):
    user = await actor(request, db)
    await quota(db, "explain:" + user.id, 10)
    view = await snapshot(db, user, incident_id)
    existing = (await db.execute(select(Explanation).where(
        Explanation.user_id == user.id, Explanation.snapshot_digest == view["digest"],
        Explanation.status.in_(["queued", "running", "complete", "fallback"]),
    ).order_by(Explanation.created_at.desc()).limit(1))).scalar_one_or_none()
    if existing:
        await db.commit()
        return {"job_id": existing.id, "status": existing.status}
    job = Explanation(
        incident_id=incident_id, user_id=user.id, incident_version=view["version"],
        snapshot=view, snapshot_digest=view["digest"], model=request.app.state.settings.llm_model,
    )
    db.add(job)
    await db.commit()
    return {"job_id": job.id, "status": job.status}


@router.get("/explanations/{job_id}")
async def get_explanation(job_id: str, request: Request, db=Depends(session_dependency)):
    user = await actor(request, db)
    job = await db.get(Explanation, job_id)
    if not job or job.user_id != user.id:
        raise HTTPException(404, "explanation_not_found")
    view = await snapshot(db, user, job.incident_id)
    if view["digest"] != job.snapshot_digest or job.status == "stale":
        job.status = "stale"
        await db.commit()
        return {"job_id": job.id, "status": "stale", "result": None}
    return {"job_id": job.id, "status": job.status, "result": job.result, "model": job.model}


@router.get("/organizations")
async def organizations(request: Request, db=Depends(session_dependency)):
    user = await actor(request, db)
    query = select(Organization)
    if user.role == "analyst":
        query = query.where(Organization.id == user.org_id)
    rows = (await db.execute(query.order_by(Organization.name))).scalars().all()
    return {"organizations": [
        {"id": o.id, "name": o.name, "active": o.active,
         "last_signal": (await db.scalar(select(func.max(Signal.received_at)).where(Signal.org_id == o.id)))}
        for o in rows
    ]}


@router.post("/admin/credentials/{credential_id}/revoke")
async def revoke(credential_id: str, request: Request, db=Depends(session_dependency)):
    user = await actor(request, db)
    if user.role != "admin":
        raise HTTPException(403, "admin_required")
    credential = await db.get(Credential, credential_id)
    if not credential:
        raise HTTPException(404, "credential_not_found")
    credential.active = False
    db.add(Audit(actor_id=user.id, action="credential_revoked", resource_id=credential.id))
    await db.commit()
    return {"status": "revoked"}


@router.get("/status")
async def system_status(request: Request, db=Depends(session_dependency)):
    user = await actor(request, db)
    if user.role not in {"admin", "coordinator"}:
        return {"service": "ready", "scope": "organization"}
    pending = await db.scalar(select(func.count()).select_from(Signal).where(Signal.processed.is_(False)))
    oldest = await db.scalar(select(func.min(Signal.received_at)).where(Signal.processed.is_(False)))
    return {
        "service": "ready", "pending_signals": pending,
        "oldest_pending_age_seconds": max(0, (utcnow() - aware(oldest)).total_seconds()) if oldest else 0,
        "inference_configured": request.app.state.settings.llm_enabled,
        "inference_model": request.app.state.settings.llm_model,
    }


@router.post("/admin/users/{user_id}/disable")
async def disable_user(user_id: str, request: Request, db=Depends(session_dependency)):
    """Revoke browser access and dependent jobs in the same committed transaction."""
    administrator = await actor(request, db)
    if administrator.role != "admin" or administrator.id == user_id:
        raise HTTPException(403, "other_administrator_required")
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "user_not_found")
    user.active = False
    await db.execute(delete(Session).where(Session.user_id == user_id))
    await db.execute(update(Explanation).where(Explanation.user_id == user_id).values(status="stale"))
    db.add(Audit(actor_id=administrator.id, action="user_disabled", resource_id=user_id))
    await db.commit()
    return {"status": "disabled"}
