# app/services/leave/leave_service.py
from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.services import LeaveApplicationRepository
from app.repositories.core import (
    StudentRepository,
    HostelRepository,
    RoomRepository,
)
from app.schemas.common.enums import LeaveStatus
from app.schemas.common.pagination import PaginationParams, PaginatedResponse
from app.schemas.leave import (
    LeaveApplicationRequest,
    LeaveCancellationRequest,
    LeaveUpdate,
    LeaveResponse,
    LeaveDetail,
    LeaveListItem,
)
from app.services.common import UnitOfWork, errors


class LeaveService:
    """
    Core leave service:

    - Apply for leave (student)
    - Cancel leave (student)
    - Get leave detail
    - List leaves (by student / by hostel)
    - Update leave (admin/supervisor, before approval)
    """

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _get_leave_repo(self, uow: UnitOfWork) -> LeaveApplicationRepository:
        return uow.get_repo(LeaveApplicationRepository)

    def _get_student_repo(self, uow: UnitOfWork) -> StudentRepository:
        return uow.get_repo(StudentRepository)

    def _get_hostel_repo(self, uow: UnitOfWork) -> HostelRepository:
        return uow.get_repo(HostelRepository)

    def _get_room_repo(self, uow: UnitOfWork) -> RoomRepository:
        return uow.get_repo(RoomRepository)

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    # ------------------------------------------------------------------ #
    # Mapping helpers
    # ------------------------------------------------------------------ #
    def _to_response(
        self,
        leave,
        *,
        student_name: str,
        hostel_name: str,
    ) -> LeaveResponse:
        return LeaveResponse(
            id=leave.id,
            created_at=leave.created_at,
            updated_at=leave.updated_at,
            student_id=leave.student_id,
            student_name=student_name,
            hostel_id=leave.hostel_id,
            hostel_name=hostel_name,
            leave_type=leave.leave_type,
            from_date=leave.from_date,
            to_date=leave.to_date,
            total_days=leave.total_days,
            status=leave.status,
            applied_at=leave.created_at,
        )

    def _to_detail(
        self,
        leave,
        *,
        student_name: str,
        student_room: Optional[str],
        hostel_name: str,
    ) -> LeaveDetail:
        # We don't have explicit approved_at/rejected_at/cancelled_at timestamps in the model.
        applied_at = leave.created_at
        approved_at = None
        rejected_at = None
        cancelled_at = None

        approved_by_name = None
        rejected_by_name = None

        return LeaveDetail(
            id=leave.id,
            created_at=leave.created_at,
            updated_at=leave.updated_at,
            student_id=leave.student_id,
            student_name=student_name,
            student_room=student_room,
            hostel_id=leave.hostel_id,
            hostel_name=hostel_name,
            leave_type=leave.leave_type,
            from_date=leave.from_date,
            to_date=leave.to_date,
            total_days=leave.total_days,
            reason=leave.reason,
            contact_during_leave=leave.contact_during_leave,
            emergency_contact=leave.emergency_contact,
            supporting_document_url=leave.supporting_document_url,
            status=leave.status,
            applied_at=applied_at,
            approved_at=approved_at,
            rejected_at=rejected_at,
            cancelled_at=cancelled_at,
            approved_by=leave.approved_by_id,
            approved_by_name=approved_by_name,
            rejected_by=leave.rejected_by_id,
            rejected_by_name=rejected_by_name,
            rejection_reason=leave.rejection_reason,
            cancellation_reason=leave.cancellation_reason,
        )

    def _to_list_item(
        self,
        leave,
        *,
        student_name: str,
        room_number: Optional[str],
    ) -> LeaveListItem:
        return LeaveListItem(
            id=leave.id,
            student_name=student_name,
            room_number=room_number,
            leave_type=leave.leave_type,
            from_date=leave.from_date,
            to_date=leave.to_date,
            total_days=leave.total_days,
            status=leave.status,
            applied_at=leave.created_at,
        )

    # ------------------------------------------------------------------ #
    # Apply / cancel
    # ------------------------------------------------------------------ #
    def apply_for_leave(self, data: LeaveApplicationRequest) -> LeaveDetail:
        """
        Create a leave application from a student request.

        - Validates student & hostel existence
        - Validates that student belongs to the hostel
        - Computes total_days
        - Sets initial status to PENDING
        """
        total_days = (data.to_date - data.from_date).days + 1
        if total_days <= 0:
            raise errors.ValidationError("to_date must be after or equal to from_date")

        with UnitOfWork(self._session_factory) as uow:
            leave_repo = self._get_leave_repo(uow)
            student_repo = self._get_student_repo(uow)
            hostel_repo = self._get_hostel_repo(uow)
            room_repo = self._get_room_repo(uow)

            student = student_repo.get(data.student_id)
            if student is None:
                raise errors.NotFoundError(f"Student {data.student_id} not found")

            hostel = hostel_repo.get(data.hostel_id)
            if hostel is None:
                raise errors.NotFoundError(f"Hostel {data.hostel_id} not found")

            if student.hostel_id != data.hostel_id:
                raise errors.ValidationError("Student does not belong to this hostel")

            payload = {
                "student_id": data.student_id,
                "hostel_id": data.hostel_id,
                "leave_type": data.leave_type,
                "from_date": data.from_date,
                "to_date": data.to_date,
                "total_days": total_days,
                "reason": data.reason,
                "contact_during_leave": data.contact_during_leave,
                "emergency_contact": data.emergency_contact,
                "supporting_document_url": data.supporting_document_url,
                "status": LeaveStatus.PENDING,
                "rejection_reason": None,
                "cancellation_reason": None,
            }
            leave = leave_repo.create(payload)  # type: ignore[arg-type]
            uow.commit()

            student_name = (
                student.user.full_name if getattr(student, "user", None) else ""
            )
            room_number = None
            if student.room_id:
                room = room_repo.get(student.room_id)
                room_number = room.room_number if room else None

            return self._to_detail(
                leave,
                student_name=student_name,
                student_room=room_number,
                hostel_name=hostel.name,
            )

    def cancel_leave(self, data: LeaveCancellationRequest) -> LeaveDetail:
        """
        Student-initiated cancellation of a leave application.

        Allowed statuses: PENDING, APPROVED.
        """
        with UnitOfWork(self._session_factory) as uow:
            leave_repo = self._get_leave_repo(uow)
            student_repo = self._get_student_repo(uow)
            hostel_repo = self._get_hostel_repo(uow)
            room_repo = self._get_room_repo(uow)

            leave = leave_repo.get(data.leave_id)
            if leave is None:
                raise errors.NotFoundError(f"Leave {data.leave_id} not found")

            if leave.student_id != data.student_id:
                raise errors.ValidationError("Student does not own this leave application")

            if leave.status not in (LeaveStatus.PENDING, LeaveStatus.APPROVED):
                raise errors.ValidationError(
                    f"Leave {data.leave_id} cannot be cancelled from status {leave.status}"
                )

            leave.status = LeaveStatus.CANCELLED  # type: ignore[attr-defined]
            leave.cancellation_reason = data.cancellation_reason  # type: ignore[attr-defined]

            uow.session.flush()  # type: ignore[union-attr]
            uow.commit()

            student = student_repo.get(leave.student_id)
            hostel = hostel_repo.get(leave.hostel_id)
            student_name = (
                student.user.full_name if student and getattr(student, "user", None) else ""
            )
            room_number = None
            if student and student.room_id:
                room = room_repo.get(student.room_id)
                room_number = room.room_number if room else None

            hostel_name = hostel.name if hostel else ""
            return self._to_detail(
                leave,
                student_name=student_name,
                student_room=room_number,
                hostel_name=hostel_name,
            )

    # ------------------------------------------------------------------ #
    # Generic read/update
    # ------------------------------------------------------------------ #
    def get_leave(self, leave_id: UUID) -> LeaveDetail:
        with UnitOfWork(self._session_factory) as uow:
            leave_repo = self._get_leave_repo(uow)
            student_repo = self._get_student_repo(uow)
            hostel_repo = self._get_hostel_repo(uow)
            room_repo = self._get_room_repo(uow)

            leave = leave_repo.get(leave_id)
            if leave is None:
                raise errors.NotFoundError(f"Leave {leave_id} not found")

            student = student_repo.get(leave.student_id)
            hostel = hostel_repo.get(leave.hostel_id)

            student_name = (
                student.user.full_name if student and getattr(student, "user", None) else ""
            )
            room_number = None
            if student and student.room_id:
                room = room_repo.get(student.room_id)
                room_number = room.room_number if room else None

            hostel_name = hostel.name if hostel else ""

            return self._to_detail(
                leave,
                student_name=student_name,
                student_room=room_number,
                hostel_name=hostel_name,
            )

    def update_leave(self, leave_id: UUID, data: LeaveUpdate) -> LeaveDetail:
        """
        Update a leave application (typically before approval).

        If from_date/to_date change but total_days is omitted, total_days is recomputed.
        """
        with UnitOfWork(self._session_factory) as uow:
            leave_repo = self._get_leave_repo(uow)

            leave = leave_repo.get(leave_id)
            if leave is None:
                raise errors.NotFoundError(f"Leave {leave_id} not found")

            mapping = data.model_dump(exclude_unset=True)

            # Recompute total_days if date range changed and total_days omitted
            if ("from_date" in mapping or "to_date" in mapping) and "total_days" not in mapping:
                fd = mapping.get("from_date", leave.from_date)
                td = mapping.get("to_date", leave.to_date)
                mapping["total_days"] = (td - fd).days + 1

            for field, value in mapping.items():
                if hasattr(leave, field) and field != "id":
                    setattr(leave, field, value)

            uow.session.flush()  # type: ignore[union-attr]
            uow.commit()

        return self.get_leave(leave_id)

    # ------------------------------------------------------------------ #
    # Listing
    # ------------------------------------------------------------------ #
    def list_leaves_for_student(
        self,
        student_id: UUID,
        params: PaginationParams,
        *,
        status: Optional[LeaveStatus] = None,
    ) -> PaginatedResponse[LeaveListItem]:
        with UnitOfWork(self._session_factory) as uow:
            leave_repo = self._get_leave_repo(uow)
            student_repo = self._get_student_repo(uow)
            room_repo = self._get_room_repo(uow)

            student = student_repo.get(student_id)
            student_name = (
                student.user.full_name if student and getattr(student, "user", None) else ""
            )
            room_number = None
            if student and student.room_id:
                room = room_repo.get(student.room_id)
                room_number = room.room_number if room else None

            records = leave_repo.list_for_student(student_id)
            if status is not None:
                records = [l for l in records if l.status == status]

            total = len(records)
            sliced = records[params.offset : params.offset + params.limit]

            items = [
                self._to_list_item(l, student_name=student_name, room_number=room_number)
                for l in sliced
            ]

            return PaginatedResponse[LeaveListItem].create(
                items=items,
                total_items=total,
                page=params.page,
                page_size=params.page_size,
            )

    def list_pending_for_hostel(
        self,
        hostel_id: UUID,
        params: PaginationParams,
    ) -> PaginatedResponse[LeaveListItem]:
        """
        List pending leave applications for a hostel.
        """
        with UnitOfWork(self._session_factory) as uow:
            leave_repo = self._get_leave_repo(uow)
            hostel_repo = self._get_hostel_repo(uow)
            student_repo = self._get_student_repo(uow)
            room_repo = self._get_room_repo(uow)

            hostel = hostel_repo.get(hostel_id)
            if hostel is None:
                raise errors.NotFoundError(f"Hostel {hostel_id} not found")

            records = leave_repo.list_pending_for_hostel(hostel_id)
            total = len(records)
            sliced = records[params.offset : params.offset + params.limit]

            items: List[LeaveListItem] = []
            for l in sliced:
                st = student_repo.get(l.student_id)
                student_name = (
                    st.user.full_name if st and getattr(st, "user", None) else ""
                )
                room_number = None
                if st and st.room_id:
                    room = room_repo.get(st.room_id)
                    room_number = room.room_number if room else None

                items.append(
                    self._to_list_item(
                        l,
                        student_name=student_name,
                        room_number=room_number,
                    )
                )

            return PaginatedResponse[LeaveListItem].create(
                items=items,
                total_items=total,
                page=params.page,
                page_size=params.page_size,
            )