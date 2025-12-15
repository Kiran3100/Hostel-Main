# app/core/exceptions.py
from __future__ import annotations

"""
Core application-level exceptions.

These are thin wrappers / aliases around the service-layer exceptions
defined in `app.services.common.errors`, allowing the rest of the app
to import exception types from a single, central place:

    from app.core import AppError, NotFoundError, ValidationError
"""

from app.services.common import errors as _errors


# Base application error
AppError = _errors.ServiceError
ServiceError = _errors.ServiceError

# Common specializations
NotFoundError = _errors.NotFoundError
ValidationError = _errors.ValidationError
ConflictError = _errors.ConflictError

__all__ = [
    "AppError",
    "ServiceError",
    "NotFoundError",
    "ValidationError",
    "ConflictError",
]