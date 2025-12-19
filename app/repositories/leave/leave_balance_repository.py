"""
Leave Balance Repository

Comprehensive leave balance and quota management with tracking,
adjustments, carry forward, and analytics.
"""

from datetime import date, datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID
from decimal import Decimal

from sqlalchemy import and_, or_, func, case
from sqlalchemy.orm import Session

from app.models.leave.leave_balance import (
    LeaveBalance,
    LeaveQuota,
    LeaveUsage,
    LeaveCarryForward,
    LeaveAdjustment,
)
from app.models.common.enums import LeaveType
from app.repositories.base.base_repository import BaseRepository
from app.repositories.base.pagination import PaginationParams, PaginatedResult


class LeaveBalanceRepository(BaseRepository[LeaveBalance]):
    """
    Leave balance repository with quota and usage tracking.
    
    Features:
    - Balance calculation and tracking
    - Quota management
    - Usage recording
    - Carry forward processing
    - Manual adjustments
    - Analytics and reporting
    """

    def __init__(self, session: Session):
        """Initialize repository with database session."""
        super().__init__(session, LeaveBalance)

    # ============================================================================
    # CORE BALANCE OPERATIONS
    # ============================================================================

    def get_or_create_balance(
        self,
        student_id: UUID,
        leave_type: LeaveType,
        academic_year_start: date,
        academic_year_end: date,
        allocated_days: int = 0
    ) -> LeaveBalance:
        """
        Get existing balance or create new one.
        
        Args:
            student_id: Student ID
            leave_type: Leave type
            academic_year_start: Academic year start
            academic_year_end: Academic year end
            allocated_days: Initial allocation
            
        Returns:
            Leave balance
        """
        balance = self.session.query(LeaveBalance).filter(
            LeaveBalance.student_id == student_id,
            LeaveBalance.leave_type == leave_type,
            LeaveBalance.academic_year_start == academic_year_start
        ).first()
        
        if not balance:
            balance = LeaveBalance(
                student_id=student_id,
                leave_type=leave_type,
                academic_year_start=academic_year_start,
                academic_year_end=academic_year_end,
                allocated_days=allocated_days,
                remaining_days=allocated_days,
                last_calculated_at=datetime.utcnow()
            )
            self.session.add(balance)
            self.session.flush()
        
        return balance

    def get_student_balance(
        self,
        student_id: UUID,
        leave_type: LeaveType,
        academic_year_start: Optional[date] = None
    ) -> Optional[LeaveBalance]:
        """
        Get leave balance for student.
        
        Args:
            student_id: Student ID
            leave_type: Leave type
            academic_year_start: Academic year (default: current)
            
        Returns:
            Leave balance or None
        """
        if academic_year_start is None:
            academic_year_start = self._get_current_academic_year_start()
        
        return self.session.query(LeaveBalance).filter(
            LeaveBalance.student_id == student_id,
            LeaveBalance.leave_type == leave_type,
            LeaveBalance.academic_year_start == academic_year_start,
            LeaveBalance.is_active == True
        ).first()

    def get_all_student_balances(
        self,
        student_id: UUID,
        academic_year_start: Optional[date] = None,
        active_only: bool = True
    ) -> List[LeaveBalance]:
        """
        Get all leave balances for student.
        
        Args:
            student_id: Student ID
            academic_year_start: Academic year (default: current)
            active_only: Return only active balances
            
        Returns:
            List of leave balances
        """
        if academic_year_start is None:
            academic_year_start = self._get_current_academic_year_start()
        
        query = self.session.query(LeaveBalance).filter(
            LeaveBalance.student_id == student_id,
            LeaveBalance.academic_year_start == academic_year_start
        )
        
        if active_only:
            query = query.filter(LeaveBalance.is_active == True)
        
        return query.all()

    def update_balance(
        self,
        balance_id: UUID,
        days_used: int = 0,
        days_pending: int = 0,
        recalculate: bool = True
    ) -> Optional[LeaveBalance]:
        """
        Update leave balance.
        
        Args:
            balance_id: Balance ID
            days_used: Additional days used
            days_pending: Additional days pending
            recalculate: Recalculate remaining days
            
        Returns:
            Updated balance or None
        """
        balance = self.find_by_id(balance_id)
        if not balance:
            return None
        
        balance.used_days += days_used
        balance.pending_days += days_pending
        
        if recalculate:
            balance.remaining_days = (
                balance.allocated_days +
                balance.carry_forward_days -
                balance.used_days -
                balance.pending_days
            )
        
        balance.last_calculated_at = datetime.utcnow()
        
        self.session.flush()
        return balance

    def recalculate_balance(
        self,
        balance_id: UUID
    ) -> Optional[LeaveBalance]:
        """
        Recalculate balance from usage records.
        
        Args:
            balance_id: Balance ID
            
        Returns:
            Recalculated balance or None
        """
        balance = self.find_by_id(balance_id)
        if not balance:
            return None
        
        # Calculate used days from approved leaves
        used_days = self.session.query(
            func.coalesce(func.sum(LeaveUsage.days_used), 0)
        ).filter(
            LeaveUsage.balance_id == balance_id,
            LeaveUsage.usage_type == 'approved'
        ).scalar() or 0
        
        # Calculate pending days from pending applications
        from app.models.leave.leave_application import LeaveApplication
        from app.models.common.enums import LeaveStatus
        
        pending_days = self.session.query(
            func.coalesce(func.sum(LeaveApplication.total_days), 0)
        ).filter(
            LeaveApplication.student_id == balance.student_id,
            LeaveApplication.leave_type == balance.leave_type,
            LeaveApplication.status == LeaveStatus.PENDING,
            LeaveApplication.from_date >= balance.academic_year_start,
            LeaveApplication.from_date < balance.academic_year_end,
            LeaveApplication.deleted_at.is_(None)
        ).scalar() or 0
        
        balance.used_days = int(used_days)
        balance.pending_days = int(pending_days)
        balance.remaining_days = (
            balance.allocated_days +
            balance.carry_forward_days -
            balance.used_days -
            balance.pending_days
        )
        balance.last_calculated_at = datetime.utcnow()
        
        self.session.flush()
        return balance

    # ============================================================================
    # QUOTA MANAGEMENT
    # ============================================================================

    def get_quota(
        self,
        hostel_id: UUID,
        leave_type: LeaveType,
        effective_date: Optional[date] = None
    ) -> Optional[LeaveQuota]:
        """
        Get leave quota configuration.
        
        Args:
            hostel_id: Hostel ID
            leave_type: Leave type
            effective_date: Date to check (default: today)
            
        Returns:
            Leave quota or None
        """
        if effective_date is None:
            effective_date = date.today()
        
        return self.session.query(LeaveQuota).filter(
            LeaveQuota.hostel_id == hostel_id,
            LeaveQuota.leave_type == leave_type,
            LeaveQuota.effective_from <= effective_date,
            or_(
                LeaveQuota.effective_to.is_(None),
                LeaveQuota.effective_to >= effective_date
            ),
            LeaveQuota.is_active == True
        ).first()

    def create_quota(
        self,
        hostel_id: UUID,
        leave_type: LeaveType,
        quota_data: Dict[str, Any]
    ) -> LeaveQuota:
        """
        Create leave quota.
        
        Args:
            hostel_id: Hostel ID
            leave_type: Leave type
            quota_data: Quota configuration
            
        Returns:
            Created quota
        """
        quota = LeaveQuota(
            hostel_id=hostel_id,
            leave_type=leave_type,
            **quota_data
        )
        
        self.session.add(quota)
        self.session.flush()
        
        return quota

    def update_quota(
        self,
        quota_id: UUID,
        update_data: Dict[str, Any]
    ) -> Optional[LeaveQuota]:
        """
        Update leave quota.
        
        Args:
            quota_id: Quota ID
            update_data: Fields to update
            
        Returns:
            Updated quota or None
        """
        quota = self.session.query(LeaveQuota).filter(
            LeaveQuota.id == quota_id
        ).first()
        
        if not quota:
            return None
        
        for key, value in update_data.items():
            if hasattr(quota, key):
                setattr(quota, key, value)
        
        self.session.flush()
        return quota

    def get_hostel_quotas(
        self,
        hostel_id: UUID,
        active_only: bool = True
    ) -> List[LeaveQuota]:
        """
        Get all quotas for hostel.
        
        Args:
            hostel_id: Hostel ID
            active_only: Return only active quotas
            
        Returns:
            List of quotas
        """
        query = self.session.query(LeaveQuota).filter(
            LeaveQuota.hostel_id == hostel_id
        )
        
        if active_only:
            query = query.filter(LeaveQuota.is_active == True)
        
        return query.all()

    # ============================================================================
    # USAGE TRACKING
    # ============================================================================

    def record_usage(
        self,
        balance_id: UUID,
        leave_id: UUID,
        usage_date: date,
        days_used: Decimal,
        usage_type: str = 'approved',
        metadata: Optional[Dict[str, Any]] = None
    ) -> LeaveUsage:
        """
        Record leave usage.
        
        Args:
            balance_id: Balance ID
            leave_id: Leave application ID
            usage_date: Date of usage
            days_used: Days used
            usage_type: Usage type
            metadata: Optional metadata
            
        Returns:
            Created usage record
        """
        usage = LeaveUsage(
            balance_id=balance_id,
            leave_id=leave_id,
            usage_date=usage_date,
            days_used=days_used,
            usage_type=usage_type,
            applied_at=datetime.utcnow(),
            approved_at=datetime.utcnow() if usage_type == 'approved' else None,
            days_notice=metadata.get('days_notice', 0) if metadata else 0,
            was_backdated=metadata.get('was_backdated', False) if metadata else False,
            had_supporting_document=metadata.get('had_supporting_document', False) if metadata else False
        )
        
        self.session.add(usage)
        self.session.flush()
        
        return usage

    def get_usage_history(
        self,
        balance_id: UUID,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
        pagination: Optional[PaginationParams] = None
    ) -> PaginatedResult[LeaveUsage]:
        """
        Get usage history for balance.
        
        Args:
            balance_id: Balance ID
            from_date: Optional start date
            to_date: Optional end date
            pagination: Pagination parameters
            
        Returns:
            Paginated usage records
        """
        query = self.session.query(LeaveUsage).filter(
            LeaveUsage.balance_id == balance_id
        )
        
        if from_date:
            query = query.filter(LeaveUsage.usage_date >= from_date)
        
        if to_date:
            query = query.filter(LeaveUsage.usage_date <= to_date)
        
        query = query.order_by(LeaveUsage.usage_date.desc())
        
        return self._paginate_query(query, pagination)

    # ============================================================================
    # CARRY FORWARD
    # ============================================================================

    def process_carry_forward(
        self,
        student_id: UUID,
        leave_type: LeaveType,
        from_year_start: date,
        to_year_start: date,
        max_carry_forward_days: Optional[int] = None,
        expiry_months: Optional[int] = None,
        processed_by: Optional[UUID] = None
    ) -> LeaveCarryForward:
        """
        Process leave carry forward.
        
        Args:
            student_id: Student ID
            leave_type: Leave type
            from_year_start: Source year start
            to_year_start: Target year start
            max_carry_forward_days: Maximum days to carry
            expiry_months: Expiry period in months
            processed_by: User processing carry forward
            
        Returns:
            Carry forward record
        """
        # Get source balance
        from_year_end = date(from_year_start.year + 1, from_year_start.month, from_year_start.day)
        source_balance = self.get_student_balance(student_id, leave_type, from_year_start)
        
        if not source_balance:
            raise ValueError("Source balance not found")
        
        # Calculate carry forward
        eligible = source_balance.remaining_days
        
        if max_carry_forward_days is not None:
            carry_forward_days = min(eligible, max_carry_forward_days)
        else:
            carry_forward_days = eligible
        
        # Calculate expiry date
        expiry_date = None
        if expiry_months:
            expiry_date = to_year_start + timedelta(days=expiry_months * 30)
        
        # Create carry forward record
        to_year_end = date(to_year_start.year + 1, to_year_start.month, to_year_start.day)
        
        carry_forward = LeaveCarryForward(
            student_id=student_id,
            leave_type=leave_type,
            from_year_start=from_year_start,
            from_year_end=from_year_end,
            to_year_start=to_year_start,
            to_year_end=to_year_end,
            original_balance=source_balance.allocated_days,
            used_in_source_year=source_balance.used_days,
            eligible_for_carry_forward=eligible,
            days_carried_forward=carry_forward_days,
            expiry_date=expiry_date,
            processed_at=datetime.utcnow(),
            processed_by=processed_by
        )
        
        self.session.add(carry_forward)
        
        # Update target year balance
        target_balance = self.get_or_create_balance(
            student_id, leave_type, to_year_start, to_year_end
        )
        target_balance.carry_forward_days = carry_forward_days
        target_balance.remaining_days += carry_forward_days
        
        self.session.flush()
        
        return carry_forward

    def get_carry_forward(
        self,
        student_id: UUID,
        leave_type: LeaveType,
        to_year_start: date
    ) -> Optional[LeaveCarryForward]:
        """
        Get carry forward record.
        
        Args:
            student_id: Student ID
            leave_type: Leave type
            to_year_start: Target year start
            
        Returns:
            Carry forward record or None
        """
        return self.session.query(LeaveCarryForward).filter(
            LeaveCarryForward.student_id == student_id,
            LeaveCarryForward.leave_type == leave_type,
            LeaveCarryForward.to_year_start == to_year_start
        ).first()

    def expire_carry_forward(
        self,
        carry_forward_id: UUID
    ) -> Optional[LeaveCarryForward]:
        """
        Mark carry forward as expired.
        
        Args:
            carry_forward_id: Carry forward ID
            
        Returns:
            Updated carry forward or None
        """
        carry_forward = self.session.query(LeaveCarryForward).filter(
            LeaveCarryForward.id == carry_forward_id
        ).first()
        
        if not carry_forward:
            return None
        
        unused_days = carry_forward.days_carried_forward - carry_forward.days_used_from_carry_forward
        
        carry_forward.is_expired = True
        carry_forward.days_expired = unused_days
        
        # Update balance
        balance = self.get_student_balance(
            carry_forward.student_id,
            carry_forward.leave_type,
            carry_forward.to_year_start
        )
        
        if balance:
            balance.remaining_days -= unused_days
            balance.carry_forward_days -= unused_days
        
        self.session.flush()
        
        return carry_forward

    def find_expiring_carry_forwards(
        self,
        days_ahead: int = 30
    ) -> List[LeaveCarryForward]:
        """
        Find carry forwards expiring soon.
        
        Args:
            days_ahead: Number of days to look ahead
            
        Returns:
            List of expiring carry forwards
        """
        cutoff_date = date.today() + timedelta(days=days_ahead)
        
        return self.session.query(LeaveCarryForward).filter(
            LeaveCarryForward.is_expired == False,
            LeaveCarryForward.expiry_date.isnot(None),
            LeaveCarryForward.expiry_date <= cutoff_date
        ).all()

    # ============================================================================
    # ADJUSTMENTS
    # ============================================================================

    def create_adjustment(
        self,
        balance_id: UUID,
        adjustment_type: str,
        adjustment_days: int,
        adjustment_reason: str,
        adjusted_by: UUID,
        adjustment_category: Optional[str] = None,
        reference_number: Optional[str] = None,
        requires_approval: bool = False,
        audit_context: Optional[Dict[str, Any]] = None
    ) -> LeaveAdjustment:
        """
        Create balance adjustment.
        
        Args:
            balance_id: Balance ID
            adjustment_type: Type of adjustment
            adjustment_days: Days to adjust
            adjustment_reason: Reason for adjustment
            adjusted_by: User making adjustment
            adjustment_category: Optional category
            reference_number: Optional reference
            requires_approval: Whether approval needed
            audit_context: Audit information
            
        Returns:
            Created adjustment
        """
        balance = self.find_by_id(balance_id)
        if not balance:
            raise ValueError("Balance not found")
        
        balance_before = balance.remaining_days
        balance_after = balance_before + adjustment_days
        
        adjustment = LeaveAdjustment(
            balance_id=balance_id,
            adjustment_type=adjustment_type,
            adjustment_days=adjustment_days,
            adjustment_reason=adjustment_reason,
            adjustment_category=adjustment_category,
            balance_before=balance_before,
            balance_after=balance_after,
            adjustment_date=datetime.utcnow(),
            adjusted_by=adjusted_by,
            requires_approval=requires_approval,
            reference_number=reference_number
        )
        
        self.session.add(adjustment)
        
        # Apply adjustment if no approval required
        if not requires_approval:
            balance.allocated_days += adjustment_days
            balance.remaining_days = balance_after
            balance.last_calculated_at = datetime.utcnow()
        
        self.session.flush()
        
        return adjustment

    def approve_adjustment(
        self,
        adjustment_id: UUID,
        approver_id: UUID
    ) -> Optional[LeaveAdjustment]:
        """
        Approve balance adjustment.
        
        Args:
            adjustment_id: Adjustment ID
            approver_id: User approving
            
        Returns:
            Updated adjustment or None
        """
        adjustment = self.session.query(LeaveAdjustment).filter(
            LeaveAdjustment.id == adjustment_id
        ).first()
        
        if not adjustment or not adjustment.requires_approval:
            return None
        
        adjustment.is_approved = True
        adjustment.approved_by = approver_id
        adjustment.approved_at = datetime.utcnow()
        
        # Apply adjustment to balance
        balance = self.find_by_id(adjustment.balance_id)
        if balance:
            balance.allocated_days += adjustment.adjustment_days
            balance.remaining_days += adjustment.adjustment_days
            balance.last_calculated_at = datetime.utcnow()
        
        self.session.flush()
        
        return adjustment

    def get_adjustments(
        self,
        balance_id: UUID,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        pagination: Optional[PaginationParams] = None
    ) -> PaginatedResult[LeaveAdjustment]:
        """
        Get adjustment history.
        
        Args:
            balance_id: Balance ID
            from_date: Optional start date
            to_date: Optional end date
            pagination: Pagination parameters
            
        Returns:
            Paginated adjustments
        """
        query = self.session.query(LeaveAdjustment).filter(
            LeaveAdjustment.balance_id == balance_id
        )
        
        if from_date:
            query = query.filter(LeaveAdjustment.adjustment_date >= from_date)
        
        if to_date:
            query = query.filter(LeaveAdjustment.adjustment_date <= to_date)
        
        query = query.order_by(LeaveAdjustment.adjustment_date.desc())
        
        return self._paginate_query(query, pagination)

    # ============================================================================
    # ANALYTICS
    # ============================================================================

    def get_balance_analytics(
        self,
        hostel_id: Optional[UUID] = None,
        leave_type: Optional[LeaveType] = None,
        academic_year_start: Optional[date] = None
    ) -> Dict[str, Any]:
        """
        Get balance analytics.
        
        Args:
            hostel_id: Optional hostel filter
            leave_type: Optional leave type filter
            academic_year_start: Optional year filter
            
        Returns:
            Analytics dictionary
        """
        if academic_year_start is None:
            academic_year_start = self._get_current_academic_year_start()
        
        query = self.session.query(LeaveBalance).filter(
            LeaveBalance.academic_year_start == academic_year_start,
            LeaveBalance.is_active == True
        )
        
        if leave_type:
            query = query.filter(LeaveBalance.leave_type == leave_type)
        
        # Get aggregate statistics
        stats = query.with_entities(
            func.count(LeaveBalance.id).label('total_balances'),
            func.sum(LeaveBalance.allocated_days).label('total_allocated'),
            func.sum(LeaveBalance.used_days).label('total_used'),
            func.sum(LeaveBalance.pending_days).label('total_pending'),
            func.sum(LeaveBalance.remaining_days).label('total_remaining'),
            func.avg(LeaveBalance.used_days).label('avg_used'),
            func.count(case([(LeaveBalance.remaining_days <= 0, 1)])).label('exhausted_count')
        ).first()
        
        # Utilization by type
        by_type = self.session.query(
            LeaveBalance.leave_type,
            func.sum(LeaveBalance.allocated_days).label('allocated'),
            func.sum(LeaveBalance.used_days).label('used'),
            func.sum(LeaveBalance.remaining_days).label('remaining')
        ).filter(
            LeaveBalance.academic_year_start == academic_year_start,
            LeaveBalance.is_active == True
        ).group_by(LeaveBalance.leave_type).all()
        
        return {
            'total_balances': stats.total_balances or 0,
            'total_allocated': stats.total_allocated or 0,
            'total_used': stats.total_used or 0,
            'total_pending': stats.total_pending or 0,
            'total_remaining': stats.total_remaining or 0,
            'average_used': round(float(stats.avg_used or 0), 2),
            'exhausted_count': stats.exhausted_count or 0,
            'utilization_rate': round(
                (stats.total_used / stats.total_allocated * 100) if stats.total_allocated else 0,
                2
            ),
            'by_type': [
                {
                    'leave_type': lt.value,
                    'allocated': allocated or 0,
                    'used': used or 0,
                    'remaining': remaining or 0,
                    'utilization': round((used / allocated * 100) if allocated else 0, 2)
                }
                for lt, allocated, used, remaining in by_type
            ]
        }

    def get_low_balance_students(
        self,
        hostel_id: Optional[UUID] = None,
        threshold_days: int = 5,
        academic_year_start: Optional[date] = None
    ) -> List[LeaveBalance]:
        """
        Find students with low leave balance.
        
        Args:
            hostel_id: Optional hostel filter
            threshold_days: Balance threshold
            academic_year_start: Optional year filter
            
        Returns:
            List of low balances
        """
        if academic_year_start is None:
            academic_year_start = self._get_current_academic_year_start()
        
        query = self.session.query(LeaveBalance).filter(
            LeaveBalance.academic_year_start == academic_year_start,
            LeaveBalance.remaining_days <= threshold_days,
            LeaveBalance.is_active == True
        )
        
        return query.all()

    # ============================================================================
    # HELPER METHODS
    # ============================================================================

    def _get_current_academic_year_start(self) -> date:
        """
        Get current academic year start date.
        
        Returns:
            Academic year start date
        """
        today = date.today()
        # Assuming academic year starts in August
        if today.month >= 8:
            return date(today.year, 8, 1)
        else:
            return date(today.year - 1, 8, 1)

    def _paginate_query(
        self,
        query,
        pagination: Optional[PaginationParams] = None
    ) -> PaginatedResult:
        """
        Apply pagination to query.
        
        Args:
            query: SQLAlchemy query
            pagination: Pagination parameters
            
        Returns:
            Paginated results
        """
        if pagination is None:
            pagination = PaginationParams(page=1, page_size=50)
        
        total = query.count()
        
        offset = (pagination.page - 1) * pagination.page_size
        items = query.offset(offset).limit(pagination.page_size).all()
        
        return PaginatedResult(
            items=items,
            total=total,
            page=pagination.page,
            page_size=pagination.page_size,
            total_pages=(total + pagination.page_size - 1) // pagination.page_size
        )