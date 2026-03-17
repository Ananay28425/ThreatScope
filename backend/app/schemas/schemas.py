"""
Pydantic v2 schemas for request/response validation.

Pydantic v2 strict mode is used on sensitive inputs (auth, signal ingestion)
to prevent type coercion attacks. Output schemas deliberately exclude
fields that could leak internal state.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


# ── Auth ─────────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    model_config = ConfigDict(strict=True)

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


# ── Signal ────────────────────────────────────────────────────────────────────

class SignalIngest(BaseModel):
    """
    Payload a node sends to the central orchestrator.
    Strict validation: every numeric field must be a float — no implicit casts.
    """
    model_config = ConfigDict(strict=True)

    node_id: str = Field(min_length=1, max_length=64)
    timestamp: datetime
    anomaly_score: float = Field(ge=0.0, le=1.0)
    fingerprint: str | None = Field(default=None, max_length=64)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    window_seconds: int = Field(default=60, ge=10, le=600)
    # Aggregated metrics only — no raw log fields allowed
    metrics: dict[str, float | int] | None = None

    @field_validator("metrics")
    @classmethod
    def block_raw_log_fields(cls, v: dict | None) -> dict | None:
        """
        Rejects any metric that looks like a raw log field
        (e.g., 'user_id', 'ip_address', 'password'). This is an explicit
        privacy guard at the schema layer.
        """
        if v is None:
            return v
        blocked = {"user_id", "ip", "ip_address", "password", "username", "payload"}
        found = blocked & set(v.keys())
        if found:
            raise ValueError(f"Raw log fields not permitted in signals: {found}")
        return v


class SignalResponse(BaseModel):
    id: UUID
    org_id: UUID
    timestamp: datetime
    anomaly_score: float
    fingerprint: str | None

    model_config = ConfigDict(from_attributes=True)


# ── Alert ─────────────────────────────────────────────────────────────────────

class AlertResponse(BaseModel):
    id: UUID
    severity: str
    fingerprint: str | None
    description: str | None
    contributing_nodes: list[str] | None
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AlertStatusUpdate(BaseModel):
    status: str = Field(pattern="^(open|investigating|resolved)$")


# ── Node / Organization ───────────────────────────────────────────────────────

class NodeResponse(BaseModel):
    id: UUID
    name: str
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── WebSocket event contract (what frontend receives) ─────────────────────────

class WSEvent(BaseModel):
    """
    Canonical shape of every WebSocket push to the frontend.
    Frontend should switch on `event_type` to decide how to update state.
    """
    event_type: str   # "new_alert" | "node_status" | "signal_pulse" | "metrics"
    payload: dict[str, Any]
    timestamp: datetime
