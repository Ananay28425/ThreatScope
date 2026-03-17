"""
SQLAlchemy ORM models for ThreatScope.

Schema design decisions:
- UUID primary keys to prevent enumeration attacks.
- created_at / updated_at on every table for audit trails.
- org_id foreign key on alerts + signals enforces tenant isolation at the DB layer.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


# ── Organization (Node) ───────────────────────────────────────────────────────

class Organization(Base):
    """Represents a participating node — a simulated company."""
    __tablename__ = "organizations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(128), nullable=False, unique=True)
    api_key_hash = Column(String(256), nullable=False)  # bcrypt hashed
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    alerts = relationship("Alert", back_populates="organization")
    signals = relationship("Signal", back_populates="organization")


# ── User ─────────────────────────────────────────────────────────────────────

class User(Base):
    """SOC analyst or admin who logs into the dashboard."""
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(256), nullable=False, unique=True, index=True)
    hashed_password = Column(String(256), nullable=False)
    role = Column(String(32), default="analyst")  # analyst | admin
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ── Signal ────────────────────────────────────────────────────────────────────

class Signal(Base):
    """
    A privacy-safe payload emitted by a node's local detection engine.
    Contains ONLY derived metrics — never raw logs.
    """
    __tablename__ = "signals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    anomaly_score = Column(Float, nullable=False)          # 0.0 – 1.0
    fingerprint = Column(String(64), nullable=True)        # e.g. "AUTH_FAIL_BURST"
    confidence = Column(Float, default=1.0)
    metrics = Column(JSONB, nullable=True)                 # windowed stats (no raw data)
    window_seconds = Column(Integer, default=60)

    organization = relationship("Organization", back_populates="signals")


# ── Alert ─────────────────────────────────────────────────────────────────────

class Alert(Base):
    """
    A global alert raised by the correlation engine when ≥N nodes
    report matching high-score signals within the correlation window.
    """
    __tablename__ = "alerts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=True)
    severity = Column(String(16), nullable=False)          # LOW | MEDIUM | HIGH | CRITICAL
    fingerprint = Column(String(64), nullable=True)
    description = Column(Text, nullable=True)
    contributing_nodes = Column(JSONB, nullable=True)      # list of org UUIDs
    status = Column(String(16), default="open")            # open | investigating | resolved
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    organization = relationship("Organization", back_populates="alerts")
