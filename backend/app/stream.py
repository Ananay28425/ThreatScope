"""Scoped WebSocket delivery from durable notifications with bounded client buffering."""
import asyncio
from contextlib import suppress

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from backend.app.security import COOKIE, actor_from_token
from backend.app.snapshots import snapshot
from backend.app.tables import Notification

router = APIRouter()


@router.websocket("/api/v1/events")
async def events(ws: WebSocket):
    settings = ws.app.state.settings
    if ws.headers.get("origin") not in settings.origins:
        await ws.close(code=4403)
        return
    token = ws.cookies.get(COOKIE)
    async with ws.app.state.database.sessions() as db:
        user, _ = await actor_from_token(db, token)
    if not user:
        await ws.close(code=4401)
        return
    try:
        cursor = int(ws.query_params.get("cursor", "0"))
        if not 0 <= cursor <= 2147483647:
            raise ValueError
    except ValueError:
        await ws.close(code=4400)
        return
    await ws.accept()
    queue: asyncio.Queue = asyncio.Queue(maxsize=32)

    async def produce():
        nonlocal cursor
        while True:
            async with ws.app.state.database.sessions() as db:
                current, _ = await actor_from_token(db, token)
                if current is None:
                    raise PermissionError("session_expired")
                rows = (await db.execute(select(Notification).where(
                    Notification.id > cursor
                ).order_by(Notification.id).limit(32))).scalars().all()
                for row in rows:
                    cursor = row.id
                    try:
                        view = await snapshot(db, current, row.incident_id)
                    except HTTPException as exc:
                        if exc.status_code == 404:
                            continue
                        raise
                    # Overflow disconnects only this viewer. The database retains its recovery cursor.
                    queue.put_nowait({"event_type": row.event_type, "cursor": cursor, "incident": view})
            await asyncio.sleep(0.5)

    async def consume():
        while True:
            try:
                item = await asyncio.wait_for(queue.get(), timeout=15)
            except TimeoutError:
                item = {"event_type": "heartbeat", "cursor": cursor}
            await asyncio.wait_for(ws.send_json(item), timeout=3)

    async def receive():
        while True:
            message = await ws.receive_text()
            if len(message) > 128:
                raise ValueError("message_too_large")

    tasks = [asyncio.create_task(fn()) for fn in (produce, consume, receive)]
    try:
        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            task.result()
    except (WebSocketDisconnect, TimeoutError, asyncio.QueueFull, PermissionError, ValueError):
        pass
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        with suppress(RuntimeError, WebSocketDisconnect):
            await ws.close(code=1013)
