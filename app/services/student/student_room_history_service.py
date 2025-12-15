# app/services/student/student_room_history_service.py
from __future__ import annotations

from datetime import date
from typing import Callable, List
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.associations import StudentRoomAssignmentRepository
from app.repositories.core import HostelRepository, RoomRepository, StudentRepository
from app.schemas.student.student_room_history import (
    RoomHistoryResponse,
    RoomHistoryItem,
)
from app.services.common import UnitOfWork, errors


class StudentRoomHistoryService:
    """
    Student room/bed history:

    - Build RoomHistoryResponse from StudentRoomAssignment records.
    """

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _get_assignment_repo(self, uow: UnitOfWork) -> StudentRoomAssignmentRepository:
        return uow.get_repo(StudentRoomAssignmentRepository)

    def _get_hostel_repo(self, uow: UnitOfWork) -> HostelRepository:
        return uow.get_repo(HostelRepository)

    def _get_room_repo(self, uow: UnitOfWork) -> RoomRepository:
        return uow.get_repo(RoomRepository)

    def _get_student_repo(self, uow: UnitOfWork) -> StudentRepository:
        return uow.get_repo(StudentRepository)

    # ------------------------------------------------------------------ #
    # API
    # ------------------------------------------------------------------ #
    def get_room_history(self, student_id: UUID) -> RoomHistoryResponse:
        with UnitOfWork(self._session_factory) as uow:
            assignment_repo = self._get_assignment_repo(uow)
            hostel_repo = self._get_hostel_repo(uow)
            room_repo = self._get_room_repo(uow)
            student_repo = self._get_student_repo(uow)

            student = student_repo.get(student_id)
            if student is None or not getattr(student, "user", None):
                raise errors.NotFoundError(f"Student {student_id} not found")

            assignments = assignment_repo.get_history_for_student(student_id)
            if not assignments:
                # Build empty response
                return RoomHistoryResponse(
                    student_id=student_id,
                    student_name=student.user.full_name,
                    hostel_id=student.hostel_id,
                    hostel_name=hostel_repo.get(student.hostel_id).name if hostel_repo.get(student.hostel_id) else "",
                    room_history=[],
                )

            hostel = hostel_repo.get(assignments[0].hostel_id)
            hostel_name = hostel.name if hostel else ""

            items: List[RoomHistoryItem] = []
            for a in assignments:
                room = room_repo.get(a.room_id)
                room_number = room.room_number if room else ""
                room_type = (
                    room.room_type.value if room and hasattr(room.room_type, "value") else ""
                )

                dur = None
                if a.move_out_date:
                    dur = (a.move_out_date - a.move_in_date).days

                items.append(
                    RoomHistoryItem(
                        id=a.id,
                        created_at=a.created_at,
                        updated_at=a.updated_at,
                        hostel_id=a.hostel_id,
                        hostel_name=hostel_name,
                        room_id=a.room_id,
                        room_number=room_number,
                        room_type=room_type,
                        bed_id=a.bed_id,
                        bed_number=None,
                        move_in_date=a.move_in_date,
                        move_out_date=a.move_out_date,
                        duration_days=dur,
                        rent_amount=a.rent_amount,
                        reason=a.reason,
                        requested_by=None,
                        approved_by=None,
                    )
                )

        return RoomHistoryResponse(
            student_id=student_id,
            student_name=student.user.full_name,
            hostel_id=student.hostel_id,
            hostel_name=hostel_name,
            room_history=items,
        )