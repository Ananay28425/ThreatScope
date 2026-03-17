"""
Alerts REST API.

Endpoints:
  GET  /api/alerts           → paginated list of all alerts (newest first)
  GET  /api/alerts/{id}      → single alert detail
  PATCH /api/alerts/{id}     → update status (open → investigating → resolved)
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user_id
from app.models.models import Alert
from app.schemas.schemas import AlertResponse, AlertStatusUpdate

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


async def get_db() -> AsyncSession:
    # Placeholder — will be replaced with proper dependency injection
    # once database.py session factory is wired in main.py
    raise NotImplementedError("Wire up AsyncSession dependency in main.py")


@router.get("/", response_model=list[AlertResponse])
async def list_alerts(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, le=200),
    severity: str | None = Query(default=None),
    status: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    _user_id: str = Depends(get_current_user_id),
) -> list[Alert]:
    """
    Return paginated alerts, newest first.
    Optional filters: severity (LOW/MEDIUM/HIGH/CRITICAL), status (open/investigating/resolved).
    """
    stmt = select(Alert).order_by(desc(Alert.created_at)).offset(skip).limit(limit)
    if severity:
        stmt = stmt.where(Alert.severity == severity.upper())
    if status:
        stmt = stmt.where(Alert.status == status.lower())

    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/{alert_id}", response_model=AlertResponse)
async def get_alert(
    alert_id: UUID,
    db: AsyncSession = Depends(get_db),
    _user_id: str = Depends(get_current_user_id),
) -> Alert:
    result = await db.execute(select(Alert).where(Alert.id == alert_id))
    alert = result.scalar_one_or_none()
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    return alert


@router.patch("/{alert_id}", response_model=AlertResponse)
async def update_alert_status(
    alert_id: UUID,
    body: AlertStatusUpdate,
    db: AsyncSession = Depends(get_db),
    _user_id: str = Depends(get_current_user_id),
) -> Alert:
    """Allow SOC analysts to progress an alert through its lifecycle."""
    result = await db.execute(select(Alert).where(Alert.id == alert_id))
    alert = result.scalar_one_or_none()
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")

    alert.status = body.status
    await db.commit()
    await db.refresh(alert)
    return alert
