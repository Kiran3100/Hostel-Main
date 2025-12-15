# app/repositories/visitor/hostel_review_repository.py
from __future__ import annotations

from typing import List
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.base import BaseRepository
from app.models.visitor import HostelReview


class HostelReviewRepository(BaseRepository[HostelReview]):
    def __init__(self, session: Session):
        super().__init__(session, HostelReview)

    def list_for_hostel(self, hostel_id: UUID, *, limit: int = 50) -> List[HostelReview]:
        stmt = (
            self._base_select()
            .where(HostelReview.hostel_id == hostel_id)
            .order_by(HostelReview.created_at.desc())
            .limit(limit)
        )
        return self.session.execute(stmt).scalars().all()