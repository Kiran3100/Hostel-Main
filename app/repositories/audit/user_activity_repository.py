# app/repositories/audit/user_activity_repository.py
from __future__ import annotations

from typing import List
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.base import BaseRepository
from app.models.audit import UserActivity


class UserActivityRepository(BaseRepository[UserActivity]):
    def __init__(self, session: Session):
        super().__init__(session, UserActivity)

    def list_for_user(self, user_id: UUID, *, limit: int = 100) -> List[UserActivity]:
        stmt = (
            self._base_select()
            .where(UserActivity.user_id == user_id)
            .order_by(UserActivity.created_at.desc())
            .limit(limit)
        )
        return self.session.execute(stmt).scalars().all()