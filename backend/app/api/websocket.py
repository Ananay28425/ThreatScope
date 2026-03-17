"""
WebSocket endpoint for real-time SOC dashboard streaming.

Every connected frontend client receives:
  - new_alert     → when the correlation engine fires
  - signal_pulse  → visual ping when a node emits a signal (for the 3D globe)
  - node_status   → periodic heartbeat of active/inactive nodes
  - metrics       → system health stats every 10 seconds

Connection manager pattern:
  A simple set of active connections. On broadcast, we iterate
  all connections and send; dead connections are removed automatically.
  For production at scale, you'd move this state into Valkey pub/sub
  so multiple FastAPI instances share the broadcast — but for this
  project's 3-server demo, the in-process set is perfectly correct.
"""

import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response
import structlog

from app.metrics.prometheus import websocket_connections

log = structlog.get_logger(__name__)

router = APIRouter()


class ConnectionManager:
    def __init__(self) -> None:
        self.active: set[WebSocket] = set()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self.active.add(ws)
        websocket_connections.set(len(self.active))
        log.info("WebSocket connected", total=len(self.active))

    def disconnect(self, ws: WebSocket) -> None:
        self.active.discard(ws)
        websocket_connections.set(len(self.active))
        log.info("WebSocket disconnected", total=len(self.active))

    async def broadcast(self, data: dict) -> None:
        """Send to all connected clients; silently drop dead connections."""
        dead: set[WebSocket] = set()
        for ws in self.active:
            try:
                await ws.send_json(data)
            except Exception:
                dead.add(ws)
        for ws in dead:
            self.disconnect(ws)


manager = ConnectionManager()


@router.websocket("/ws/threat-stream")
async def threat_stream(websocket: WebSocket) -> None:
    await manager.connect(websocket)
    try:
        # Send a welcome handshake so the frontend knows the connection is live
        await websocket.send_json({
            "event_type": "connected",
            "payload": {"message": "ThreatScope SOC stream active"},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        # Keep the connection alive; all outbound messages are pushed via manager.broadcast
        while True:
            # We don't expect the client to send messages, but we need to
            # keep the receive loop running to detect disconnects
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as exc:
        log.error("WebSocket error", error=str(exc))
        manager.disconnect(websocket)


@router.get("/metrics", include_in_schema=False)
async def prometheus_metrics() -> Response:
    """Prometheus scrape endpoint."""
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )
