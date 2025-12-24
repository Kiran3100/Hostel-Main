"""
Admin role management service.

Handles role definition, role-based permissions, hierarchy management,
and role analytics.
"""

from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime

from sqlalchemy.orm import Session

from app.services.base import (
    BaseService,
    ServiceResult,
    ServiceError,
    ErrorCode,
    ErrorSeverity,
)
from app.repositories.admin import AdminPermissionsRepository
from app.models.admin import AdminRole, RolePermission
from app.models.base.enums import UserRole
from app.schemas.admin.admin_permissions import RolePermissionsUpdate


class AdminRoleService(BaseService[AdminRole, AdminPermissionsRepository]):
    """
    Service for admin role and role-based permission management.
    
    Responsibilities:
    - Role definition and management
    - Role-based permission assignment
    - Role hierarchy and inheritance
    - Role analytics and comparison
    """
    
    def __init__(
        self,
        repository: AdminPermissionsRepository,
        db_session: Session,
    ):
        """
        Initialize role service.
        
        Args:
            repository: Permission repository (handles roles)
            db_session: Database session
        """
        super().__init__(repository, db_session)
    
    # =========================================================================
    # Role Management
    # =========================================================================
    
    def create_role(
        self,
        role_name: str,
        description: Optional[str] = None,
        hierarchy_level: int = 0,
        permissions: Optional[Dict[str, Any]] = None,
        created_by: Optional[UUID] = None,
    ) -> ServiceResult[AdminRole]:
        """
        Create a new admin role.
        
        Args:
            role_name: Name of the role
            description: Role description
            hierarchy_level: Position in hierarchy (higher = more authority)
            permissions: Default permissions for this role
            created_by: ID of user creating the role
            
        Returns:
            ServiceResult containing created role or error
        """
        try:
            # Check uniqueness
            if self.repository.get_role_by_name(role_name):
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.ALREADY_EXISTS,
                        message=f"Role '{role_name}' already exists",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            # Create role
            role_data = {
                'role_name': role_name,
                'description': description,
                'hierarchy_level': hierarchy_level,
                'is_system_role': False,
                'created_by': created_by,
                'is_active': True,
            }
            
            role = self.repository.create_role(role_data)
            self.db.flush()
            
            # Create role permissions if provided
            if permissions:
                self._create_role_permissions(role.id, permissions)
                self.db.flush()
            
            self.db.commit()
            
            self._logger.info(
                f"Admin role created: {role_name}",
                extra={
                    "role_id": str(role.id),
                    "hierarchy_level": hierarchy_level,
                    "created_by": str(created_by) if created_by else None,
                },
            )
            
            return ServiceResult.success(
                role,
                message="Role created successfully",
            )
            
        except Exception as e:
            self.db.rollback()
            return self._handle_exception(e, "create role")
    
    def update_role(
        self,
        role_id: UUID,
        role_name: Optional[str] = None,
        description: Optional[str] = None,
        hierarchy_level: Optional[int] = None,
        is_active: Optional[bool] = None,
    ) -> ServiceResult[AdminRole]:
        """
        Update an existing role.
        
        Args:
            role_id: Role ID
            role_name: New role name
            description: New description
            hierarchy_level: New hierarchy level
            is_active: Active status
            
        Returns:
            ServiceResult containing updated role or error
        """
        try:
            role = self.repository.get_role_by_id(role_id)
            if not role:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message="Role not found",
                        severity=ErrorSeverity.ERROR,
                    )
                )
            
            # Protect system roles
            if role.is_system_role:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.BUSINESS_RULE_VIOLATION,
                        message="Cannot modify system roles",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            # Build update dictionary
            update_data = {}
            if role_name is not None:
                # Check name uniqueness
                existing = self.repository.get_role_by_name(role_name)
                if existing and existing.id != role_id:
                    return ServiceResult.failure(
                        ServiceError(
                            code=ErrorCode.ALREADY_EXISTS,
                            message=f"Role name '{role_name}' already in use",
                            severity=ErrorSeverity.WARNING,
                        )
                    )
                update_data['role_name'] = role_name
            
            if description is not None:
                update_data['description'] = description
            if hierarchy_level is not None:
                update_data['hierarchy_level'] = hierarchy_level
            if is_active is not None:
                update_data['is_active'] = is_active
            
            if not update_data:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="No update data provided",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            # Update role
            updated_role = self.repository.update_role(role_id, update_data)
            self.db.commit()
            
            self._logger.info(
                f"Role updated: {role.role_name}",
                extra={
                    "role_id": str(role_id),
                    "changes": list(update_data.keys()),
                },
            )
            
            return ServiceResult.success(
                updated_role,
                message="Role updated successfully",
            )
            
        except Exception as e:
            self.db.rollback()
            return self._handle_exception(e, "update role", role_id)
    
    def delete_role(
        self,
        role_id: UUID,
        force: bool = False,
    ) -> ServiceResult[bool]:
        """
        Delete a role.
        
        Args:
            role_id: Role ID
            force: Force deletion even if in use (will reassign admins)
            
        Returns:
            ServiceResult indicating success or error
        """
        try:
            role = self.repository.get_role_by_id(role_id)
            if not role:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message="Role not found",
                        severity=ErrorSeverity.ERROR,
                    )
                )
            
            # Protect system roles
            if role.is_system_role:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.BUSINESS_RULE_VIOLATION,
                        message="Cannot delete system roles",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            # Check if role is in use
            admin_count = self.repository.count_admins_with_role(role_id)
            if admin_count > 0 and not force:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.CONFLICT,
                        message=f"Cannot delete role: {admin_count} admins currently have this role",
                        details={"admin_count": admin_count},
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            # Delete role
            self.repository.delete_role(role_id)
            self.db.commit()
            
            self._logger.info(
                f"Role deleted: {role.role_name}",
                extra={
                    "role_id": str(role_id),
                    "affected_admins": admin_count,
                    "forced": force,
                },
            )
            
            return ServiceResult.success(
                True,
                message="Role deleted successfully",
            )
            
        except Exception as e:
            self.db.rollback()
            return self._handle_exception(e, "delete role", role_id)
    
    # =========================================================================
    # Role Permissions
    # =========================================================================
    
    def update_role_permissions(
        self,
        role_id: UUID,
        permissions: Dict[str, Any],
    ) -> ServiceResult[RolePermission]:
        """
        Update permissions for a role.
        
        Args:
            role_id: Role ID
            permissions: Permission configuration
            
        Returns:
            ServiceResult containing updated permissions
        """
        try:
            role = self.repository.get_role_by_id(role_id)
            if not role:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message="Role not found",
                        severity=ErrorSeverity.ERROR,
                    )
                )
            
            # Get existing role permissions
            existing_perms = self.repository.get_role_permissions(role_id)
            
            if existing_perms:
                # Update existing
                updated_perms = self.repository.update_role_permission(
                    existing_perms.id,
                    permissions,
                )
            else:
                # Create new
                perm_data = {'role_id': role_id, **permissions}
                updated_perms = self.repository.create_role_permission(perm_data)
            
            self.db.commit()
            
            self._logger.info(
                f"Role permissions updated for: {role.role_name}",
                extra={"role_id": str(role_id)},
            )
            
            return ServiceResult.success(
                updated_perms,
                message="Role permissions updated successfully",
            )
            
        except Exception as e:
            self.db.rollback()
            return self._handle_exception(e, "update role permissions", role_id)
    
    def get_role_permissions(
        self,
        role_id: UUID,
    ) -> ServiceResult[RolePermission]:
        """
        Get permissions for a role.
        
        Args:
            role_id: Role ID
            
        Returns:
            ServiceResult containing role permissions
        """
        try:
            permissions = self.repository.get_role_permissions(role_id)
            
            if not permissions:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message="Role permissions not found",
                        severity=ErrorSeverity.ERROR,
                    )
                )
            
            return ServiceResult.success(
                permissions,
                message="Role permissions retrieved successfully",
            )
            
        except Exception as e:
            return self._handle_exception(e, "get role permissions", role_id)
    
    # =========================================================================
    # Role Queries
    # =========================================================================
    
    def get_all_roles(
        self,
        include_inactive: bool = False,
        include_system: bool = True,
    ) -> ServiceResult[List[AdminRole]]:
        """
        Get all roles.
        
        Args:
            include_inactive: Include inactive roles
            include_system: Include system roles
            
        Returns:
            ServiceResult containing list of roles
        """
        try:
            roles = self.repository.get_all_roles(
                include_inactive=include_inactive,
                include_system=include_system,
            )
            
            return ServiceResult.success(
                roles,
                message="Roles retrieved successfully",
                metadata={
                    "count": len(roles),
                    "include_inactive": include_inactive,
                    "include_system": include_system,
                },
            )
            
        except Exception as e:
            return self._handle_exception(e, "get all roles")
    
    def get_role_by_name(
        self,
        role_name: str,
    ) -> ServiceResult[Optional[AdminRole]]:
        """
        Get role by name.
        
        Args:
            role_name: Role name
            
        Returns:
            ServiceResult containing role or None
        """
        try:
            role = self.repository.get_role_by_name(role_name)
            
            return ServiceResult.success(
                role,
                message="Role found" if role else "Role not found",
            )
            
        except Exception as e:
            return self._handle_exception(e, "get role by name")
    
    def get_role_hierarchy(self) -> ServiceResult[List[Dict[str, Any]]]:
        """
        Get role hierarchy ordered by level.
        
        Returns:
            ServiceResult containing hierarchical role structure
        """
        try:
            hierarchy = self.repository.get_role_hierarchy()
            
            return ServiceResult.success(
                hierarchy,
                message="Role hierarchy retrieved successfully",
                metadata={"levels": len(set(r.get('hierarchy_level', 0) for r in hierarchy))},
            )
            
        except Exception as e:
            return self._handle_exception(e, "get role hierarchy")
    
    # =========================================================================
    # Role Analytics
    # =========================================================================
    
    def get_role_statistics(
        self,
        role_id: UUID,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Get statistics for a specific role.
        
        Args:
            role_id: Role ID
            
        Returns:
            ServiceResult containing role statistics
        """
        try:
            role = self.repository.get_role_by_id(role_id)
            if not role:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message="Role not found",
                        severity=ErrorSeverity.ERROR,
                    )
                )
            
            admin_count = self.repository.count_admins_with_role(role_id)
            permissions = self.repository.get_role_permissions(role_id)
            
            stats = {
                "role_id": str(role_id),
                "role_name": role.role_name,
                "hierarchy_level": role.hierarchy_level,
                "admin_count": admin_count,
                "is_active": role.is_active,
                "is_system_role": role.is_system_role,
                "has_permissions": permissions is not None,
                "created_at": role.created_at.isoformat() if hasattr(role, 'created_at') else None,
            }
            
            return ServiceResult.success(
                stats,
                message="Role statistics retrieved successfully",
            )
            
        except Exception as e:
            return self._handle_exception(e, "get role statistics", role_id)
    
    def compare_roles(
        self,
        role_id_1: UUID,
        role_id_2: UUID,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Compare permissions between two roles.
        
        Args:
            role_id_1: First role ID
            role_id_2: Second role ID
            
        Returns:
            ServiceResult containing comparison data
        """
        try:
            role1 = self.repository.get_role_by_id(role_id_1)
            role2 = self.repository.get_role_by_id(role_id_2)
            
            if not role1 or not role2:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message="One or both roles not found",
                        severity=ErrorSeverity.ERROR,
                    )
                )
            
            perms1 = self.repository.get_role_permissions(role_id_1)
            perms2 = self.repository.get_role_permissions(role_id_2)
            
            # Build comparison
            comparison = {
                "role_1": {
                    "id": str(role1.id),
                    "name": role1.role_name,
                    "hierarchy_level": role1.hierarchy_level,
                },
                "role_2": {
                    "id": str(role2.id),
                    "name": role2.role_name,
                    "hierarchy_level": role2.hierarchy_level,
                },
                "hierarchy_difference": role1.hierarchy_level - role2.hierarchy_level,
            }
            
            # Compare permissions if both exist
            if perms1 and perms2:
                perm_comparison = self._compare_permission_objects(perms1, perms2)
                comparison.update(perm_comparison)
            else:
                comparison["permissions_comparison"] = {
                    "role_1_has_permissions": perms1 is not None,
                    "role_2_has_permissions": perms2 is not None,
                }
            
            return ServiceResult.success(
                comparison,
                message="Role comparison completed successfully",
            )
            
        except Exception as e:
            return self._handle_exception(e, "compare roles")
    
    # =========================================================================
    # Private Helper Methods
    # =========================================================================
    
    def _create_role_permissions(
        self,
        role_id: UUID,
        permissions: Dict[str, Any],
    ) -> RolePermission:
        """Create role permissions."""
        perm_data = {'role_id': role_id, **permissions}
        return self.repository.create_role_permission(perm_data)
    
    def _compare_permission_objects(
        self,
        perms1: RolePermission,
        perms2: RolePermission,
    ) -> Dict[str, Any]:
        """
        Compare two permission objects.
        
        Args:
            perms1: First permission object
            perms2: Second permission object
            
        Returns:
            Comparison dictionary
        """
        perms1_dict = perms1.to_dict() if hasattr(perms1, 'to_dict') else vars(perms1)
        perms2_dict = perms2.to_dict() if hasattr(perms2, 'to_dict') else vars(perms2)
        
        # Remove non-permission fields
        excluded_fields = {'id', 'role_id', 'created_at', 'updated_at'}
        perms1_dict = {k: v for k, v in perms1_dict.items() if k not in excluded_fields}
        perms2_dict = {k: v for k, v in perms2_dict.items() if k not in excluded_fields}
        
        all_keys = set(perms1_dict.keys()) | set(perms2_dict.keys())
        
        only_in_role_1 = []
        only_in_role_2 = []
        common_permissions = []
        different_values = []
        
        for key in all_keys:
            val1 = perms1_dict.get(key)
            val2 = perms2_dict.get(key)
            
            if val1 and not val2:
                only_in_role_1.append(key)
            elif val2 and not val1:
                only_in_role_2.append(key)
            elif val1 == val2:
                common_permissions.append(key)
            else:
                different_values.append({
                    "permission": key,
                    "role_1_value": val1,
                    "role_2_value": val2,
                })
        
        return {
            "permissions_only_in_role_1": only_in_role_1,
            "permissions_only_in_role_2": only_in_role_2,
            "common_permissions": common_permissions,
            "different_values": different_values,
            "permission_count": {
                "role_1": sum(1 for v in perms1_dict.values() if v),
                "role_2": sum(1 for v in perms2_dict.values() if v),
            },
        }