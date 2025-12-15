# app/services/common/__init__.py
"""
Shared service-layer infrastructure.

This module provides core utilities for building service layer components:

- **UnitOfWork**: Transaction boundary & repository factory with savepoint support
- **security**: Password hashing (bcrypt) and JWT token management
- **permissions**: Role-based access control (RBAC) and fine-grained permissions
- **mapping**: Type-safe model-to-schema conversions with batch operations
- **pagination**: Paginated response builders with validation
- **errors**: Service-layer exception hierarchy

Example usage:
    >>> from app.services.common import UnitOfWork, security, permissions
    >>> 
    >>> # Transaction management
    >>> with UnitOfWork(session_factory) as uow:
    ...     user_repo = uow.get_repo(UserRepository)
    ...     user = user_repo.create(...)
    ...     uow.commit()
    >>> 
    >>> # Security
    >>> hashed = security.hash_password("password")
    >>> token = security.create_access_token(
    ...     subject=user.id,
    ...     email=user.email,
    ...     role=user.role,
    ...     jwt_settings=settings,
    ... )
    >>> 
    >>> # Permissions
    >>> principal = permissions.Principal(user_id=user.id, role=user.role)
    >>> permissions.require_permission(principal, "complaint.view")
"""
from __future__ import annotations

from . import errors, mapping, pagination, permissions, security
from .unit_of_work import NestedUnitOfWork, UnitOfWork

__all__ = [
    # Modules
    "errors",
    "mapping",
    "pagination",
    "permissions",
    "security",
    # Classes
    "UnitOfWork",
    "NestedUnitOfWork",
]
