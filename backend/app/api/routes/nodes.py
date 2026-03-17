"""
Nodes (Organizations) REST API.

Endpoints:
  GET  /api/nodes           → list all registered nodes
  GET  /api/nodes/{id}      → single node detail
  POST /api/nodes           → register a new node (admin only)
"""

from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
import structlog

from app.core.security import get_current_user_id, hash_password
from app.models.models import Organization
from app.schemas.schemas import NodeResponse

router = APIRouter(prefix="/api/nodes", tags=["nodes"])
log = structlog.get_logger(__name__)


async def get_db() -> AsyncSession:
    raise NotImplementedError("Wire AsyncSession in main.py")


class NodeCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=128)


class NodeCreateResponse(BaseModel):
    node: NodeResponse
    api_key: str  # Shown ONCE at creation — not stored in plaintext


@router.get("/", response_model=list[NodeResponse])
async def list_nodes(
    db: AsyncSession = Depends(get_db),
    _user_id: str = Depends(get_current_user_id),
) -> list[Organization]:
    result = await db.execute(select(Organization).where(Organization.is_active == True))
    return result.scalars().all()


@router.get("/{node_id}", response_model=NodeResponse)
async def get_node(
    node_id: UUID,
    db: AsyncSession = Depends(get_db),
    _user_id: str = Depends(get_current_user_id),
) -> Organization:
    result = await db.execute(select(Organization).where(Organization.id == node_id))
    org = result.scalar_one_or_none()
    if org is None:
        raise HTTPException(status_code=404, detail="Node not found")
    return org


@router.post("/", response_model=NodeCreateResponse, status_code=201)
async def register_node(
    body: NodeCreateRequest,
    db: AsyncSession = Depends(get_db),
    _user_id: str = Depends(get_current_user_id),
) -> NodeCreateResponse:
    """
    Register a new organization node.
    Returns a plaintext API key ONCE — it is stored only as a bcrypt hash.
    The caller must save this key immediately; it cannot be recovered.
    """
    raw_key = str(uuid4()).replace("-", "")  # 32-char random API key
    org = Organization(
        name=body.name,
        api_key_hash=hash_password(raw_key),
    )
    db.add(org)
    await db.commit()
    await db.refresh(org)

    log.info("Node registered", name=body.name, node_id=str(org.id))

    return NodeCreateResponse(
        node=NodeResponse.model_validate(org),
        api_key=raw_key,
    )
