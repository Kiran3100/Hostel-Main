# app/services/admin/permission_matrix_service.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Mapping, Protocol, Set

from app.schemas.admin import PermissionMatrix, RolePermissions
from app.schemas.common.enums import UserRole
from app.services.auth import RBACService


class PermissionMatrixStore(Protocol):
    """
    Abstract storage for role → permissions matrix.

    Implementations may use DB, Redis, or config files.
    """

    def load_matrix(self) -> Mapping[str, List[str]]: ...
    def save_matrix(self, matrix: Mapping[str, List[str]]) -> None: ...


@dataclass
class PermissionMatrixService:
    """
    Manage the global role-based permission matrix.

    - Load/save matrix via a store
    - Expose RolePermissions and PermissionMatrix schemas
    - Bridge into RBACService for permission checking (done elsewhere)
    """

    store: PermissionMatrixStore

    def _load_internal(self) -> Dict[UserRole, Set[str]]:
        raw = self.store.load_matrix()
        matrix: Dict[UserRole, Set[str]] = {}
        for role_str, perms in raw.items():
            try:
                role = UserRole(role_str)
            except ValueError:
                # Ignore unknown roles
                continue
            matrix[role] = set(perms or [])
        return matrix

    def _save_internal(self, matrix: Mapping[UserRole, Set[str]]) -> None:
        raw: Dict[str, List[str]] = {
            role.value: sorted(list(perms)) for role, perms in matrix.items()
        }
        self.store.save_matrix(raw)

    # ------------------------------------------------------------------ #
    # Read APIs
    # ------------------------------------------------------------------ #
    def get_permission_matrix(self) -> PermissionMatrix:
        """
        Return the current matrix as a PermissionMatrix schema.
        """
        internal = self._load_internal()
        rbac = RBACService(permission_matrix=internal)
        return rbac.get_permission_matrix()

    def get_role_permissions(self, role: UserRole) -> RolePermissions:
        """
        Get permissions for a single role.
        """
        internal = self._load_internal()
        rbac = RBACService(permission_matrix=internal)
        return rbac.get_role_permissions(role)

    # ------------------------------------------------------------------ #
    # Write APIs
    # ------------------------------------------------------------------ #
    def set_role_permissions(self, role: UserRole, permissions: List[str]) -> RolePermissions:
        """
        Overwrite the permission list for a given role.
        """
        internal = self._load_internal()
        internal[role] = set(permissions)
        self._save_internal(internal)

        rbac = RBACService(permission_matrix=internal)
        return rbac.get_role_permissions(role)

    def add_permissions(self, role: UserRole, permissions: List[str]) -> RolePermissions:
        """
        Add permissions (idempotent) for a role.
        """
        internal = self._load_internal()
        current = internal.get(role, set())
        current.update(permissions)
        internal[role] = current
        self._save_internal(internal)

        rbac = RBACService(permission_matrix=internal)
        return rbac.get_role_permissions(role)

    def remove_permissions(self, role: UserRole, permissions: List[str]) -> RolePermissions:
        """
        Remove permissions for a role (ignore missing).
        """
        internal = self._load_internal()
        current = internal.get(role, set())
        for p in permissions:
            current.discard(p)
        internal[role] = current
        self._save_internal(internal)

        rbac = RBACService(permission_matrix=internal)
        return rbac.get_role_permissions(role)