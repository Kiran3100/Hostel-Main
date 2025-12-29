"""
Admin Permissions Repository

Manages granular permission control with role-based access,
inheritance, validation, and optimization.
"""

from typing import List, Optional, Dict, Any, Set
from uuid import UUID
from datetime import datetime, date
from sqlalchemy import select, and_, or_, func, desc
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.exc import IntegrityError

from app.models.admin.admin_permissions import (
    AdminPermission,
    PermissionGroup,
    RolePermission,
    PermissionAudit,
    PermissionTemplate
)
from app.models.admin.admin_user import AdminUser, AdminRole
from app.repositories.base.base_repository import BaseRepository
from app.core.exceptions import (
    EntityNotFoundError,
    ValidationError,
    DuplicateError,
)


class AdminPermissionsRepository(BaseRepository[AdminPermission]):
    """
    Comprehensive permission management with:
    - Granular permission control per hostel
    - Role-based inheritance
    - Permission conflict detection and resolution
    - Usage tracking and optimization
    - Template-based permission assignment
    """

    def __init__(self, db: Session):
        super().__init__(AdminPermission, db)

    # ==================== PERMISSION CRUD ====================

    async def create_permission_set(
        self,
        admin_id: UUID,
        hostel_id: Optional[UUID],
        permissions: Dict[str, Any],
        granted_by_id: Optional[UUID] = None,
        notes: Optional[str] = None
    ) -> AdminPermission:
        """
        Create permission set for admin.
        
        Args:
            admin_id: Admin user ID
            hostel_id: Hostel ID (None for global permissions)
            permissions: Permission configuration
            granted_by_id: Who granted these permissions
            notes: Additional notes
            
        Returns:
            Created AdminPermission instance
        """
        # Check for existing permission set
        existing = await self.find_by_admin_and_hostel(admin_id, hostel_id)
        if existing:
            raise DuplicateError(
                f"Permission set already exists for admin {admin_id} "
                f"and hostel {hostel_id or 'global'}"
            )

        # Validate permission keys
        valid_permissions = self._validate_permission_keys(permissions)

        permission_set = AdminPermission(
            admin_id=admin_id,
            hostel_id=hostel_id,
            permission_level=permissions.get('permission_level', 'FULL_ACCESS'),
            granted_by_id=granted_by_id,
            granted_at=datetime.utcnow(),
            notes=notes,
            **valid_permissions
        )

        self.db.add(permission_set)

        try:
            await self.db.flush()

            # Create audit record
            await self._create_audit_record(
                permission_id=permission_set.id,
                admin_id=admin_id,
                action='created',
                new_values=valid_permissions,
                changed_by_id=granted_by_id
            )

            return permission_set

        except IntegrityError as e:
            await self.db.rollback()
            raise ValidationError(f"Failed to create permissions: {str(e)}")

    async def find_by_admin_and_hostel(
        self,
        admin_id: UUID,
        hostel_id: Optional[UUID]
    ) -> Optional[AdminPermission]:
        """Find permission set for admin and specific hostel."""
        stmt = (
            select(AdminPermission)
            .where(AdminPermission.admin_id == admin_id)
            .where(AdminPermission.is_deleted == False)
        )

        if hostel_id:
            stmt = stmt.where(AdminPermission.hostel_id == hostel_id)
        else:
            stmt = stmt.where(AdminPermission.hostel_id.is_(None))

        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all_permissions_for_admin(
        self,
        admin_id: UUID
    ) -> List[AdminPermission]:
        """Get all permission sets for admin (global + hostel-specific)."""
        stmt = (
            select(AdminPermission)
            .where(AdminPermission.admin_id == admin_id)
            .where(AdminPermission.is_deleted == False)
            .order_by(AdminPermission.hostel_id.nullsfirst())
        )

        result = await self.db.execute(stmt)
        return result.scalars().all()

    # ==================== EFFECTIVE PERMISSIONS ====================

    async def get_effective_permissions(
        self,
        admin_id: UUID,
        hostel_id: Optional[UUID] = None
    ) -> Dict[str, bool]:
        """
        Calculate effective permissions with proper inheritance.
        
        Priority:
        1. Hostel-specific permissions (if hostel_id provided)
        2. Global admin permissions
        3. Role-based permissions
        4. Default permissions
        """
        # Get admin
        admin = await self.db.get(AdminUser, admin_id)
        if not admin:
            raise EntityNotFoundError(f"Admin {admin_id} not found")

        # Initialize with default permissions
        effective = self._get_default_permissions()

        # Super admin gets all permissions
        if admin.is_super_admin:
            return self._get_super_admin_permissions()

        # Apply global permissions
        global_perms = await self.find_by_admin_and_hostel(admin_id, None)
        if global_perms:
            effective.update(self._extract_permission_dict(global_perms))

        # Apply hostel-specific permissions
        if hostel_id:
            hostel_perms = await self.find_by_admin_and_hostel(admin_id, hostel_id)
            if hostel_perms:
                effective.update(self._extract_permission_dict(hostel_perms))

        # Apply admin-level overrides
        if admin.permissions_override:
            effective.update(admin.permissions_override)

        return effective

    def _extract_permission_dict(self, permission: AdminPermission) -> Dict[str, bool]:
        """Extract all permission flags from AdminPermission object."""
        return {
            'can_manage_rooms': permission.can_manage_rooms,
            'can_manage_beds': permission.can_manage_beds,
            'can_manage_students': permission.can_manage_students,
            'can_check_in_students': permission.can_check_in_students,
            'can_check_out_students': permission.can_check_out_students,
            'can_approve_bookings': permission.can_approve_bookings,
            'can_manage_waitlist': permission.can_manage_waitlist,
            'can_manage_fees': permission.can_manage_fees,
            'can_process_payments': permission.can_process_payments,
            'can_issue_refunds': permission.can_issue_refunds,
            'can_manage_supervisors': permission.can_manage_supervisors,
            'can_configure_supervisor_permissions': permission.can_configure_supervisor_permissions,
            'can_override_supervisor_actions': permission.can_override_supervisor_actions,
            'can_view_financials': permission.can_view_financials,
            'can_export_financial_data': permission.can_export_financial_data,
            'can_manage_hostel_settings': permission.can_manage_hostel_settings,
            'can_manage_hostel_profile': permission.can_manage_hostel_profile,
            'can_toggle_public_visibility': permission.can_toggle_public_visibility,
            'can_delete_records': permission.can_delete_records,
            'can_export_data': permission.can_export_data,
            'can_import_data': permission.can_import_data,
            'can_view_analytics': permission.can_view_analytics,
            'can_manage_announcements': permission.can_manage_announcements,
            'can_manage_maintenance': permission.can_manage_maintenance,
            'can_approve_maintenance_costs': permission.can_approve_maintenance_costs,
            'can_manage_complaints': permission.can_manage_complaints,
            'can_escalate_complaints': permission.can_escalate_complaints,
            'can_manage_mess_menu': permission.can_manage_mess_menu,
            'can_manage_dietary_options': permission.can_manage_dietary_options,
            'can_manage_attendance': permission.can_manage_attendance,
            'can_configure_attendance_policies': permission.can_configure_attendance_policies,
            'can_approve_leaves': permission.can_approve_leaves,
            'can_manage_leave_policies': permission.can_manage_leave_policies,
        }

    def _get_default_permissions(self) -> Dict[str, bool]:
        """Get default permission set (all False)."""
        return {
            'can_manage_rooms': False,
            'can_manage_beds': False,
            'can_manage_students': False,
            'can_check_in_students': False,
            'can_check_out_students': False,
            'can_approve_bookings': False,
            'can_manage_waitlist': False,
            'can_manage_fees': False,
            'can_process_payments': False,
            'can_issue_refunds': False,
            'can_manage_supervisors': False,
            'can_configure_supervisor_permissions': False,
            'can_override_supervisor_actions': False,
            'can_view_financials': False,
            'can_export_financial_data': False,
            'can_manage_hostel_settings': False,
            'can_manage_hostel_profile': False,
            'can_toggle_public_visibility': False,
            'can_delete_records': False,
            'can_export_data': False,
            'can_import_data': False,
            'can_view_analytics': False,
            'can_manage_announcements': False,
            'can_manage_maintenance': False,
            'can_approve_maintenance_costs': False,
            'can_manage_complaints': False,
            'can_escalate_complaints': False,
            'can_manage_mess_menu': False,
            'can_manage_dietary_options': False,
            'can_manage_attendance': False,
            'can_configure_attendance_policies': False,
            'can_approve_leaves': False,
            'can_manage_leave_policies': False,
        }

    def _get_super_admin_permissions(self) -> Dict[str, bool]:
        """Get super admin permission set (all True)."""
        return {key: True for key in self._get_default_permissions().keys()}

    # ==================== PERMISSION VALIDATION ====================

    async def validate_permission_set(
        self,
        permissions: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Validate permission configuration.
        
        Returns:
            Dict with validation results and warnings
        """
        validation_result = {
            'is_valid': True,
            'errors': [],
            'warnings': [],
            'validated_permissions': {}
        }

        # Check for unknown permission keys
        valid_keys = set(self._get_default_permissions().keys())
        provided_keys = set(permissions.keys())
        unknown_keys = provided_keys - valid_keys

        if unknown_keys:
            validation_result['warnings'].append(
                f"Unknown permission keys: {', '.join(unknown_keys)}"
            )

        # Validate permission values
        for key, value in permissions.items():
            if key in valid_keys:
                if not isinstance(value, bool):
                    validation_result['errors'].append(
                        f"Permission '{key}' must be boolean, got {type(value)}"
                    )
                    validation_result['is_valid'] = False
                else:
                    validation_result['validated_permissions'][key] = value

        # Check for conflicting permissions
        conflicts = self._check_permission_conflicts(
            validation_result['validated_permissions']
        )
        if conflicts:
            validation_result['warnings'].extend(conflicts)

        return validation_result

    def _check_permission_conflicts(self, permissions: Dict[str, bool]) -> List[str]:
        """Check for conflicting permission combinations."""
        conflicts = []

        # Example: Can't manage fees without viewing financials
        if permissions.get('can_manage_fees') and not permissions.get('can_view_financials'):
            conflicts.append(
                "Permission conflict: 'can_manage_fees' requires 'can_view_financials'"
            )

        # Can't issue refunds without processing payments
        if permissions.get('can_issue_refunds') and not permissions.get('can_process_payments'):
            conflicts.append(
                "Permission conflict: 'can_issue_refunds' requires 'can_process_payments'"
            )

        # Can't configure supervisor permissions without managing supervisors
        if (permissions.get('can_configure_supervisor_permissions') and 
            not permissions.get('can_manage_supervisors')):
            conflicts.append(
                "Permission conflict: 'can_configure_supervisor_permissions' "
                "requires 'can_manage_supervisors'"
            )

        return conflicts

    def _validate_permission_keys(self, permissions: Dict[str, Any]) -> Dict[str, bool]:
        """Validate and extract only valid permission keys."""
        valid_keys = set(self._get_default_permissions().keys())
        return {
            k: bool(v) for k, v in permissions.items()
            if k in valid_keys and isinstance(v, bool)
        }

    async def find_permission_conflicts(self, admin_id: UUID) -> List[Dict[str, Any]]:
        """Find all permission conflicts for an admin across hostels."""
        all_perms = await self.get_all_permissions_for_admin(admin_id)
        conflicts = []

        for perm_set in all_perms:
            perm_dict = self._extract_permission_dict(perm_set)
            conflict_list = self._check_permission_conflicts(perm_dict)

            if conflict_list:
                conflicts.append({
                    'permission_id': perm_set.id,
                    'hostel_id': perm_set.hostel_id,
                    'conflicts': conflict_list
                })

        return conflicts

    # ==================== PERMISSION TEMPLATES ====================

    async def create_template(
        self,
        name: str,
        display_name: str,
        category: str,
        permissions: Dict[str, bool],
        description: Optional[str] = None,
        created_by_id: Optional[UUID] = None
    ) -> PermissionTemplate:
        """Create reusable permission template."""
        # Validate permissions
        validation = await self.validate_permission_set(permissions)
        if not validation['is_valid']:
            raise ValidationError(f"Invalid permissions: {validation['errors']}")

        template = PermissionTemplate(
            name=name,
            display_name=display_name,
            description=description,
            category=category,
            permissions=validation['validated_permissions'],
            created_by_id=created_by_id,
            is_active=True
        )

        self.db.add(template)
        await self.db.flush()
        return template

    async def apply_template(
        self,
        template_id: UUID,
        admin_id: UUID,
        hostel_id: Optional[UUID] = None,
        applied_by_id: Optional[UUID] = None
    ) -> AdminPermission:
        """Apply permission template to admin."""
        template = await self.db.get(PermissionTemplate, template_id)
        if not template or not template.is_active:
            raise EntityNotFoundError(f"Template {template_id} not found or inactive")

        # Create permission set from template
        permission_set = await self.create_permission_set(
            admin_id=admin_id,
            hostel_id=hostel_id,
            permissions=template.permissions,
            granted_by_id=applied_by_id,
            notes=f"Applied from template: {template.name}"
        )

        # Update template usage stats
        template.usage_count += 1
        template.last_used_at = datetime.utcnow()

        await self.db.flush()
        return permission_set

    async def get_templates_by_category(self, category: str) -> List[PermissionTemplate]:
        """Get all active templates in category."""
        stmt = (
            select(PermissionTemplate)
            .where(PermissionTemplate.category == category)
            .where(PermissionTemplate.is_active == True)
            .where(PermissionTemplate.is_deleted == False)
            .order_by(PermissionTemplate.display_order, PermissionTemplate.name)
        )

        result = await self.db.execute(stmt)
        return result.scalars().all()

    # ==================== PERMISSION AUDITING ====================

    async def _create_audit_record(
        self,
        permission_id: UUID,
        admin_id: UUID,
        action: str,
        old_values: Optional[Dict] = None,
        new_values: Optional[Dict] = None,
        changed_by_id: Optional[UUID] = None,
        reason: Optional[str] = None
    ) -> PermissionAudit:
        """Create permission change audit record."""
        # Determine changed fields
        changed_fields = []
        if old_values and new_values:
            changed_fields = [
                key for key in new_values.keys()
                if old_values.get(key) != new_values.get(key)
            ]

        audit = PermissionAudit(
            permission_id=permission_id,
            admin_id=admin_id,
            action=action,
            changed_at=datetime.utcnow(),
            changed_by_id=changed_by_id,
            old_values=old_values,
            new_values=new_values,
            changed_fields=changed_fields,
            reason=reason
        )

        self.db.add(audit)
        await self.db.flush()
        return audit

    async def get_permission_history(
        self,
        admin_id: UUID,
        hostel_id: Optional[UUID] = None,
        limit: int = 50
    ) -> List[PermissionAudit]:
        """Get permission change history for admin."""
        stmt = (
            select(PermissionAudit)
            .where(PermissionAudit.admin_id == admin_id)
            .order_by(desc(PermissionAudit.changed_at))
            .limit(limit)
        )

        if hostel_id:
            # Join with AdminPermission to filter by hostel
            stmt = stmt.join(
                AdminPermission,
                PermissionAudit.permission_id == AdminPermission.id
            ).where(AdminPermission.hostel_id == hostel_id)

        result = await self.db.execute(stmt)
        return result.scalars().all()

    # ==================== PERMISSION ANALYTICS ====================

    async def track_permission_usage(
        self,
        admin_id: UUID,
        permission_key: str,
        hostel_id: Optional[UUID] = None
    ) -> None:
        """Track permission usage for analytics."""
        # This would typically update a usage counter or log to analytics system
        # For now, we'll just note the pattern for future implementation
        pass

    async def get_permission_statistics(self) -> Dict[str, Any]:
        """Get overall permission statistics."""
        # Total permission sets
        total_stmt = select(func.count(AdminPermission.id)).where(
            AdminPermission.is_deleted == False
        )
        total_sets = await self.db.scalar(total_stmt)

        # Global vs hostel-specific
        global_stmt = select(func.count(AdminPermission.id)).where(
            and_(
                AdminPermission.is_deleted == False,
                AdminPermission.hostel_id.is_(None)
            )
        )
        global_sets = await self.db.scalar(global_stmt)

        # Most common permissions
        # This would require analyzing the permission JSON fields
        # Simplified for now

        return {
            'total_permission_sets': total_sets,
            'global_permissions': global_sets,
            'hostel_specific_permissions': total_sets - global_sets,
            'avg_permissions_per_admin': total_sets / max(1, global_sets)
        }

    async def suggest_role_optimization(
        self,
        admin_id: UUID
    ) -> Dict[str, Any]:
        """Suggest role optimizations based on permission patterns."""
        all_perms = await self.get_all_permissions_for_admin(admin_id)

        if not all_perms:
            return {'suggestions': [], 'current_complexity': 0}

        # Analyze permission patterns
        permission_counts = {}
        for perm_set in all_perms:
            perm_dict = self._extract_permission_dict(perm_set)
            for key, value in perm_dict.items():
                if value:
                    permission_counts[key] = permission_counts.get(key, 0) + 1

        # Find most common permissions
        common_perms = sorted(
            permission_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]

        suggestions = []

        # Suggest consolidation if too many permission sets
        if len(all_perms) > 5:
            suggestions.append({
                'type': 'consolidation',
                'message': f'Consider consolidating {len(all_perms)} permission sets',
                'priority': 'medium'
            })

        # Suggest template if pattern matches existing
        # This would query against templates
        # Simplified for now

        return {
            'current_complexity': len(all_perms),
            'common_permissions': common_perms,
            'suggestions': suggestions
        }