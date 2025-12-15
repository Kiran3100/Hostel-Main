# app/repositories/transactions/payment_repository.py
from __future__ import annotations

from datetime import date
from typing import List, Optional
from uuid import UUID

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.repositories.base import BaseRepository
from app.models.transactions import Payment
from app.schemas.common.enums import PaymentStatus, PaymentType


class PaymentRepository(BaseRepository[Payment]):
    def __init__(self, session: Session):
        super().__init__(session, Payment)

    def list_for_student(
        self,
        student_id: UUID,
        *,
        status: Optional[PaymentStatus] = None,
    ) -> List[Payment]:
        stmt = self._base_select().where(Payment.student_id == student_id)
        if status is not None:
            stmt = stmt.where(Payment.payment_status == status)
        stmt = stmt.order_by(Payment.due_date.asc().nulls_last())
        return self.session.execute(stmt).scalars().all()

    def list_due_for_hostel(
        self,
        hostel_id: UUID,
        *,
        on_or_before: Optional[date] = None,
    ) -> List[Payment]:
        stmt = self._base_select().where(
            Payment.hostel_id == hostel_id,
            Payment.payment_status == PaymentStatus.PENDING,
        )
        if on_or_before is not None:
            stmt = stmt.where(Payment.due_date <= on_or_before)
        stmt = stmt.order_by(Payment.due_date.asc())
        return self.session.execute(stmt).scalars().all()

    def list_for_booking(self, booking_id: UUID) -> List[Payment]:
        stmt = self._base_select().where(Payment.booking_id == booking_id)
        return self.session.execute(stmt).scalars().all()