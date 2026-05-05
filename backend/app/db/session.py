"""Async engine and session factory."""

from __future__ import annotations

import logging
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


engine: AsyncEngine | None = None
async_session_maker: async_sessionmaker[AsyncSession] | None = None


def _build_engine() -> AsyncEngine | None:
    settings = get_settings()
    if not settings.enable_persistence:
        return None
    url = settings.database_url
    if not url:
        return None
    return create_async_engine(
        url,
        echo=False,
        pool_pre_ping=True,
    )


async def init_db() -> bool:
    """Create tables if persistence is enabled and DB is reachable."""
    global engine, async_session_maker
    engine = _build_engine()
    if engine is None:
        logger.warning("Persistence disabled or no DATABASE_URL")
        return False
    async_session_maker = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    try:
        from app.db import models  # noqa: F401 — register tables

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables ready (create_all)")
        return True
    except Exception as e:
        logger.error(
            "Database init failed: %s — Postgres is not reachable on DATABASE_URL. "
            "Fix: start DB (e.g. `docker compose up -d postgres redis` from repo root) "
            "or set ENABLE_PERSISTENCE=false in .env to run without chat persistence.",
            e,
        )
        await engine.dispose()
        engine = None
        async_session_maker = None
        return False


async def close_db() -> None:
    global engine, async_session_maker
    if engine is not None:
        await engine.dispose()
        engine = None
        async_session_maker = None


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: yields a session for one request."""
    if async_session_maker is None:
        raise RuntimeError("Database not initialized")
    async with async_session_maker() as session:
        yield session
