"""Deterministic predicate correlation and decision-changing requests over durable evidence."""
from datetime import timedelta

from sqlalchemy import select, update

from backend.app.tables import (
    Evidence,
    EvidenceHistory,
    EvidenceRequest,
    Explanation,
    Incident,
    Notification,
    Organization,
    Participation,
    Signal,
)
from common.contracts import CATALOGUE, EVIDENCE_TTL_SECONDS, PREDICATES, Family, aware, utcnow


def source_decision(family: str, values: dict[str, str]) -> str:
    """Evaluate a declared scenario rule; supported means rule support, not proven compromise."""
    if family == Family.AUTH:
        if values.get("failure_kind") == "unavailable":
            return "contradicted"
        if values.get("auth_failure") == "low" or values.get("source_spread") == "narrow":
            return "contradicted"
        if all(values.get(k) == v for k, v in {
            "auth_failure": "high", "source_spread": "wide", "failure_kind": "rejected"
        }.items()):
            return "supported"
    elif family == Family.TRAFFIC:
        if values.get("request_rate") == "normal" or values.get("service_errors") == "low":
            return "contradicted"
        if all(values.get(k) == v for k, v in {
            "request_rate": "spike", "source_spread": "wide", "service_errors": "high"
        }.items()):
            return "supported"
    return "unresolved"


def choose_entry(family: str, values: dict, attempted: set[str]) -> str | None:
    """Ask the cheapest remaining decision predicate, with a stable lexical tie-break."""
    if source_decision(family, values) != "unresolved":
        return None
    eligible = [k for k in PREDICATES.get(family, ()) if k not in attempted and k not in values]
    return min(eligible, key=lambda k: (CATALOGUE[k]["cost"], k)) if eligible else None


async def bump(db, incident: Incident, event_type: str = "incident_changed") -> None:
    incident.version += 1
    incident.updated_at = utcnow()
    db.add(Notification(incident_id=incident.id, version=incident.version, event_type=event_type))
    await db.execute(update(Explanation).where(
        Explanation.incident_id == incident.id, Explanation.status != "stale"
    ).values(status="stale"))


async def evaluate(db, incident: Incident, settings, force_change: bool = False) -> None:
    """Use one representative per organization and one vote per enrolled provenance group."""
    rows = (await db.execute(
        select(Participation, Organization, Signal).join(Organization, Organization.id == Participation.org_id)
        .join(Signal, Signal.id == Participation.signal_id)
        .where(Participation.incident_id == incident.id, Organization.active.is_(True))
        .order_by(Organization.id)
    )).all()
    evidence = (await db.execute(select(Evidence).where(Evidence.incident_id == incident.id))).scalars().all()
    requests = (await db.execute(select(EvidenceRequest).where(
        EvidenceRequest.incident_id == incident.id
    ))).scalars().all()
    now = utcnow()
    for item in evidence:
        if item.active and (now - aware(item.created_at)).total_seconds() >= EVIDENCE_TTL_SECONDS:
            item.active = False
            item.version += 1
            db.add(EvidenceHistory(evidence_id=item.id, version=item.version,
                                  body={"active": False, "reason": "expired"}))
            force_change = True
    for req in requests:
        if req.status == "pending" and aware(req.deadline) <= now:
            req.status = "expired"
    groups: dict[str, list[str]] = {}
    details = []
    for participant, org, signal in rows:
        values = {e.entry: e.value for e in evidence if e.org_id == org.id and e.active}
        decision = source_decision(incident.family, values)
        groups.setdefault(signal.provenance_group, []).append(decision)
        details.append((participant, org, values, decision))
    # Conflicting reports within the same provenance group cannot provide independent support.
    votes = [
        "supported" if set(v) == {"supported"} else
        "contradicted" if set(v) == {"contradicted"} else "unresolved"
        for v in groups.values()
    ]
    supported = votes.count("supported")
    contradicted = votes.count("contradicted")
    if supported >= settings.quorum and contradicted >= settings.quorum:
        outcome, reason = "unresolved", "conflicting_independent_evidence"
    elif supported >= settings.quorum:
        outcome, reason = "supported", "declared_predicates_satisfied"
    elif contradicted >= settings.quorum:
        outcome, reason = "contradicted", "declared_benign_alternative"
    else:
        outcome = "unresolved"
        reason = "insufficient_independent_sources" if len(groups) < settings.quorum else "missing_evidence"
    if outcome == "unresolved" and len(groups) >= settings.quorum and aware(incident.deadline) > now:
        for participant, org, values, decision in details:
            org_requests = [r for r in requests if r.org_id == org.id]
            if decision != "unresolved" or any(r.status == "pending" for r in org_requests):
                continue
            # One denial with no useful coarsening is terminal for this source in this investigation.
            if any(r.status in {"denied", "expired"} for r in org_requests):
                continue
            entry = choose_entry(incident.family, values, {r.entry for r in org_requests})
            if entry:
                signal = await db.get(Signal, participant.signal_id)
                req = EvidenceRequest(
                    incident_id=incident.id, org_id=org.id, snapshot_id=signal.snapshot_id,
                    entry=entry, recipient="coordinator", status="pending", deadline=incident.deadline,
                )
                db.add(req)
                requests.append(req)
    if outcome != "unresolved":
        for req in requests:
            if req.status == "pending":
                req.status = "cancelled"
    elif aware(incident.deadline) <= now:
        reason = "deadline_exhausted"
    elif requests and not any(r.status == "pending" for r in requests):
        reason = "no_useful_authorized_evidence"
    summary = {
        "organizations": len(rows), "independent_groups": len(groups),
        "supporting_groups": supported, "contradicting_groups": contradicted,
        "pending_requests": sum(r.status == "pending" for r in requests),
        "denied_requests": sum(r.status == "denied" for r in requests),
        "coverage": "complete_for_rule" if outcome != "unresolved" else "partial",
    }
    changed = force_change or incident.outcome != outcome or incident.reason != reason or incident.summary != summary
    incident.outcome, incident.reason, incident.summary = outcome, reason, summary
    if changed:
        await bump(db, incident)


async def process_pending(db, settings) -> int:
    """Process a bounded batch in the worker transaction; API processes never own correlation state."""
    signals = (await db.execute(select(Signal).where(Signal.processed.is_(False))
        .order_by(Signal.received_at, Signal.id).limit(100))).scalars().all()
    for signal in signals:
        if signal.family not in PREDICATES or signal.score < settings.score_threshold:
            signal.processed = True
            continue
        bucket = int(aware(signal.observed_end).timestamp()) // settings.window_seconds
        key = f"{signal.family}:{bucket}"
        incident = (await db.execute(select(Incident).where(Incident.correlation_key == key).with_for_update())).scalar_one_or_none()
        if incident is None:
            incident = Incident(
                correlation_key=key, family=signal.family,
                deadline=utcnow() + timedelta(seconds=settings.request_timeout_seconds),
            )
            db.add(incident)
            await db.flush()
        participant = await db.get(Participation, (incident.id, signal.org_id))
        if not participant:
            db.add(Participation(incident_id=incident.id, org_id=signal.org_id, signal_id=signal.id))
        signal.processed = True
        await db.flush()
        await evaluate(db, incident, settings)
    # Expire investigations even when no new signals arrive.
    pending = (await db.execute(select(Incident).where(
        Incident.outcome == "unresolved", Incident.deadline <= utcnow(),
        Incident.reason != "deadline_exhausted",
    ).with_for_update().limit(100))).scalars().all()
    for incident in pending:
        await evaluate(db, incident, settings)
    expired_ids = (await db.execute(select(Evidence.incident_id).where(
        Evidence.active.is_(True), Evidence.created_at <= utcnow() - timedelta(seconds=EVIDENCE_TTL_SECONDS)
    ).distinct().limit(100))).scalars().all()
    for incident_id in expired_ids:
        incident = (await db.execute(select(Incident).where(Incident.id == incident_id).with_for_update())).scalar_one()
        await evaluate(db, incident, settings)
    return len(signals)
