"""Async database ownership shared by the API and independent workers."""
from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.app.config import Settings


class Database:
    def __init__(self, settings: Settings):
        single_connection = settings.app_env == "demo" and settings.database_url.startswith("sqlite")
        pool_options = {"pool_size": 1, "max_overflow": 0} if single_connection else {}
        self.engine = create_async_engine(settings.database_url, pool_pre_ping=True, **pool_options)
        if single_connection:
            @event.listens_for(self.engine.sync_engine, "connect")
            def sqlite_foreign_keys(connection, _record):
                cursor = connection.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)

    async def close(self) -> None:
        await self.engine.dispose()
