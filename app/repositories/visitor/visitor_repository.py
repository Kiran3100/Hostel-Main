# app/repositories/visitor/visitor_repository.py
from typing import Union
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.base import BaseRepository
from app.models.visitor import Visitor


class VisitorRepository(BaseRepository[Visitor]):
    def __init__(self, session: Session):
        super().__init__(session, Visitor)

    def get_by_user_id(self, user_id: UUID) -> Union[Visitor, None]:
        stmt = self._base_select().where(Visitor.user_id == user_id)
        return self.session.execute(stmt).scalar_one_or_none()