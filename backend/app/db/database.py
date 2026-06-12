"""
Database engine, session factory, and initialization helpers.
Uses SQLAlchemy async engine backed by aiosqlite.

SQLite tuning (PRD §5.2.1):
  - WAL journal mode: improves concurrent read/write throughput
  - NORMAL synchronous: safe for NAS use (fdatasync on checkpoint)
  - foreign_keys ON: enforce referential integrity
  - cache_size -20000: ~20 MB page cache
  - BEGIN IMMEDIATE: prevents deferred-to-exclusive upgrade conflicts
"""
from collections.abc import AsyncGenerator
from pathlib import Path

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import get_settings
from app.models.base import Base

# Import all models so their tables are registered on Base.metadata
import app.models  # noqa: F401

settings = get_settings()

# Ensure the DB directory exists before SQLite tries to create the file
Path(settings.database_url.split("///")[-1]).parent.mkdir(parents=True, exist_ok=True)

engine = create_async_engine(
    settings.database_url,
    echo=False,          # Set True for SQL query logging during development
    future=True,
    connect_args={
        "check_same_thread": False,
        "timeout": 15.0,  # 15s busy-timeout before raising OperationalError
    },
)


@event.listens_for(engine.sync_engine, "connect")
def _configure_sqlite(dbapi_connection, _connection_record) -> None:
    """Apply SQLite PRAGMAs on every new connection."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute("PRAGMA synchronous=NORMAL;")
    cursor.execute("PRAGMA foreign_keys=ON;")
    cursor.execute("PRAGMA cache_size=-20000;")
    cursor.close()


@event.listens_for(engine.sync_engine, "begin")
def _begin_immediate(conn) -> None:
    """Use BEGIN IMMEDIATE to avoid deferred→exclusive upgrade deadlocks."""
    conn.exec_driver_sql("BEGIN IMMEDIATE")


AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def _run_migrations(conn) -> None:
    """Apply lightweight schema migrations for columns added after initial deploy."""
    # diaries.cover_photo_id — added to store explicit cover selection
    existing = await conn.execute(text("PRAGMA table_info(diaries)"))
    cols = {row[1] for row in existing.fetchall()}
    if "cover_photo_id" not in cols:
        await conn.execute(
            text("ALTER TABLE diaries ADD COLUMN cover_photo_id INTEGER REFERENCES photos(id)")
        )


async def init_db() -> None:
    """Create all tables on startup (idempotent), then apply column migrations."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _run_migrations(conn)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency — yields a per-request async DB session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
