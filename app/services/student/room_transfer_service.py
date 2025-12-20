"""
Room transfer service.

Room assignment and transfer management with approval workflows,
financial tracking, and handover documentation.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.repositories.student.room_transfer_history_repository import RoomTransferHistoryRepository
from app.repositories.student.student_repository import StudentRepository
from app.models.student.room_transfer_history import RoomTransferHistory
from app.core.exceptions import (
    ValidationError,
    NotFoundError,
    BusinessRuleViolationError
)


class RoomTransferService:
    """
    Room transfer service for room assignment and transfer management.
    
    Handles:
        - Transfer request creation
        - Approval workflows
        - Room handover process
        - Financial impact calculation
        - Transfer history tracking
        - Analytics and reporting
    """

    def __init__(self, db: Session):
        """Initialize service with database session."""
        self.db = db
        self.transfer_repo = RoomTransferHistoryRepository(db)
        self.student_repo = StudentRepository(db)

    # ============================================================================
    # TRANSFER REQUEST MANAGEMENT
    # ============================================================================

    def create_transfer_request(
        self,
        student_id: str,
        to_room_id: str,
        to_bed_id: Optional[str],
        reason: str,
        transfer_type: str = 'request',
        requested_date: Optional[date] = None,
        audit_context: Optional[dict[str, Any]] = None
    ) -> RoomTransferHistory:
        """
        Create new room transfer request.
        
        Args:
            student_id: Student UUID
            to_room_id: Target room UUID
            to_bed_id: Target bed UUID (optional)
            reason: Transfer reason
            transfer_type: Transfer type
            requested_date: Requested transfer date
            audit_context: Audit context
            
        Returns:
            Created transfer request
            
        Raises:
            NotFoundError: If student not found
            BusinessRuleViolationError: If transfer not allowed
        """
        try:
            # Validate student exists
            student = self.student_repo.find_by_id(student_id)
            if not student:
                raise NotFoundError(f"Student {student_id} not found")
            
            # Check for pending transfers
            if self.transfer_repo.has_pending_transfer(student_id):
                raise BusinessRuleViolationError(
                    "Student already has a pending transfer request"
                )
            
            # Validate reason
            if not reason or len(reason.strip()) < 10:
                raise ValidationError(
                    "Transfer reason must be at least 10 characters"
                )
            
            # Create transfer request
            transfer = self.transfer_repo.create_transfer_request(
                student_id,
                to_room_id,
                to_bed_id,
                reason,
                transfer_type,
                audit_context
            )
            
            self.db.commit()
            
            return transfer
            
        except (NotFoundError, ValidationError, BusinessRuleViolationError):
            self.db.rollback()
            raise
        except SQLAlchemyError as e:
            self.db.rollback()
            raise ValidationError(f"Database error: {str(e)}")

    def get_transfer_by_id(
        self,
        transfer_id: str,
        include_relations: bool = False
    ) -> RoomTransferHistory:
        """
        Get transfer by ID.
        
        Args:
            transfer_id: Transfer UUID
            include_relations: Load related entities
            
        Returns:
            Transfer history instance
            
        Raises:
            NotFoundError: If transfer not found
        """
        transfer = self.transfer_repo.find_by_id(
            transfer_id,
            eager_load=include_relations
        )
        
        if not transfer:
            raise NotFoundError(f"Transfer {transfer_id} not found")
        
        return transfer

    def get_student_transfer_history(
        self,
        student_id: str,
        transfer_type: Optional[str] = None,
        offset: int = 0,
        limit: int = 50
    ) -> list[RoomTransferHistory]:
        """
        Get transfer history for student.
        
        Args:
            student_id: Student UUID
            transfer_type: Optional transfer type filter
            offset: Pagination offset
            limit: Page size
            
        Returns:
            List of transfer records
        """
        return self.transfer_repo.find_by_student_id(
            student_id,
            transfer_type,
            offset,
            limit
        )

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
        return self.transfer_repo.get_current_assignment(student_id)

    # ============================================================================
    # APPROVAL WORKFLOW
    # ============================================================================

    def approve_transfer(
        self,
        transfer_id: str,
        approved_by: str,
        approval_notes: Optional[str] = None,
        audit_context: Optional[dict[str, Any]] = None
    ) -> RoomTransferHistory:
        """
        Approve transfer request.
        
        Args:
            transfer_id: Transfer UUID
            approved_by: Admin user ID
            approval_notes: Approval notes
            audit_context: Audit context
            
        Returns:
            Updated transfer instance
            
        Raises:
            NotFoundError: If transfer not found
            BusinessRuleViolationError: If approval not allowed
        """
        try:
            transfer = self.get_transfer_by_id(transfer_id)
            
            # Validate transfer can be approved
            if transfer.approval_status != 'pending':
                raise BusinessRuleViolationError(
                    f"Cannot approve transfer with status: {transfer.approval_status}"
                )
            
            # Approve transfer
            transfer = self.transfer_repo.approve_transfer(
                transfer_id,
                approved_by,
                approval_notes,
                audit_context
            )
            
            self.db.commit()
            
            return transfer
            
        except (NotFoundError, BusinessRuleViolationError):
            self.db.rollback()
            raise
        except SQLAlchemyError as e:
            self.db.rollback()
            raise ValidationError(f"Database error: {str(e)}")

    def reject_transfer(
        self,
        transfer_id: str,
        rejected_by: str,
        rejection_reason: str,
        audit_context: Optional[dict[str, Any]] = None
    ) -> RoomTransferHistory:
        """
        Reject transfer request.
        
        Args:
            transfer_id: Transfer UUID
            rejected_by: Admin user ID
            rejection_reason: Rejection reason
            audit_context: Audit context
            
        Returns:
            Updated transfer instance
            
        Raises:
            NotFoundError: If transfer not found
            ValidationError: If rejection reason missing
        """
        try:
            transfer = self.get_transfer_by_id(transfer_id)
            
            # Validate rejection reason
            if not rejection_reason or len(rejection_reason.strip()) < 10:
                raise ValidationError(
                    "Rejection reason must be at least 10 characters"
                )
            
            # Validate transfer can be rejected
            if transfer.approval_status != 'pending':
                raise BusinessRuleViolationError(
                    f"Cannot reject transfer with status: {transfer.approval_status}"
                )
            
            # Reject transfer
            transfer = self.transfer_repo.reject_transfer(
                transfer_id,
                rejected_by,
                rejection_reason,
                audit_context
            )
            
            self.db.commit()
            
            return transfer
            
        except (NotFoundError, ValidationError, BusinessRuleViolationError):
            self.db.rollback()
            raise
        except SQLAlchemyError as e:
            self.db.rollback()
            raise ValidationError(f"Database error: {str(e)}")

    def get_pending_approvals(
        self,
        hostel_id: Optional[str] = None,
        priority: Optional[str] = None,
        offset: int = 0,
        limit: int = 50
    ) -> list[RoomTransferHistory]:
        """
        Get transfers pending approval.
        
        Args:
            hostel_id: Optional hostel filter
            priority: Optional priority filter
            offset: Pagination offset
            limit: Page size
            
        Returns:
            List of pending transfers
        """
        return self.transfer_repo.find_pending_approvals(
            hostel_id,
            priority,
            offset,
            limit
        )

    # ============================================================================
    # TRANSFER EXECUTION
    # ============================================================================

    def complete_transfer(
        self,
        transfer_id: str,
        completion_notes: Optional[str] = None,
        room_condition: Optional[str] = None,
        damages: Optional[str] = None,
        damage_charges: Decimal = Decimal('0.00'),
        audit_context: Optional[dict[str, Any]] = None
    ) -> RoomTransferHistory:
        """
        Complete transfer and update student room assignment.
        
        Args:
            transfer_id: Transfer UUID
            completion_notes: Completion notes
            room_condition: New room condition
            damages: Any damages noted
            damage_charges: Damage charges if any
            audit_context: Audit context
            
        Returns:
            Updated transfer instance
            
        Raises:
            NotFoundError: If transfer not found
            BusinessRuleViolationError: If completion not allowed
        """
        try:
            transfer = self.get_transfer_by_id(transfer_id)
            
            # Validate transfer can be completed
            if transfer.transfer_status not in ['pending', 'in_progress']:
                raise BusinessRuleViolationError(
                    f"Cannot complete transfer with status: {transfer.transfer_status}"
                )
            
            if transfer.approval_status != 'approved':
                raise BusinessRuleViolationError(
                    "Transfer must be approved before completion"
                )
            
            # Update transfer with completion details
            update_data = {
                'new_room_condition': room_condition,
                'previous_room_damages': damages,
                'damage_charges': damage_charges
            }
            
            self.transfer_repo.update(transfer_id, update_data, audit_context)
            
            # Mark transfer as completed
            transfer = self.transfer_repo.complete_transfer(
                transfer_id,
                completion_notes,
                audit_context
            )
            
            # Update student's current room assignment
            self.student_repo.update(
                transfer.student_id,
                {
                    'room_id': transfer.to_room_id,
                    'bed_id': transfer.to_bed_id
                },
                audit_context
            )
            
            self.db.commit()
            
            return transfer
            
        except (NotFoundError, BusinessRuleViolationError):
            self.db.rollback()
            raise
        except SQLAlchemyError as e:
            self.db.rollback()
            raise ValidationError(f"Database error: {str(e)}")

    def cancel_transfer(
        self,
        transfer_id: str,
        cancellation_reason: str,
        audit_context: Optional[dict[str, Any]] = None
    ) -> RoomTransferHistory:
        """
        Cancel transfer request.
        
        Args:
            transfer_id: Transfer UUID
            cancellation_reason: Cancellation reason
            audit_context: Audit context
            
        Returns:
            Updated transfer instance
        """
        try:
            transfer = self.get_transfer_by_id(transfer_id)
            
            # Validate cancellation reason
            if not cancellation_reason or len(cancellation_reason.strip()) < 10:
                raise ValidationError(
                    "Cancellation reason must be at least 10 characters"
                )
            
            # Validate transfer can be cancelled
            if transfer.transfer_status == 'completed':
                raise BusinessRuleViolationError(
                    "Cannot cancel completed transfer"
                )
            
            transfer = self.transfer_repo.cancel_transfer(
                transfer_id,
                cancellation_reason,
                audit_context
            )
            
            self.db.commit()
            
            return transfer
            
        except (NotFoundError, ValidationError, BusinessRuleViolationError):
            self.db.rollback()
            raise
        except SQLAlchemyError as e:
            self.db.rollback()
            raise ValidationError(f"Database error: {str(e)}")

    # ============================================================================
    # FINANCIAL TRACKING
    # ============================================================================

    def calculate_transfer_financials(
        self,
        transfer_id: str,
        new_rent: Decimal,
        previous_rent: Optional[Decimal] = None,
        transfer_charges: Decimal = Decimal('0.00'),
        calculate_prorated: bool = True,
        audit_context: Optional[dict[str, Any]] = None
    ) -> RoomTransferHistory:
        """
        Calculate and record financial impact of transfer.
        
        Args:
            transfer_id: Transfer UUID
            new_rent: New monthly rent
            previous_rent: Previous monthly rent
            transfer_charges: One-time transfer charges
            calculate_prorated: Calculate prorated rent
            audit_context: Audit context
            
        Returns:
            Updated transfer instance
        """
        try:
            transfer = self.get_transfer_by_id(transfer_id)
            
            # Calculate rent difference
            rent_difference = None
            if previous_rent is not None:
                rent_difference = new_rent - previous_rent
            
            update_data = {
                'new_rent': new_rent,
                'previous_rent': previous_rent,
                'rent_difference': rent_difference,
                'transfer_charges': transfer_charges
            }
            
            # Calculate prorated rent if requested
            if calculate_prorated:
                prorated_amount = self._calculate_prorated_rent(
                    transfer.transfer_date,
                    new_rent
                )
                update_data['prorated_amount'] = prorated_amount
                update_data['prorated_rent_calculated'] = True
            
            transfer = self.transfer_repo.update(
                transfer_id,
                update_data,
                audit_context
            )
            
            self.db.commit()
            
            return transfer
            
        except NotFoundError:
            self.db.rollback()
            raise
        except SQLAlchemyError as e:
            self.db.rollback()
            raise ValidationError(f"Database error: {str(e)}")

    def _calculate_prorated_rent(
        self,
        transfer_date: date,
        monthly_rent: Decimal
    ) -> Decimal:
        """
        Calculate prorated rent for partial month.
        
        Args:
            transfer_date: Transfer date
            monthly_rent: Monthly rent amount
            
        Returns:
            Prorated rent amount
        """
        from calendar import monthrange
        
        # Get number of days in the month
        days_in_month = monthrange(transfer_date.year, transfer_date.month)[1]
        
        # Calculate days remaining in month
        days_remaining = days_in_month - transfer_date.day + 1
        
        # Calculate prorated amount
        daily_rate = monthly_rent / days_in_month
        prorated = daily_rate * days_remaining
        
        return prorated.quantize(Decimal('0.01'))

    def get_total_transfer_charges(
        self,
        student_id: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> Decimal:
        """
        Get total transfer charges for student.
        
        Args:
            student_id: Student UUID
            start_date: Start date filter
            end_date: End date filter
            
        Returns:
            Total transfer charges
        """
        return self.transfer_repo.calculate_total_transfer_charges(
            student_id,
            start_date,
            end_date
        )

    def get_rent_change_history(
        self,
        student_id: str
    ) -> list[dict[str, Any]]:
        """
        Get complete rent change history.
        
        Args:
            student_id: Student UUID
            
        Returns:
            List of rent changes
        """
        return self.transfer_repo.get_rent_change_history(student_id)

    # ============================================================================
    # QUERIES AND ANALYTICS
    # ============================================================================

    def get_room_transfers(
        self,
        room_id: str,
        direction: str = 'both'
    ) -> list[RoomTransferHistory]:
        """
        Get transfers involving a room.
        
        Args:
            room_id: Room UUID
            direction: Direction filter ('from', 'to', 'both')
            
        Returns:
            List of transfers
        """
        return self.transfer_repo.find_by_room(room_id, direction)

    def get_in_progress_transfers(
        self,
        hostel_id: Optional[str] = None
    ) -> list[RoomTransferHistory]:
        """
        Get transfers currently in progress.
        
        Args:
            hostel_id: Optional hostel filter
            
        Returns:
            List of in-progress transfers
        """
        return self.transfer_repo.find_in_progress_transfers(hostel_id)

    def get_emergency_transfers(
        self,
        hostel_id: Optional[str] = None
    ) -> list[RoomTransferHistory]:
        """
        Get emergency transfers.
        
        Args:
            hostel_id: Optional hostel filter
            
        Returns:
            List of emergency transfers
        """
        return self.transfer_repo.find_emergency_transfers(hostel_id)

    def get_transfer_statistics(
        self,
        hostel_id: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> dict[str, Any]:
        """
        Get transfer statistics.
        
        Args:
            hostel_id: Optional hostel filter
            start_date: Start date filter
            end_date: End date filter
            
        Returns:
            Transfer statistics
        """
        return self.transfer_repo.get_transfer_statistics(
            hostel_id,
            start_date,
            end_date
        )

    def get_transfer_type_distribution(
        self,
        hostel_id: Optional[str] = None
    ) -> dict[str, int]:
        """
        Get distribution of transfer types.
        
        Args:
            hostel_id: Optional hostel filter
            
        Returns:
            Transfer type distribution
        """
        return self.transfer_repo.get_transfer_type_distribution(hostel_id)

    def count_student_transfers(
        self,
        student_id: str,
        transfer_type: Optional[str] = None
    ) -> int:
        """
        Count transfers for a student.
        
        Args:
            student_id: Student UUID
            transfer_type: Optional transfer type filter
            
        Returns:
            Transfer count
        """
        return self.transfer_repo.count_transfers_by_student(
            student_id,
            transfer_type
        )