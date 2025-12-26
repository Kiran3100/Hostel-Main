# app/services/student/room_transfer_service.py
"""
Room Transfer Service

Handles student room/bed transfers, swaps, and maintains transfer history
with comprehensive validation and workflow support.
"""

from __future__ import annotations

import logging
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.repositories.student import (
    RoomTransferHistoryRepository,
    StudentRepository,
)
from app.repositories.room import BedAssignmentRepository
from app.schemas.student import (
    RoomHistoryResponse,
    RoomHistoryItem,
    RoomTransferRequest,
    RoomTransferApproval,
    RoomTransferStatus,
    BulkRoomTransfer,
    SingleTransfer,
    RoomSwapRequest,
)
from app.core.exceptions import (
    ValidationException,
    BusinessLogicException,
    NotFoundException,
)
from app.models.base.enums import StudentStatus

logger = logging.getLogger(__name__)


class RoomTransferService:
    """
    High-level service for room/bed transfers and history management.

    Responsibilities:
    - Submit and track transfer requests
    - Approve/reject transfer requests
    - Execute bulk transfers
    - Handle room swaps between students
    - Provide comprehensive transfer history
    - Validate transfer eligibility

    Transfer workflow:
    1. Request submission (student or admin)
    2. Validation and approval
    3. Execution with bed assignment updates
    4. History recording
    5. Notification dispatch
    """

    def __init__(
        self,
        transfer_repo: RoomTransferHistoryRepository,
        student_repo: StudentRepository,
        bed_assignment_repo: BedAssignmentRepository,
    ) -> None:
        """
        Initialize service with required repositories.

        Args:
            transfer_repo: Repository for transfer operations
            student_repo: Repository for student operations
            bed_assignment_repo: Repository for bed assignments
        """
        self.transfer_repo = transfer_repo
        self.student_repo = student_repo
        self.bed_assignment_repo = bed_assignment_repo

    # -------------------------------------------------------------------------
    # Transfer History
    # -------------------------------------------------------------------------

    def get_room_history(
        self,
        db: Session,
        student_id: UUID,
        limit: Optional[int] = None,
    ) -> RoomHistoryResponse:
        """
        Retrieve comprehensive room history for a student.

        Args:
            db: Database session
            student_id: UUID of student
            limit: Maximum number of history records to return

        Returns:
            RoomHistoryResponse: Complete room history with statistics

        Raises:
            NotFoundException: If student not found
        """
        student = self.student_repo.get_by_id(db, student_id)
        if not student:
            raise NotFoundException(f"Student not found: {student_id}")

        try:
            history_rows = self.transfer_repo.get_history_for_student(
                db,
                student_id,
                limit=limit,
            )

            items = [RoomHistoryItem.model_validate(h) for h in history_rows]

            # Calculate statistics
            total_assignments = len(items)
            total_transfers = sum(1 for i in items if i.transfer_type == "transfer")
            has_changed_rooms = any(i.transfer_type == "transfer" for i in items)

            return RoomHistoryResponse(
                student_id=student_id,
                student_name=student.user.full_name if student.user else None,
                current_room_id=student.room_id,
                current_bed_id=student.bed_id,
                room_history=items,
                total_assignments=total_assignments,
                total_transfers=total_transfers,
                has_changed_rooms=has_changed_rooms,
            )

        except SQLAlchemyError as e:
            logger.error(f"Database error retrieving room history: {str(e)}")
            raise BusinessLogicException(
                f"Failed to retrieve room history: {str(e)}"
            ) from e

    # -------------------------------------------------------------------------
    # Transfer Request Management
    # -------------------------------------------------------------------------

    def submit_transfer_request(
        self,
        db: Session,
        request: RoomTransferRequest,
    ) -> RoomTransferStatus:
        """
        Submit a room transfer request for approval.

        Args:
            db: Database session
            request: Transfer request data

        Returns:
            RoomTransferStatus: Created transfer request status

        Raises:
            NotFoundException: If student not found
            ValidationException: If student not eligible for transfer
        """
        student = self.student_repo.get_by_id(db, request.student_id)
        if not student:
            raise NotFoundException(f"Student not found: {request.student_id}")

        # Validate transfer eligibility
        self._validate_transfer_eligibility(db, student, request)

        try:
            obj = self.transfer_repo.create_transfer_request(
                db=db,
                data=request.model_dump(exclude_none=True),
            )
            
            logger.info(
                f"Transfer request submitted: {obj.id} "
                f"for student: {request.student_id}"
            )
            
            return RoomTransferStatus.model_validate(obj)

        except SQLAlchemyError as e:
            logger.error(f"Database error submitting transfer request: {str(e)}")
            raise BusinessLogicException(
                f"Failed to submit transfer request: {str(e)}"
            ) from e

    def approve_transfer(
        self,
        db: Session,
        approval: RoomTransferApproval,
    ) -> RoomTransferStatus:
        """
        Approve or reject a transfer request.

        Args:
            db: Database session
            approval: Approval/rejection data

        Returns:
            RoomTransferStatus: Updated transfer status

        Raises:
            NotFoundException: If transfer request not found
            ValidationException: If transfer cannot be approved
        """
        transfer = self.transfer_repo.get_by_id(db, approval.transfer_request_id)
        if not transfer:
            raise NotFoundException(
                f"Transfer request not found: {approval.transfer_request_id}"
            )

        # Check if already processed
        if transfer.status in ["approved", "rejected", "completed"]:
            raise ValidationException(
                f"Transfer request already {transfer.status}"
            )

        try:
            if approval.approved:
                # Validate destination room/bed availability
                self._validate_destination(
                    db,
                    approval.new_room_id,
                    approval.new_bed_id,
                )

                obj = self.transfer_repo.approve_and_execute_transfer(
                    db=db,
                    transfer=transfer,
                    approved_by=approval.approved_by,
                    new_room_id=approval.new_room_id,
                    new_bed_id=approval.new_bed_id,
                    effective_date=approval.transfer_date or datetime.utcnow(),
                    notes=approval.notes,
                )
                
                logger.info(
                    f"Transfer approved and executed: {approval.transfer_request_id}"
                )
            else:
                obj = self.transfer_repo.reject_transfer(
                    db=db,
                    transfer=transfer,
                    rejected_by=approval.approved_by,
                    reason=approval.rejection_reason,
                )
                
                logger.info(
                    f"Transfer rejected: {approval.transfer_request_id}, "
                    f"reason: {approval.rejection_reason}"
                )

            return RoomTransferStatus.model_validate(obj)

        except SQLAlchemyError as e:
            logger.error(f"Database error processing transfer approval: {str(e)}")
            raise BusinessLogicException(
                f"Failed to process transfer approval: {str(e)}"
            ) from e

    def get_transfer_status(
        self,
        db: Session,
        transfer_id: UUID,
    ) -> RoomTransferStatus:
        """
        Get current status for a transfer request.

        Args:
            db: Database session
            transfer_id: UUID of transfer request

        Returns:
            RoomTransferStatus: Transfer status details

        Raises:
            NotFoundException: If transfer not found
        """
        obj = self.transfer_repo.get_by_id(db, transfer_id)
        if not obj:
            raise NotFoundException(f"Transfer request not found: {transfer_id}")
        
        return RoomTransferStatus.model_validate(obj)

    def get_pending_transfers(
        self,
        db: Session,
        hostel_id: Optional[UUID] = None,
    ) -> List[RoomTransferStatus]:
        """
        Get all pending transfer requests.

        Args:
            db: Database session
            hostel_id: Optional hostel filter

        Returns:
            List of pending transfers
        """
        try:
            transfers = self.transfer_repo.get_pending_transfers(db, hostel_id)
            return [RoomTransferStatus.model_validate(t) for t in transfers]

        except SQLAlchemyError as e:
            logger.error(f"Database error retrieving pending transfers: {str(e)}")
            raise BusinessLogicException(
                f"Failed to retrieve pending transfers: {str(e)}"
            ) from e

    # -------------------------------------------------------------------------
    # Bulk Transfers
    # -------------------------------------------------------------------------

    def execute_bulk_transfer(
        self,
        db: Session,
        bulk_request: BulkRoomTransfer,
        executed_by: UUID,
    ) -> List[RoomTransferStatus]:
        """
        Execute bulk transfers (admin operation).

        Each transfer is executed immediately without approval workflow.

        Args:
            db: Database session
            bulk_request: Bulk transfer request data
            executed_by: UUID of user executing transfers

        Returns:
            List of transfer results

        Raises:
            ValidationException: If confirmation not provided or validation fails
        """
        if not bulk_request.confirm_bulk_transfer:
            raise ValidationException(
                "Bulk transfer must be explicitly confirmed"
            )

        if not bulk_request.transfers:
            raise ValidationException("No transfers provided")

        results: List[RoomTransferStatus] = []
        successful = 0
        failed = 0

        logger.info(
            f"Starting bulk transfer of {len(bulk_request.transfers)} students "
            f"by user: {executed_by}"
        )

        for transfer in bulk_request.transfers:
            try:
                result = self._execute_single_transfer(
                    db=db,
                    transfer=transfer,
                    transfer_date=bulk_request.transfer_date,
                    reason=bulk_request.reason,
                    executed_by=executed_by,
                    skip_on_error=bulk_request.skip_on_error,
                    prorated_rent=bulk_request.prorated_rent,
                )
                results.append(result)
                
                if result.status == "completed":
                    successful += 1
                else:
                    failed += 1

            except Exception as e:
                logger.error(f"Error in bulk transfer: {str(e)}")
                if not bulk_request.skip_on_error:
                    raise
                failed += 1
                results.append(
                    RoomTransferStatus(
                        transfer_request_id=None,
                        status="failed",
                        reason=str(e),
                    )
                )

        logger.info(
            f"Bulk transfer completed: {successful} successful, {failed} failed"
        )

        return results

    def _execute_single_transfer(
        self,
        db: Session,
        transfer: SingleTransfer,
        transfer_date: datetime,
        reason: Optional[str],
        executed_by: UUID,
        skip_on_error: bool,
        prorated_rent: bool,
    ) -> RoomTransferStatus:
        """
        Execute a single transfer in bulk context.

        Args:
            db: Database session
            transfer: Single transfer data
            transfer_date: Date of transfer
            reason: Reason for transfer
            executed_by: UUID of executor
            skip_on_error: Whether to skip on errors
            prorated_rent: Whether to prorate rent

        Returns:
            RoomTransferStatus: Transfer result
        """
        student = self.student_repo.get_by_id(db, transfer.student_id)
        
        if not student:
            if skip_on_error:
                return RoomTransferStatus(
                    transfer_request_id=None,
                    status="failed",
                    reason=f"Student not found: {transfer.student_id}",
                )
            raise NotFoundException(f"Student not found: {transfer.student_id}")

        try:
            # Validate destination
            self._validate_destination(
                db,
                transfer.new_room_id,
                transfer.new_bed_id,
            )

            obj = self.transfer_repo.execute_direct_transfer(
                db=db,
                student=student,
                new_room_id=transfer.new_room_id,
                new_bed_id=transfer.new_bed_id,
                transfer_date=transfer_date,
                reason=reason,
                executed_by=executed_by,
                prorated_rent=prorated_rent,
            )
            
            return RoomTransferStatus.model_validate(obj)

        except Exception as exc:
            if skip_on_error:
                return RoomTransferStatus(
                    transfer_request_id=None,
                    status="failed",
                    reason=str(exc),
                )
            raise

    # -------------------------------------------------------------------------
    # Room Swaps
    # -------------------------------------------------------------------------

    def request_room_swap(
        self,
        db: Session,
        request: RoomSwapRequest,
    ) -> Dict[str, Any]:
        """
        Execute room swap between two students.

        Args:
            db: Database session
            request: Room swap request data

        Returns:
            Dictionary with swap execution results

        Raises:
            ValidationException: If swap is invalid
        """
        if request.student_1_id == request.student_2_id:
            raise ValidationException(
                "Cannot swap rooms with the same student"
            )

        # Validate both students exist and have rooms
        student1 = self.student_repo.get_by_id(db, request.student_1_id)
        student2 = self.student_repo.get_by_id(db, request.student_2_id)

        if not student1 or not student2:
            raise NotFoundException("One or both students not found")

        if not student1.room_id or not student2.room_id:
            raise ValidationException(
                "Both students must have assigned rooms to swap"
            )

        try:
            result = self.transfer_repo.execute_room_swap(
                db=db,
                student_1_id=request.student_1_id,
                student_2_id=request.student_2_id,
                swap_date=request.swap_date or datetime.utcnow(),
                reason=request.reason,
                handle_rent_difference=request.handle_rent_difference,
            )
            
            logger.info(
                f"Room swap executed between students: "
                f"{request.student_1_id} and {request.student_2_id}"
            )
            
            return result

        except SQLAlchemyError as e:
            logger.error(f"Database error executing room swap: {str(e)}")
            raise BusinessLogicException(
                f"Failed to execute room swap: {str(e)}"
            ) from e

    # -------------------------------------------------------------------------
    # Validation Helpers
    # -------------------------------------------------------------------------

    def _validate_transfer_eligibility(
        self,
        db: Session,
        student: Any,
        request: RoomTransferRequest,
    ) -> None:
        """
        Validate that student is eligible for transfer.

        Args:
            db: Database session
            student: Student ORM object
            request: Transfer request

        Raises:
            ValidationException: If student not eligible
        """
        # Check student status
        if student.student_status not in [
            StudentStatus.ACTIVE,
            StudentStatus.NOTICE_PERIOD,
        ]:
            raise ValidationException(
                f"Only active or notice-period students can request transfer. "
                f"Current status: {student.student_status}"
            )

        # Check if student has pending transfers
        pending = self.transfer_repo.get_pending_for_student(db, student.id)
        if pending:
            raise ValidationException(
                "Student already has a pending transfer request"
            )

        # Check if student currently has a room
        if not student.room_id:
            raise ValidationException(
                "Student must have an assigned room to request transfer"
            )

    def _validate_destination(
        self,
        db: Session,
        room_id: UUID,
        bed_id: Optional[UUID],
    ) -> None:
        """
        Validate destination room and bed availability.

        Args:
            db: Database session
            room_id: Destination room ID
            bed_id: Optional destination bed ID

        Raises:
            ValidationException: If destination invalid or unavailable
        """
        # Check room exists and has capacity
        # This would typically query room repository
        # Simplified for this example
        
        if bed_id:
            # Check bed availability
            bed = self.bed_assignment_repo.get_by_id(db, bed_id)
            if not bed:
                raise ValidationException(f"Bed not found: {bed_id}")
            
            if bed.is_occupied:
                raise ValidationException(f"Bed is already occupied: {bed_id}")
            
            if bed.room_id != room_id:
                raise ValidationException(
                    "Bed does not belong to specified room"
                )

    # -------------------------------------------------------------------------
    # Statistics
    # -------------------------------------------------------------------------

    def get_transfer_statistics(
        self,
        db: Session,
        hostel_id: UUID,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Get transfer statistics for a hostel.

        Args:
            db: Database session
            hostel_id: UUID of hostel
            start_date: Optional start date for statistics
            end_date: Optional end date for statistics

        Returns:
            Dictionary with various statistics
        """
        try:
            stats = self.transfer_repo.get_transfer_statistics(
                db,
                hostel_id=hostel_id,
                start_date=start_date,
                end_date=end_date,
            )
            return stats

        except SQLAlchemyError as e:
            logger.error(f"Database error retrieving transfer statistics: {str(e)}")
            raise BusinessLogicException(
                f"Failed to retrieve transfer statistics: {str(e)}"
            ) from e