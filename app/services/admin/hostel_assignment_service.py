"""
Hostel Assignment Service

Business logic for managing admin-hostel assignments including
workload balancing, transfer workflows, and coverage optimization.
"""

from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime, date, timedelta
from sqlalchemy.orm import Session

from app.models.admin.admin_hostel_assignment import (
    AdminHostelAssignment,
    AssignmentHistory
)
from app.repositories.admin.admin_hostel_assignment_repository import (
    AdminHostelAssignmentRepository
)
from app.repositories.admin.admin_user_repository import AdminUserRepository
from app.core.exceptions import (
    ValidationError,
    EntityNotFoundError,
    BusinessRuleViolationError,
    ConflictError
)


class HostelAssignmentService:
    """
    Assignment management service with:
    - Multi-hostel assignment with validation
    - Workload balancing and optimization
    - Transfer workflows with handover
    - Coverage gap analysis
    - Assignment analytics
    """

    def __init__(self, db: Session):
        self.db = db
        self.assignment_repo = AdminHostelAssignmentRepository(db)
        self.admin_repo = AdminUserRepository(db)

        # Configuration
        self.max_assignments_per_admin = 5  # Default limit
        self.min_admins_per_hostel = 1
        self.handover_period_days = 7

    # ==================== ASSIGNMENT CREATION ====================

    async def assign_admin_to_hostel(
        self,
        admin_id: UUID,
        hostel_id: UUID,
        assigned_by_id: UUID,
        permissions: Optional[Dict] = None,
        effective_from: Optional[date] = None,
        effective_until: Optional[date] = None,
        notes: Optional[str] = None,
        set_as_primary: bool = False
    ) -> AdminHostelAssignment:
        """
        Assign admin to single hostel with validation.
        
        Args:
            admin_id: Admin to assign
            hostel_id: Hostel ID
            assigned_by_id: Who is making assignment
            permissions: Optional permission overrides
            effective_from: Start date
            effective_until: End date
            notes: Assignment notes
            set_as_primary: Set as primary hostel
            
        Returns:
            Created assignment
        """
        # Validate assigning admin has authority
        await self._validate_assignment_authority(assigned_by_id, hostel_id)

        # Check workload limits
        await self._validate_workload_limits(admin_id)

        # Create assignment
        assignment = await self.assignment_repo.assign_single_hostel(
            admin_id=admin_id,
            hostel_id=hostel_id,
            assigned_by_id=assigned_by_id,
            permissions=permissions,
            effective_from=effective_from,
            effective_until=effective_until,
            notes=notes,
            set_first_as_primary=set_as_primary
        )

        # Set as primary if requested
        if set_as_primary:
            await self.assignment_repo.set_primary_hostel(
                admin_id=admin_id,
                hostel_id=hostel_id,
                set_by_id=assigned_by_id,
                reason="Set during assignment"
            )

        await self.db.commit()
        return assignment

    async def assign_admin_to_multiple_hostels(
        self,
        admin_id: UUID,
        hostel_ids: List[UUID],
        assigned_by_id: UUID,
        permissions: Optional[Dict] = None,
        set_first_as_primary: bool = True
    ) -> List[AdminHostelAssignment]:
        """Assign admin to multiple hostels at once."""
        # Validate assigning admin
        assigner = await self.admin_repo.find_by_id(assigned_by_id)
        if not assigner:
            raise EntityNotFoundError(f"Assigning admin {assigned_by_id} not found")

        # Create assignments
        assignments = await self.assignment_repo.assign_admin_to_hostels(
            admin_id=admin_id,
            hostel_ids=hostel_ids,
            assigned_by_id=assigned_by_id,
            permissions=permissions,
            set_first_as_primary=set_first_as_primary
        )

        await self.db.commit()
        return assignments

    async def _validate_assignment_authority(
        self,
        assigning_admin_id: UUID,
        hostel_id: UUID
    ) -> None:
        """Validate admin has authority to make assignment."""
        assigner = await self.admin_repo.find_by_id(assigning_admin_id)
        if not assigner:
            raise EntityNotFoundError(f"Admin {assigning_admin_id} not found")

        # Super admin can assign anyone
        if assigner.is_super_admin:
            return

        # Must have can_manage_admins permission
        if not assigner.can_manage_admins:
            raise ValidationError("Insufficient permissions to assign admins")

        # Must have access to the hostel
        if not assigner.can_access_all_hostels:
            assignment = await self.assignment_repo.find_assignment(
                assigning_admin_id,
                hostel_id
            )
            if not assignment or not assignment.is_active:
                raise ValidationError(
                    f"Admin does not have access to hostel {hostel_id}"
                )

    async def _validate_workload_limits(self, admin_id: UUID) -> None:
        """Validate admin hasn't exceeded assignment limits."""
        admin = await self.admin_repo.find_by_id(admin_id)
        if not admin:
            raise EntityNotFoundError(f"Admin {admin_id} not found")

        # Check current assignment count
        current_count = await self.assignment_repo._get_active_assignment_count(
            admin_id
        )

        # Check against admin-specific limit
        if admin.max_hostel_limit:
            if current_count >= admin.max_hostel_limit:
                raise BusinessRuleViolationError(
                    f"Admin has reached maximum assignment limit "
                    f"({admin.max_hostel_limit})"
                )
        # Check against global limit
        elif current_count >= self.max_assignments_per_admin:
            raise BusinessRuleViolationError(
                f"Admin has reached maximum assignment limit "
                f"({self.max_assignments_per_admin})"
            )

    # ==================== ASSIGNMENT QUERIES ====================

    async def get_admin_assignments(
        self,
        admin_id: UUID,
        include_inactive: bool = False,
        include_expired: bool = False
    ) -> List[AdminHostelAssignment]:
        """Get all assignments for admin."""
        return await self.assignment_repo.get_admin_assignments(
            admin_id=admin_id,
            include_inactive=include_inactive,
            include_expired=include_expired
        )

    async def get_hostel_assignments(
        self,
        hostel_id: UUID,
        include_inactive: bool = False
    ) -> List[AdminHostelAssignment]:
        """Get all admin assignments for hostel."""
        return await self.assignment_repo.get_hostel_assignments(
            hostel_id=hostel_id,
            include_inactive=include_inactive
        )

    async def get_primary_assignment(
        self,
        admin_id: UUID
    ) -> Optional[AdminHostelAssignment]:
        """Get admin's primary hostel assignment."""
        return await self.assignment_repo.get_primary_assignment(admin_id)

    async def find_assignment(
        self,
        admin_id: UUID,
        hostel_id: UUID
    ) -> Optional[AdminHostelAssignment]:
        """Find specific assignment."""
        return await self.assignment_repo.find_assignment(admin_id, hostel_id)

    # ==================== ASSIGNMENT UPDATES ====================

    async def update_assignment(
        self,
        assignment_id: UUID,
        updates: Dict[str, Any],
        updated_by_id: UUID,
        reason: Optional[str] = None
    ) -> AdminHostelAssignment:
        """Update assignment with validation."""
        assignment = await self.assignment_repo.find_by_id(assignment_id)
        if not assignment:
            raise EntityNotFoundError(f"Assignment {assignment_id} not found")

        # Validate authority
        await self._validate_assignment_authority(
            updated_by_id,
            assignment.hostel_id
        )

        # Update
        updated_assignment = await self.assignment_repo.update_assignment(
            assignment_id=assignment_id,
            updates=updates,
            updated_by_id=updated_by_id,
            reason=reason
        )

        await self.db.commit()
        return updated_assignment

    async def revoke_assignment(
        self,
        assignment_id: UUID,
        revoked_by_id: UUID,
        reason: str,
        revoke_date: Optional[date] = None
    ) -> AdminHostelAssignment:
        """Revoke an assignment."""
        assignment = await self.assignment_repo.find_by_id(assignment_id)
        if not assignment:
            raise EntityNotFoundError(f"Assignment {assignment_id} not found")

        # Validate authority
        await self._validate_assignment_authority(
            revoked_by_id,
            assignment.hostel_id
        )

        # Check hostel coverage
        await self._validate_hostel_coverage_after_revocation(
            assignment.hostel_id,
            assignment.admin_id
        )

        # Revoke
        revoked_assignment = await self.assignment_repo.revoke_assignment(
            assignment_id=assignment_id,
            revoked_by_id=revoked_by_id,
            reason=reason,
            revoke_date=revoke_date
        )

        await self.db.commit()
        return revoked_assignment

    async def _validate_hostel_coverage_after_revocation(
        self,
        hostel_id: UUID,
        admin_id: UUID
    ) -> None:
        """Ensure hostel will still have minimum coverage."""
        assignments = await self.assignment_repo.get_hostel_assignments(
            hostel_id,
            include_inactive=False
        )

        # Count active assignments excluding the one being revoked
        active_count = len([
            a for a in assignments 
            if a.admin_id != admin_id and a.is_active
        ])

        if active_count < self.min_admins_per_hostel:
            raise BusinessRuleViolationError(
                f"Cannot revoke assignment - hostel would have less than "
                f"minimum required admins ({self.min_admins_per_hostel})"
            )

    async def reactivate_assignment(
        self,
        assignment_id: UUID,
        reactivated_by_id: UUID,
        reason: Optional[str] = None
    ) -> AdminHostelAssignment:
        """Reactivate a revoked assignment."""
        assignment = await self.assignment_repo.find_by_id(assignment_id)
        if not assignment:
            raise EntityNotFoundError(f"Assignment {assignment_id} not found")

        # Validate workload limits
        await self._validate_workload_limits(assignment.admin_id)

        # Reactivate
        reactivated = await self.assignment_repo.reactivate_assignment(
            assignment_id=assignment_id,
            reactivated_by_id=reactivated_by_id,
            reason=reason
        )

        await self.db.commit()
        return reactivated

    # ==================== PRIMARY HOSTEL MANAGEMENT ====================

    async def set_primary_hostel(
        self,
        admin_id: UUID,
        hostel_id: UUID,
        set_by_id: UUID,
        reason: Optional[str] = None
    ) -> AdminHostelAssignment:
        """Set primary hostel for admin."""
        assignment = await self.assignment_repo.set_primary_hostel(
            admin_id=admin_id,
            hostel_id=hostel_id,
            set_by_id=set_by_id,
            reason=reason
        )

        await self.db.commit()
        return assignment

    async def get_primary_hostel_history(
        self,
        admin_id: UUID
    ) -> List:
        """Get history of primary hostel changes."""
        from sqlalchemy import select
        from app.models.admin.admin_hostel_assignment import PrimaryHostelDesignation
        
        stmt = (
            select(PrimaryHostelDesignation)
            .where(PrimaryHostelDesignation.admin_id == admin_id)
            .order_by(PrimaryHostelDesignation.designated_from.desc())
        )
        
        result = await self.db.execute(stmt)
        return result.scalars().all()

    # ==================== TRANSFER WORKFLOWS ====================

    async def transfer_responsibilities(
        self,
        from_admin_id: UUID,
        to_admin_id: UUID,
        hostel_ids: Optional[List[UUID]] = None,
        transferred_by_id: UUID,
        transfer_notes: Optional[str] = None,
        require_handover: bool = True
    ) -> Dict[str, Any]:
        """
        Transfer hostel responsibilities between admins.
        
        Returns:
            Transfer summary with details
        """
        # Validate transfer authority
        await self._validate_transfer_authority(
            transferred_by_id,
            from_admin_id,
            to_admin_id
        )

        # Validate target admin capacity
        await self._validate_transfer_capacity(to_admin_id, hostel_ids)

        # Execute transfer
        result = await self.assignment_repo.transfer_responsibilities(
            from_admin_id=from_admin_id,
            to_admin_id=to_admin_id,
            hostel_ids=hostel_ids,
            transferred_by_id=transferred_by_id,
            transfer_notes=transfer_notes,
            require_handover=require_handover
        )

        await self.db.commit()

        # Notify both admins
        await self._notify_transfer(result)

        return result

    async def _validate_transfer_authority(
        self,
        transferring_admin_id: UUID,
        from_admin_id: UUID,
        to_admin_id: UUID
    ) -> None:
        """Validate admin has authority to transfer."""
        transferrer = await self.admin_repo.find_by_id(transferring_admin_id)
        if not transferrer:
            raise EntityNotFoundError(f"Admin {transferring_admin_id} not found")

        # Super admin can transfer
        if transferrer.is_super_admin:
            return

        # Must have can_manage_admins
        if not transferrer.can_manage_admins:
            raise ValidationError("Insufficient permissions to transfer assignments")

        # Check hierarchy - cannot transfer from higher level admin
        from_admin = await self.admin_repo.find_by_id(from_admin_id)
        if from_admin and from_admin.admin_level > transferrer.admin_level:
            raise ValidationError(
                "Cannot transfer from admin with higher level"
            )

    async def _validate_transfer_capacity(
        self,
        to_admin_id: UUID,
        hostel_ids: Optional[List[UUID]]
    ) -> None:
        """Validate target admin has capacity for transfer."""
        to_admin = await self.admin_repo.find_by_id(to_admin_id)
        if not to_admin:
            raise EntityNotFoundError(f"Target admin {to_admin_id} not found")

        # Get current assignment count
        current_count = await self.assignment_repo._get_active_assignment_count(
            to_admin_id
        )

        # Calculate new total
        transfer_count = len(hostel_ids) if hostel_ids else 0
        new_total = current_count + transfer_count

        # Check limits
        if to_admin.max_hostel_limit:
            if new_total > to_admin.max_hostel_limit:
                raise BusinessRuleViolationError(
                    f"Transfer would exceed target admin's limit "
                    f"({to_admin.max_hostel_limit})"
                )
        elif new_total > self.max_assignments_per_admin:
            raise BusinessRuleViolationError(
                f"Transfer would exceed maximum assignment limit "
                f"({self.max_assignments_per_admin})"
            )

    async def _notify_transfer(self, transfer_result: Dict[str, Any]) -> None:
        """Notify admins of transfer."""
        # Implementation would send notifications
        pass

    async def complete_handover(
        self,
        assignment_id: UUID,
        completed_by_id: UUID,
        notes: Optional[str] = None
    ) -> AdminHostelAssignment:
        """Mark handover as completed."""
        assignment = await self.assignment_repo.complete_handover(
            assignment_id=assignment_id,
            completed_by_id=completed_by_id,
            notes=notes
        )

        await self.db.commit()
        return assignment

    async def get_pending_handovers(
        self,
        admin_id: Optional[UUID] = None
    ) -> List[AdminHostelAssignment]:
        """Get assignments with pending handovers."""
        from sqlalchemy import select
        
        stmt = (
            select(AdminHostelAssignment)
            .where(AdminHostelAssignment.transferred_from_id.isnot(None))
            .where(AdminHostelAssignment.handover_completed == False)
            .where(AdminHostelAssignment.is_active == True)
        )

        if admin_id:
            stmt = stmt.where(AdminHostelAssignment.admin_id == admin_id)

        result = await self.db.execute(stmt)
        return result.scalars().all()

    # ==================== WORKLOAD MANAGEMENT ====================

    async def balance_workload(
        self,
        target_assignments_per_admin: int = 3,
        max_variance: int = 1
    ) -> Dict[str, Any]:
        """Analyze and get workload balancing recommendations."""
        return await self.assignment_repo.balance_workload(
            target_assignments_per_admin=target_assignments_per_admin,
            max_variance=max_variance
        )

    async def find_overloaded_admins(
        self,
        threshold: int = 5
    ) -> List[Dict[str, Any]]:
        """Find admins exceeding workload threshold."""
        return await self.assignment_repo.find_overloaded_admins(threshold)

    async def auto_balance_workload(
        self,
        initiated_by_id: UUID,
        dry_run: bool = True
    ) -> Dict[str, Any]:
        """
        Automatically balance workload across admins.
        
        Args:
            initiated_by_id: Admin initiating balance
            dry_run: If True, only return plan without executing
            
        Returns:
            Balancing plan and results
        """
        # Get balancing recommendations
        analysis = await self.balance_workload()

        if not analysis['recommendations']:
            return {
                'balanced': True,
                'actions_needed': 0,
                'recommendations': [],
                'executed': []
            }

        results = {
            'balanced': False,
            'actions_needed': len(analysis['recommendations']),
            'recommendations': analysis['recommendations'],
            'executed': []
        }

        if dry_run:
            return results

        # Execute recommendations
        for recommendation in analysis['recommendations']:
            try:
                # Get hostels to transfer (simplified - would need actual hostel selection)
                from_admin_id = recommendation['from_admin_id']
                to_admin_id = recommendation['to_admin_id']
                
                # Transfer suggested number of hostels
                # This is simplified - real implementation would intelligently select which hostels
                transfer_result = await self.transfer_responsibilities(
                    from_admin_id=from_admin_id,
                    to_admin_id=to_admin_id,
                    hostel_ids=None,  # Would select specific hostels
                    transferred_by_id=initiated_by_id,
                    transfer_notes="Automatic workload balancing"
                )

                results['executed'].append({
                    'success': True,
                    'from_admin': from_admin_id,
                    'to_admin': to_admin_id,
                    'transferred_count': transfer_result['transfer_count']
                })
            except Exception as e:
                results['executed'].append({
                    'success': False,
                    'from_admin': recommendation['from_admin_id'],
                    'to_admin': recommendation['to_admin_id'],
                    'error': str(e)
                })

        return results

    # ==================== COVERAGE ANALYSIS ====================

    async def get_coverage_gaps(self) -> List[Dict[str, Any]]:
        """Identify hostels without adequate admin coverage."""
        return await self.assignment_repo.get_coverage_gaps()

    async def recommend_assignments(
        self,
        hostel_id: UUID,
        criteria: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Recommend admins for hostel assignment."""
        return await self.assignment_repo.recommend_assignments(
            hostel_id=hostel_id,
            criteria=criteria
        )

    async def analyze_coverage_health(self) -> Dict[str, Any]:
        """Analyze overall coverage health across all hostels."""
        gaps = await self.get_coverage_gaps()
        
        from sqlalchemy import select, func
        from app.models.hostel.hostel import Hostel
        
        # Get total hostels
        total_stmt = select(func.count(Hostel.id)).where(
            Hostel.is_deleted == False
        )
        total_hostels = await self.db.scalar(total_stmt) or 0

        # Calculate metrics
        coverage_percentage = (
            ((total_hostels - len(gaps)) / total_hostels * 100)
            if total_hostels > 0 else 0
        )

        return {
            'total_hostels': total_hostels,
            'hostels_with_coverage': total_hostels - len(gaps),
            'hostels_without_coverage': len(gaps),
            'coverage_percentage': round(coverage_percentage, 2),
            'health_status': self._determine_coverage_health(coverage_percentage),
            'gaps': gaps
        }

    def _determine_coverage_health(self, coverage_percentage: float) -> str:
        """Determine coverage health status."""
        if coverage_percentage >= 95:
            return 'excellent'
        elif coverage_percentage >= 85:
            return 'good'
        elif coverage_percentage >= 70:
            return 'fair'
        else:
            return 'critical'

    # ==================== ASSIGNMENT ANALYTICS ====================

    async def get_assignment_statistics(
        self,
        admin_id: Optional[UUID] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> Dict[str, Any]:
        """Get comprehensive assignment statistics."""
        return await self.assignment_repo.get_assignment_statistics(
            admin_id=admin_id,
            start_date=start_date,
            end_date=end_date
        )

    async def get_assignment_history(
        self,
        admin_id: Optional[UUID] = None,
        hostel_id: Optional[UUID] = None,
        limit: int = 50
    ) -> List[AssignmentHistory]:
        """Get assignment change history."""
        return await self.assignment_repo.track_assignment_history(
            admin_id=admin_id,
            hostel_id=hostel_id,
            limit=limit
        )

    async def get_assignment_trends(
        self,
        days: int = 90
    ) -> Dict[str, Any]:
        """Get assignment trends over time."""
        end_date = date.today()
        start_date = end_date - timedelta(days=days)

        # Get statistics for each week
        trends = []
        current_date = start_date
        
        while current_date <= end_date:
            week_end = min(current_date + timedelta(days=7), end_date)
            
            stats = await self.get_assignment_statistics(
                start_date=current_date,
                end_date=week_end
            )
            
            trends.append({
                'period_start': current_date,
                'period_end': week_end,
                'total_assignments': stats['total_assignments'],
                'active_assignments': stats['active_assignments']
            })
            
            current_date = week_end + timedelta(days=1)

        return {
            'period_days': days,
            'trends': trends,
            'overall_growth': self._calculate_growth_rate(trends)
        }

    def _calculate_growth_rate(self, trends: List[Dict]) -> float:
        """Calculate assignment growth rate."""
        if len(trends) < 2:
            return 0.0

        first_count = trends[0]['total_assignments']
        last_count = trends[-1]['total_assignments']

        if first_count == 0:
            return 0.0

        return ((last_count - first_count) / first_count) * 100

    # ==================== BULK OPERATIONS ====================

    async def bulk_assign_admin(
        self,
        admin_id: UUID,
        hostel_ids: List[UUID],
        assigned_by_id: UUID
    ) -> Dict[str, Any]:
        """Bulk assign admin to multiple hostels."""
        results = {
            'success': [],
            'failed': []
        }

        for hostel_id in hostel_ids:
            try:
                assignment = await self.assign_admin_to_hostel(
                    admin_id=admin_id,
                    hostel_id=hostel_id,
                    assigned_by_id=assigned_by_id
                )
                results['success'].append({
                    'hostel_id': str(hostel_id),
                    'assignment_id': str(assignment.id)
                })
            except Exception as e:
                results['failed'].append({
                    'hostel_id': str(hostel_id),
                    'error': str(e)
                })

        return results

    async def bulk_revoke_assignments(
        self,
        assignment_ids: List[UUID],
        revoked_by_id: UUID,
        reason: str
    ) -> Dict[str, Any]:
        """Bulk revoke multiple assignments."""
        results = {
            'success': [],
            'failed': []
        }

        for assignment_id in assignment_ids:
            try:
                assignment = await self.revoke_assignment(
                    assignment_id=assignment_id,
                    revoked_by_id=revoked_by_id,
                    reason=reason
                )
                results['success'].append(str(assignment_id))
            except Exception as e:
                results['failed'].append({
                    'assignment_id': str(assignment_id),
                    'error': str(e)
                })

        return results