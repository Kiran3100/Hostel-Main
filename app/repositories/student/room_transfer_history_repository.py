# --- File: room_transfer_history_repository.py ---

"""
Room transfer history repository.

Room assignment and transfer tracking with audit trail, analytics,
and workflow management.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Optional
from sqlalchemy import and_, or_, func, desc
from sqlalchemy.orm import Session, joinedload

from app.models.student.room_transfer_history import RoomTransferHistory
from app.models.student.student import Student
from app.models.room.room import Room
from app.models.hostel.hostel import Hostel


class RoomTransferHistoryRepository:
    """
    Room transfer history repository for comprehensive transfer management.
    
    Handles:
        - Complete room assignment history tracking
        - Transfer workflow management
        - Approval process coordination
        - Financial impact tracking
        - Room handover documentation
        - Transfer analytics and reporting
        - Audit trail maintenance
    """

    def __init__(self, db: Session):
        """Initialize repository with database session."""
        self.db = db

    # ============================================================================
    # CORE CRUD OPERATIONS
    # ============================================================================

    def create(
        self,
        transfer_data: dict[str, Any],
        audit_context: Optional[dict[str, Any]] = None
    ) -> RoomTransferHistory:
        """
        Create room transfer record with audit logging.
        
        Args:
            transfer_data: Transfer information
            audit_context: Audit context
            
        Returns:
            Created transfer history instance
        """
        if audit_context:
            transfer_data['created_by'] = audit_context.get('user_id')
            transfer_data['updated_by'] = audit_context.get('user_id')
            
            if 'requested_by' not in transfer_data:
                transfer_data['requested_by'] = audit_context.get('user_id')

        transfer = RoomTransferHistory(**transfer_data)
        self.db.add(transfer)
        self.db.flush()
        
        return transfer

    def find_by_id(
        self,
        transfer_id: str,
        eager_load: bool = False
    ) -> Optional[RoomTransferHistory]:
        """
        Find transfer by ID with optional eager loading.
        
        Args:
            transfer_id: Transfer UUID
            eager_load: Load related entities
            
        Returns:
            Transfer history instance or None
        """
        query = self.db.query(RoomTransferHistory)
        
        if eager_load:
            query = query.options(
                joinedload(RoomTransferHistory.student),
                joinedload(RoomTransferHistory.hostel),
                joinedload(RoomTransferHistory.from_room),
                joinedload(RoomTransferHistory.to_room),
                joinedload(RoomTransferHistory.requester),
                joinedload(RoomTransferHistory.approver)
            )
        
        return query.filter(RoomTransferHistory.id == transfer_id).first()

    def find_by_student_id(
        self,
        student_id: str,
        transfer_type: Optional[str] = None,
        offset: int = 0,
        limit: int = 50
    ) -> list[RoomTransferHistory]:
        """
        Find transfer history for a student.
        
        Args:
            student_id: Student UUID
            transfer_type: Filter by transfer type
            offset: Pagination offset
            limit: Page size
            
        Returns:
            List of transfer records
        """
        query = self.db.query(RoomTransferHistory).filter(
            RoomTransferHistory.student_id == student_id
        )
        
        if transfer_type:
            query = query.filter(RoomTransferHistory.transfer_type == transfer_type)
        
        return query.order_by(
            desc(RoomTransferHistory.transfer_date)
        ).offset(offset).limit(limit).all()

    def update(
        self,
        transfer_id: str,
        update_data: dict[str, Any],
        audit_context: Optional[dict[str, Any]] = None
    ) -> Optional[RoomTransferHistory]:
        """
        Update transfer record with audit logging.
        
        Args:
            transfer_id: Transfer UUID
            update_data: Fields to update
            audit_context: Audit context
            
        Returns:
            Updated transfer history instance or None
        """
        transfer = self.find_by_id(transfer_id)
        if not transfer:
            return None
        
        if audit_context:
            update_data['updated_by'] = audit_context.get('user_id')
        update_data['updated_at'] = datetime.utcnow()
        
        for key, value in update_data.items():
            if hasattr(transfer, key):
                setattr(transfer, key, value)
        
        self.db.flush()
        return transfer

    # ============================================================================
    # TRANSFER WORKFLOW
    # ============================================================================

    def create_transfer_request(
        self,
        student_id: str,
        to_room_id: str,
        to_bed_id: Optional[str],
        reason: str,
        transfer_type: str = 'request',
        audit_context: Optional[dict[str, Any]] = None
    ) -> RoomTransferHistory:
        """
        Create new transfer request.
        
        Args:
            student_id: Student UUID
            to_room_id: Target room UUID
            to_bed_id: Target bed UUID (optional)
            reason: Transfer reason
            transfer_type: Transfer type
            audit_context: Audit context
            
        Returns:
            Created transfer request
        """
        # Get student's current room assignment
        student = self.db.query(Student).filter(Student.id == student_id).first()
        
        transfer_data = {
            'student_id': student_id,
            'hostel_id': student.hostel_id if student else None,
            'from_room_id': student.room_id if student else None,
            'from_bed_id': student.bed_id if student else None,
            'to_room_id': to_room_id,
            'to_bed_id': to_bed_id,
            'transfer_type': transfer_type,
            'transfer_date': date.today(),
            'move_in_date': date.today(),
            'reason': reason,
            'student_initiated': True,
            'transfer_status': 'pending',
            'approval_status': 'pending'
        }
        
        return self.create(transfer_data, audit_context)

    def approve_transfer(
        self,
        transfer_id: str,
        approved_by: str,
        approval_notes: Optional[str] = None,
        audit_context: Optional[dict[str, Any]] = None
    ) -> Optional[RoomTransferHistory]:
        """
        Approve transfer request.
        
        Args:
            transfer_id: Transfer UUID
            approved_by: Admin user ID who approved
            approval_notes: Approval notes
            audit_context: Audit context
            
        Returns:
            Updated transfer instance or None
        """
        update_data = {
            'approval_status': 'approved',
            'approved_by': approved_by,
            'approved_at': date.today(),
            'approval_notes': approval_notes,
            'transfer_status': 'in_progress'
        }
        
        return self.update(transfer_id, update_data, audit_context)

    def reject_transfer(
        self,
        transfer_id: str,
        rejected_by: str,
        rejection_reason: str,
        audit_context: Optional[dict[str, Any]] = None
    ) -> Optional[RoomTransferHistory]:
        """
        Reject transfer request.
        
        Args:
            transfer_id: Transfer UUID
            rejected_by: Admin user ID who rejected
            rejection_reason: Rejection reason
            audit_context: Audit context
            
        Returns:
            Updated transfer instance or None
        """
        update_data = {
            'approval_status': 'rejected',
            'approved_by': rejected_by,
            'approved_at': date.today(),
            'approval_notes': rejection_reason,
            'transfer_status': 'cancelled',
            'cancellation_reason': rejection_reason
        }
        
        return self.update(transfer_id, update_data, audit_context)

    def complete_transfer(
        self,
        transfer_id: str,
        completion_notes: Optional[str] = None,
        audit_context: Optional[dict[str, Any]] = None
    ) -> Optional[RoomTransferHistory]:
        """
        Mark transfer as completed.
        
        Args:
            transfer_id: Transfer UUID
            completion_notes: Completion notes
            audit_context: Audit context
            
        Returns:
            Updated transfer instance or None
        """
        transfer = self.find_by_id(transfer_id)
        if not transfer:
            return None
        
        update_data = {
            'transfer_status': 'completed',
            'completion_date': date.today(),
            'handover_completed': True
        }
        
        # Mark this as current assignment
        self._update_current_assignment(transfer.student_id, transfer_id)
        
        return self.update(transfer_id, update_data, audit_context)

    def cancel_transfer(
        self,
        transfer_id: str,
        cancellation_reason: str,
        audit_context: Optional[dict[str, Any]] = None
    ) -> Optional[RoomTransferHistory]:
        """
        Cancel transfer request.
        
        Args:
            transfer_id: Transfer UUID
            cancellation_reason: Cancellation reason
            audit_context: Audit context
            
        Returns:
            Updated transfer instance or None
        """
        update_data = {
            'transfer_status': 'cancelled',
            'cancellation_reason': cancellation_reason
        }
        
        return self.update(transfer_id, update_data, audit_context)

    def _update_current_assignment(
        self,
        student_id: str,
        new_assignment_id: str
    ) -> None:
        """
        Update current assignment flag for student transfers.
        
        Args:
            student_id: Student UUID
            new_assignment_id: New assignment transfer ID
        """
        # Unset current assignment for all other transfers
        self.db.query(RoomTransferHistory).filter(
            and_(
                RoomTransferHistory.student_id == student_id,
                RoomTransferHistory.id != new_assignment_id
            )
        ).update(
            {'is_current_assignment': False},
            synchronize_session=False
        )
        
        # Set new current assignment
        self.db.query(RoomTransferHistory).filter(
            RoomTransferHistory.id == new_assignment_id
        ).update(
            {'is_current_assignment': True},
            synchronize_session=False
        )
        
        self.db.flush()

    # ============================================================================
    # QUERIES
    # ============================================================================

    def get_current_assignment(
        self,
        student_id: str
    ) -> Optional[RoomTransferHistory]:
        """
        Get current room assignment for student.
        
        Args:
            student_id: Student UUID
            
        Returns:
            Current assignment or None
        """
        return self.db.query(RoomTransferHistory).filter(
            and_(
                RoomTransferHistory.student_id == student_id,
                RoomTransferHistory.is_current_assignment == True
            )
        ).first()

    def find_pending_approvals(
        self,
        hostel_id: Optional[str] = None,
        priority: Optional[str] = None,
        offset: int = 0,
        limit: int = 50
    ) -> list[RoomTransferHistory]:
        """
        Find transfers pending approval.
        
        Args:
            hostel_id: Optional hostel filter
            priority: Filter by priority
            offset: Pagination offset
            limit: Page size
            
        Returns:
            List of pending transfers
        """
        query = self.db.query(RoomTransferHistory).filter(
            RoomTransferHistory.approval_status == 'pending'
        )
        
        if hostel_id:
            query = query.filter(RoomTransferHistory.hostel_id == hostel_id)
        
        if priority:
            query = query.filter(RoomTransferHistory.priority == priority)
        
        return query.order_by(
            RoomTransferHistory.priority.desc(),
            RoomTransferHistory.created_at.asc()
        ).offset(offset).limit(limit).all()

    def find_in_progress_transfers(
        self,
        hostel_id: Optional[str] = None
    ) -> list[RoomTransferHistory]:
        """
        Find transfers currently in progress.
        
        Args:
            hostel_id: Optional hostel filter
            
        Returns:
            List of in-progress transfers
        """
        query = self.db.query(RoomTransferHistory).filter(
            RoomTransferHistory.transfer_status == 'in_progress'
        )
        
        if hostel_id:
            query = query.filter(RoomTransferHistory.hostel_id == hostel_id)
        
        return query.order_by(RoomTransferHistory.transfer_date.asc()).all()

    def find_by_room(
        self,
        room_id: str,
        direction: str = 'both'
    ) -> list[RoomTransferHistory]:
        """
        Find transfers involving a specific room.
        
        Args:
            room_id: Room UUID
            direction: Direction filter ('from', 'to', 'both')
            
        Returns:
            List of transfers
        """
        if direction == 'from':
            query = self.db.query(RoomTransferHistory).filter(
                RoomTransferHistory.from_room_id == room_id
            )
        elif direction == 'to':
            query = self.db.query(RoomTransferHistory).filter(
                RoomTransferHistory.to_room_id == room_id
            )
        else:  # both
            query = self.db.query(RoomTransferHistory).filter(
                or_(
                    RoomTransferHistory.from_room_id == room_id,
                    RoomTransferHistory.to_room_id == room_id
                )
            )
        
        return query.order_by(desc(RoomTransferHistory.transfer_date)).all()

    def find_emergency_transfers(
        self,
        hostel_id: Optional[str] = None
    ) -> list[RoomTransferHistory]:
        """
        Find emergency transfers.
        
        Args:
            hostel_id: Optional hostel filter
            
        Returns:
            List of emergency transfers
        """
        query = self.db.query(RoomTransferHistory).filter(
            RoomTransferHistory.is_emergency == True
        )
        
        if hostel_id:
            query = query.filter(RoomTransferHistory.hostel_id == hostel_id)
        
        return query.order_by(desc(RoomTransferHistory.created_at)).all()

    def find_with_financial_impact(
        self,
        hostel_id: Optional[str] = None,
        impact_type: Optional[str] = None
    ) -> list[RoomTransferHistory]:
        """
        Find transfers with financial impact.
        
        Args:
            hostel_id: Optional hostel filter
            impact_type: Impact type ('increase', 'decrease', 'any')
            
        Returns:
            List of transfers with financial impact
        """
        query = self.db.query(RoomTransferHistory).filter(
            RoomTransferHistory.rent_difference.isnot(None)
        )
        
        if impact_type == 'increase':
            query = query.filter(RoomTransferHistory.rent_difference > 0)
        elif impact_type == 'decrease':
            query = query.filter(RoomTransferHistory.rent_difference < 0)
        
        if hostel_id:
            query = query.filter(RoomTransferHistory.hostel_id == hostel_id)
        
        return query.all()

    # ============================================================================
    # FINANCIAL TRACKING
    # ============================================================================

    def calculate_total_transfer_charges(
        self,
        student_id: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> Decimal:
        """
        Calculate total transfer charges for student.
        
        Args:
            student_id: Student UUID
            start_date: Start date filter
            end_date: End date filter
            
        Returns:
            Total transfer charges
        """
        query = self.db.query(
            func.sum(RoomTransferHistory.transfer_charges)
        ).filter(RoomTransferHistory.student_id == student_id)
        
        if start_date:
            query = query.filter(RoomTransferHistory.transfer_date >= start_date)
        
        if end_date:
            query = query.filter(RoomTransferHistory.transfer_date <= end_date)
        
        result = query.scalar()
        return result if result else Decimal('0.00')

    def calculate_total_damage_charges(
        self,
        student_id: str
    ) -> Decimal:
        """
        Calculate total damage charges for student.
        
        Args:
            student_id: Student UUID
            
        Returns:
            Total damage charges
        """
        result = self.db.query(
            func.sum(RoomTransferHistory.damage_charges)
        ).filter(RoomTransferHistory.student_id == student_id).scalar()
        
        return result if result else Decimal('0.00')

    def get_rent_change_history(
        self,
        student_id: str
    ) -> list[dict[str, Any]]:
        """
        Get complete rent change history for student.
        
        Args:
            student_id: Student UUID
            
        Returns:
            List of rent changes with dates
        """
        transfers = self.db.query(RoomTransferHistory).filter(
            and_(
                RoomTransferHistory.student_id == student_id,
                RoomTransferHistory.rent_difference.isnot(None)
            )
        ).order_by(RoomTransferHistory.transfer_date.asc()).all()
        
        return [
            {
                'transfer_id': t.id,
                'transfer_date': t.transfer_date,
                'previous_rent': t.previous_rent,
                'new_rent': t.new_rent,
                'rent_difference': t.rent_difference,
                'transfer_type': t.transfer_type
            }
            for t in transfers
        ]

    # ============================================================================
    # STATISTICS AND ANALYTICS
    # ============================================================================

    def get_transfer_statistics(
        self,
        hostel_id: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> dict[str, Any]:
        """
        Get comprehensive transfer statistics.
        
        Args:
            hostel_id: Optional hostel filter
            start_date: Start date filter
            end_date: End date filter
            
        Returns:
            Dictionary with transfer statistics
        """
        query = self.db.query(RoomTransferHistory)
        
        if hostel_id:
            query = query.filter(RoomTransferHistory.hostel_id == hostel_id)
        
        if start_date:
            query = query.filter(RoomTransferHistory.transfer_date >= start_date)
        
        if end_date:
            query = query.filter(RoomTransferHistory.transfer_date <= end_date)
        
        total_transfers = query.count()
        
        completed = query.filter(
            RoomTransferHistory.transfer_status == 'completed'
        ).count()
        
        pending = query.filter(
            RoomTransferHistory.transfer_status == 'pending'
        ).count()
        
        in_progress = query.filter(
            RoomTransferHistory.transfer_status == 'in_progress'
        ).count()
        
        cancelled = query.filter(
            RoomTransferHistory.transfer_status == 'cancelled'
        ).count()
        
        student_initiated = query.filter(
            RoomTransferHistory.student_initiated == True
        ).count()
        
        emergency = query.filter(
            RoomTransferHistory.is_emergency == True
        ).count()
        
        avg_completion_time = self._calculate_average_completion_time(
            hostel_id, start_date, end_date
        )
        
        return {
            'total_transfers': total_transfers,
            'completed': completed,
            'pending': pending,
            'in_progress': in_progress,
            'cancelled': cancelled,
            'student_initiated': student_initiated,
            'emergency_transfers': emergency,
            'completion_rate': round((completed / total_transfers * 100), 2) if total_transfers > 0 else 0,
            'average_completion_days': avg_completion_time
        }

    def _calculate_average_completion_time(
        self,
        hostel_id: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> Optional[float]:
        """
        Calculate average time to complete transfers.
        
        Args:
            hostel_id: Optional hostel filter
            start_date: Start date filter
            end_date: End date filter
            
        Returns:
            Average completion time in days or None
        """
        query = self.db.query(RoomTransferHistory).filter(
            and_(
                RoomTransferHistory.transfer_status == 'completed',
                RoomTransferHistory.completion_date.isnot(None)
            )
        )
        
        if hostel_id:
            query = query.filter(RoomTransferHistory.hostel_id == hostel_id)
        
        if start_date:
            query = query.filter(RoomTransferHistory.transfer_date >= start_date)
        
        if end_date:
            query = query.filter(RoomTransferHistory.transfer_date <= end_date)
        
        transfers = query.all()
        
        if not transfers:
            return None
        
        total_days = sum(
            (t.completion_date - t.transfer_date).days
            for t in transfers
        )
        
        return round(total_days / len(transfers), 2)

    def get_transfer_type_distribution(
        self,
        hostel_id: Optional[str] = None
    ) -> dict[str, int]:
        """
        Get distribution of transfer types.
        
        Args:
            hostel_id: Optional hostel filter
            
        Returns:
            Dictionary mapping transfer types to counts
        """
        query = self.db.query(
            RoomTransferHistory.transfer_type,
            func.count(RoomTransferHistory.id).label('count')
        )
        
        if hostel_id:
            query = query.filter(RoomTransferHistory.hostel_id == hostel_id)
        
        query = query.group_by(RoomTransferHistory.transfer_type)
        
        results = query.all()
        
        return {transfer_type: count for transfer_type, count in results}

    def get_most_active_transfer_months(
        self,
        hostel_id: Optional[str] = None,
        limit: int = 12
    ) -> list[dict[str, Any]]:
        """
        Get months with most transfer activity.
        
        Args:
            hostel_id: Optional hostel filter
            limit: Number of months to return
            
        Returns:
            List of months with transfer counts
        """
        query = self.db.query(
            func.strftime('%Y-%m', RoomTransferHistory.transfer_date).label('month'),
            func.count(RoomTransferHistory.id).label('count')
        )
        
        if hostel_id:
            query = query.filter(RoomTransferHistory.hostel_id == hostel_id)
        
        query = query.group_by('month')
        query = query.order_by(func.count(RoomTransferHistory.id).desc())
        query = query.limit(limit)
        
        results = query.all()
        
        return [
            {'month': month, 'transfer_count': count}
            for month, count in results
        ]

    def count_transfers_by_student(
        self,
        student_id: str,
        transfer_type: Optional[str] = None
    ) -> int:
        """
        Count total transfers for a student.
        
        Args:
            student_id: Student UUID
            transfer_type: Optional transfer type filter
            
        Returns:
            Count of transfers
        """
        query = self.db.query(func.count(RoomTransferHistory.id)).filter(
            RoomTransferHistory.student_id == student_id
        )
        
        if transfer_type:
            query = query.filter(RoomTransferHistory.transfer_type == transfer_type)
        
        return query.scalar()

    # ============================================================================
    # VALIDATION
    # ============================================================================

    def has_pending_transfer(self, student_id: str) -> bool:
        """
        Check if student has pending transfer.
        
        Args:
            student_id: Student UUID
            
        Returns:
            True if pending transfer exists
        """
        return self.db.query(
            self.db.query(RoomTransferHistory).filter(
                and_(
                    RoomTransferHistory.student_id == student_id,
                    RoomTransferHistory.transfer_status.in_(['pending', 'in_progress'])
                )
            ).exists()
        ).scalar()