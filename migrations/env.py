"""Alembic runs against the same explicitly configured database as the application."""
import asyncio

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

from backend.app.config import get_settings
from backend.app.tables import Base


def migrate(connection):
    context.configure(connection=connection, target_metadata=Base.metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


async def run():
    engine = create_async_engine(get_settings().database_url)
    async with engine.connect() as connection:
        await connection.run_sync(migrate)
    await engine.dispose()


asyncio.run(run())
