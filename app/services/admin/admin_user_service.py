"""
Admin User Service

Business logic for admin user management including creation,
updates, hierarchy management, and lifecycle operations.
"""

from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime, date
from sqlalchemy.orm import Session

from app.models.admin.admin_user import AdminUser, AdminProfile
from app.repositories.admin.admin_user_repository import AdminUserRepository
from app.repositories.admin.admin_permissions_repository import AdminPermissionsRepository
from app.repositories.admin.admin_hostel_assignment_repository import AdminHostelAssignmentRepository
from app.core.exceptions import (
    ValidationError,
    EntityNotFoundError,
    AuthorizationError,
    BusinessRuleViolationError
)
from app.core.security import hash_password, generate_employee_id


class AdminUserService:
    """
    Admin user management service with:
    - User lifecycle management
    - Hierarchy validation
    - Permission enforcement
    - Profile management
    - Analytics and reporting
    """

    def __init__(self, db: Session):
        self.db = db
        self.admin_repo = AdminUserRepository(db)
        self.permission_repo = AdminPermissionsRepository(db)
        self.assignment_repo = AdminHostelAssignmentRepository(db)

    # ==================== USER CREATION ====================

    async def create_admin(
        self,
        user_id: UUID,
        admin_data: Dict[str, Any],
        created_by_id: Optional[UUID] = None,
        auto_assign_hostels: Optional[List[UUID]] = None
    ) -> AdminUser:
        """
        Create new admin user with validation.
        
        Args:
            user_id: Base user account ID
            admin_data: Admin attributes
            created_by_id: Creating admin ID
            auto_assign_hostels: Optional hostels to auto-assign
            
        Returns:
            Created AdminUser
        """
        # Validate creating admin has permission
        if created_by_id:
            await self._validate_admin_creation_permission(created_by_id)

        # Validate admin level hierarchy
        if admin_data.get('reports_to_id'):
            await self._validate_hierarchy(
                admin_data['reports_to_id'],
                admin_data.get('admin_level', 1)
            )

        # Generate employee ID if not provided
        if not admin_data.get('employee_id'):
            admin_data['employee_id'] = await self._generate_employee_id()

        # Create admin
        admin = await self.admin_repo.create_admin(
            user_id=user_id,
            admin_data=admin_data,
            created_by_id=created_by_id,
            audit_context={
                'action': 'create_admin',
                'timestamp': datetime.utcnow(),
                'ip_address': admin_data.get('ip_address')
            }
        )

        # Create default permissions
        await self._initialize_default_permissions(admin.id, admin_data.get('admin_level', 1))

        # Auto-assign hostels if specified
        if auto_assign_hostels and created_by_id:
            await self.assignment_repo.assign_admin_to_hostels(
                admin_id=admin.id,
                hostel_ids=auto_assign_hostels,
                assigned_by_id=created_by_id
            )

        await self.db.commit()
        return admin

    async def _validate_admin_creation_permission(self, admin_id: UUID) -> None:
        """Validate admin has permission to create other admins."""
        admin = await self.admin_repo.find_by_id(admin_id)
        if not admin:
            raise EntityNotFoundError(f"Admin {admin_id} not found")

        if not admin.can_manage_admins and not admin.is_super_admin:
            raise AuthorizationError("Admin does not have permission to create other admins")

    async def _validate_hierarchy(
        self,
        reports_to_id: UUID,
        new_admin_level: int
    ) -> None:
        """Validate reporting hierarchy rules."""
        manager = await self.admin_repo.find_by_id(reports_to_id)
        if not manager:
            raise ValidationError(f"Manager admin {reports_to_id} not found")

        # Manager must have higher or equal level
        if manager.admin_level < new_admin_level:
            raise BusinessRuleViolationError(
                f"Manager level ({manager.admin_level}) must be >= "
                f"subordinate level ({new_admin_level})"
            )

    async def _generate_employee_id(self) -> str:
        """Generate unique employee ID."""
        # Get count of admins to generate sequential ID
        base_id = f"ADM{datetime.now().year}"
        counter = 1
        
        while True:
            employee_id = f"{base_id}{counter:04d}"
            existing = await self.admin_repo.find_by_employee_id(employee_id)
            if not existing:
                return employee_id
            counter += 1

    async def _initialize_default_permissions(
        self,
        admin_id: UUID,
        admin_level: int
    ) -> None:
        """Initialize default permissions based on admin level."""
        # Get default permissions for level
        default_perms = self._get_default_permissions_for_level(admin_level)
        
        await self.permission_repo.create_permission_set(
            admin_id=admin_id,
            hostel_id=None,  # Global permissions
            permissions=default_perms,
            notes="Initial default permissions"
        )

    def _get_default_permissions_for_level(self, level: int) -> Dict[str, bool]:
        """Get default permission set based on admin level."""
        if level <= 3:
            return {
                'permission_level': 'LIMITED_ACCESS',
                'can_view_analytics': True,
                'can_manage_students': False,
                'can_approve_bookings': False,
                'can_manage_fees': False
            }
        elif level <= 6:
            return {
                'permission_level': 'STANDARD_ACCESS',
                'can_view_analytics': True,
                'can_manage_students': True,
                'can_approve_bookings': True,
                'can_manage_fees': False,
                'can_view_financials': True
            }
        else:
            return {
                'permission_level': 'FULL_ACCESS',
                'can_view_analytics': True,
                'can_manage_students': True,
                'can_approve_bookings': True,
                'can_manage_fees': True,
                'can_view_financials': True,
                'can_export_data': True
            }

    # ==================== USER RETRIEVAL ====================

    async def get_admin_by_id(
        self,
        admin_id: UUID,
        include_profile: bool = True,
        include_assignments: bool = False
    ) -> Optional[AdminUser]:
        """Get admin by ID with optional related data."""
        admin = await self.admin_repo.find_by_id(admin_id)
        
        if admin and include_assignments:
            admin.hostel_assignments = await self.assignment_repo.get_admin_assignments(admin_id)
        
        return admin

    async def get_admin_by_email(self, email: str) -> Optional[AdminUser]:
        """Get admin by email address."""
        return await self.admin_repo.find_by_email(email)

    async def get_admin_by_employee_id(self, employee_id: str) -> Optional[AdminUser]:
        """Get admin by employee ID."""
        return await self.admin_repo.find_by_employee_id(employee_id)

    async def search_admins(
        self,
        filters: Optional[Dict[str, Any]] = None,
        page: int = 1,
        per_page: int = 20
    ) -> Dict[str, Any]:
        """
        Search admins with filters and pagination.
        
        Supported filters:
        - department
        - admin_level
        - is_active
        - is_super_admin
        - reports_to_id
        """
        # Implementation would use repository search methods
        # with dynamic filter building
        pass

    # ==================== USER UPDATES ====================

    async def update_admin(
        self,
        admin_id: UUID,
        updates: Dict[str, Any],
        updated_by_id: Optional[UUID] = None
    ) -> AdminUser:
        """Update admin user details."""
        admin = await self.admin_repo.find_by_id(admin_id)
        if not admin:
            raise EntityNotFoundError(f"Admin {admin_id} not found")

        # Validate updates
        await self._validate_admin_updates(admin, updates, updated_by_id)

        # Apply updates
        for key, value in updates.items():
            if hasattr(admin, key) and key not in ['id', 'user_id', 'created_at']:
                setattr(admin, key, value)

        admin.updated_at = datetime.utcnow()
        await self.db.commit()
        
        return admin

    async def _validate_admin_updates(
        self,
        admin: AdminUser,
        updates: Dict[str, Any],
        updated_by_id: Optional[UUID]
    ) -> None:
        """Validate admin update operations."""
        # Check if updating own record
        is_self_update = updated_by_id == admin.id

        # Validate hierarchy changes
        if 'reports_to_id' in updates and updates['reports_to_id'] != admin.reports_to_id:
            await self._validate_hierarchy_change(
                admin.id,
                updates['reports_to_id'],
                admin.admin_level
            )

        # Validate level changes
        if 'admin_level' in updates and updates['admin_level'] != admin.admin_level:
            if is_self_update:
                raise AuthorizationError("Cannot change own admin level")
            
            await self._validate_level_change(
                admin,
                updates['admin_level'],
                updated_by_id
            )

        # Validate permission changes
        if 'is_super_admin' in updates and updates['is_super_admin'] != admin.is_super_admin:
            if is_self_update:
                raise AuthorizationError("Cannot change own super admin status")
            
            # Only super admins can create other super admins
            if updated_by_id:
                updater = await self.admin_repo.find_by_id(updated_by_id)
                if not updater or not updater.is_super_admin:
                    raise AuthorizationError("Only super admins can grant super admin status")

    async def _validate_hierarchy_change(
        self,
        admin_id: UUID,
        new_reports_to_id: Optional[UUID],
        admin_level: int
    ) -> None:
        """Validate hierarchy change doesn't create circular reporting."""
        if not new_reports_to_id:
            return

        # Check for circular reporting
        current_manager_id = new_reports_to_id
        visited = {admin_id}

        while current_manager_id:
            if current_manager_id in visited:
                raise BusinessRuleViolationError("Circular reporting structure detected")
            
            visited.add(current_manager_id)
            manager = await self.admin_repo.find_by_id(current_manager_id)
            
            if not manager:
                break
            
            current_manager_id = manager.reports_to_id

        # Validate level hierarchy
        await self._validate_hierarchy(new_reports_to_id, admin_level)

    async def _validate_level_change(
        self,
        admin: AdminUser,
        new_level: int,
        updated_by_id: Optional[UUID]
    ) -> None:
        """Validate admin level change."""
        if not 1 <= new_level <= 10:
            raise ValidationError("Admin level must be between 1 and 10")

        # Check if admin has subordinates
        hierarchy = await self.admin_repo.get_admin_hierarchy(admin.id)
        if hierarchy['subordinates']:
            # Ensure new level is still >= all subordinates
            max_subordinate_level = max(
                sub['admin'].admin_level 
                for sub in hierarchy['subordinates']
            )
            if new_level < max_subordinate_level:
                raise BusinessRuleViolationError(
                    f"New level ({new_level}) must be >= highest subordinate level "
                    f"({max_subordinate_level})"
                )

    # ==================== PROFILE MANAGEMENT ====================

    async def update_admin_profile(
        self,
        admin_id: UUID,
        profile_data: Dict[str, Any]
    ) -> AdminProfile:
        """Update admin profile information."""
        admin = await self.admin_repo.find_by_id(admin_id)
        if not admin:
            raise EntityNotFoundError(f"Admin {admin_id} not found")

        if not admin.admin_profile:
            # Create new profile
            profile = await self.admin_repo._create_admin_profile(
                admin_id,
                profile_data
            )
        else:
            # Update existing profile
            profile = admin.admin_profile
            for key, value in profile_data.items():
                if hasattr(profile, key):
                    setattr(profile, key, value)
            
            profile.updated_at = datetime.utcnow()

        await self.db.commit()
        return profile

    # ==================== STATUS MANAGEMENT ====================

    async def suspend_admin(
        self,
        admin_id: UUID,
        suspended_by_id: UUID,
        reason: str
    ) -> AdminUser:
        """Suspend admin account."""
        # Validate suspending admin has permission
        suspender = await self.admin_repo.find_by_id(suspended_by_id)
        if not suspender or not suspender.can_manage_admins:
            raise AuthorizationError("Insufficient permissions to suspend admin")

        # Cannot suspend self
        if admin_id == suspended_by_id:
            raise BusinessRuleViolationError("Cannot suspend own account")

        admin = await self.admin_repo.suspend_admin(
            admin_id=admin_id,
            suspended_by_id=suspended_by_id,
            reason=reason
        )

        await self.db.commit()
        return admin

    async def reactivate_admin(
        self,
        admin_id: UUID,
        reactivated_by_id: UUID
    ) -> AdminUser:
        """Reactivate suspended admin."""
        reactivator = await self.admin_repo.find_by_id(reactivated_by_id)
        if not reactivator or not reactivator.can_manage_admins:
            raise AuthorizationError("Insufficient permissions to reactivate admin")

        admin = await self.admin_repo.reactivate_admin(
            admin_id=admin_id,
            reactivated_by_id=reactivated_by_id
        )

        await self.db.commit()
        return admin

    async def terminate_admin(
        self,
        admin_id: UUID,
        terminated_by_id: UUID,
        reason: str
    ) -> AdminUser:
        """Permanently terminate admin account."""
        terminator = await self.admin_repo.find_by_id(terminated_by_id)
        if not terminator or not terminator.can_manage_admins:
            raise AuthorizationError("Insufficient permissions to terminate admin")

        # Cannot terminate self
        if admin_id == terminated_by_id:
            raise BusinessRuleViolationError("Cannot terminate own account")

        # Check if admin has active responsibilities
        assignments = await self.assignment_repo.get_admin_assignments(admin_id)
        active_count = len([a for a in assignments if a.is_active])
        
        if active_count > 0:
            raise BusinessRuleViolationError(
                f"Cannot terminate admin with {active_count} active hostel assignments. "
                f"Transfer responsibilities first."
            )

        admin = await self.admin_repo.terminate_admin(
            admin_id=admin_id,
            reason=reason,
            terminated_by_id=terminated_by_id
        )

        await self.db.commit()
        return admin

    # ==================== HIERARCHY MANAGEMENT ====================

    async def get_admin_hierarchy(
        self,
        admin_id: UUID,
        include_subordinates: bool = True
    ) -> Dict[str, Any]:
        """Get complete reporting hierarchy for admin."""
        return await self.admin_repo.get_admin_hierarchy(
            admin_id,
            include_subordinates
        )

    async def get_team_members(
        self,
        admin_id: UUID,
        include_indirect: bool = False
    ) -> List[AdminUser]:
        """Get all team members reporting to admin."""
        hierarchy = await self.admin_repo.get_admin_hierarchy(admin_id)
        
        if not include_indirect:
            # Only direct reports
            return [sub['admin'] for sub in hierarchy['subordinates']]
        
        # Include all subordinates recursively
        all_members = []
        
        def collect_subordinates(subs):
            for sub in subs:
                all_members.append(sub['admin'])
                if sub.get('subordinates'):
                    collect_subordinates(sub['subordinates'])
        
        collect_subordinates(hierarchy['subordinates'])
        return all_members

    async def reassign_subordinates(
        self,
        from_admin_id: UUID,
        to_admin_id: UUID,
        reassigned_by_id: UUID
    ) -> int:
        """Reassign all subordinates from one admin to another."""
        # Validate new manager
        await self._validate_hierarchy(to_admin_id, 1)  # Will check manager exists

        # Get direct reports
        hierarchy = await self.admin_repo.get_admin_hierarchy(from_admin_id)
        direct_reports = hierarchy['subordinates']

        count = 0
        for sub_data in direct_reports:
            subordinate = sub_data['admin']
            
            # Validate hierarchy
            await self._validate_hierarchy(to_admin_id, subordinate.admin_level)
            
            # Update reporting
            subordinate.reports_to_id = to_admin_id
            count += 1

        await self.db.commit()
        return count

    # ==================== ANALYTICS ====================

    async def get_admin_statistics(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> Dict[str, Any]:
        """Get comprehensive admin statistics."""
        return await self.admin_repo.get_admin_statistics(start_date, end_date)

    async def get_admin_performance(
        self,
        admin_id: UUID,
        period_days: int = 30
    ) -> Dict[str, Any]:
        """Get performance metrics for admin."""
        metrics = await self.admin_repo.get_admin_performance_metrics(
            admin_id,
            period_days
        )

        # Enhance with assignment metrics
        assignments = await self.assignment_repo.get_admin_assignments(admin_id)
        
        metrics['hostel_assignments'] = {
            'total': len(assignments),
            'active': len([a for a in assignments if a.is_active]),
            'primary': next((a for a in assignments if a.is_primary), None)
        }

        return metrics

    async def get_team_statistics(
        self,
        admin_id: UUID
    ) -> Dict[str, Any]:
        """Get statistics for admin's team."""
        return await self.admin_repo.get_team_statistics(admin_id)

    # ==================== BULK OPERATIONS ====================

    async def bulk_update_admins(
        self,
        admin_ids: List[UUID],
        updates: Dict[str, Any],
        updated_by_id: UUID
    ) -> Dict[str, Any]:
        """Bulk update multiple admins."""
        results = {
            'success': [],
            'failed': []
        }

        for admin_id in admin_ids:
            try:
                admin = await self.update_admin(admin_id, updates, updated_by_id)
                results['success'].append(admin_id)
            except Exception as e:
                results['failed'].append({
                    'admin_id': admin_id,
                    'error': str(e)
                })

        await self.db.commit()
        return results

    async def bulk_assign_hostels(
        self,
        admin_id: UUID,
        hostel_ids: List[UUID],
        assigned_by_id: UUID
    ) -> List:
        """Bulk assign admin to multiple hostels."""
        return await self.assignment_repo.assign_admin_to_hostels(
            admin_id=admin_id,
            hostel_ids=hostel_ids,
            assigned_by_id=assigned_by_id
        )