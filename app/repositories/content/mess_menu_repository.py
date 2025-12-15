# app/repositories/content/mess_menu_repository.py
from __future__ import annotations

from datetime import date
from typing import List
from uuid import UUID

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.repositories.base import BaseRepository
from app.models.content import MessMenu


class MessMenuRepository(BaseRepository[MessMenu]):
    def __init__(self, session: Session):
        super().__init__(session, MessMenu)

    def get_for_date(self, hostel_id: UUID, menu_date: date) -> List[MessMenu]:
        stmt = (
            self._base_select()
            .where(
                and_(
                    MessMenu.hostel_id == hostel_id,
                    MessMenu.menu_date == menu_date,
                )
            )
        )
        return self.session.execute(stmt).scalars().all()

    def get_range(
        self,
        hostel_id: UUID,
        start_date: date,
        end_date: date,
    ) -> List[MessMenu]:
        stmt = (
            self._base_select()
            .where(
                and_(
                    MessMenu.hostel_id == hostel_id,
                    MessMenu.menu_date >= start_date,
                    MessMenu.menu_date <= end_date,
                )
            )
            .order_by(MessMenu.menu_date.asc())
        )
        return self.session.execute(stmt).scalars().all()