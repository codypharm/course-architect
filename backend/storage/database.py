"""Async SQLAlchemy engine and session factory.

Phase 1: SQLite via aiosqlite (DATABASE_URL defaults to a local file).
Phase 2: swap DATABASE_URL to postgresql+asyncpg://... pointing at Aurora RDS.
No other code changes needed — SQLAlchemy async API is identical across drivers.
"""
import os
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    "sqlite+aiosqlite:///./courses.db",
)

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    # SQLite-specific: allow the same connection to be used across threads
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an async DB session per request."""
    async with AsyncSessionLocal() as session:
        yield session
