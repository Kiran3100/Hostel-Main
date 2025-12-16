# app/repositories/core/user_repository.py
from typing import List, Union
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.repositories.base import BaseRepository
from app.models.core import User
from app.schemas.common.enums import UserRole


class UserRepository(BaseRepository[User]):
    def __init__(self, session: Session):
        super().__init__(session, User)

    def get_by_email(self, email: str) -> Union[User, None]:
        stmt = self._base_select().where(User.email == email)
        return self.session.execute(stmt).scalar_one_or_none()

    def get_by_phone(self, phone: str) -> Union[User, None]:
        stmt = self._base_select().where(User.phone == phone)
        return self.session.execute(stmt).scalar_one_or_none()

    def list_by_role(self, role: UserRole, *, limit: int = 100) -> List[User]:
        stmt = (
            self._base_select()
            .where(User.user_role == role)
            .order_by(User.created_at.desc())
            .limit(limit)
        )
        return self.session.execute(stmt).scalars().all()