# app/services/student/room_transfer_service.py
"""
Room Transfer Service

Handles student room/bed transfers and swaps.
"""

from __future__ import annotations

from typing import List
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.student import RoomTransferHistoryRepository, StudentRepository
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
from app.core.exceptions import ValidationException, BusinessLogicException
from app.models.base.enums import StudentStatus


class RoomTransferService:
    """
    High-level service for room/bed transfers and history.

    Responsibilities:
    - Submit transfer requests
    - Approve/reject transfers
    - Execute bulk transfers
    - Handle room swaps
    - Provide room history views
    """

    def __init__(
        self,
        transfer_repo: RoomTransferHistoryRepository,
        student_repo: StudentRepository,
        bed_assignment_repo: BedAssignmentRepository,
    ) -> None:
        self.transfer_repo = transfer_repo
        self.student_repo = student_repo
        self.bed_assignment_repo = bed_assignment_repo

    # -------------------------------------------------------------------------
    # History
    # -------------------------------------------------------------------------

    def get_room_history(
        self,
        db: Session,
        student_id: UUID,
    ) -> RoomHistoryResponse:
        """
        Return room history (assignments/transfers) for a student.
        """
        student = self.student_repo.get_by_id(db, student_id)
        if not student:
            raise ValidationException("Student not found")

        history_rows = self.transfer_repo.get_history_for_student(db, student_id)

        items = [RoomHistoryItem.model_validate(h) for h in history_rows]

        return RoomHistoryResponse(
            student_id=student_id,
            student_name=student.user.full_name if student.user else None,
            current_room_id=student.room_id,
            current_bed_id=student.bed_id,
            room_history=items,
            total_assignments=len(items),
            total_transfers=sum(1 for i in items if i.transfer_type == "transfer"),
            has_changed_rooms=any(i.transfer_type == "transfer" for i in items),
        )

    # -------------------------------------------------------------------------
    # Transfers
    # -------------------------------------------------------------------------

    def submit_transfer_request(
        self,
        db: Session,
        request: RoomTransferRequest,
    ) -> RoomTransferStatus:
        """
        Submit a room transfer request for approval.
        """
        student = self.student_repo.get_by_id(db, request.student_id)
        if not student:
            raise ValidationException("Student not found")

        if student.student_status not in [StudentStatus.ACTIVE, StudentStatus.NOTICE_PERIOD]:
            raise BusinessLogicException("Only active or notice-period students can request transfer")

        obj = self.transfer_repo.create_transfer_request(
            db=db,
            data=request.model_dump(exclude_none=True),
        )
        return RoomTransferStatus.model_validate(obj)

    def approve_transfer(
        self,
        db: Session,
        approval: RoomTransferApproval,
    ) -> RoomTransferStatus:
        """
        Approve a transfer and move the student to the new room/bed.
        """
        transfer = self.transfer_repo.get_by_id(db, approval.transfer_request_id)
        if not transfer:
            raise ValidationException("Transfer request not found")

        if approval.approved:
            # Perform room transfer via repository (handles assignment & history)
            obj = self.transfer_repo.approve_and_execute_transfer(
                db=db,
                transfer=transfer,
                approved_by=approval.approved_by,
                new_room_id=approval.new_room_id,
                new_bed_id=approval.new_bed_id,
                effective_date=approval.transfer_date,
                notes=approval.notes,
            )
        else:
            obj = self.transfer_repo.reject_transfer(
                db=db,
                transfer=transfer,
                rejected_by=approval.approved_by,
                reason=approval.rejection_reason,
            )

        return RoomTransferStatus.model_validate(obj)

    def get_transfer_status(
        self,
        db: Session,
        transfer_id: UUID,
    ) -> RoomTransferStatus:
        """
        Get current status for a transfer request.
        """
        obj = self.transfer_repo.get_by_id(db, transfer_id)
        if not obj:
            raise ValidationException("Transfer request not found")
        return RoomTransferStatus.model_validate(obj)

    # -------------------------------------------------------------------------
    # Bulk transfers
    # -------------------------------------------------------------------------

    def execute_bulk_transfer(
        self,
        db: Session,
        bulk_request: BulkRoomTransfer,
        executed_by: UUID,
    ) -> List[RoomTransferStatus]:
        """
        Execute bulk transfers (admin operation).

        Each SingleTransfer is executed immediately without approval workflow.
        """
        if not bulk_request.confirm_bulk_transfer:
            raise ValidationException("Bulk transfer must be explicitly confirmed")

        results: List[RoomTransferStatus] = []

        for tr in bulk_request.transfers:
            results.append(
                self._execute_single_transfer(
                    db=db,
                    transfer=tr,
                    transfer_date=bulk_request.transfer_date,
                    reason=bulk_request.reason,
                    executed_by=executed_by,
                    skip_on_error=bulk_request.skip_on_error,
                    prorated_rent=bulk_request.prorated_rent,
                )
            )

        return results

    def _execute_single_transfer(
        self,
        db: Session,
        transfer: SingleTransfer,
        transfer_date,
        reason: str | None,
        executed_by: UUID,
        skip_on_error: bool,
        prorated_rent: bool,
    ) -> RoomTransferStatus:
        """
        Helper to execute a single transfer in bulk context.
        """
        student = self.student_repo.get_by_id(db, transfer.student_id)
        if not student:
            if skip_on_error:
                return RoomTransferStatus(
                    transfer_request_id=None,
                    status="failed",
                    reason="Student not found",
                )
            raise ValidationException("Student not found")

        try:
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
    # Swaps
    # -------------------------------------------------------------------------

    def request_room_swap(
        self,
        db: Session,
        request: RoomSwapRequest,
    ) -> None:
        """
        Record a room swap request between two students.

        Execution can be handled synchronously or via a separate workflow,
        depending on your business rules; here we assume immediate swap.
        """
        if request.student_1_id == request.student_2_id:
            raise ValidationException("Cannot swap rooms with the same student")

        # Use repository helper to perform swap and record histories
        self.transfer_repo.execute_room_swap(
            db=db,
            student_1_id=request.student_1_id,
            student_2_id=request.student_2_id,
            swap_date=request.swap_date,
            reason=request.reason,
            handle_rent_difference=request.handle_rent_difference,
        )