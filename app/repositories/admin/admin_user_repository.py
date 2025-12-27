"""
Admin User Repository

Manages admin users with role-based access, security monitoring,
multi-tenant support, and comprehensive activity tracking.
"""

from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID
from datetime import datetime, date, timedelta
from decimal import Decimal
from sqlalchemy import select, and_, or_, func, desc, asc, exists
from sqlalchemy.orm import Session, selectinload, joinedload
from sqlalchemy.exc import IntegrityError

from app.models.admin.admin_user import (
    AdminUser,
    AdminProfile,
    AdminRole,
    AdminSession
)
from app.models.user.user import User
from app.models.admin.admin_hostel_assignment import AdminHostelAssignment
from app.repositories.base.base_repository import BaseRepository
from app.core1.exceptions import (
    EntityNotFoundError,
    ValidationError,
    SecurityError,
    DuplicateError
)


class AdminUserRepository(BaseRepository[AdminUser]):
    """
    Comprehensive admin user management with:
    - Role-based access control with inheritance
    - Multi-hostel assignment tracking
    - Security monitoring and threat detection
    - Performance analytics and reporting
    - Session management with concurrent login control
    """

    def __init__(self, db: Session):
        super().__init__(AdminUser, db)

    # ==================== CORE CRUD OPERATIONS ====================

    async def create_admin(
        self,
        user_id: UUID,
        admin_data: Dict[str, Any],
        created_by_id: Optional[UUID] = None,
        audit_context: Optional[Dict] = None
    ) -> AdminUser:
        """
        Create new admin with validation and audit trail.
        
        Args:
            user_id: Base user account ID
            admin_data: Admin-specific attributes
            created_by_id: Admin who created this account
            audit_context: Audit trail information
            
        Returns:
            Created AdminUser instance
            
        Raises:
            ValidationError: Invalid data
            DuplicateError: Admin already exists for user
        """
        # Check if admin already exists for this user
        existing = await self.find_by_user_id(user_id)
        if existing:
            raise DuplicateError(f"Admin already exists for user {user_id}")

        # Validate admin level
        admin_level = admin_data.get('admin_level', 1)
        if not 1 <= admin_level <= 10:
            raise ValidationError("Admin level must be between 1 and 10")

        # Create admin user
        admin = AdminUser(
            user_id=user_id,
            admin_level=admin_level,
            is_super_admin=admin_data.get('is_super_admin', False),
            reports_to_id=admin_data.get('reports_to_id'),
            employee_id=admin_data.get('employee_id'),
            department=admin_data.get('department'),
            designation=admin_data.get('designation'),
            join_date=admin_data.get('join_date', datetime.utcnow()),
            is_active=admin_data.get('is_active', True),
            can_manage_admins=admin_data.get('can_manage_admins', False),
            can_access_all_hostels=admin_data.get('can_access_all_hostels', False),
            max_hostel_limit=admin_data.get('max_hostel_limit'),
            permissions_override=admin_data.get('permissions_override'),
            settings=admin_data.get('settings', {})
        )

        self.db.add(admin)
        
        try:
            await self.db.flush()
            
            # Create admin profile if profile data provided
            if 'profile' in admin_data:
                await self._create_admin_profile(admin.id, admin_data['profile'])
            
            # Log creation audit
            await self._log_audit('CREATE_ADMIN', admin, audit_context)
            
            return admin
            
        except IntegrityError as e:
            await self.db.rollback()
            raise ValidationError(f"Failed to create admin: {str(e)}")

    async def find_by_user_id(self, user_id: UUID) -> Optional[AdminUser]:
        """Find admin by base user ID with eager loading."""
        stmt = (
            select(AdminUser)
            .where(AdminUser.user_id == user_id)
            .where(AdminUser.is_deleted == False)
            .options(
                joinedload(AdminUser.user),
                selectinload(AdminUser.admin_profile),
                selectinload(AdminUser.hostel_assignments)
            )
        )
        result = await self.db.execute(stmt)
        return result.unique().scalar_one_or_none()

    async def find_by_email(self, email: str) -> Optional[AdminUser]:
        """Find admin by email address."""
        stmt = (
            select(AdminUser)
            .join(AdminUser.user)
            .where(User.email == email)
            .where(AdminUser.is_deleted == False)
            .options(
                joinedload(AdminUser.user),
                selectinload(AdminUser.admin_profile)
            )
        )
        result = await self.db.execute(stmt)
        return result.unique().scalar_one_or_none()

    async def find_by_employee_id(self, employee_id: str) -> Optional[AdminUser]:
        """Find admin by employee ID."""
        stmt = (
            select(AdminUser)
            .where(AdminUser.employee_id == employee_id)
            .where(AdminUser.is_deleted == False)
            .options(joinedload(AdminUser.user))
        )
        result = await self.db.execute(stmt)
        return result.unique().scalar_one_or_none()

    # ==================== SEARCH & FILTERING ====================

    async def find_by_permissions(
        self,
        required_permissions: List[str],
        match_all: bool = True
    ) -> List[AdminUser]:
        """
        Find admins with specific permissions.
        
        Args:
            required_permissions: List of permission keys
            match_all: If True, admin must have all permissions
            
        Returns:
            List of admins with matching permissions
        """
        stmt = select(AdminUser).where(AdminUser.is_deleted == False)

        if match_all:
            # Admin must have all specified permissions
            for perm in required_permissions:
                stmt = stmt.where(
                    AdminUser.permissions_override[perm].astext.cast(Boolean) == True
                )
        else:
            # Admin must have at least one permission
            or_conditions = [
                AdminUser.permissions_override[perm].astext.cast(Boolean) == True
                for perm in required_permissions
            ]
            stmt = stmt.where(or_(*or_conditions))

        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def find_multi_hostel_admins(self) -> List[AdminUser]:
        """Find admins managing multiple hostels."""
        subquery = (
            select(AdminHostelAssignment.admin_id)
            .where(AdminHostelAssignment.is_active == True)
            .where(AdminHostelAssignment.is_deleted == False)
            .group_by(AdminHostelAssignment.admin_id)
            .having(func.count(AdminHostelAssignment.hostel_id) > 1)
        )

        stmt = (
            select(AdminUser)
            .where(AdminUser.id.in_(subquery))
            .where(AdminUser.is_deleted == False)
            .options(selectinload(AdminUser.hostel_assignments))
        )

        result = await self.db.execute(stmt)
        return result.unique().scalars().all()

    async def find_by_activity_level(
        self,
        period_days: int = 30,
        min_logins: int = 1
    ) -> List[AdminUser]:
        """
        Find admins by activity level.
        
        Args:
            period_days: Period to check activity
            min_logins: Minimum login count
            
        Returns:
            Active admins within period
        """
        cutoff_date = datetime.utcnow() - timedelta(days=period_days)

        stmt = (
            select(AdminUser)
            .where(AdminUser.is_deleted == False)
            .where(AdminUser.last_active_at >= cutoff_date)
            .where(AdminUser.login_count >= min_logins)
            .order_by(desc(AdminUser.last_active_at))
        )

        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def find_inactive_admins(self, days_inactive: int = 90) -> List[AdminUser]:
        """Find admins with no activity for specified days."""
        cutoff_date = datetime.utcnow() - timedelta(days=days_inactive)

        stmt = (
            select(AdminUser)
            .where(AdminUser.is_deleted == False)
            .where(AdminUser.is_active == True)
            .where(
                or_(
                    AdminUser.last_active_at < cutoff_date,
                    AdminUser.last_active_at.is_(None)
                )
            )
            .order_by(asc(AdminUser.last_active_at))
        )

        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def find_pending_approval(self) -> List[AdminUser]:
        """Find admin accounts pending verification/approval."""
        stmt = (
            select(AdminUser)
            .where(AdminUser.is_deleted == False)
            .where(AdminUser.is_verified == False)
            .order_by(asc(AdminUser.created_at))
        )

        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def find_expiring_access(self, days: int = 30) -> List[Dict[str, Any]]:
        """
        Find admins with assignments expiring within specified days.
        
        Returns:
            List of dicts with admin and expiring assignment info
        """
        cutoff_date = date.today() + timedelta(days=days)

        stmt = (
            select(
                AdminUser,
                AdminHostelAssignment,
                func.count(AdminHostelAssignment.id).over(
                    partition_by=AdminUser.id
                ).label('expiring_count')
            )
            .join(AdminUser.hostel_assignments)
            .where(AdminUser.is_deleted == False)
            .where(AdminHostelAssignment.is_active == True)
            .where(AdminHostelAssignment.effective_until <= cutoff_date)
            .order_by(AdminHostelAssignment.effective_until)
        )

        result = await self.db.execute(stmt)
        
        expiring_data = []
        for row in result:
            expiring_data.append({
                'admin': row.AdminUser,
                'assignment': row.AdminHostelAssignment,
                'expiring_count': row.expiring_count,
                'days_until_expiry': (row.AdminHostelAssignment.effective_until - date.today()).days
            })

        return expiring_data

    # ==================== HIERARCHY & REPORTING ====================

    async def get_admin_hierarchy(
        self,
        admin_id: UUID,
        include_subordinates: bool = True
    ) -> Dict[str, Any]:
        """
        Get complete reporting hierarchy for admin.
        
        Returns:
            Dict with managers (upward) and subordinates (downward)
        """
        admin = await self.find_by_id(admin_id)
        if not admin:
            raise EntityNotFoundError(f"Admin {admin_id} not found")

        hierarchy = {
            'admin': admin,
            'managers': [],
            'subordinates': [] if include_subordinates else None
        }

        # Get upward hierarchy (managers)
        current_admin = admin
        while current_admin.reports_to_id:
            manager = await self.find_by_id(current_admin.reports_to_id)
            if not manager:
                break
            hierarchy['managers'].append(manager)
            current_admin = manager

        # Get downward hierarchy (subordinates)
        if include_subordinates:
            subordinates = await self._get_all_subordinates(admin_id)
            hierarchy['subordinates'] = subordinates

        return hierarchy

    async def _get_all_subordinates(
        self,
        admin_id: UUID,
        depth: int = 0,
        max_depth: int = 10
    ) -> List[Dict[str, Any]]:
        """Recursively get all subordinates with depth tracking."""
        if depth >= max_depth:
            return []

        stmt = (
            select(AdminUser)
            .where(AdminUser.reports_to_id == admin_id)
            .where(AdminUser.is_deleted == False)
        )
        result = await self.db.execute(stmt)
        direct_reports = result.scalars().all()

        subordinates = []
        for subordinate in direct_reports:
            sub_data = {
                'admin': subordinate,
                'depth': depth + 1,
                'subordinates': await self._get_all_subordinates(
                    subordinate.id,
                    depth + 1,
                    max_depth
                )
            }
            subordinates.append(sub_data)

        return subordinates

    async def get_team_statistics(self, admin_id: UUID) -> Dict[str, Any]:
        """Get statistics for admin's team."""
        hierarchy = await self.get_admin_hierarchy(admin_id)
        
        def count_subordinates(subs):
            count = len(subs)
            for sub in subs:
                count += count_subordinates(sub.get('subordinates', []))
            return count

        total_subordinates = count_subordinates(hierarchy['subordinates'])
        direct_reports = len(hierarchy['subordinates'])

        return {
            'admin_id': admin_id,
            'total_subordinates': total_subordinates,
            'direct_reports': direct_reports,
            'hierarchy_depth': len(hierarchy['managers']),
            'team_size': total_subordinates + 1,  # +1 for the admin themselves
        }

    # ==================== PERMISSION MANAGEMENT ====================

    async def get_effective_permissions(
        self,
        admin_id: UUID,
        hostel_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """
        Calculate effective permissions with inheritance and overrides.
        
        Priority (highest to lowest):
        1. Hostel-specific assignment permissions
        2. Global admin permission overrides
        3. Role-based permissions
        4. Default permissions based on admin level
        """
        admin = await self.find_by_id(admin_id)
        if not admin:
            raise EntityNotFoundError(f"Admin {admin_id} not found")

        # Start with default permissions based on level
        permissions = self._get_default_permissions(admin.admin_level)

        # Apply super admin override
        if admin.is_super_admin:
            permissions = self._get_super_admin_permissions()

        # Apply global permission overrides
        if admin.permissions_override:
            permissions.update(admin.permissions_override)

        # Apply hostel-specific permissions if context provided
        if hostel_id:
            hostel_perms = await self._get_hostel_specific_permissions(
                admin_id,
                hostel_id
            )
            if hostel_perms:
                permissions.update(hostel_perms)

        return {
            'admin_id': admin_id,
            'hostel_id': hostel_id,
            'effective_permissions': permissions,
            'permission_source': self._determine_permission_source(
                admin, hostel_id
            ),
            'is_super_admin': admin.is_super_admin
        }

    def _get_default_permissions(self, admin_level: int) -> Dict[str, bool]:
        """Get default permissions based on admin level."""
        # Level 1-3: Basic permissions
        if admin_level <= 3:
            return {
                'can_view_data': True,
                'can_manage_students': False,
                'can_approve_bookings': False,
                'can_manage_fees': False,
                'can_view_financials': False
            }
        # Level 4-6: Intermediate permissions
        elif admin_level <= 6:
            return {
                'can_view_data': True,
                'can_manage_students': True,
                'can_approve_bookings': True,
                'can_manage_fees': False,
                'can_view_financials': True
            }
        # Level 7-10: Advanced permissions
        else:
            return {
                'can_view_data': True,
                'can_manage_students': True,
                'can_approve_bookings': True,
                'can_manage_fees': True,
                'can_view_financials': True,
                'can_export_data': True
            }

    def _get_super_admin_permissions(self) -> Dict[str, bool]:
        """Get all permissions for super admin."""
        return {
            'can_view_data': True,
            'can_manage_students': True,
            'can_approve_bookings': True,
            'can_manage_fees': True,
            'can_view_financials': True,
            'can_export_data': True,
            'can_manage_admins': True,
            'can_manage_hostel_settings': True,
            'can_delete_records': True,
            'can_override_supervisor_actions': True
        }

    async def _get_hostel_specific_permissions(
        self,
        admin_id: UUID,
        hostel_id: UUID
    ) -> Optional[Dict[str, bool]]:
        """Get permissions for specific hostel assignment."""
        stmt = (
            select(AdminHostelAssignment.permissions)
            .where(AdminHostelAssignment.admin_id == admin_id)
            .where(AdminHostelAssignment.hostel_id == hostel_id)
            .where(AdminHostelAssignment.is_active == True)
            .where(AdminHostelAssignment.is_deleted == False)
        )
        result = await self.db.execute(stmt)
        permissions = result.scalar_one_or_none()
        return permissions if permissions else None

    def _determine_permission_source(
        self,
        admin: AdminUser,
        hostel_id: Optional[UUID]
    ) -> str:
        """Determine the source of effective permissions."""
        if admin.is_super_admin:
            return 'super_admin'
        elif hostel_id:
            return 'hostel_assignment'
        elif admin.permissions_override:
            return 'admin_override'
        else:
            return 'default_level'

    async def validate_permission(
        self,
        admin_id: UUID,
        permission_key: str,
        hostel_id: Optional[UUID] = None
    ) -> bool:
        """Validate if admin has specific permission."""
        permissions = await self.get_effective_permissions(admin_id, hostel_id)
        return permissions['effective_permissions'].get(permission_key, False)

    # ==================== SECURITY & SESSION MANAGEMENT ====================

    async def track_login(
        self,
        admin_id: UUID,
        ip_address: str,
        user_agent: str,
        device_info: Optional[Dict] = None
    ) -> AdminSession:
        """
        Track admin login with security monitoring.
        
        Creates session and updates login metrics.
        Detects suspicious activity patterns.
        """
        admin = await self.find_by_id(admin_id)
        if not admin:
            raise EntityNotFoundError(f"Admin {admin_id} not found")

        # Check if admin can login
        if not admin.can_login:
            raise SecurityError(
                f"Admin login disabled: "
                f"{'suspended' if admin.is_suspended else 'terminated'}"
            )

        # Update login metrics
        admin.last_login_at = datetime.utcnow()
        admin.last_active_at = datetime.utcnow()
        admin.login_count += 1

        # Create session
        session = AdminSession(
            admin_id=admin_id,
            session_token=self._generate_session_token(),
            started_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(hours=8),
            ip_address=ip_address,
            user_agent=user_agent,
            device_info=device_info or {},
            is_active=True
        )

        self.db.add(session)

        # Security checks
        is_suspicious = await self._check_suspicious_login(
            admin_id,
            ip_address,
            user_agent
        )
        if is_suspicious:
            session.is_suspicious = True
            session.security_flags = ['unusual_location', 'new_device']
            # Notify security team
            await self._notify_suspicious_activity(admin, session)

        await self.db.flush()
        return session

    async def _check_suspicious_login(
        self,
        admin_id: UUID,
        ip_address: str,
        user_agent: str
    ) -> bool:
        """Detect suspicious login patterns."""
        # Get recent sessions
        recent_sessions = await self._get_recent_sessions(admin_id, hours=24)

        # Check for unusual patterns
        suspicious_indicators = []

        # 1. New IP address
        known_ips = {s.ip_address for s in recent_sessions if s.ip_address}
        if ip_address not in known_ips and len(known_ips) > 0:
            suspicious_indicators.append('new_ip')

        # 2. Multiple login attempts from different IPs
        unique_ips_today = len({s.ip_address for s in recent_sessions})
        if unique_ips_today > 5:
            suspicious_indicators.append('multiple_ips')

        # 3. High frequency logins
        if len(recent_sessions) > 20:
            suspicious_indicators.append('high_frequency')

        return len(suspicious_indicators) >= 2

    async def _get_recent_sessions(
        self,
        admin_id: UUID,
        hours: int = 24
    ) -> List[AdminSession]:
        """Get recent sessions for security analysis."""
        cutoff = datetime.utcnow() - timedelta(hours=hours)

        stmt = (
            select(AdminSession)
            .where(AdminSession.admin_id == admin_id)
            .where(AdminSession.started_at >= cutoff)
            .order_by(desc(AdminSession.started_at))
        )

        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def end_session(self, session_id: UUID, reason: str = 'logout') -> bool:
        """End admin session."""
        session = await self.db.get(AdminSession, session_id)
        if not session:
            return False

        session.is_active = False
        session.ended_at = datetime.utcnow()
        session.end_reason = reason

        await self.db.flush()
        return True

    async def get_active_sessions(self, admin_id: UUID) -> List[AdminSession]:
        """Get all active sessions for admin."""
        stmt = (
            select(AdminSession)
            .where(AdminSession.admin_id == admin_id)
            .where(AdminSession.is_active == True)
            .where(AdminSession.expires_at > datetime.utcnow())
            .order_by(desc(AdminSession.started_at))
        )

        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def terminate_all_sessions(
        self,
        admin_id: UUID,
        reason: str = 'force_logout'
    ) -> int:
        """Terminate all active sessions for admin."""
        sessions = await self.get_active_sessions(admin_id)
        
        for session in sessions:
            session.is_active = False
            session.ended_at = datetime.utcnow()
            session.end_reason = reason

        await self.db.flush()
        return len(sessions)

    # ==================== ADMIN STATUS MANAGEMENT ====================

    async def suspend_admin(
        self,
        admin_id: UUID,
        suspended_by_id: UUID,
        reason: str,
        audit_context: Optional[Dict] = None
    ) -> AdminUser:
        """Suspend admin account."""
        admin = await self.find_by_id(admin_id)
        if not admin:
            raise EntityNotFoundError(f"Admin {admin_id} not found")

        admin.is_active = False
        admin.suspended_at = datetime.utcnow()
        admin.suspended_by_id = suspended_by_id
        admin.suspension_reason = reason

        # Terminate all active sessions
        await self.terminate_all_sessions(admin_id, 'account_suspended')

        # Log audit
        await self._log_audit('SUSPEND_ADMIN', admin, audit_context)

        await self.db.flush()
        return admin

    async def reactivate_admin(
        self,
        admin_id: UUID,
        reactivated_by_id: UUID,
        audit_context: Optional[Dict] = None
    ) -> AdminUser:
        """Reactivate suspended admin."""
        admin = await self.find_by_id(admin_id)
        if not admin:
            raise EntityNotFoundError(f"Admin {admin_id} not found")

        admin.is_active = True
        admin.suspended_at = None
        admin.suspended_by_id = None
        admin.suspension_reason = None

        # Log audit
        await self._log_audit('REACTIVATE_ADMIN', admin, audit_context)

        await self.db.flush()
        return admin

    async def terminate_admin(
        self,
        admin_id: UUID,
        reason: str,
        terminated_by_id: UUID,
        audit_context: Optional[Dict] = None
    ) -> AdminUser:
        """Permanently terminate admin account."""
        admin = await self.find_by_id(admin_id)
        if not admin:
            raise EntityNotFoundError(f"Admin {admin_id} not found")

        admin.is_active = False
        admin.terminated_at = datetime.utcnow()
        admin.termination_reason = reason

        # Terminate all sessions
        await self.terminate_all_sessions(admin_id, 'account_terminated')

        # Deactivate all hostel assignments
        await self._deactivate_all_assignments(admin_id)

        # Log audit
        await self._log_audit('TERMINATE_ADMIN', admin, audit_context)

        await self.db.flush()
        return admin

    async def _deactivate_all_assignments(self, admin_id: UUID) -> None:
        """Deactivate all hostel assignments for admin."""
        stmt = (
            select(AdminHostelAssignment)
            .where(AdminHostelAssignment.admin_id == admin_id)
            .where(AdminHostelAssignment.is_active == True)
        )
        result = await self.db.execute(stmt)
        assignments = result.scalars().all()

        for assignment in assignments:
            assignment.is_active = False
            assignment.revoked_date = date.today()
            assignment.revoke_reason = "Admin account terminated"

    # ==================== ANALYTICS & REPORTING ====================

    async def get_admin_statistics(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> Dict[str, Any]:
        """Get comprehensive admin statistics."""
        if not start_date:
            start_date = date.today() - timedelta(days=30)
        if not end_date:
            end_date = date.today()

        # Total admins
        total_stmt = select(func.count(AdminUser.id)).where(
            AdminUser.is_deleted == False
        )
        total_admins = await self.db.scalar(total_stmt)

        # Active admins
        active_stmt = select(func.count(AdminUser.id)).where(
            and_(
                AdminUser.is_deleted == False,
                AdminUser.is_active == True,
                AdminUser.terminated_at.is_(None)
            )
        )
        active_admins = await self.db.scalar(active_stmt)

        # Super admins
        super_stmt = select(func.count(AdminUser.id)).where(
            and_(
                AdminUser.is_deleted == False,
                AdminUser.is_super_admin == True
            )
        )
        super_admins = await self.db.scalar(super_stmt)

        # New admins in period
        new_stmt = select(func.count(AdminUser.id)).where(
            and_(
                AdminUser.is_deleted == False,
                AdminUser.created_at >= start_date,
                AdminUser.created_at <= end_date
            )
        )
        new_admins = await self.db.scalar(new_stmt)

        # By admin level distribution
        level_dist_stmt = (
            select(
                AdminUser.admin_level,
                func.count(AdminUser.id).label('count')
            )
            .where(AdminUser.is_deleted == False)
            .group_by(AdminUser.admin_level)
        )
        level_result = await self.db.execute(level_dist_stmt)
        level_distribution = {
            row.admin_level: row.count for row in level_result
        }

        return {
            'period': {'start': start_date, 'end': end_date},
            'total_admins': total_admins,
            'active_admins': active_admins,
            'super_admins': super_admins,
            'inactive_admins': total_admins - active_admins,
            'new_admins': new_admins,
            'level_distribution': level_distribution,
            'activity_rate': (active_admins / total_admins * 100) if total_admins > 0 else 0
        }

    async def get_admin_performance_metrics(
        self,
        admin_id: UUID,
        period_days: int = 30
    ) -> Dict[str, Any]:
        """Get performance metrics for specific admin."""
        admin = await self.find_by_id(admin_id)
        if not admin:
            raise EntityNotFoundError(f"Admin {admin_id} not found")

        start_date = datetime.utcnow() - timedelta(days=period_days)

        # Session statistics
        sessions = await self._get_recent_sessions(admin_id, period_days * 24)
        total_sessions = len(sessions)
        avg_session_duration = (
            sum(s.duration_seconds for s in sessions if s.duration_seconds) / total_sessions
            if total_sessions > 0 else 0
        )

        # Hostel assignment stats
        assignment_stmt = (
            select(func.count(AdminHostelAssignment.id))
            .where(AdminHostelAssignment.admin_id == admin_id)
            .where(AdminHostelAssignment.is_active == True)
        )
        active_assignments = await self.db.scalar(assignment_stmt)

        return {
            'admin_id': admin_id,
            'period_days': period_days,
            'login_count': admin.login_count,
            'total_sessions': total_sessions,
            'avg_session_duration_minutes': avg_session_duration / 60,
            'active_hostel_assignments': active_assignments,
            'last_active': admin.last_active_at,
            'account_age_days': (datetime.utcnow() - admin.created_at).days,
        }

    # ==================== HELPER METHODS ====================

    async def _create_admin_profile(
        self,
        admin_id: UUID,
        profile_data: Dict[str, Any]
    ) -> AdminProfile:
        """Create admin profile with extended information."""
        profile = AdminProfile(
            admin_id=admin_id,
            date_of_birth=profile_data.get('date_of_birth'),
            nationality=profile_data.get('nationality'),
            id_proof_type=profile_data.get('id_proof_type'),
            id_proof_number=profile_data.get('id_proof_number'),
            contract_type=profile_data.get('contract_type'),
            work_phone=profile_data.get('work_phone'),
            personal_phone=profile_data.get('personal_phone'),
            emergency_contact_name=profile_data.get('emergency_contact_name'),
            emergency_contact_phone=profile_data.get('emergency_contact_phone'),
            current_address=profile_data.get('current_address'),
            qualifications=profile_data.get('qualifications'),
            experience_years=profile_data.get('experience_years'),
            skills=profile_data.get('skills'),
            bio=profile_data.get('bio'),
            profile_picture_url=profile_data.get('profile_picture_url')
        )

        self.db.add(profile)
        await self.db.flush()
        return profile

    def _generate_session_token(self) -> str:
        """Generate secure session token."""
        import secrets
        return secrets.token_urlsafe(32)

    async def _notify_suspicious_activity(
        self,
        admin: AdminUser,
        session: AdminSession
    ) -> None:
        """Notify security team of suspicious login."""
        # Implementation would send notification via email/SMS/Slack
        # For now, just log it
        pass

    async def _log_audit(
        self,
        action: str,
        entity: Any,
        context: Optional[Dict]
    ) -> None:
        """Log audit trail for admin actions."""
        # Implementation would create audit log entry
        pass