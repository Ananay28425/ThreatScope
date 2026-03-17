"""
Authentication endpoints for SOC dashboard users.

This module provides a lightweight FastAPI auth API with:
  - POST /api/auth/login
  - POST /api/auth/refresh
  - POST /api/auth/logout

It is intentionally self-contained so it can be dropped into the current
ThreatScope backend structure without requiring immediate database wiring.
If a real user store is available later, replace the in-memory demo lookup
with a database-backed implementation.

Security notes:
  - Passwords are verified with passlib's bcrypt helpers
  - Access/refresh JWTs are generated via app.core.security helpers
  - Refresh tokens are validated and rotated
  - Logout is stateless by default
"""

from dataclasses import dataclass

import structlog
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    verify_password,
)
from app.schemas.schemas import LoginRequest, TokenResponse
from fastapi import APIRouter, HTTPException, Response, status

router = APIRouter(prefix="/api/auth", tags=["auth"])
log = structlog.get_logger(__name__)


@dataclass
class DemoUser:
    id: str
    email: str
    hashed_password: str
    is_active: bool = True


# Demo-only user store.
# Replace with a DB query layer when User ORM wiring is added.
_DEMO_USERS: dict[str, DemoUser] = {
    "analyst@threatscope.local": DemoUser(
        id="user_demo_1",
        email="analyst@threatscope.local",
        hashed_password=get_password_hash("threatscope123"),
        is_active=True,
    ),
}


def _get_user_by_email(email: str) -> DemoUser | None:
    return _DEMO_USERS.get(email.lower())


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest) -> TokenResponse:
    """
    Authenticate a dashboard user and return fresh access/refresh tokens.

    Current behavior:
      - Uses a small in-memory demo user registry
      - Returns 401 on invalid credentials
      - Returns 403 if the account is disabled
    """
    user = _get_user_by_email(body.email)

    if user is None or not verify_password(body.password, user.hashed_password):
        log.warning("Failed login attempt", email=body.email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account disabled",
        )

    log.info("Successful login", user_id=user.id)

    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(refresh_token: str) -> TokenResponse:
    """
    Exchange a valid refresh token for a new access/refresh pair.
    """
    try:
        payload = decode_token(refresh_token)
    except Exception as exc:
        log.warning("Refresh token rejected", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        ) from exc

    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Expected refresh token",
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed token payload",
        )

    log.info("Refresh token accepted", user_id=user_id)

    return TokenResponse(
        access_token=create_access_token(user_id),
        refresh_token=create_refresh_token(user_id),
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout() -> Response:
    """
    Stateless JWT logout.

    The client must discard stored tokens. If token revocation is needed,
    add a denylist store keyed by token ID (jti) and validate it in the
    auth dependency layer.
    """
    return Response(status_code=status.HTTP_204_NO_CONTENT)
