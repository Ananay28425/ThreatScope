"""Finite evidence catalogue and versioned network contracts; raw records have no wire type."""
from datetime import datetime, timezone
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def utcnow() -> datetime:
    """Return an aware UTC clock value."""
    return datetime.now(timezone.utc)


def aware(value: datetime) -> datetime:
    """Normalize database values, including SQLite's naive UTC timestamps."""
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


class Family(StrEnum):
    AUTH = "authentication_burst"
    TRAFFIC = "traffic_burst"
    UNKNOWN = "unknown"
    NONE = "none"


# The integer costs are policy units, not differential privacy epsilon.
EVIDENCE_TTL_SECONDS = 86400
CATALOGUE = {
    "auth_failure": {"cost": 1, "values": ("low", "high", "unknown")},
    "source_spread": {"cost": 2, "values": ("narrow", "wide", "unknown")},
    "failure_kind": {"cost": 2, "values": ("rejected", "unavailable", "mixed", "unknown")},
    "request_rate": {"cost": 1, "values": ("normal", "elevated", "spike", "unknown")},
    "service_errors": {"cost": 1, "values": ("low", "high", "unknown")},
}
PREDICATES = {
    Family.AUTH: ("auth_failure", "source_spread", "failure_kind"),
    Family.TRAFFIC: ("request_rate", "source_spread", "service_errors"),
}


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class SignalIn(Contract):
    schema_version: Literal[1] = 1
    signal_id: UUID
    snapshot_id: UUID
    observation_start: datetime
    observation_end: datetime
    family: Family
    anomaly_score: float = Field(ge=0, le=1)
    detector_version: Literal["rules-iforest/2"] = "rules-iforest/2"
    model_state: Literal["warmup", "ready", "rules_only"] = "rules_only"
    confidence: float | None = Field(default=None, ge=0, le=1)
    policy_version: int = Field(ge=1, default=1)
    recipient: Literal["coordinator"] = "coordinator"
    initial_cost: Literal[1] = 1

    @field_validator("observation_start", "observation_end")
    @classmethod
    def timezone_required(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timezone_required")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def interval_valid(self):
        duration = (self.observation_end - self.observation_start).total_seconds()
        if not 1 <= duration <= 600:
            raise ValueError("observation_window_out_of_range")
        return self


class EvidenceResponse(Contract):
    schema_version: Literal[1] = 1
    request_id: UUID
    snapshot_id: UUID
    entry: str
    status: Literal["approved", "coarsened", "denied"]
    value: str | None = None
    evidence_id: UUID | None = None
    policy_version: int = Field(ge=1)
    cost: int = Field(ge=0, le=2)
    reason: Literal["policy", "budget", "expired", "missing", "released"] = "released"

    @model_validator(mode="after")
    def catalogue_valid(self):
        if self.entry not in CATALOGUE:
            raise ValueError("unknown_catalogue_entry")
        if self.status == "denied":
            if self.value is not None or self.evidence_id is not None or self.cost != 0:
                raise ValueError("denial_cannot_contain_evidence")
        else:
            if self.value not in CATALOGUE[self.entry]["values"] or self.evidence_id is None:
                raise ValueError("invalid_catalogue_value")
            expected = 0 if self.status == "coarsened" else CATALOGUE[self.entry]["cost"]
            if self.cost != expected or (self.status == "coarsened" and self.value != "unknown"):
                raise ValueError("invalid_representation_cost")
        return self


class EvidenceRevision(Contract):
    version: int = Field(ge=1)
    value: str | None = None
    withdraw: bool = False


class LoginIn(Contract):
    email: str = Field(min_length=3, max_length=256)
    password: str = Field(min_length=1, max_length=256)


class WorkflowIn(Contract):
    status: Literal["open", "investigating", "resolved"]


class Claim(Contract):
    kind: Literal["observation", "inference", "unknown", "advice"]
    predicate: Literal["evidence_value", "outcome", "family", "coverage", "review_local_logs"]
    value: str = Field(max_length=64)
    evidence_id: str | None = Field(default=None, max_length=36)
    evidence_version: int | None = Field(default=None, ge=1)


class ClaimSet(Contract):
    claims: list[Claim] = Field(max_length=12)

