# app/repositories/visitor/hostel_booking_repository.py
from __future__ import annotations

from typing import List
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.base import BaseRepository
from app.models.visitor import HostelBooking


class HostelBookingRepository(BaseRepository[HostelBooking]):
    def __init__(self, session: Session):
        super().__init__(session, HostelBooking)

    def list_for_visitor(self, visitor_id: UUID) -> List[HostelBooking]:
        stmt = (
            self._base_select()
            .where(HostelBooking.visitor_id == visitor_id)
            .order_by(HostelBooking.check_in_date.desc())
        )
        return self.session.execute(stmt).scalars().all()