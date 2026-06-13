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

    # persons.is_locked — added to protect named persons from accidental deletion
    existing_p = await conn.execute(text("PRAGMA table_info(persons)"))
    person_cols = {row[1] for row in existing_p.fetchall()}
    if "is_locked" not in person_cols:
        await conn.execute(
            text("ALTER TABLE persons ADD COLUMN is_locked BOOLEAN NOT NULL DEFAULT 0")
        )

    # photos.clip_embedding — CLIP-ViT-B/32 semantic vector (512 float32, raw bytes)
    existing_ph = await conn.execute(text("PRAGMA table_info(photos)"))
    photo_cols = {row[1] for row in existing_ph.fetchall()}
    if "clip_embedding" not in photo_cols:
        await conn.execute(text("ALTER TABLE photos ADD COLUMN clip_embedding BLOB"))
    if "stack_id" not in photo_cols:
        await conn.execute(text("ALTER TABLE photos ADD COLUMN stack_id TEXT"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_photos_stack_id ON photos(stack_id)"))
    if "is_stack_cover" not in photo_cols:
        await conn.execute(text("ALTER TABLE photos ADD COLUMN is_stack_cover BOOLEAN NOT NULL DEFAULT 0"))
    if "vision_analyzed_at" not in photo_cols:
        await conn.execute(text("ALTER TABLE photos ADD COLUMN vision_analyzed_at DATETIME"))
    if "face_analyzed_at" not in photo_cols:
        await conn.execute(text("ALTER TABLE photos ADD COLUMN face_analyzed_at DATETIME"))
    if "media_type" not in photo_cols:
        await conn.execute(text("ALTER TABLE photos ADD COLUMN media_type TEXT NOT NULL DEFAULT 'photo'"))
    if "duration" not in photo_cols:
        await conn.execute(text("ALTER TABLE photos ADD COLUMN duration REAL"))

    # Face embedding dimension migration: face_recognition was 128-dim, insightface is 512-dim.
    # Clear incompatible legacy face data so the next /persons/run starts clean.
    try:
        sample = await conn.execute(text("SELECT embedding FROM face_crops LIMIT 1"))
        row = sample.fetchone()
        if row and row[0]:
            dim = len(row[0].split(","))
            if dim != 512:
                import logging as _log
                _log.getLogger(__name__).info(
                    "Clearing legacy %d-dim face embeddings (expected 512 from insightface)", dim
                )
                await conn.execute(text("DELETE FROM face_crops"))
                await conn.execute(text("DELETE FROM persons"))
    except Exception:
        pass  # Tables may not exist yet on fresh install


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
