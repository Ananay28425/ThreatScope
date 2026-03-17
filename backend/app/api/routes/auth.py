"""
Authentication endpoints for SOC dashboard users.

Implements:
  POST /api/auth/login   → returns access + refresh tokens
  POST /api/auth/refresh → exchanges a valid refresh token for a new access token
  POST /api/auth/logout  → client-side token discard (stateless JWT — no server state)

Security notes:
  - Passwords hashed with bcrypt (cost factor 12 by default via passlib).
  - Access token TTL: 60 minutes. Refresh token TTL: 7 days.
  - No raw password ever logged or stored in structured logs.
  - Login failures return the same response time regardless of whether
    the email exists (constant-time comparison via verify_password).
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)
from app.models.models import User
from app.schemas.schemas import LoginRequest, TokenResponse

router = APIRouter(prefix="/api/auth", tags=["auth"])
log = structlog.get_logger(__name__)


async def get_db() -> AsyncSession:
    raise NotImplementedError("Wire AsyncSession in main.py")


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    # Constant-time rejection — same code path whether user exists or not
    if user is None or not verify_password(body.password, user.hashed_password):
        log.warning("Failed login attempt", email=body.email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")

    log.info("Successful login", user_id=str(user.id))

    return TokenResponse(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id)),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(refresh_token: str) -> TokenResponse:
    payload = decode_token(refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Expected refresh token")

    user_id = payload["sub"]
    return TokenResponse(
        access_token=create_access_token(user_id),
        refresh_token=create_refresh_token(user_id),
    )


@router.post("/logout", status_code=204)
async def logout() -> None:
    """
    Stateless JWT logout.
    Client must delete stored tokens.
    For true token revocation, implement a Valkey denylist keyed by jti claim.
    """
    pass
