"""Async SQLAlchemy engine and session factory.

Supports two databases selected by DATABASE_URL at startup:
  sqlite+aiosqlite:///./courses.db          — local dev, no setup needed
  postgresql+asyncpg://user:pass@host/db    — Aurora RDS Serverless v2 (production)

The SQLAlchemy async API is identical across both drivers 
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

_is_sqlite   = DATABASE_URL.startswith("sqlite")
_is_postgres = DATABASE_URL.startswith("postgresql")

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    # Validate connections before checkout — essential for Aurora Serverless v2
    # which can pause after inactivity and silently drop idle connections.
    pool_pre_ping=True,
    # Driver-specific connection arguments
    connect_args=(
        {"check_same_thread": False} if _is_sqlite   # SQLite: allow cross-thread reuse
        else {"ssl": "require"}      if _is_postgres  # Aurora: SSL required
        else {}
    ),
    # Connection pool sizing — PostgreSQL only.
    # SQLite uses NullPool / StaticPool internally and ignores these.
    **({
        "pool_size": 5,
        "max_overflow": 10,
    } if _is_postgres else {}),
)

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an async DB session per request."""
    async with AsyncSessionLocal() as session:
        yield session
