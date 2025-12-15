# app/core/__init__.py
from __future__ import annotations

"""
Core infrastructure exports.

This module re-exports frequently used core utilities to
simplify imports across the project, allowing patterns like:

    from app.core import (
        DEFAULT_PAGE,
        engine,
        get_session,
        AppError,
        security,
    )
"""

from .constants import (
    DEFAULT_PAGE,
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    API_PREFIX,
    API_V1_PREFIX,
)
from .database import (
    engine,
    SessionLocal,
    get_session,
    session_scope,
    init_db,
)
from .exceptions import (
    AppError,
    ServiceError,
    NotFoundError,
    ValidationError,
    ConflictError,
)
from . import security
from . import permissions
from . import pagination
from . import middleware

__all__ = [
    # constants
    "DEFAULT_PAGE",
    "DEFAULT_PAGE_SIZE",
    "MAX_PAGE_SIZE",
    "API_PREFIX",
    "API_V1_PREFIX",
    # db
    "engine",
    "SessionLocal",
    "get_session",
    "session_scope",
    "init_db",
    # exceptions
    "AppError",
    "ServiceError",
    "NotFoundError",
    "ValidationError",
    "ConflictError",
    # submodules
    "security",
    "permissions",
    "pagination",
    "middleware",
]