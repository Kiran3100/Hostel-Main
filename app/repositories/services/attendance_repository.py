# app/repositories/services/attendance_repository.py
from datetime import date
from typing import List
from uuid import UUID

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.repositories.base import BaseRepository
from app.models.services import Attendance
from app.schemas.common.enums import AttendanceStatus


class AttendanceRepository(BaseRepository[Attendance]):
    def __init__(self, session: Session):
        super().__init__(session, Attendance)

    def list_for_student_range(
        self,
        student_id: UUID,
        start_date: date,
        end_date: date,
    ) -> List[Attendance]:
        stmt = (
            self._base_select()
            .where(
                and_(
                    Attendance.student_id == student_id,
                    Attendance.attendance_date >= start_date,
                    Attendance.attendance_date <= end_date,
                )
            )
            .order_by(Attendance.attendance_date.asc())
        )
        return self.session.execute(stmt).scalars().all()

    def list_for_hostel_date(
        self,
        hostel_id: UUID,
        day: date,
    ) -> List[Attendance]:
        stmt = (
            self._base_select()
            .where(
                and_(
                    Attendance.hostel_id == hostel_id,
                    Attendance.attendance_date == day,
                )
            )
        )
        return self.session.execute(stmt).scalars().all()

    def list_by_status_for_hostel(
        self,
        hostel_id: UUID,
        day: date,
        status: AttendanceStatus,
    ) -> List[Attendance]:
        stmt = (
            self._base_select()
            .where(
                and_(
                    Attendance.hostel_id == hostel_id,
                    Attendance.attendance_date == day,
                    Attendance.status == status,
                )
            )
        )
        return self.session.execute(stmt).scalars().all()