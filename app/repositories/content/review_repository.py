# app/repositories/content/review_repository.py
from typing import List, Union
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.repositories.base import BaseRepository
from app.models.content import Review


class ReviewRepository(BaseRepository[Review]):
    def __init__(self, session: Session):
        super().__init__(session, Review)

    def list_for_hostel(self, hostel_id: UUID, *, limit: int = 50) -> List[Review]:
        stmt = (
            self._base_select()
            .where(Review.hostel_id == hostel_id)
            .order_by(Review.created_at.desc())
            .limit(limit)
        )
        return self.session.execute(stmt).scalars().all()

    def get_aggregates_for_hostel(self, hostel_id: UUID) -> dict:
        stmt = (
            select(
                func.count(Review.id),
                func.coalesce(func.avg(Review.overall_rating), 0),
            )
            .where(Review.hostel_id == hostel_id)
        )
        count, avg_rating = self.session.execute(stmt).one()
        return {"total_reviews": count, "average_rating": float(avg_rating)}