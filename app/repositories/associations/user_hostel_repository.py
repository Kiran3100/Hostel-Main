# app/repositories/associations/user_hostel_repository.py
from __future__ import annotations

from typing import List
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.repositories.base import BaseRepository
from app.models.associations import UserHostel
from app.models.core import Hostel


class UserHostelRepository(BaseRepository[UserHostel]):
    def __init__(self, session: Session):
        super().__init__(session, UserHostel)

    def get_recent_hostels_for_user(self, user_id: UUID, limit: int = 5) -> List[Hostel]:
        stmt = (
            select(Hostel)
            .join(UserHostel, UserHostel.hostel_id == Hostel.id)
            .where(
                UserHostel.user_id == user_id,
                UserHostel.association_type == "recent",
            )
            .order_by(UserHostel.created_date.desc())
            .limit(limit)
        )
        return self.session.execute(stmt).scalars().all()

    def get_favorite_hostels_for_user(self, user_id: UUID) -> List[Hostel]:
        stmt = (
            select(Hostel)
            .join(UserHostel, UserHostel.hostel_id == Hostel.id)
            .where(
                UserHostel.user_id == user_id,
                UserHostel.association_type == "favorite",
            )
        )
        return self.session.execute(stmt).scalars().all()