# app/repositories/services/leave_application_repository.py
from datetime import date
from typing import List
from uuid import UUID

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.repositories.base import BaseRepository
from app.models.services import LeaveApplication
from app.schemas.common.enums import LeaveStatus


class LeaveApplicationRepository(BaseRepository[LeaveApplication]):
    def __init__(self, session: Session):
        super().__init__(session, LeaveApplication)

    def list_for_student(self, student_id: UUID) -> List[LeaveApplication]:
        stmt = (
            self._base_select()
            .where(LeaveApplication.student_id == student_id)
            .order_by(LeaveApplication.from_date.desc())
        )
        return self.session.execute(stmt).scalars().all()

    def list_pending_for_hostel(self, hostel_id: UUID) -> List[LeaveApplication]:
        stmt = (
            self._base_select()
            .where(
                and_(
                    LeaveApplication.hostel_id == hostel_id,
                    LeaveApplication.status == LeaveStatus.PENDING,
                )
            )
            .order_by(LeaveApplication.from_date.asc())
        )
        return self.session.execute(stmt).scalars().all()