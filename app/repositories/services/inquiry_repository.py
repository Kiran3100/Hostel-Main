# app/repositories/services/inquiry_repository.py
from __future__ import annotations

from typing import List
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.base import BaseRepository
from app.models.services import Inquiry
from app.schemas.common.enums import InquiryStatus


class InquiryRepository(BaseRepository[Inquiry]):
    def __init__(self, session: Session):
        super().__init__(session, Inquiry)

    def list_open_for_hostel(self, hostel_id: UUID) -> List[Inquiry]:
        stmt = (
            self._base_select()
            .where(
                Inquiry.hostel_id == hostel_id,
                Inquiry.status == InquiryStatus.PENDING,
            )
            .order_by(Inquiry.created_at.asc())
        )
        return self.session.execute(stmt).scalars().all()