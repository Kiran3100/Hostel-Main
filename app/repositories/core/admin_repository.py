# app/repositories/core/admin_repository.py
from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.base import BaseRepository
from app.models.core import Admin


class AdminRepository(BaseRepository[Admin]):
    def __init__(self, session: Session):
        super().__init__(session, Admin)

    def get_by_user_id(self, user_id: UUID) -> Optional[Admin]:
        stmt = self._base_select().where(Admin.user_id == user_id)
        return self.session.execute(stmt).scalar_one_or_none()