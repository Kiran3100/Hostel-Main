# app/services/auth/rbac_service.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Set

from app.schemas.admin import PermissionMatrix, RolePermissions
from app.schemas.common.enums import UserRole
from app.services.common.permissions import Principal, has_permission


@dataclass
class RBACService:
    """
    Simple RBAC helper service based on a role -> permissions matrix.

    You can load the matrix from configuration, DB, or hard-code it.
    """

    permission_matrix: Dict[UserRole, Set[str]]

    def get_role_permissions(self, role: UserRole) -> RolePermissions:
        perms = sorted(self.permission_matrix.get(role, set()))
        return RolePermissions(
            role=role,
            permissions=perms,
            description=f"Permissions for role {role.value}",
        )

    def get_permission_matrix(self) -> PermissionMatrix:
        mapping: Dict[UserRole, List[str]] = {
            role: sorted(perms) for role, perms in self.permission_matrix.items()
        }
        return PermissionMatrix(permissions=mapping)

    def check_permission(self, principal: Principal, permission_key: str) -> bool:
        return has_permission(principal, permission_key, matrix=self.permission_matrix)