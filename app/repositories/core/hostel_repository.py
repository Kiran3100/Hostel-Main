# app/repositories/core/hostel_repository.py
from __future__ import annotations

from typing import List, Optional

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.repositories.base import BaseRepository
from app.models.core import Hostel


class HostelRepository(BaseRepository[Hostel]):
    def __init__(self, session: Session):
        super().__init__(session, Hostel)

    def get_by_slug(self, slug: str) -> Optional[Hostel]:
        stmt = self._base_select().where(Hostel.slug == slug)
        return self.session.execute(stmt).scalar_one_or_none()

    def list_public(
        self,
        *,
        city: Optional[str] = None,
        state: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 50,
    ) -> List[Hostel]:
        stmt = self._base_select().where(
            Hostel.is_public.is_(True),
            Hostel.is_active.is_(True),
        )

        if city:
            stmt = stmt.where(Hostel.city == city)
        if state:
            stmt = stmt.where(Hostel.state == state)
        if search:
            ilike = f"%{search.lower()}%"
            stmt = stmt.where(
                or_(
                    Hostel.name.ilike(ilike),
                    Hostel.address_line1.ilike(ilike),
                    Hostel.city.ilike(ilike),
                )
            )

        stmt = stmt.order_by(Hostel.is_featured.desc(), Hostel.average_rating.desc())
        stmt = stmt.limit(limit)
        return self.session.execute(stmt).scalars().all()