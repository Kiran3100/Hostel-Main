# app/repositories/transactions/booking_repository.py
from __future__ import annotations

from datetime import datetime
from typing import List
from uuid import UUID

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.repositories.base import BaseRepository
from app.models.transactions import Booking
from app.schemas.common.enums import BookingStatus


class BookingRepository(BaseRepository[Booking]):
    def __init__(self, session: Session):
        super().__init__(session, Booking)

    def list_pending_for_hostel(self, hostel_id: UUID) -> List[Booking]:
        stmt = (
            self._base_select()
            .where(
                and_(
                    Booking.hostel_id == hostel_id,
                    Booking.booking_status == BookingStatus.PENDING,
                )
            )
            .order_by(Booking.booking_date.asc())
        )
        return self.session.execute(stmt).scalars().all()

    def list_active_for_visitor(self, visitor_id: UUID) -> List[Booking]:
        stmt = (
            self._base_select()
            .where(
                and_(
                    Booking.visitor_id == visitor_id,
                    Booking.booking_status.in_(
                        [
                            BookingStatus.PENDING,
                            BookingStatus.CONFIRMED,
                            BookingStatus.CHECKED_IN,
                        ]
                    ),
                )
            )
            .order_by(Booking.booking_date.desc())
        )
        return self.session.execute(stmt).scalars().all()