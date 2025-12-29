"""
Admin Hostel Assignment Repository

Manages multi-hostel assignments with workload balancing,
transfer workflows, coverage analysis, and performance tracking.
"""

from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID
from datetime import datetime, date, timedelta
from decimal import Decimal
from sqlalchemy import select, and_, or_, func, desc, asc, case
from sqlalchemy.orm import Session, selectinload, joinedload
from sqlalchemy.exc import IntegrityError

from app.models.admin.admin_hostel_assignment import (
    AdminHostelAssignment,
    AssignmentPermission,
    AssignmentHistory,
    PrimaryHostelDesignation
)
from app.models.admin.admin_user import AdminUser
from app.models.hostel.hostel import Hostel
from app.repositories.base.base_repository import BaseRepository
from app.core.exceptions import (
    EntityNotFoundError,
    ValidationError,
    ConflictError,
    BusinessRuleViolationError
)


class AdminHostelAssignmentRepository(BaseRepository[AdminHostelAssignment]):
    """
    Multi-hostel assignment management with:
    - Workload balancing and optimization
    - Transfer workflows with handover tracking
    - Coverage gap analysis
    - Assignment history and audit trail
    - Performance metrics per assignment
    """

    def __init__(self, db: Session):
        super().__init__(AdminHostelAssignment, db)

    # ==================== ASSIGNMENT CREATION ====================

    async def assign_admin_to_hostels(
        self,
        admin_id: UUID,
        hostel_ids: List[UUID],
        assigned_by_id: UUID,
        permissions: Optional[Dict] = None,
        effective_from: Optional[date] = None,
        effective_until: Optional[date] = None,
        notes: Optional[str] = None,
        set_first_as_primary: bool = True
    ) -> List[AdminHostelAssignment]:
        """
        Assign admin to multiple hostels with comprehensive validation.
        
        Args:
            admin_id: Admin to assign
            hostel_ids: List of hostel IDs
            assigned_by_id: Who is making the assignment
            permissions: Optional permission overrides
            effective_from: Start date of assignment
            effective_until: End date of assignment
            notes: Assignment notes
            set_first_as_primary: Set first hostel as primary
            
        Returns:
            List of created assignments
            
        Raises:
            ValidationError: Invalid data
            BusinessRuleViolationError: Violates business rules
            ConflictError: Assignment conflicts
        """
        # Validate admin exists and is active
        admin = await self.db.get(AdminUser, admin_id)
        if not admin:
            raise EntityNotFoundError(f"Admin {admin_id} not found")
        
        if not admin.is_active:
            raise ValidationError(f"Admin {admin_id} is not active")

        # Check hostel limit
        if admin.max_hostel_limit:
            current_count = await self._get_active_assignment_count(admin_id)
            if current_count + len(hostel_ids) > admin.max_hostel_limit:
                raise BusinessRuleViolationError(
                    f"Admin can manage maximum {admin.max_hostel_limit} hostels. "
                    f"Current: {current_count}, Requested: {len(hostel_ids)}"
                )

        # Check for existing assignments
        conflicts = await self._check_assignment_conflicts(admin_id, hostel_ids)
        if conflicts:
            raise ConflictError(
                f"Active assignments already exist for hostels: "
                f"{', '.join(str(h) for h in conflicts)}"
            )

        # Validate all hostels exist
        await self._validate_hostels_exist(hostel_ids)

        # Create assignments
        assignments = []
        for idx, hostel_id in enumerate(hostel_ids):
            is_primary = (idx == 0 and set_first_as_primary and not admin.primary_hostel_id)
            
            assignment = AdminHostelAssignment(
                admin_id=admin_id,
                hostel_id=hostel_id,
                assigned_by_id=assigned_by_id,
                assigned_date=date.today(),
                effective_from=effective_from or date.today(),
                effective_until=effective_until,
                permission_level='FULL_ACCESS',
                permissions=permissions or {},
                is_active=True,
                is_primary=is_primary,
                assignment_notes=notes
            )

            self.db.add(assignment)
            assignments.append(assignment)

        try:
            await self.db.flush()

            # Set primary hostel if needed
            if set_first_as_primary and not admin.primary_hostel_id:
                admin.primary_hostel_id = hostel_ids[0]
                await self._create_primary_designation(
                    admin_id, hostel_ids[0], assigned_by_id
                )

            # Create assignment history for each
            for assignment in assignments:
                await self._create_assignment_history(
                    assignment_id=assignment.id,
                    admin_id=admin_id,
                    hostel_id=assignment.hostel_id,
                    action='created',
                    performed_by_id=assigned_by_id,
                    new_values=self._assignment_to_dict(assignment)
                )

            return assignments

        except IntegrityError as e:
            await self.db.rollback()
            raise ValidationError(f"Failed to create assignments: {str(e)}")

    async def assign_single_hostel(
        self,
        admin_id: UUID,
        hostel_id: UUID,
        assigned_by_id: UUID,
        **kwargs
    ) -> AdminHostelAssignment:
        """Assign admin to a single hostel."""
        assignments = await self.assign_admin_to_hostels(
            admin_id=admin_id,
            hostel_ids=[hostel_id],
            assigned_by_id=assigned_by_id,
            **kwargs
        )
        return assignments[0]

    # ==================== ASSIGNMENT RETRIEVAL ====================

    async def get_admin_assignments(
        self,
        admin_id: UUID,
        include_inactive: bool = False,
        include_expired: bool = False
    ) -> List[AdminHostelAssignment]:
        """Get all assignments for an admin."""
        stmt = (
            select(AdminHostelAssignment)
            .where(AdminHostelAssignment.admin_id == admin_id)
            .where(AdminHostelAssignment.is_deleted == False)
            .options(
                selectinload(AdminHostelAssignment.hostel),
                selectinload(AdminHostelAssignment.assigned_by)
            )
        )

        if not include_inactive:
            stmt = stmt.where(AdminHostelAssignment.is_active == True)

        if not include_expired:
            today = date.today()
            stmt = stmt.where(
                or_(
                    AdminHostelAssignment.effective_until.is_(None),
                    AdminHostelAssignment.effective_until >= today
                )
            )

        stmt = stmt.order_by(
            desc(AdminHostelAssignment.is_primary),
            AdminHostelAssignment.assigned_date
        )

        result = await self.db.execute(stmt)
        return result.unique().scalars().all()

    async def get_hostel_assignments(
        self,
        hostel_id: UUID,
        include_inactive: bool = False
    ) -> List[AdminHostelAssignment]:
        """Get all admin assignments for a hostel."""
        stmt = (
            select(AdminHostelAssignment)
            .where(AdminHostelAssignment.hostel_id == hostel_id)
            .where(AdminHostelAssignment.is_deleted == False)
            .options(
                selectinload(AdminHostelAssignment.admin).selectinload(AdminUser.user)
            )
        )

        if not include_inactive:
            stmt = stmt.where(AdminHostelAssignment.is_active == True)

        stmt = stmt.order_by(
            desc(AdminHostelAssignment.is_primary),
            AdminHostelAssignment.assigned_date
        )

        result = await self.db.execute(stmt)
        return result.unique().scalars().all()

    async def find_assignment(
        self,
        admin_id: UUID,
        hostel_id: UUID
    ) -> Optional[AdminHostelAssignment]:
        """Find specific assignment."""
        stmt = (
            select(AdminHostelAssignment)
            .where(AdminHostelAssignment.admin_id == admin_id)
            .where(AdminHostelAssignment.hostel_id == hostel_id)
            .where(AdminHostelAssignment.is_deleted == False)
            .options(
                selectinload(AdminHostelAssignment.hostel),
                selectinload(AdminHostelAssignment.assignment_permissions)
            )
        )

        result = await self.db.execute(stmt)
        return result.unique().scalar_one_or_none()

    async def get_primary_assignment(self, admin_id: UUID) -> Optional[AdminHostelAssignment]:
        """Get admin's primary hostel assignment."""
        stmt = (
            select(AdminHostelAssignment)
            .where(AdminHostelAssignment.admin_id == admin_id)
            .where(AdminHostelAssignment.is_primary == True)
            .where(AdminHostelAssignment.is_active == True)
            .where(AdminHostelAssignment.is_deleted == False)
            .options(selectinload(AdminHostelAssignment.hostel))
        )

        result = await self.db.execute(stmt)
        return result.unique().scalar_one_or_none()

    # ==================== ASSIGNMENT UPDATES ====================

    async def update_assignment(
        self,
        assignment_id: UUID,
        updates: Dict[str, Any],
        updated_by_id: UUID,
        reason: Optional[str] = None
    ) -> AdminHostelAssignment:
        """Update assignment with audit trail."""
        assignment = await self.find_by_id(assignment_id)
        if not assignment:
            raise EntityNotFoundError(f"Assignment {assignment_id} not found")

        # Store old values for audit
        old_values = self._assignment_to_dict(assignment)

        # Apply updates
        for key, value in updates.items():
            if hasattr(assignment, key):
                setattr(assignment, key, value)

        await self.db.flush()

        # Create audit record
        await self._create_assignment_history(
            assignment_id=assignment_id,
            admin_id=assignment.admin_id,
            hostel_id=assignment.hostel_id,
            action='updated',
            performed_by_id=updated_by_id,
            old_values=old_values,
            new_values=self._assignment_to_dict(assignment),
            reason=reason
        )

        return assignment

    async def revoke_assignment(
        self,
        assignment_id: UUID,
        revoked_by_id: UUID,
        reason: str,
        revoke_date: Optional[date] = None
    ) -> AdminHostelAssignment:
        """Revoke an assignment."""
        assignment = await self.find_by_id(assignment_id)
        if not assignment:
            raise EntityNotFoundError(f"Assignment {assignment_id} not found")

        assignment.is_active = False
        assignment.revoked_date = revoke_date or date.today()
        assignment.revoked_by_id = revoked_by_id
        assignment.revoke_reason = reason

        # If this was primary, unset it
        if assignment.is_primary:
            assignment.is_primary = False
            admin = await self.db.get(AdminUser, assignment.admin_id)
            if admin and admin.primary_hostel_id == assignment.hostel_id:
                admin.primary_hostel_id = None

        await self.db.flush()

        # Create audit record
        await self._create_assignment_history(
            assignment_id=assignment_id,
            admin_id=assignment.admin_id,
            hostel_id=assignment.hostel_id,
            action='revoked',
            performed_by_id=revoked_by_id,
            reason=reason
        )

        return assignment

    async def reactivate_assignment(
        self,
        assignment_id: UUID,
        reactivated_by_id: UUID,
        reason: Optional[str] = None
    ) -> AdminHostelAssignment:
        """Reactivate a revoked assignment."""
        assignment = await self.find_by_id(assignment_id)
        if not assignment:
            raise EntityNotFoundError(f"Assignment {assignment_id} not found")

        if assignment.is_active:
            raise ValidationError("Assignment is already active")

        assignment.is_active = True
        assignment.revoked_date = None
        assignment.revoked_by_id = None
        assignment.revoke_reason = None

        await self.db.flush()

        # Create audit record
        await self._create_assignment_history(
            assignment_id=assignment_id,
            admin_id=assignment.admin_id,
            hostel_id=assignment.hostel_id,
            action='reactivated',
            performed_by_id=reactivated_by_id,
            reason=reason
        )

        return assignment

    # ==================== PRIMARY HOSTEL MANAGEMENT ====================

    async def set_primary_hostel(
        self,
        admin_id: UUID,
        hostel_id: UUID,
        set_by_id: UUID,
        reason: Optional[str] = None
    ) -> AdminHostelAssignment:
        """Set primary hostel for admin."""
        # Verify assignment exists and is active
        assignment = await self.find_assignment(admin_id, hostel_id)
        if not assignment or not assignment.is_active:
            raise ValidationError(
                f"No active assignment found for admin {admin_id} and hostel {hostel_id}"
            )

        # Unset current primary
        current_primary = await self.get_primary_assignment(admin_id)
        if current_primary and current_primary.id != assignment.id:
            current_primary.is_primary = False
            # End primary designation
            await self._end_primary_designation(admin_id, current_primary.hostel_id)

        # Set new primary
        assignment.is_primary = True

        # Update admin's primary hostel
        admin = await self.db.get(AdminUser, admin_id)
        admin.primary_hostel_id = hostel_id

        # Create primary designation record
        await self._create_primary_designation(admin_id, hostel_id, set_by_id, reason)

        await self.db.flush()

        # Create audit record
        await self._create_assignment_history(
            assignment_id=assignment.id,
            admin_id=admin_id,
            hostel_id=hostel_id,
            action='set_as_primary',
            performed_by_id=set_by_id,
            reason=reason
        )

        return assignment

    async def _create_primary_designation(
        self,
        admin_id: UUID,
        hostel_id: UUID,
        designated_by_id: UUID,
        reason: Optional[str] = None
    ) -> PrimaryHostelDesignation:
        """Create primary hostel designation record."""
        # End any current designation
        await self._end_primary_designation(admin_id)

        designation = PrimaryHostelDesignation(
            admin_id=admin_id,
            hostel_id=hostel_id,
            designated_from=date.today(),
            designated_by_id=designated_by_id,
            reason=reason,
            is_current=True
        )

        self.db.add(designation)
        await self.db.flush()
        return designation

    async def _end_primary_designation(
        self,
        admin_id: UUID,
        hostel_id: Optional[UUID] = None
    ) -> None:
        """End current primary designation."""
        stmt = (
            select(PrimaryHostelDesignation)
            .where(PrimaryHostelDesignation.admin_id == admin_id)
            .where(PrimaryHostelDesignation.is_current == True)
        )

        if hostel_id:
            stmt = stmt.where(PrimaryHostelDesignation.hostel_id == hostel_id)

        result = await self.db.execute(stmt)
        current_designations = result.scalars().all()

        for designation in current_designations:
            designation.is_current = False
            designation.designated_until = date.today()

    # ==================== TRANSFER WORKFLOWS ====================

    async def transfer_responsibilities(
        self,
        from_admin_id: UUID,
        to_admin_id: UUID,
        transferred_by_id: UUID,  
        hostel_ids: Optional[List[UUID]] = None,
        transfer_notes: Optional[str] = None,
        require_handover: bool = True
    ) -> Dict[str, Any]:
        """
        Transfer hostel responsibilities between admins.
        
        Args:
            from_admin_id: Source admin
            to_admin_id: Target admin
            hostel_ids: Specific hostels (None = all)
            transferred_by_id: Who initiated transfer
            transfer_notes: Transfer notes
            require_handover: Require handover completion
            
        Returns:
            Transfer summary with new and revoked assignments
        """
        # Get source assignments
        source_assignments = await self.get_admin_assignments(from_admin_id)
        
        if hostel_ids:
            source_assignments = [
                a for a in source_assignments if a.hostel_id in hostel_ids
            ]

        if not source_assignments:
            raise ValidationError(
                f"No active assignments found for admin {from_admin_id}"
            )

        # Validate target admin
        to_admin = await self.db.get(AdminUser, to_admin_id)
        if not to_admin or not to_admin.is_active:
            raise ValidationError(f"Target admin {to_admin_id} is not active")

        transferred_hostels = []
        new_assignments = []

        for source_assignment in source_assignments:
            # Revoke source assignment
            await self.revoke_assignment(
                assignment_id=source_assignment.id,
                revoked_by_id=transferred_by_id,
                reason=f"Transferred to admin {to_admin_id}"
            )

            # Create new assignment
            new_assignment = AdminHostelAssignment(
                admin_id=to_admin_id,
                hostel_id=source_assignment.hostel_id,
                assigned_by_id=transferred_by_id,
                assigned_date=date.today(),
                permission_level=source_assignment.permission_level,
                permissions=source_assignment.permissions,
                transferred_from_id=from_admin_id,
                transfer_notes=transfer_notes,
                handover_completed=not require_handover,
                is_active=True
            )

            self.db.add(new_assignment)
            new_assignments.append(new_assignment)
            transferred_hostels.append(source_assignment.hostel_id)

        await self.db.flush()

        # Create history records
        for assignment in new_assignments:
            await self._create_assignment_history(
                assignment_id=assignment.id,
                admin_id=to_admin_id,
                hostel_id=assignment.hostel_id,
                action='transferred_in',
                performed_by_id=transferred_by_id,
                reason=f"Transferred from admin {from_admin_id}"
            )

        return {
            'from_admin_id': from_admin_id,
            'to_admin_id': to_admin_id,
            'transferred_hostels': transferred_hostels,
            'transfer_count': len(new_assignments),
            'new_assignments': new_assignments,
            'handover_required': require_handover
        }

    async def complete_handover(
        self,
        assignment_id: UUID,
        completed_by_id: UUID,
        notes: Optional[str] = None
    ) -> AdminHostelAssignment:
        """Mark handover as completed for transferred assignment."""
        assignment = await self.find_by_id(assignment_id)
        if not assignment:
            raise EntityNotFoundError(f"Assignment {assignment_id} not found")

        if not assignment.transferred_from_id:
            raise ValidationError("Assignment is not a transfer")

        if assignment.handover_completed:
            raise ValidationError("Handover already completed")

        assignment.handover_completed = True
        assignment.handover_completed_at = datetime.utcnow()
        if notes:
            assignment.transfer_notes = (
                f"{assignment.transfer_notes}\n\nHandover notes: {notes}"
                if assignment.transfer_notes else f"Handover notes: {notes}"
            )

        await self.db.flush()

        await self._create_assignment_history(
            assignment_id=assignment_id,
            admin_id=assignment.admin_id,
            hostel_id=assignment.hostel_id,
            action='handover_completed',
            performed_by_id=completed_by_id,
            reason=notes
        )

        return assignment

    # ==================== WORKLOAD MANAGEMENT ====================

    async def balance_workload(
        self,
        target_assignments_per_admin: int = 3,
        max_variance: int = 1
    ) -> Dict[str, Any]:
        """
        Analyze and suggest workload balancing.
        
        Returns recommendations for reassignments to balance load.
        """
        # Get all active admins with assignment counts
        stmt = (
            select(
                AdminUser.id,
                AdminUser.max_hostel_limit,
                func.count(AdminHostelAssignment.id).label('assignment_count')
            )
            .outerjoin(
                AdminHostelAssignment,
                and_(
                    AdminUser.id == AdminHostelAssignment.admin_id,
                    AdminHostelAssignment.is_active == True,
                    AdminHostelAssignment.is_deleted == False
                )
            )
            .where(AdminUser.is_active == True)
            .where(AdminUser.is_deleted == False)
            .group_by(AdminUser.id, AdminUser.max_hostel_limit)
        )

        result = await self.db.execute(stmt)
        admin_workloads = result.all()

        overloaded = []
        underutilized = []
        balanced = []

        for admin_id, max_limit, count in admin_workloads:
            if count > target_assignments_per_admin + max_variance:
                overloaded.append({
                    'admin_id': admin_id,
                    'current_count': count,
                    'excess': count - target_assignments_per_admin
                })
            elif count < target_assignments_per_admin - max_variance:
                underutilized.append({
                    'admin_id': admin_id,
                    'current_count': count,
                    'capacity': target_assignments_per_admin - count,
                    'max_limit': max_limit
                })
            else:
                balanced.append({
                    'admin_id': admin_id,
                    'current_count': count
                })

        # Generate recommendations
        recommendations = []
        for overloaded_admin in overloaded:
            for underutil_admin in underutilized:
                if (not underutil_admin['max_limit'] or 
                    underutil_admin['current_count'] < underutil_admin['max_limit']):
                    
                    transfer_count = min(
                        overloaded_admin['excess'],
                        underutil_admin['capacity']
                    )
                    
                    if transfer_count > 0:
                        recommendations.append({
                            'from_admin_id': overloaded_admin['admin_id'],
                            'to_admin_id': underutil_admin['admin_id'],
                            'suggested_transfer_count': transfer_count
                        })

        return {
            'target_per_admin': target_assignments_per_admin,
            'overloaded_admins': overloaded,
            'underutilized_admins': underutilized,
            'balanced_admins': balanced,
            'recommendations': recommendations,
            'balance_score': len(balanced) / len(admin_workloads) if admin_workloads else 0
        }

    async def find_overloaded_admins(
        self,
        threshold: int = 5
    ) -> List[Dict[str, Any]]:
        """Find admins exceeding workload threshold."""
        stmt = (
            select(
                AdminUser,
                func.count(AdminHostelAssignment.id).label('assignment_count')
            )
            .join(
                AdminHostelAssignment,
                AdminUser.id == AdminHostelAssignment.admin_id
            )
            .where(AdminUser.is_active == True)
            .where(AdminUser.is_deleted == False)
            .where(AdminHostelAssignment.is_active == True)
            .where(AdminHostelAssignment.is_deleted == False)
            .group_by(AdminUser.id)
            .having(func.count(AdminHostelAssignment.id) > threshold)
            .order_by(desc(func.count(AdminHostelAssignment.id)))
        )

        result = await self.db.execute(stmt)
        
        overloaded = []
        for admin, count in result:
            overloaded.append({
                'admin': admin,
                'assignment_count': count,
                'max_limit': admin.max_hostel_limit,
                'overload_amount': count - threshold,
                'utilization_rate': (count / admin.max_hostel_limit * 100) 
                    if admin.max_hostel_limit else None
            })

        return overloaded

    # ==================== COVERAGE ANALYSIS ====================

    async def get_coverage_gaps(self) -> List[Dict[str, Any]]:
        """Identify hostels without adequate admin coverage."""
        stmt = (
            select(
                Hostel.id,
                Hostel.name,
                Hostel.is_active,
                func.count(AdminHostelAssignment.id).label('admin_count')
            )
            .outerjoin(
                AdminHostelAssignment,
                and_(
                    Hostel.id == AdminHostelAssignment.hostel_id,
                    AdminHostelAssignment.is_active == True,
                    AdminHostelAssignment.is_deleted == False
                )
            )
            .where(Hostel.is_deleted == False)
            .group_by(Hostel.id, Hostel.name, Hostel.is_active)
            .having(func.count(AdminHostelAssignment.id) < 1)
        )

        result = await self.db.execute(stmt)
        
        gaps = []
        for hostel_id, name, is_active, admin_count in result:
            gaps.append({
                'hostel_id': hostel_id,
                'hostel_name': name,
                'is_active': is_active,
                'admin_count': admin_count,
                'priority': 'high' if is_active else 'medium'
            })

        return gaps

    async def recommend_assignments(
        self,
        hostel_id: UUID,
        criteria: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Recommend admins for hostel assignment.
        
        Considers:
        - Current workload
        - Admin level and permissions
        - Geographic proximity
        - Performance history
        """
        # Get admins with capacity
        stmt = (
            select(
                AdminUser,
                func.count(AdminHostelAssignment.id).label('current_assignments')
            )
            .outerjoin(
                AdminHostelAssignment,
                and_(
                    AdminUser.id == AdminHostelAssignment.admin_id,
                    AdminHostelAssignment.is_active == True,
                    AdminHostelAssignment.is_deleted == False
                )
            )
            .where(AdminUser.is_active == True)
            .where(AdminUser.is_deleted == False)
            .group_by(AdminUser.id)
        )

        result = await self.db.execute(stmt)
        
        recommendations = []
        for admin, current_count in result:
            # Check if admin has capacity
            has_capacity = (
                not admin.max_hostel_limit or 
                current_count < admin.max_hostel_limit
            )
            
            if has_capacity:
                # Calculate recommendation score
                score = 100 - (current_count * 10)  # Prefer less loaded admins
                score += admin.admin_level * 5  # Higher level = higher score
                
                # Apply criteria filters if provided
                if criteria:
                    if criteria.get('min_level') and admin.admin_level < criteria['min_level']:
                        continue
                    if criteria.get('department') and admin.department != criteria['department']:
                        continue

                recommendations.append({
                    'admin': admin,
                    'current_assignments': current_count,
                    'available_capacity': (
                        admin.max_hostel_limit - current_count
                        if admin.max_hostel_limit else 'unlimited'
                    ),
                    'recommendation_score': score,
                    'reason': self._generate_recommendation_reason(
                        admin, current_count
                    )
                })

        # Sort by score
        recommendations.sort(key=lambda x: x['recommendation_score'], reverse=True)
        
        return recommendations[:10]  # Top 10 recommendations

    def _generate_recommendation_reason(
        self,
        admin: AdminUser,
        current_count: int
    ) -> str:
        """Generate human-readable recommendation reason."""
        reasons = []
        
        if current_count == 0:
            reasons.append("Currently unassigned - available for immediate assignment")
        elif current_count < 3:
            reasons.append(f"Low workload ({current_count} assignments)")
        
        if admin.admin_level >= 7:
            reasons.append("Senior admin with advanced permissions")
        
        if admin.is_super_admin:
            reasons.append("Super admin with full platform access")
        
        return "; ".join(reasons) if reasons else "Available for assignment"

    # ==================== ASSIGNMENT ANALYTICS ====================

    async def track_assignment_history(
        self,
        admin_id: Optional[UUID] = None,
        hostel_id: Optional[UUID] = None,
        limit: int = 50
    ) -> List[AssignmentHistory]:
        """Get assignment history with filters."""
        stmt = (
            select(AssignmentHistory)
            .options(
                selectinload(AssignmentHistory.admin),
                selectinload(AssignmentHistory.hostel)
            )
            .order_by(desc(AssignmentHistory.action_timestamp))
            .limit(limit)
        )

        if admin_id:
            stmt = stmt.where(AssignmentHistory.admin_id == admin_id)
        
        if hostel_id:
            stmt = stmt.where(AssignmentHistory.hostel_id == hostel_id)

        result = await self.db.execute(stmt)
        return result.unique().scalars().all()

    async def get_assignment_statistics(
        self,
        admin_id: Optional[UUID] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> Dict[str, Any]:
        """Get comprehensive assignment statistics."""
        if not start_date:
            start_date = date.today() - timedelta(days=30)
        if not end_date:
            end_date = date.today()

        base_filter = and_(
            AdminHostelAssignment.is_deleted == False,
            AdminHostelAssignment.assigned_date >= start_date,
            AdminHostelAssignment.assigned_date <= end_date
        )

        if admin_id:
            base_filter = and_(base_filter, AdminHostelAssignment.admin_id == admin_id)

        # Total assignments
        total_stmt = select(func.count(AdminHostelAssignment.id)).where(base_filter)
        total = await self.db.scalar(total_stmt)

        # Active assignments
        active_stmt = select(func.count(AdminHostelAssignment.id)).where(
            and_(base_filter, AdminHostelAssignment.is_active == True)
        )
        active = await self.db.scalar(active_stmt)

        # Average duration
        avg_duration_stmt = select(
            func.avg(AdminHostelAssignment.assignment_duration_days)
        ).where(base_filter)
        avg_duration = await self.db.scalar(avg_duration_stmt)

        return {
            'period': {'start': start_date, 'end': end_date},
            'total_assignments': total,
            'active_assignments': active,
            'revoked_assignments': total - active,
            'avg_assignment_duration_days': float(avg_duration) if avg_duration else 0,
            'admin_id': admin_id
        }

    async def update_activity_metrics(
        self,
        assignment_id: UUID,
        actions_performed: int = 1,
        decisions_made: int = 0,
        session_duration_minutes: int = 0
    ) -> AdminHostelAssignment:
        """Update assignment activity metrics."""
        assignment = await self.find_by_id(assignment_id)
        if not assignment:
            raise EntityNotFoundError(f"Assignment {assignment_id} not found")

        assignment.last_accessed = datetime.utcnow()
        assignment.access_count += 1
        assignment.actions_performed += actions_performed
        assignment.decisions_made += decisions_made
        assignment.total_session_time_minutes += session_duration_minutes

        await self.db.flush()
        return assignment

    # ==================== HELPER METHODS ====================

    async def _get_active_assignment_count(self, admin_id: UUID) -> int:
        """Get count of active assignments for admin."""
        stmt = select(func.count(AdminHostelAssignment.id)).where(
            and_(
                AdminHostelAssignment.admin_id == admin_id,
                AdminHostelAssignment.is_active == True,
                AdminHostelAssignment.is_deleted == False
            )
        )
        return await self.db.scalar(stmt) or 0

    async def _check_assignment_conflicts(
        self,
        admin_id: UUID,
        hostel_ids: List[UUID]
    ) -> List[UUID]:
        """Check for existing active assignments."""
        stmt = (
            select(AdminHostelAssignment.hostel_id)
            .where(AdminHostelAssignment.admin_id == admin_id)
            .where(AdminHostelAssignment.hostel_id.in_(hostel_ids))
            .where(AdminHostelAssignment.is_active == True)
            .where(AdminHostelAssignment.is_deleted == False)
        )

        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def _validate_hostels_exist(self, hostel_ids: List[UUID]) -> None:
        """Validate all hostels exist."""
        stmt = select(func.count(Hostel.id)).where(
            and_(
                Hostel.id.in_(hostel_ids),
                Hostel.is_deleted == False
            )
        )
        count = await self.db.scalar(stmt)
        
        if count != len(hostel_ids):
            raise ValidationError("One or more hostels not found")

    async def _create_assignment_history(
        self,
        assignment_id: UUID,
        admin_id: UUID,
        hostel_id: UUID,
        action: str,
        performed_by_id: UUID,
        old_values: Optional[Dict] = None,
        new_values: Optional[Dict] = None,
        reason: Optional[str] = None
    ) -> AssignmentHistory:
        """Create assignment history record."""
        # Determine changed fields
        changed_fields = []
        if old_values and new_values:
            changed_fields = [
                key for key in new_values.keys()
                if old_values.get(key) != new_values.get(key)
            ]

        history = AssignmentHistory(
            assignment_id=assignment_id,
            admin_id=admin_id,
            hostel_id=hostel_id,
            action=action,
            action_timestamp=datetime.utcnow(),
            performed_by_id=performed_by_id,
            old_values=old_values,
            new_values=new_values,
            changed_fields=changed_fields,
            reason=reason
        )

        self.db.add(history)
        await self.db.flush()
        return history

    def _assignment_to_dict(self, assignment: AdminHostelAssignment) -> Dict[str, Any]:
        """Convert assignment to dictionary for audit."""
        return {
            'is_active': assignment.is_active,
            'is_primary': assignment.is_primary,
            'permission_level': assignment.permission_level,
            'permissions': assignment.permissions,
            'effective_from': assignment.effective_from.isoformat() if assignment.effective_from else None,
            'effective_until': assignment.effective_until.isoformat() if assignment.effective_until else None,
        }