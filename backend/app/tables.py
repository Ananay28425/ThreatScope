"""Authoritative v2 state; separate table names preserve the original prototype's records."""
from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from common.contracts import utcnow


def uid() -> str:
    return str(uuid4())


class Base(DeclarativeBase):
    pass


class Organization(Base):
    __tablename__ = "ts_organizations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(128), unique=True)
    provenance_group: Mapped[str] = mapped_column(String(64))
    active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Credential(Base):
    __tablename__ = "ts_credentials"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    org_id: Mapped[str] = mapped_column(ForeignKey("ts_organizations.id"), index=True)
    key_hash: Mapped[str] = mapped_column(String(64), unique=True)
    active: Mapped[bool] = mapped_column(default=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class User(Base):
    __tablename__ = "ts_users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    email: Mapped[str] = mapped_column(String(256), unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(String(16))  # admin, coordinator, analyst
    org_id: Mapped[str | None] = mapped_column(ForeignKey("ts_organizations.id"))
    active: Mapped[bool] = mapped_column(default=True)


class Session(Base):
    __tablename__ = "ts_sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("ts_users.id"), index=True)
    csrf: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class RateBucket(Base):
    __tablename__ = "ts_rate_buckets"
    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    minute: Mapped[int] = mapped_column(Integer, primary_key=True)
    count: Mapped[int] = mapped_column(Integer, default=1)


class Signal(Base):
    __tablename__ = "ts_signals"
    __table_args__ = (
        UniqueConstraint("org_id", "external_id"), UniqueConstraint("org_id", "snapshot_id"),
        Index("ix_ts_signal_pending", "processed", "received_at"),
        Index("ix_ts_signal_window", "family", "observed_end"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    org_id: Mapped[str] = mapped_column(ForeignKey("ts_organizations.id"))
    external_id: Mapped[str] = mapped_column(String(36))
    snapshot_id: Mapped[str] = mapped_column(String(36))
    digest: Mapped[str] = mapped_column(String(64))
    family: Mapped[str] = mapped_column(String(32))
    score: Mapped[float] = mapped_column(Float)
    provenance_group: Mapped[str] = mapped_column(String(64))
    observed_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    body: Mapped[dict] = mapped_column(JSON)
    processed: Mapped[bool] = mapped_column(default=False)
    research_eligible: Mapped[bool] = mapped_column(default=True)


class Incident(Base):
    __tablename__ = "ts_incidents"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    correlation_key: Mapped[str] = mapped_column(String(80), unique=True)
    family: Mapped[str] = mapped_column(String(32))
    outcome: Mapped[str] = mapped_column(String(16), default="unresolved")
    workflow: Mapped[str] = mapped_column(String(16), default="open")
    reason: Mapped[str] = mapped_column(String(64), default="insufficient_independent_sources")
    version: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    summary: Mapped[dict] = mapped_column(JSON, default=dict)


class Participation(Base):
    __tablename__ = "ts_participation"
    incident_id: Mapped[str] = mapped_column(ForeignKey("ts_incidents.id"), primary_key=True)
    org_id: Mapped[str] = mapped_column(ForeignKey("ts_organizations.id"), primary_key=True)
    signal_id: Mapped[str] = mapped_column(ForeignKey("ts_signals.id"))


class EvidenceRequest(Base):
    __tablename__ = "ts_requests"
    __table_args__ = (UniqueConstraint("org_id", "snapshot_id", "entry", "recipient"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    incident_id: Mapped[str] = mapped_column(ForeignKey("ts_incidents.id"), index=True)
    org_id: Mapped[str] = mapped_column(ForeignKey("ts_organizations.id"), index=True)
    snapshot_id: Mapped[str] = mapped_column(String(36))
    entry: Mapped[str] = mapped_column(String(32))
    recipient: Mapped[str] = mapped_column(String(32), default="coordinator")
    status: Mapped[str] = mapped_column(String(16), default="pending")
    deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    response_digest: Mapped[str | None] = mapped_column(String(64))
    response: Mapped[dict | None] = mapped_column(JSON)


class Evidence(Base):
    __tablename__ = "ts_evidence"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    request_id: Mapped[str] = mapped_column(ForeignKey("ts_requests.id"), unique=True)
    incident_id: Mapped[str] = mapped_column(ForeignKey("ts_incidents.id"), index=True)
    org_id: Mapped[str] = mapped_column(ForeignKey("ts_organizations.id"))
    entry: Mapped[str] = mapped_column(String(32))
    value: Mapped[str] = mapped_column(String(32))
    version: Mapped[int] = mapped_column(default=1)
    policy_version: Mapped[int] = mapped_column()
    active: Mapped[bool] = mapped_column(default=True)
    cost: Mapped[int] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class EvidenceHistory(Base):
    __tablename__ = "ts_evidence_history"
    evidence_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    version: Mapped[int] = mapped_column(primary_key=True)
    body: Mapped[dict] = mapped_column(JSON)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Notification(Base):
    __tablename__ = "ts_notifications"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    incident_id: Mapped[str] = mapped_column(ForeignKey("ts_incidents.id"), index=True)
    version: Mapped[int] = mapped_column()
    event_type: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (UniqueConstraint("incident_id", "version", "event_type"),)


class Explanation(Base):
    __tablename__ = "ts_explanations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    incident_id: Mapped[str] = mapped_column(ForeignKey("ts_incidents.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("ts_users.id"))
    incident_version: Mapped[int] = mapped_column()
    snapshot: Mapped[dict] = mapped_column(JSON)
    snapshot_digest: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), default="queued", index=True)
    result: Mapped[dict | None] = mapped_column(JSON)
    model: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Audit(Base):
    __tablename__ = "ts_audit"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    actor_id: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(64))
    resource_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class LegacyArchive(Base):
    __tablename__ = "ts_legacy_archive"
    table_name: Mapped[str] = mapped_column(String(32), primary_key=True)
    row_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    body: Mapped[dict] = mapped_column(JSON)
    research_eligible: Mapped[bool] = mapped_column(Boolean, default=False)
