"""Isolated databases and enrolled identities for behavior and authorization tests."""
import os
import secrets
from datetime import timedelta
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from backend.app.config import Settings
from backend.app.database import Database
from backend.app.security import PASSWORDS, hash_token
from backend.app.tables import Base, Credential, Organization, User
from backend.main import create_app
from common.contracts import utcnow


@pytest.fixture
async def system(tmp_path):
    url = os.getenv("TEST_DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'central.db'}")
    settings = Settings(app_env="test", database_url=url)
    db = Database(settings)
    schema = None
    if url.startswith("postgresql"):
        schema = "test_" + uuid4().hex
        async with db.engine.begin() as connection:
            await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        await db.close()
        db.engine = create_async_engine(url, connect_args={"server_settings": {"search_path": schema}})
        from sqlalchemy.ext.asyncio import async_sessionmaker
        db.sessions = async_sessionmaker(db.engine, expire_on_commit=False)
    async with db.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    keys, orgs = [], []
    async with db.sessions() as session, session.begin():
        admin = User(email="admin@example.test", password_hash=PASSWORDS.hash("test-password"), role="admin")
        session.add(admin)
        for index in range(4):
            org = Organization(name=f"Organization {index}", provenance_group=f"independent-{index}")
            session.add(org)
            await session.flush()
            key = secrets.token_urlsafe(32)
            session.add(Credential(org_id=org.id, key_hash=hash_token(key),
                                   expires_at=utcnow() + timedelta(days=1)))
            session.add(User(email=f"org{index}@example.test", password_hash=admin.password_hash,
                             role="analyst", org_id=org.id))
            keys.append(key)
            orgs.append(org.id)
    app = create_app(settings, db)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver",
                                headers={"Origin": "http://localhost:5173"}) as client:
        yield {"settings": settings, "db": db, "client": client, "keys": keys, "orgs": orgs, "app": app}
    await db.close()
    if schema:
        cleanup = create_async_engine(url)
        async with cleanup.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        await cleanup.dispose()


async def login(client, email="admin@example.test"):
    response = await client.post("/api/v1/auth/login", json={"email": email, "password": "test-password"})
    assert response.status_code == 200, response.text
    client.headers["X-CSRF-Token"] = response.json()["csrf"]
    return response.json()
