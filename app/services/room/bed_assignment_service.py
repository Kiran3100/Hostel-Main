# app/services/room/bed_assignment_service.py
from __future__ import annotations

from datetime import date
from typing import Callable, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.core import BedRepository, RoomRepository, StudentRepository, HostelRepository
from app.repositories.associations import StudentRoomAssignmentRepository
from app.schemas.room.bed_base import BedAssignmentRequest, BedReleaseRequest
from app.schemas.room.bed_response import (
    BedAssignment,
    BedHistory,
    BedAssignmentHistory,
)
from app.schemas.common.enums import BedStatus
from app.services.common import UnitOfWork, errors


class BedAssignmentService:
    """
    Bed assignment history service:

    - Assign bed to student (update Bed + Student + StudentRoomAssignment)
    - Release bed from student
    - Get bed history
    """

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _get_bed_repo(self, uow: UnitOfWork) -> BedRepository:
        return uow.get_repo(BedRepository)

    def _get_room_repo(self, uow: UnitOfWork) -> RoomRepository:
        return uow.get_repo(RoomRepository)

    def _get_student_repo(self, uow: UnitOfWork) -> StudentRepository:
        return uow.get_repo(StudentRepository)

    def _get_hostel_repo(self, uow: UnitOfWork) -> HostelRepository:
        return uow.get_repo(HostelRepository)

    def _get_assignment_repo(self, uow: UnitOfWork) -> StudentRoomAssignmentRepository:
        return uow.get_repo(StudentRoomAssignmentRepository)

    # ------------------------------------------------------------------ #
    # Assign
    # ------------------------------------------------------------------ #
    def assign_bed(self, req: BedAssignmentRequest) -> BedAssignment:
        with UnitOfWork(self._session_factory) as uow:
            bed_repo = self._get_bed_repo(uow)
            room_repo = self._get_room_repo(uow)
            student_repo = self._get_student_repo(uow)
            hostel_repo = self._get_hostel_repo(uow)
            assignment_repo = self._get_assignment_repo(uow)

            bed = bed_repo.get(req.bed_id)
            if bed is None:
                raise errors.NotFoundError(f"Bed {req.bed_id} not found")

            room = room_repo.get(bed.room_id)
            if room is None:
                raise errors.NotFoundError(f"Room {bed.room_id} not found")

            hostel = hostel_repo.get(UUID(room.hostel_id) if isinstance(room.hostel_id, str) else room.hostel_id)
            if hostel is None:
                raise errors.NotFoundError(f"Hostel {room.hostel_id} not found")

            student = student_repo.get(req.student_id)
            if student is None or not getattr(student, "user", None):
                raise errors.NotFoundError(f"Student {req.student_id} not found")

            # Ensure bed is free
            if bed.current_student_id is not None:
                raise errors.ConflictError("Bed is already occupied")

            # Update bed
            bed.current_student_id = student.id  # type: ignore[attr-defined]
            bed.occupied_from = req.occupied_from  # type: ignore[attr-defined]
            bed.status = BedStatus.OCCUPIED  # type: ignore[attr-defined]

            # Update student
            student.room_id = room.id  # type: ignore[attr-defined]
            student.bed_id = bed.id  # type: ignore[attr-defined]

            # Create assignment history
            assignment_repo.create(
                {
                    "student_id": student.id,
                    "hostel_id": hostel.id,
                    "room_id": room.id,
                    "bed_id": bed.id,
                    "move_in_date": req.occupied_from,
                    "move_out_date": None,
                    "rent_amount": student.monthly_rent_amount,
                    "reason": None,
                }
            )

            uow.session.flush()  # type: ignore[union-attr]
            uow.commit()

            return BedAssignment(
                id=None,
                created_at=None,
                updated_at=None,
                bed_id=bed.id,
                room_id=room.id,
                room_number=room.room_number,
                bed_number=bed.bed_number,
                student_id=student.id,
                student_name=student.user.full_name,
                occupied_from=req.occupied_from,
                expected_vacate_date=None,
                monthly_rent=student.monthly_rent_amount,
            )

    # ------------------------------------------------------------------ #
    # Release
    # ------------------------------------------------------------------ #
    def release_bed(self, req: BedReleaseRequest) -> None:
        with UnitOfWork(self._session_factory) as uow:
            bed_repo = self._get_bed_repo(uow)
            student_repo = self._get_student_repo(uow)
            assignment_repo = self._get_assignment_repo(uow)

            bed = bed_repo.get(req.bed_id)
            if bed is None:
                raise errors.NotFoundError(f"Bed {req.bed_id} not found")

            if bed.current_student_id is None:
                raise errors.ConflictError("Bed is not currently occupied")

            student = student_repo.get(bed.current_student_id)
            if student is None or not getattr(student, "user", None):
                raise errors.NotFoundError(f"Student {bed.current_student_id} not found")

            # Clear bed
            bed.current_student_id = None  # type: ignore[attr-defined]
            bed.occupied_from = None  # type: ignore[attr-defined]
            bed.status = BedStatus.AVAILABLE  # type: ignore[attr-defined]

            # Clear student bed assign (keep room_id if you want history)
            student.bed_id = None  # type: ignore[attr-defined]

            # Close active assignment
            active = assignment_repo.get_active_assignment(student.id)
            if active:
                active.move_out_date = req.release_date  # type: ignore[attr-defined]
                if req.reason:
                    active.reason = req.reason  # type: ignore[attr-defined]

            uow.session.flush()  # type: ignore[union-attr]
            uow.commit()

    # ------------------------------------------------------------------ #
    # History
    # ------------------------------------------------------------------ #
    def get_bed_history(self, bed_id: UUID) -> BedHistory:
        with UnitOfWork(self._session_factory) as uow:
            bed_repo = self._get_bed_repo(uow)
            room_repo = self._get_room_repo(uow)
            assignment_repo = self._get_assignment_repo(uow)
            student_repo = self._get_student_repo(uow)

            bed = bed_repo.get(bed_id)
            if bed is None:
                raise errors.NotFoundError(f"Bed {bed_id} not found")

            room = room_repo.get(bed.room_id)
            room_number = room.room_number if room else ""

            assignments = assignment_repo.get_multi(
                skip=0,
                limit=None,  # type: ignore[arg-type]
                filters={"bed_id": bed_id},
            )

            history_items: List[BedAssignmentHistory] = []
            for a in assignments:
                st = student_repo.get(a.student_id)
                student_name = st.user.full_name if st and getattr(st, "user", None) else ""
                dur = None
                if a.move_out_date:
                    dur = (a.move_out_date - a.move_in_date).days
                history_items.append(
                    BedAssignmentHistory(
                        student_id=a.student_id,
                        student_name=student_name,
                        move_in_date=a.move_in_date,
                        move_out_date=a.move_out_date,
                        duration_days=dur,
                    )
                )

        return BedHistory(
            bed_id=bed_id,
            room_number=room_number,
            bed_number=bed.bed_number,
            assignments=history_items,
        )