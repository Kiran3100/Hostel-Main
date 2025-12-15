# app/repositories/associations/student_room_assignment_repository.py
from __future__ import annotations

from datetime import date
from typing import List, Optional
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.repositories.base import BaseRepository
from app.models.associations import StudentRoomAssignment


class StudentRoomAssignmentRepository(BaseRepository[StudentRoomAssignment]):
    def __init__(self, session: Session):
        super().__init__(session, StudentRoomAssignment)

    def get_history_for_student(self, student_id: UUID) -> List[StudentRoomAssignment]:
        stmt = (
            self._base_select()
            .where(StudentRoomAssignment.student_id == student_id)
            .order_by(StudentRoomAssignment.move_in_date.asc())
        )
        return self.session.execute(stmt).scalars().all()

    def get_active_assignment(self, student_id: UUID) -> Optional[StudentRoomAssignment]:
        stmt = (
            self._base_select()
            .where(
                and_(
                    StudentRoomAssignment.student_id == student_id,
                    StudentRoomAssignment.move_out_date.is_(None),
                )
            )
            .order_by(StudentRoomAssignment.move_in_date.desc())
            .limit(1)
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def get_assignments_for_room(
        self,
        room_id: UUID,
        *,
        active_only: bool = True,
    ) -> List[StudentRoomAssignment]:
        stmt = self._base_select().where(StudentRoomAssignment.room_id == room_id)
        if active_only:
            stmt = stmt.where(StudentRoomAssignment.move_out_date.is_(None))
        return self.session.execute(stmt).scalars().all()