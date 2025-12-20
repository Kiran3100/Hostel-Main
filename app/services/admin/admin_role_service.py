"""
Admin Role Service

Business logic for role management including creation, assignment,
hierarchy, and role-based permission management.
"""

from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime
from sqlalchemy.orm import Session

from app.models.admin.admin_user import AdminRole
from app.repositories.admin.admin_user_repository import AdminUserRepository
from app.repositories.admin.admin_permissions_repository import AdminPermissionsRepository
from app.core.exceptions import (
    ValidationError,
    EntityNotFoundError,
    ConflictError,
    AuthorizationError
)


class AdminRoleService:
    """
    Role management service with:
    - Role CRUD operations
    - Role hierarchy management
    - Permission assignment to roles
    - Role-based access control
    - Role templates and presets
    """

    def __init__(self, db: Session):
        self.db = db
        self.admin_repo = AdminUserRepository(db)
        self.permission_repo = AdminPermissionsRepository(db)

    # ==================== ROLE MANAGEMENT ====================

    async def create_role(
        self,
        name: str,
        display_name: str,
        hierarchy_level: int,
        permissions: Dict[str, bool],
        description: Optional[str] = None,
        parent_role_id: Optional[UUID] = None,
        created_by_id: Optional[UUID] = None
    ) -> AdminRole:
        """
        Create new admin role.
        
        Args:
            name: Unique role identifier
            display_name: Human-readable name
            hierarchy_level: Role level (1-10)
            permissions: Role permissions
            description: Role description
            parent_role_id: Parent role for inheritance
            created_by_id: Creating admin ID
        """
        # Validate creating admin
        if created_by_id:
            creator = await self.admin_repo.find_by_id(created_by_id)
            if not creator or not creator.can_manage_admins:
                raise AuthorizationError(
                    "Insufficient permissions to create roles"
                )

        # Validate hierarchy level
        if not 1 <= hierarchy_level <= 10:
            raise ValidationError("Hierarchy level must be between 1 and 10")

        # Validate parent role if specified
        if parent_role_id:
            parent = await self.db.get(AdminRole, parent_role_id)
            if not parent:
                raise EntityNotFoundError(f"Parent role {parent_role_id} not found")
            
            # Parent must have higher or equal hierarchy level
            if parent.hierarchy_level < hierarchy_level:
                raise ValidationError(
                    f"Parent role level ({parent.hierarchy_level}) must be >= "
                    f"child level ({hierarchy_level})"
                )

        # Validate permissions
        validation = await self.permission_repo.validate_permission_set(permissions)
        if not validation['is_valid']:
            raise ValidationError(f"Invalid permissions: {validation['errors']}")

        # Create role
        role = AdminRole(
            name=name,
            display_name=display_name,
            description=description,
            hierarchy_level=hierarchy_level,
            parent_role_id=parent_role_id,
            permissions=validation['validated_permissions'],
            inherits_permissions=True,
            is_active=True,
            is_system_role=False
        )

        self.db.add(role)
        await self.db.flush()
        await self.db.commit()

        return role

    async def update_role(
        self,
        role_id: UUID,
        updates: Dict[str, Any],
        updated_by_id: Optional[UUID] = None
    ) -> AdminRole:
        """Update role details."""
        role = await self.db.get(AdminRole, role_id)
        if not role:
            raise EntityNotFoundError(f"Role {role_id} not found")

        # Cannot modify system roles
        if role.is_system_role:
            raise ValidationError("Cannot modify system roles")

        # Validate updating admin
        if updated_by_id:
            updater = await self.admin_repo.find_by_id(updated_by_id)
            if not updater or not updater.can_manage_admins:
                raise AuthorizationError("Insufficient permissions")

        # Validate updates
        if 'permissions' in updates:
            validation = await self.permission_repo.validate_permission_set(
                updates['permissions']
            )
            if not validation['is_valid']:
                raise ValidationError(f"Invalid permissions: {validation['errors']}")
            updates['permissions'] = validation['validated_permissions']

        if 'hierarchy_level' in updates:
            new_level = updates['hierarchy_level']
            if not 1 <= new_level <= 10:
                raise ValidationError("Hierarchy level must be between 1 and 10")
            
            # Validate against child roles
            await self._validate_hierarchy_level_change(role, new_level)

        # Apply updates
        for key, value in updates.items():
            if hasattr(role, key) and key not in ['id', 'created_at', 'is_system_role']:
                setattr(role, key, value)

        role.updated_at = datetime.utcnow()
        await self.db.commit()

        return role

    async def delete_role(
        self,
        role_id: UUID,
        deleted_by_id: Optional[UUID] = None
    ) -> bool:
        """Delete role (soft delete)."""
        role = await self.db.get(AdminRole, role_id)
        if not role:
            return False

        # Cannot delete system roles
        if role.is_system_role:
            raise ValidationError("Cannot delete system roles")

        # Check if role is in use
        # Would need to check admin_role_assignments
        # Simplified for now

        role.is_deleted = True
        role.deleted_at = datetime.utcnow()
        await self.db.commit()

        return True

    async def _validate_hierarchy_level_change(
        self,
        role: AdminRole,
        new_level: int
    ) -> None:
        """Validate hierarchy level change doesn't break child relationships."""
        # Check child roles
        if role.child_roles:
            min_child_level = min(child.hierarchy_level for child in role.child_roles)
            if new_level < min_child_level:
                raise ValidationError(
                    f"New level ({new_level}) must be >= "
                    f"minimum child level ({min_child_level})"
                )

    # ==================== ROLE QUERIES ====================

    async def get_role_by_id(self, role_id: UUID) -> Optional[AdminRole]:
        """Get role by ID."""
        return await self.db.get(AdminRole, role_id)

    async def get_role_by_name(self, name: str) -> Optional[AdminRole]:
        """Get role by name."""
        from sqlalchemy import select
        
        stmt = (
            select(AdminRole)
            .where(AdminRole.name == name)
            .where(AdminRole.is_deleted == False)
        )
        
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all_roles(
        self,
        active_only: bool = True,
        include_system: bool = True
    ) -> List[AdminRole]:
        """Get all roles with filters."""
        from sqlalchemy import select
        
        stmt = select(AdminRole).where(AdminRole.is_deleted == False)
        
        if active_only:
            stmt = stmt.where(AdminRole.is_active == True)
        
        if not include_system:
            stmt = stmt.where(AdminRole.is_system_role == False)
        
        stmt = stmt.order_by(AdminRole.hierarchy_level.desc(), AdminRole.name)
        
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def get_roles_by_level(
        self,
        min_level: Optional[int] = None,
        max_level: Optional[int] = None
    ) -> List[AdminRole]:
        """Get roles within hierarchy level range."""
        from sqlalchemy import select
        
        stmt = (
            select(AdminRole)
            .where(AdminRole.is_deleted == False)
            .where(AdminRole.is_active == True)
        )
        
        if min_level:
            stmt = stmt.where(AdminRole.hierarchy_level >= min_level)
        if max_level:
            stmt = stmt.where(AdminRole.hierarchy_level <= max_level)
        
        stmt = stmt.order_by(AdminRole.hierarchy_level.desc())
        
        result = await self.db.execute(stmt)
        return result.scalars().all()

    # ==================== ROLE HIERARCHY ====================

    async def get_role_hierarchy(
        self,
        role_id: UUID
    ) -> Dict[str, Any]:
        """Get complete role hierarchy."""
        role = await self.db.get(AdminRole, role_id)
        if not role:
            raise EntityNotFoundError(f"Role {role_id} not found")

        hierarchy = {
            'role': role,
            'parents': [],
            'children': []
        }

        # Get parent chain
        current = role
        while current.parent_role_id:
            parent = await self.db.get(AdminRole, current.parent_role_id)
            if not parent:
                break
            hierarchy['parents'].append(parent)
            current = parent

        # Get children
        hierarchy['children'] = await self._get_child_roles(role_id)

        return hierarchy

    async def _get_child_roles(
        self,
        role_id: UUID,
        depth: int = 0,
        max_depth: int = 10
    ) -> List[Dict[str, Any]]:
        """Recursively get child roles."""
        if depth >= max_depth:
            return []

        from sqlalchemy import select
        
        stmt = (
            select(AdminRole)
            .where(AdminRole.parent_role_id == role_id)
            .where(AdminRole.is_deleted == False)
        )
        
        result = await self.db.execute(stmt)
        children = result.scalars().all()

        child_data = []
        for child in children:
            child_info = {
                'role': child,
                'depth': depth + 1,
                'children': await self._get_child_roles(child.id, depth + 1, max_depth)
            }
            child_data.append(child_info)

        return child_data

    # ==================== PERMISSION MANAGEMENT ====================

    async def get_role_permissions(
        self,
        role_id: UUID,
        include_inherited: bool = True
    ) -> Dict[str, bool]:
        """Get effective permissions for role."""
        role = await self.db.get(AdminRole, role_id)
        if not role:
            raise EntityNotFoundError(f"Role {role_id} not found")

        permissions = role.permissions.copy()

        if include_inherited and role.inherits_permissions and role.parent_role_id:
            # Get parent permissions
            parent_perms = await self.get_role_permissions(
                role.parent_role_id,
                include_inherited=True
            )
            
            # Merge with parent (role's permissions override parent's)
            for key, value in parent_perms.items():
                if key not in permissions:
                    permissions[key] = value

        return permissions

    async def update_role_permissions(
        self,
        role_id: UUID,
        permissions: Dict[str, bool],
        updated_by_id: Optional[UUID] = None
    ) -> AdminRole:
        """Update role permissions."""
        return await self.update_role(
            role_id,
            {'permissions': permissions},
            updated_by_id
        )

    async def add_permission_to_role(
        self,
        role_id: UUID,
        permission_key: str,
        permission_value: bool = True
    ) -> AdminRole:
        """Add single permission to role."""
        role = await self.db.get(AdminRole, role_id)
        if not role:
            raise EntityNotFoundError(f"Role {role_id} not found")

        role.permissions[permission_key] = permission_value
        role.updated_at = datetime.utcnow()
        
        await self.db.commit()
        return role

    async def remove_permission_from_role(
        self,
        role_id: UUID,
        permission_key: str
    ) -> AdminRole:
        """Remove permission from role."""
        role = await self.db.get(AdminRole, role_id)
        if not role:
            raise EntityNotFoundError(f"Role {role_id} not found")

        if permission_key in role.permissions:
            del role.permissions[permission_key]
            role.updated_at = datetime.utcnow()
            await self.db.commit()

        return role

    # ==================== ROLE TEMPLATES ====================

    async def create_default_roles(self) -> List[AdminRole]:
        """Create default system roles."""
        default_roles = [
            {
                'name': 'super_admin',
                'display_name': 'Super Administrator',
                'hierarchy_level': 10,
                'permissions': self._get_super_admin_permissions(),
                'description': 'Full platform access',
                'is_system_role': True
            },
            {
                'name': 'hostel_manager',
                'display_name': 'Hostel Manager',
                'hierarchy_level': 7,
                'permissions': self._get_manager_permissions(),
                'description': 'Full hostel management access',
                'is_system_role': True
            },
            {
                'name': 'hostel_admin',
                'display_name': 'Hostel Administrator',
                'hierarchy_level': 5,
                'permissions': self._get_admin_permissions(),
                'description': 'Standard administrative access',
                'is_system_role': True
            },
            {
                'name': 'hostel_staff',
                'display_name': 'Hostel Staff',
                'hierarchy_level': 3,
                'permissions': self._get_staff_permissions(),
                'description': 'Limited operational access',
                'is_system_role': True
            }
        ]

        created_roles = []
        for role_data in default_roles:
            # Check if role already exists
            existing = await self.get_role_by_name(role_data['name'])
            if existing:
                continue

            role = AdminRole(**role_data)
            self.db.add(role)
            created_roles.append(role)

        await self.db.flush()
        await self.db.commit()

        return created_roles

    def _get_super_admin_permissions(self) -> Dict[str, bool]:
        """Get super admin permission set (all permissions)."""
        return {
            'can_manage_rooms': True,
            'can_manage_beds': True,
            'can_manage_students': True,
            'can_check_in_students': True,
            'can_check_out_students': True,
            'can_approve_bookings': True,
            'can_manage_waitlist': True,
            'can_manage_fees': True,
            'can_process_payments': True,
            'can_issue_refunds': True,
            'can_manage_supervisors': True,
            'can_configure_supervisor_permissions': True,
            'can_override_supervisor_actions': True,
            'can_view_financials': True,
            'can_export_financial_data': True,
            'can_manage_hostel_settings': True,
            'can_manage_hostel_profile': True,
            'can_toggle_public_visibility': True,
            'can_delete_records': True,
            'can_export_data': True,
            'can_import_data': True,
            'can_view_analytics': True,
            'can_manage_announcements': True,
            'can_manage_maintenance': True,
            'can_approve_maintenance_costs': True,
            'can_manage_complaints': True,
            'can_escalate_complaints': True,
            'can_manage_mess_menu': True,
            'can_manage_dietary_options': True,
            'can_manage_attendance': True,
            'can_configure_attendance_policies': True,
            'can_approve_leaves': True,
            'can_manage_leave_policies': True
        }

    def _get_manager_permissions(self) -> Dict[str, bool]:
        """Get hostel manager permission set."""
        perms = self._get_super_admin_permissions()
        # Managers can't delete records or toggle visibility
        perms['can_delete_records'] = False
        perms['can_toggle_public_visibility'] = False
        return perms

    def _get_admin_permissions(self) -> Dict[str, bool]:
        """Get standard admin permission set."""
        return {
            'can_manage_rooms': True,
            'can_manage_beds': True,
            'can_manage_students': True,
            'can_check_in_students': True,
            'can_check_out_students': True,
            'can_approve_bookings': True,
            'can_manage_waitlist': True,
            'can_manage_fees': True,
            'can_process_payments': True,
            'can_issue_refunds': False,
            'can_manage_supervisors': False,
            'can_view_financials': True,
            'can_export_financial_data': True,
            'can_view_analytics': True,
            'can_manage_announcements': True,
            'can_manage_maintenance': True,
            'can_manage_complaints': True,
            'can_manage_mess_menu': True,
            'can_manage_attendance': True,
            'can_approve_leaves': True
        }

    def _get_staff_permissions(self) -> Dict[str, bool]:
        """Get staff permission set."""
        return {
            'can_manage_rooms': False,
            'can_manage_beds': False,
            'can_manage_students': True,
            'can_check_in_students': True,
            'can_check_out_students': True,
            'can_approve_bookings': False,
            'can_manage_waitlist': True,
            'can_view_analytics': True,
            'can_manage_announcements': False,
            'can_manage_maintenance': True,
            'can_manage_complaints': True,
            'can_manage_attendance': True,
            'can_approve_leaves': False
        }

    # ==================== ANALYTICS ====================

    async def get_role_statistics(self) -> Dict[str, Any]:
        """Get role usage statistics."""
        from sqlalchemy import select, func
        
        # Total roles
        total_stmt = (
            select(func.count(AdminRole.id))
            .where(AdminRole.is_deleted == False)
        )
        total_roles = await self.db.scalar(total_stmt)

        # Active roles
        active_stmt = (
            select(func.count(AdminRole.id))
            .where(AdminRole.is_deleted == False)
            .where(AdminRole.is_active == True)
        )
        active_roles = await self.db.scalar(active_stmt)

        # System roles
        system_stmt = (
            select(func.count(AdminRole.id))
            .where(AdminRole.is_deleted == False)
            .where(AdminRole.is_system_role == True)
        )
        system_roles = await self.db.scalar(system_stmt)

        return {
            'total_roles': total_roles,
            'active_roles': active_roles,
            'system_roles': system_roles,
            'custom_roles': total_roles - system_roles
        }