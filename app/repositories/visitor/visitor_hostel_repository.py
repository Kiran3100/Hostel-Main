# app/repositories/visitor/visitor_hostel_repository.py
from __future__ import annotations

from typing import List, Optional

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.repositories.base import BaseRepository
from app.models.visitor import VisitorHostel


class VisitorHostelRepository(BaseRepository[VisitorHostel]):
    def __init__(self, session: Session):
        super().__init__(session, VisitorHostel)

    def search(
        self,
        *,
        city: Optional[str] = None,
        area: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        gender_type: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 50,
    ) -> List[VisitorHostel]:
        stmt = self._base_select()

        if city:
            stmt = stmt.where(VisitorHostel.city == city)
        if area:
            stmt = stmt.where(VisitorHostel.area == area)
        if gender_type:
            stmt = stmt.where(VisitorHostel.gender_type == gender_type)
        if min_price is not None:
            stmt = stmt.where(VisitorHostel.min_price >= min_price)
        if max_price is not None:
            stmt = stmt.where(VisitorHostel.max_price <= max_price)
        if search:
            ilike = f"%{search.lower()}%"
            stmt = stmt.where(
                or_(
                    VisitorHostel.hostel_name.ilike(ilike),
                    VisitorHostel.location.ilike(ilike),
                    VisitorHostel.city.ilike(ilike),
                )
            )

        stmt = stmt.order_by(VisitorHostel.rating.desc(), VisitorHostel.min_price.asc().nulls_last())
        stmt = stmt.limit(limit)
        return self.session.execute(stmt).scalars().all()