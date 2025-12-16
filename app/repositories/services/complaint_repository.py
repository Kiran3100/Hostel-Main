# app/repositories/services/complaint_repository.py
from datetime import datetime
from typing import List, Union
from uuid import UUID

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.repositories.base import BaseRepository
from app.models.services import Complaint
from app.schemas.common.enums import ComplaintStatus, ComplaintCategory, Priority


class ComplaintRepository(BaseRepository[Complaint]):
    def __init__(self, session: Session):
        super().__init__(session, Complaint)

    def list_open_for_hostel(
        self,
        hostel_id: UUID,
        *,
        category: Union[ComplaintCategory, None] = None,
        priority: Union[Priority, None] = None,
    ) -> List[Complaint]:
        stmt = self._base_select().where(
            Complaint.hostel_id == hostel_id,
            Complaint.status.in_(
                [ComplaintStatus.OPEN, ComplaintStatus.IN_PROGRESS]
            ),
        )
        if category is not None:
            stmt = stmt.where(Complaint.category == category)
        if priority is not None:
            stmt = stmt.where(Complaint.priority == priority)
        stmt = stmt.order_by(Complaint.opened_at.asc())
        return self.session.execute(stmt).scalars().all()

    def list_for_student(self, student_id: UUID) -> List[Complaint]:
        stmt = (
            self._base_select()
            .where(Complaint.student_id == student_id)
            .order_by(Complaint.opened_at.desc())
        )
        return self.session.execute(stmt).scalars().all()

    def list_for_supervisor(
        self,
        supervisor_id: UUID,
        *,
        include_closed: bool = False,
    ) -> List[Complaint]:
        stmt = self._base_select().where(Complaint.assigned_to_id == supervisor_id)
        if not include_closed:
            stmt = stmt.where(
                Complaint.status.in_(
                    [ComplaintStatus.OPEN, ComplaintStatus.IN_PROGRESS]
                )
            )
        return self.session.execute(stmt).scalars().all()