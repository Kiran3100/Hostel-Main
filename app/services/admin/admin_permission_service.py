"""
Admin Permission Service

Business logic for permission management including validation,
inheritance, conflict resolution, and template application.
"""

from typing import List, Optional, Dict, Any, Set
from uuid import UUID
from datetime import datetime
from sqlalchemy.orm import Session

from app.models.admin.admin_permissions import (
    AdminPermission,
    PermissionGroup,
    PermissionTemplate
)
from app.repositories.admin.admin_permissions_repository import AdminPermissionsRepository
from app.repositories.admin.admin_user_repository import AdminUserRepository
from app.repositories.admin.admin_hostel_assignment_repository import AdminHostelAssignmentRepository
from app.core.exceptions import (
    ValidationError,
    EntityNotFoundError,
    AuthorizationError,
    ConflictError
)


class AdminPermissionService:
    """
    Permission management service with:
    - Effective permission calculation
    - Permission validation and conflict resolution
    - Template-based assignment
    - Permission inheritance
    - Usage tracking and optimization
    """

    def __init__(self, db: Session):
        self.db = db
        self.permission_repo = AdminPermissionsRepository(db)
        self.admin_repo = AdminUserRepository(db)
        self.assignment_repo = AdminHostelAssignmentRepository(db)

    # ==================== PERMISSION MANAGEMENT ====================

    async def grant_permissions(
        self,
        admin_id: UUID,
        hostel_id: Optional[UUID],
        permissions: Dict[str, Any],
        granted_by_id: UUID,
        notes: Optional[str] = None
    ) -> AdminPermission:
        """
        Grant permissions to admin for specific hostel or globally.
        
        Args:
            admin_id: Admin to grant permissions to
            hostel_id: Hostel context (None for global)
            permissions: Permission configuration
            granted_by_id: Admin granting permissions
            notes: Optional notes
            
        Returns:
            Created permission set
        """
        # Validate granting admin has authority
        await self._validate_grant_authority(granted_by_id, admin_id, hostel_id)

        # Validate permission configuration
        validation = await self.permission_repo.validate_permission_set(permissions)
        if not validation['is_valid']:
            raise ValidationError(f"Invalid permissions: {validation['errors']}")

        # Check for conflicts
        if validation['warnings']:
            # Log warnings but proceed
            pass

        # If hostel-specific, verify assignment exists
        if hostel_id:
            assignment = await self.assignment_repo.find_assignment(admin_id, hostel_id)
            if not assignment:
                raise ValidationError(
                    f"Admin {admin_id} not assigned to hostel {hostel_id}"
                )

        # Create permission set
        permission_set = await self.permission_repo.create_permission_set(
            admin_id=admin_id,
            hostel_id=hostel_id,
            permissions=validation['validated_permissions'],
            granted_by_id=granted_by_id,
            notes=notes
        )

        await self.db.commit()
        return permission_set

    async def update_permissions(
        self,
        permission_id: UUID,
        updates: Dict[str, Any],
        updated_by_id: UUID,
        reason: Optional[str] = None
    ) -> AdminPermission:
        """Update existing permission set."""
        permission_set = await self.permission_repo.find_by_id(permission_id)
        if not permission_set:
            raise EntityNotFoundError(f"Permission set {permission_id} not found")

        # Validate authority
        await self._validate_grant_authority(
            updated_by_id,
            permission_set.admin_id,
            permission_set.hostel_id
        )

        # Validate updates
        validation = await self.permission_repo.validate_permission_set(updates)
        if not validation['is_valid']:
            raise ValidationError(f"Invalid permissions: {validation['errors']}")

        # Store old values for audit
        old_values = self.permission_repo._extract_permission_dict(permission_set)

        # Apply updates
        for key, value in validation['validated_permissions'].items():
            if hasattr(permission_set, key):
                setattr(permission_set, key, value)

        permission_set.updated_at = datetime.utcnow()

        # Create audit record
        await self.permission_repo._create_audit_record(
            permission_id=permission_id,
            admin_id=permission_set.admin_id,
            action='updated',
            old_values=old_values,
            new_values=validation['validated_permissions'],
            changed_by_id=updated_by_id,
            reason=reason
        )

        await self.db.commit()
        return permission_set

    async def revoke_permissions(
        self,
        permission_id: UUID,
        revoked_by_id: UUID,
        reason: str
    ) -> bool:
        """Revoke permission set (soft delete)."""
        permission_set = await self.permission_repo.find_by_id(permission_id)
        if not permission_set:
            return False

        # Validate authority
        await self._validate_grant_authority(
            revoked_by_id,
            permission_set.admin_id,
            permission_set.hostel_id
        )

        # Soft delete
        permission_set.is_deleted = True
        permission_set.deleted_at = datetime.utcnow()

        # Create audit record
        await self.permission_repo._create_audit_record(
            permission_id=permission_id,
            admin_id=permission_set.admin_id,
            action='revoked',
            changed_by_id=revoked_by_id,
            reason=reason
        )

        await self.db.commit()
        return True

    async def _validate_grant_authority(
        self,
        granting_admin_id: UUID,
        target_admin_id: UUID,
        hostel_id: Optional[UUID]
    ) -> None:
        """Validate admin has authority to grant/modify permissions."""
        granter = await self.admin_repo.find_by_id(granting_admin_id)
        if not granter:
            raise EntityNotFoundError(f"Admin {granting_admin_id} not found")

        # Super admin can grant any permissions
        if granter.is_super_admin:
            return

        # Must have can_manage_admins permission
        if not granter.can_manage_admins:
            raise AuthorizationError(
                "Admin does not have permission to manage other admins"
            )

        # If hostel-specific, must have access to that hostel
        if hostel_id:
            assignment = await self.assignment_repo.find_assignment(
                granting_admin_id,
                hostel_id
            )
            if not assignment or not assignment.is_active:
                raise AuthorizationError(
                    f"Admin does not have access to hostel {hostel_id}"
                )

        # Cannot grant permissions to someone with higher admin level
        target = await self.admin_repo.find_by_id(target_admin_id)
        if target and target.admin_level > granter.admin_level:
            raise AuthorizationError(
                "Cannot grant permissions to admin with higher level"
            )

    # ==================== PERMISSION QUERIES ====================

    async def get_effective_permissions(
        self,
        admin_id: UUID,
        hostel_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """
        Calculate effective permissions with full inheritance chain.
        
        Returns complete permission set with metadata about sources.
        """
        return await self.permission_repo.get_effective_permissions(
            admin_id,
            hostel_id
        )

    async def check_permission(
        self,
        admin_id: UUID,
        permission_key: str,
        hostel_id: Optional[UUID] = None
    ) -> bool:
        """Check if admin has specific permission."""
        effective_perms = await self.get_effective_permissions(admin_id, hostel_id)
        return effective_perms['effective_permissions'].get(permission_key, False)

    async def check_multiple_permissions(
        self,
        admin_id: UUID,
        permission_keys: List[str],
        hostel_id: Optional[UUID] = None,
        require_all: bool = True
    ) -> bool:
        """
        Check multiple permissions at once.
        
        Args:
            admin_id: Admin to check
            permission_keys: List of permission keys
            hostel_id: Optional hostel context
            require_all: If True, all permissions must be granted
            
        Returns:
            True if permission check passes
        """
        effective_perms = await self.get_effective_permissions(admin_id, hostel_id)
        perms = effective_perms['effective_permissions']

        if require_all:
            return all(perms.get(key, False) for key in permission_keys)
        else:
            return any(perms.get(key, False) for key in permission_keys)

    async def get_admin_permissions(
        self,
        admin_id: UUID,
        include_inherited: bool = True
    ) -> List[AdminPermission]:
        """Get all permission sets for admin."""
        return await self.permission_repo.get_all_permissions_for_admin(admin_id)

    async def compare_permissions(
        self,
        admin_id_1: UUID,
        admin_id_2: UUID,
        hostel_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """Compare permissions between two admins."""
        perms1 = await self.get_effective_permissions(admin_id_1, hostel_id)
        perms2 = await self.get_effective_permissions(admin_id_2, hostel_id)

        p1 = set(k for k, v in perms1['effective_permissions'].items() if v)
        p2 = set(k for k, v in perms2['effective_permissions'].items() if v)

        return {
            'admin_1_id': admin_id_1,
            'admin_2_id': admin_id_2,
            'hostel_id': hostel_id,
            'common_permissions': list(p1 & p2),
            'admin_1_only': list(p1 - p2),
            'admin_2_only': list(p2 - p1),
            'admin_1_count': len(p1),
            'admin_2_count': len(p2),
            'similarity_percentage': (len(p1 & p2) / max(len(p1 | p2), 1)) * 100
        }

    # ==================== CONFLICT RESOLUTION ====================

    async def find_and_resolve_conflicts(
        self,
        admin_id: UUID,
        auto_resolve: bool = False,
        resolved_by_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """Find and optionally resolve permission conflicts."""
        conflicts = await self.permission_repo.find_permission_conflicts(admin_id)

        if not conflicts:
            return {
                'has_conflicts': False,
                'conflicts': [],
                'resolved': []
            }

        resolved = []

        if auto_resolve and resolved_by_id:
            for conflict_info in conflicts:
                resolution = await self._auto_resolve_conflict(
                    conflict_info,
                    resolved_by_id
                )
                resolved.append(resolution)

        return {
            'has_conflicts': len(conflicts) > 0,
            'conflicts': conflicts,
            'resolved': resolved,
            'auto_resolve_enabled': auto_resolve
        }

    async def _auto_resolve_conflict(
        self,
        conflict_info: Dict[str, Any],
        resolved_by_id: UUID
    ) -> Dict[str, Any]:
        """Automatically resolve permission conflict."""
        permission_id = conflict_info['permission_id']
        conflicts = conflict_info['conflicts']

        # Get permission set
        perm_set = await self.permission_repo.find_by_id(permission_id)
        if not perm_set:
            return {'success': False, 'reason': 'Permission set not found'}

        # Resolution strategy: Enable dependent permissions
        updates = {}
        
        for conflict_msg in conflicts:
            if 'requires' in conflict_msg:
                # Parse and enable required permission
                # Example: "can_manage_fees requires can_view_financials"
                parts = conflict_msg.split(' requires ')
                if len(parts) == 2:
                    required_perm = parts[1].strip("'")
                    updates[required_perm] = True

        if updates:
            await self.update_permissions(
                permission_id,
                updates,
                resolved_by_id,
                reason=f"Auto-resolved conflicts: {', '.join(conflicts)}"
            )

        return {
            'success': True,
            'permission_id': permission_id,
            'updates_applied': updates,
            'conflicts_resolved': conflicts
        }

    # ==================== TEMPLATE MANAGEMENT ====================

    async def create_template(
        self,
        name: str,
        display_name: str,
        category: str,
        permissions: Dict[str, bool],
        description: Optional[str] = None,
        created_by_id: Optional[UUID] = None
    ) -> PermissionTemplate:
        """Create permission template for reuse."""
        return await self.permission_repo.create_template(
            name=name,
            display_name=display_name,
            category=category,
            permissions=permissions,
            description=description,
            created_by_id=created_by_id
        )

    async def apply_template(
        self,
        template_id: UUID,
        admin_id: UUID,
        hostel_id: Optional[UUID] = None,
        applied_by_id: Optional[UUID] = None
    ) -> AdminPermission:
        """Apply permission template to admin."""
        # Validate authority
        if applied_by_id:
            await self._validate_grant_authority(applied_by_id, admin_id, hostel_id)

        permission_set = await self.permission_repo.apply_template(
            template_id=template_id,
            admin_id=admin_id,
            hostel_id=hostel_id,
            applied_by_id=applied_by_id
        )

        await self.db.commit()
        return permission_set

    async def get_templates(
        self,
        category: Optional[str] = None,
        active_only: bool = True
    ) -> List[PermissionTemplate]:
        """Get permission templates."""
        if category:
            return await self.permission_repo.get_templates_by_category(category)
        else:
            # Would need to add this to repository
            return []

    async def suggest_template(
        self,
        admin_id: UUID,
        hostel_id: Optional[UUID] = None
    ) -> Optional[PermissionTemplate]:
        """Suggest best matching template for admin's permissions."""
        # Get current permissions
        current_perms = await self.get_effective_permissions(admin_id, hostel_id)
        current_set = set(
            k for k, v in current_perms['effective_permissions'].items() if v
        )

        # Get all templates
        # This would need repository support
        # For now, simplified
        return None

    # ==================== BULK OPERATIONS ====================

    async def bulk_grant_permissions(
        self,
        admin_ids: List[UUID],
        permissions: Dict[str, Any],
        hostel_id: Optional[UUID],
        granted_by_id: UUID
    ) -> Dict[str, Any]:
        """Grant same permissions to multiple admins."""
        results = {
            'success': [],
            'failed': []
        }

        for admin_id in admin_ids:
            try:
                perm_set = await self.grant_permissions(
                    admin_id=admin_id,
                    hostel_id=hostel_id,
                    permissions=permissions,
                    granted_by_id=granted_by_id
                )
                results['success'].append({
                    'admin_id': admin_id,
                    'permission_id': perm_set.id
                })
            except Exception as e:
                results['failed'].append({
                    'admin_id': admin_id,
                    'error': str(e)
                })

        return results

    async def copy_permissions(
        self,
        from_admin_id: UUID,
        to_admin_id: UUID,
        hostel_id: Optional[UUID],
        copied_by_id: UUID
    ) -> AdminPermission:
        """Copy permissions from one admin to another."""
        # Get source permissions
        source_perms = await self.get_effective_permissions(from_admin_id, hostel_id)

        # Grant to target
        return await self.grant_permissions(
            admin_id=to_admin_id,
            hostel_id=hostel_id,
            permissions=source_perms['effective_permissions'],
            granted_by_id=copied_by_id,
            notes=f"Copied from admin {from_admin_id}"
        )

    # ==================== ANALYTICS ====================

    async def get_permission_usage_stats(
        self,
        admin_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """Get permission usage statistics."""
        if admin_id:
            # Stats for specific admin
            perms = await self.get_admin_permissions(admin_id)
            
            return {
                'admin_id': admin_id,
                'total_permission_sets': len(perms),
                'global_permissions': len([p for p in perms if not p.hostel_id]),
                'hostel_specific': len([p for p in perms if p.hostel_id])
            }
        else:
            # Platform-wide stats
            return await self.permission_repo.get_permission_statistics()

    async def get_permission_audit_trail(
        self,
        admin_id: UUID,
        hostel_id: Optional[UUID] = None,
        limit: int = 50
    ) -> List:
        """Get permission change history."""
        return await self.permission_repo.get_permission_history(
            admin_id=admin_id,
            hostel_id=hostel_id,
            limit=limit
        )

    async def suggest_optimizations(
        self,
        admin_id: UUID
    ) -> Dict[str, Any]:
        """Suggest permission optimizations."""
        return await self.permission_repo.suggest_role_optimization(admin_id)

    # ==================== VALIDATION ====================

    async def validate_permission_change(
        self,
        admin_id: UUID,
        permission_key: str,
        new_value: bool,
        hostel_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """Validate permission change before applying."""
        # Get current permissions
        current = await self.get_effective_permissions(admin_id, hostel_id)
        current_value = current['effective_permissions'].get(permission_key, False)

        if current_value == new_value:
            return {
                'is_valid': True,
                'is_change': False,
                'message': 'No change in permission value'
            }

        # Check for dependency violations
        test_perms = current['effective_permissions'].copy()
        test_perms[permission_key] = new_value

        validation = await self.permission_repo.validate_permission_set(test_perms)

        return {
            'is_valid': validation['is_valid'],
            'is_change': True,
            'errors': validation.get('errors', []),
            'warnings': validation.get('warnings', []),
            'current_value': current_value,
            'new_value': new_value
        }