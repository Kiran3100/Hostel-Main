# app/core/database.py
from __future__ import annotations

"""
Database engine and session management.

This module defines:
- The global SQLAlchemy engine.
- A configured SessionLocal factory.
- Helpers for obtaining/using sessions with FastAPI and scripts.

Notes:
    - DATABASE_URL is read from the environment (ENV_DATABASE_URL) with
      a sensible default (`sqlite:///./app.db`).
    - In production, you should use Alembic migrations instead of `init_db()`.
"""

import os
from contextlib import contextmanager
from typing import Iterator, Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.constants import ENV_DATABASE_URL
from app.models.base import Base


# ------------------------------------------------------------------ #
# Engine & Session
# ------------------------------------------------------------------ #
DATABASE_URL = os.getenv(ENV_DATABASE_URL, "postgresql://postgres:Kiran$123@localhost:5432/HostelDb")

engine = create_engine(
    DATABASE_URL,
    future=True,
    echo=False,          # set True for SQL echo in development
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    class_=Session,
)


def get_session() -> Generator[Session, None, None]:
    """
    FastAPI-friendly dependency for a DB session.

    Example integration:

        def get_db():
            db = SessionLocal()
            try:
                yield db
            finally:
                db.close()

    Here we export get_session directly so application code can do:

        from app.core import get_session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def session_scope() -> Iterator[Session]:
    """
    Context manager for scripts / CLIs / background tasks.

    Usage:

        from app.core import session_scope

        with session_scope() as session:
            # use session
            ...

    This commits on success, and rolls back on any exception.
    """
    session: Session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db() -> None:
    """
    Simple helper to create all tables from SQLAlchemy models.

    In production, prefer Alembic migrations instead of calling this
    directly, to ensure schema changes are managed and versioned.
    """
    Base.metadata.create_all(bind=engine)