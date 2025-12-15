# app/services/common/permissions.py
"""
Permission and authorization utilities.

Provides a flexible RBAC (Role-Based Access Control) system with support
for role-based and fine-grained permissions.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Mapping, Optional, Set, Union
from uuid import UUID

from app.schemas.common.enums import UserRole

from .errors import AuthorizationError


class PermissionDenied(AuthorizationError):
    """Raised when a user lacks required permissions."""
    
    def __init__(
        self,
        message: str,
        user_id: Optional[UUID] = None,
        role: Optional[UserRole] = None,
        required_permission: Optional[str] = None,
    ) -> None:
        super().__init__(message, required_permission=required_permission)
        self.user_id = user_id
        self.role = role


@dataclass(frozen=True)
class Principal:
    """
    Represents an authenticated user in the service layer.

    Attributes:
        user_id: Unique identifier for the user
        role: User's primary role
        permissions: Optional set of fine-grained permission strings
        metadata: Optional additional user context
    """
    user_id: UUID
    role: UserRole
    permissions: Optional[Set[str]] = None
    metadata: dict = field(default_factory=dict)

    def has_role(self, role: UserRole) -> bool:
        """Check if principal has a specific role."""
        return self.role == role

    def has_any_role(self, roles: Iterable[UserRole]) -> bool:
        """Check if principal has any of the specified roles."""
        return self.role in set(roles)

    def has_all_roles(self, roles: Iterable[UserRole]) -> bool:
        """Check if principal has all specified roles (for multi-role systems)."""
        # Current implementation supports single role
        # Extend if multi-role support is needed
        return self.role in set(roles)

    def get_permission_set(self) -> Set[str]:
        """Get all permissions for this principal."""
        return self.permissions or set()


def role_in(principal: Principal, allowed_roles: Iterable[UserRole]) -> bool:
    """
    Check if principal's role is in the allowed set.

    Args:
        principal: The authenticated user
        allowed_roles: Set of allowed roles

    Returns:
        True if principal's role is allowed

    Example:
        >>> if role_in(principal, [UserRole.ADMIN, UserRole.WARDEN]):
        ...     # Allow access
    """
    return principal.has_any_role(allowed_roles)


def require_role(
    principal: Principal,
    allowed_roles: Iterable[UserRole],
    *,
    error_message: Optional[str] = None,
) -> None:
    """
    Assert that principal has one of the allowed roles.

    Args:
        principal: The authenticated user
        allowed_roles: Set of allowed roles
        error_message: Custom error message

    Raises:
        PermissionDenied: If principal lacks required role

    Example:
        >>> require_role(principal, [UserRole.ADMIN])
    """
    if not role_in(principal, allowed_roles):
        roles_str = ", ".join(r.value for r in allowed_roles)
        msg = error_message or (
            f"User {principal.user_id} with role '{principal.role.value}' "
            f"does not have one of required roles: {roles_str}"
        )
        raise PermissionDenied(
            msg,
            user_id=principal.user_id,
            role=principal.role,
        )


def has_permission(
    principal: Principal,
    permission_key: str,
    *,
    matrix: Optional[Mapping[UserRole, Set[str]]] = None,
) -> bool:
    """
    Check if principal has a specific permission.

    Resolution order:
    1. Check explicit principal.permissions
    2. Fall back to role-based matrix

    Args:
        principal: The authenticated user
        permission_key: Permission to check (e.g., 'complaint.view')
        matrix: Optional role-to-permissions mapping

    Returns:
        True if principal has the permission

    Example:
        >>> PERMISSION_MATRIX = {
        ...     UserRole.ADMIN: {'complaint.view', 'complaint.edit'},
        ...     UserRole.STUDENT: {'complaint.view'},
        ... }
        >>> if has_permission(principal, 'complaint.edit', matrix=PERMISSION_MATRIX):
        ...     # Allow edit
    """
    # Check explicit permissions first
    if principal.permissions is not None:
        if permission_key in principal.permissions:
            return True

    # Fall back to role-based matrix
    if matrix is not None:
        allowed_for_role = matrix.get(principal.role, set())
        if permission_key in allowed_for_role:
            return True

    return False


def require_permission(
    principal: Principal,
    permission_key: str,
    *,
    matrix: Optional[Mapping[UserRole, Set[str]]] = None,
    error_message: Optional[str] = None,
) -> None:
    """
    Assert that principal has a specific permission.

    Args:
        principal: The authenticated user
        permission_key: Required permission
        matrix: Optional role-to-permissions mapping
        error_message: Custom error message

    Raises:
        PermissionDenied: If principal lacks the permission

    Example:
        >>> require_permission(
        ...     principal,
        ...     'complaint.delete',
        ...     matrix=PERMISSION_MATRIX,
        ... )
    """
    if not has_permission(principal, permission_key, matrix=matrix):
        msg = error_message or (
            f"User {principal.user_id} with role '{principal.role.value}' "
            f"lacks permission '{permission_key}'"
        )
        raise PermissionDenied(
            msg,
            user_id=principal.user_id,
            role=principal.role,
            required_permission=permission_key,
        )


def has_any_permission(
    principal: Principal,
    permission_keys: Iterable[str],
    *,
    matrix: Optional[Mapping[UserRole, Set[str]]] = None,
) -> bool:
    """
    Check if principal has any of the specified permissions.

    Args:
        principal: The authenticated user
        permission_keys: Set of permissions to check
        matrix: Optional role-to-permissions mapping

    Returns:
        True if principal has at least one permission

    Example:
        >>> if has_any_permission(principal, ['complaint.edit', 'complaint.delete']):
        ...     # User can edit OR delete
    """
    return any(
        has_permission(principal, perm, matrix=matrix)
        for perm in permission_keys
    )


def has_all_permissions(
    principal: Principal,
    permission_keys: Iterable[str],
    *,
    matrix: Optional[Mapping[UserRole, Set[str]]] = None,
) -> bool:
    """
    Check if principal has all specified permissions.

    Args:
        principal: The authenticated user
        permission_keys: Set of permissions to check
        matrix: Optional role-to-permissions mapping

    Returns:
        True if principal has all permissions

    Example:
        >>> if has_all_permissions(principal, ['user.view', 'user.edit']):
        ...     # User can both view AND edit
    """
    return all(
        has_permission(principal, perm, matrix=matrix)
        for perm in permission_keys
    )


def is_resource_owner(
    principal: Principal,
    resource_owner_id: UUID,
) -> bool:
    """
    Check if principal owns a resource.

    Args:
        principal: The authenticated user
        resource_owner_id: ID of the resource owner

    Returns:
        True if principal is the resource owner

    Example:
        >>> if is_resource_owner(principal, complaint.student_id):
        ...     # Allow access to own complaint
    """
    return principal.user_id == resource_owner_id


def require_resource_ownership(
    principal: Principal,
    resource_owner_id: UUID,
    *,
    resource_type: str = "resource",
    error_message: Optional[str] = None,
) -> None:
    """
    Assert that principal owns a resource.

    Args:
        principal: The authenticated user
        resource_owner_id: ID of the resource owner
        resource_type: Type of resource (for error message)
        error_message: Custom error message

    Raises:
        PermissionDenied: If principal is not the owner

    Example:
        >>> require_resource_ownership(
        ...     principal,
        ...     complaint.student_id,
        ...     resource_type="complaint",
        ... )
    """
    if not is_resource_owner(principal, resource_owner_id):
        msg = error_message or (
            f"User {principal.user_id} does not own {resource_type} "
            f"owned by {resource_owner_id}"
        )
        raise PermissionDenied(
            msg,
            user_id=principal.user_id,
            role=principal.role,
        )


class PermissionChecker:
    """
    Reusable permission checker with pre-configured matrix.

    Example:
        >>> MATRIX = {UserRole.ADMIN: {'complaint.view', 'complaint.edit'}}
        >>> checker = PermissionChecker(matrix=MATRIX)
        >>> if checker.check(principal, 'complaint.edit'):
        ...     # Allow edit
    """

    def __init__(self, matrix: Mapping[UserRole, Set[str]]) -> None:
        """
        Initialize permission checker.

        Args:
            matrix: Role-to-permissions mapping
        """
        self.matrix = matrix

    def check(self, principal: Principal, permission_key: str) -> bool:
        """Check if principal has permission."""
        return has_permission(principal, permission_key, matrix=self.matrix)

    def require(
        self,
        principal: Principal,
        permission_key: str,
        error_message: Optional[str] = None,
    ) -> None:
        """Require principal to have permission."""
        require_permission(
            principal,
            permission_key,
            matrix=self.matrix,
            error_message=error_message,
        )

    def check_any(self, principal: Principal, permission_keys: Iterable[str]) -> bool:
        """Check if principal has any of the permissions."""
        return has_any_permission(principal, permission_keys, matrix=self.matrix)

    def check_all(self, principal: Principal, permission_keys: Iterable[str]) -> bool:
        """Check if principal has all permissions."""
        return has_all_permissions(principal, permission_keys, matrix=self.matrix)