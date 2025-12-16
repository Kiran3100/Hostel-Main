# app/repositories/visitor/visitor_hostel_repository.py
from typing import List, Union

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
        city: Union[str, None] = None,
        area: Union[str, None] = None,
        min_price: Union[float, None] = None,
        max_price: Union[float, None] = None,
        gender_type: Union[str, None] = None,
        search: Union[str, None] = None,
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