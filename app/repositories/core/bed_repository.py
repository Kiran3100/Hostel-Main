# app/repositories/core/bed_repository.py
from typing import List
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.repositories.base import BaseRepository
from app.models.core import Bed
from app.schemas.common.enums import BedStatus


class BedRepository(BaseRepository[Bed]):
    def __init__(self, session: Session):
        super().__init__(session, Bed)

    def list_available_beds_for_room(self, room_id: UUID) -> List[Bed]:
        stmt = (
            self._base_select()
            .where(
                and_(
                    Bed.room_id == room_id,
                    Bed.status == BedStatus.AVAILABLE,
                )
            )
        )
        return self.session.execute(stmt).scalars().all()

    def list_beds_for_student(self, student_id: UUID) -> List[Bed]:
        stmt = self._base_select().where(Bed.current_student_id == student_id)
        return self.session.execute(stmt).scalars().all()