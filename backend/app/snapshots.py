"""Recipient-specific evidence views shared by the API, stream, and explanation worker."""
from sqlalchemy import select

from backend.app.security import authorize_incident, digest
from backend.app.tables import Evidence, EvidenceRequest
from common.contracts import EVIDENCE_TTL_SECONDS, aware, utcnow


async def snapshot(db, user, incident_id: str) -> dict:
    incident = await authorize_incident(db, user, incident_id)
    ev_query = select(Evidence).where(Evidence.incident_id == incident_id)
    req_query = select(EvidenceRequest).where(EvidenceRequest.incident_id == incident_id)
    if user.role == "analyst":
        ev_query = ev_query.where(Evidence.org_id == user.org_id)
        req_query = req_query.where(EvidenceRequest.org_id == user.org_id)
    evidence = (await db.execute(ev_query.order_by(Evidence.id))).scalars().all()
    requests = (await db.execute(req_query.order_by(EvidenceRequest.id))).scalars().all()
    def current(item):
        return item.active and (utcnow() - aware(item.created_at)).total_seconds() < EVIDENCE_TTL_SECONDS
    from datetime import timedelta
    expired = await db.scalar(select(Evidence.id).where(
        Evidence.incident_id == incident_id, Evidence.active.is_(True),
        Evidence.created_at <= utcnow() - timedelta(seconds=EVIDENCE_TTL_SECONDS)
    ).limit(1)) is not None
    result = {
        "schema_version": 1, "incident_id": incident.id, "version": incident.version,
        "family": incident.family, "outcome": "unresolved" if expired else incident.outcome, "workflow": incident.workflow,
        "reason": "evidence_expired" if expired else incident.reason, "created_at": incident.created_at.isoformat(),
        "coverage": "partial" if expired else incident.summary.get("coverage", "partial"),
        "audience": user.org_id or "coordinator",
        "evidence": [
            {"id": e.id, "entry": e.entry, "value": e.value if current(e) else "withdrawn",
             "version": e.version, "active": current(e), "policy_version": e.policy_version,
             "cost": e.cost} for e in evidence
        ],
        "requests": [
            {"id": r.id, "entry": r.entry, "status": r.status, "deadline": r.deadline.isoformat()}
            for r in requests
        ],
    }
    # Aggregate conclusions are explicitly shared with enrolled participants; foreign evidence is not.
    if user.role in {"admin", "coordinator"}:
        result["summary"] = incident.summary
    result["digest"] = digest(result)
    return result
