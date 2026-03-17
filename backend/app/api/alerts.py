"""
ThreatScope backend alerts API module.

Provides:
  - List alerts
  - Get a single alert
  - Update alert status
  - Create demo alerts in-memory when DB models are not wired yet

This module is intentionally self-contained so the project can expose a
working alerts API even before the full ORM layer is finalized.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


class AlertRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    severity: str
    fingerprint: str | None = None
    description: str | None = None
    contributing_nodes: list[str] = Field(default_factory=list)
    status: str = "open"
    created_at: datetime
    updated_at: datetime


class AlertStatusUpdate(BaseModel):
    status: str = Field(pattern="^(open|investigating|resolved)$")


class AlertCreate(BaseModel):
    severity: str = Field(min_length=3, max_length=16)
    fingerprint: str | None = Field(default=None, max_length=64)
    description: str | None = Field(default=None, max_length=500)
    contributing_nodes: list[str] = Field(default_factory=list)
    status: str = Field(default="open", pattern="^(open|investigating|resolved)$")


# Simple in-memory store for early integration/demo use.
# Replace this with SQLAlchemy-backed persistence once models are fully wired.
_ALERTS: list[AlertRecord] = [
    AlertRecord(
        id=uuid4(),
        severity="HIGH",
        fingerprint="AUTH_FAIL_BURST",
        description="Distributed authentication failure burst detected across multiple nodes.",
        contributing_nodes=["org_1", "org_3", "org_7"],
        status="open",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    ),
    AlertRecord(
        id=uuid4(),
        severity="MEDIUM",
        fingerprint="TRAFFIC_SPIKE",
        description="Correlated traffic spike observed within the active correlation window.",
        contributing_nodes=["org_2", "org_5", "org_8"],
        status="investigating",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    ),
]


async def get_current_user_id() -> str:
    """
    Stub auth dependency.

    Replace with JWT/session validation later. For now it ensures the route
    shape matches the rest of the backend without blocking local development.
    """
    return "dev-user"


def _normalize_severity(value: str) -> str:
    normalized = value.upper()
    if normalized not in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Severity must be one of LOW, MEDIUM, HIGH, CRITICAL",
        )
    return normalized


def _get_alert_or_404(alert_id: UUID) -> AlertRecord:
    for alert in _ALERTS:
        if alert.id == alert_id:
            return alert
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")


@router.get("/", response_model=list[AlertRecord])
async def list_alerts(
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    severity: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    _user_id: str = Depends(get_current_user_id),
) -> list[AlertRecord]:
    """
    Return alerts ordered newest-first.

    Supports optional filtering by:
      - severity: LOW | MEDIUM | HIGH | CRITICAL
      - status: open | investigating | resolved
    """
    records = sorted(_ALERTS, key=lambda item: item.created_at, reverse=True)

    if severity:
        wanted = _normalize_severity(severity)
        records = [item for item in records if item.severity == wanted]

    if status_filter:
        wanted_status = status_filter.lower()
        if wanted_status not in {"open", "investigating", "resolved"}:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Status must be one of open, investigating, resolved",
            )
        records = [item for item in records if item.status == wanted_status]

    return records[skip : skip + limit]


@router.get("/{alert_id}", response_model=AlertRecord)
async def get_alert(
    alert_id: UUID,
    _user_id: str = Depends(get_current_user_id),
) -> AlertRecord:
    """Return a single alert by ID."""
    return _get_alert_or_404(alert_id)


@router.patch("/{alert_id}", response_model=AlertRecord)
async def update_alert_status(
    alert_id: UUID,
    body: AlertStatusUpdate,
    _user_id: str = Depends(get_current_user_id),
) -> AlertRecord:
    """Update the workflow status of an alert."""
    existing = _get_alert_or_404(alert_id)
    updated = existing.model_copy(
        update={
            "status": body.status,
            "updated_at": datetime.now(timezone.utc),
        }
    )

    for index, alert in enumerate(_ALERTS):
        if alert.id == alert_id:
            _ALERTS[index] = updated
            return updated

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")


@router.post(
    "/",
    response_model=AlertRecord,
    status_code=status.HTTP_201_CREATED,
)
async def create_alert(
    body: AlertCreate,
    _user_id: str = Depends(get_current_user_id),
) -> AlertRecord:
    """
    Create an alert.

    This is primarily useful for demo/testing workflows until the correlation
    engine persists alerts directly to the database.
    """
    now = datetime.now(timezone.utc)
    record = AlertRecord(
        id=uuid4(),
        severity=_normalize_severity(body.severity),
        fingerprint=body.fingerprint,
        description=body.description,
        contributing_nodes=body.contributing_nodes,
        status=body.status,
        created_at=now,
        updated_at=now,
    )
    _ALERTS.append(record)
    return record
