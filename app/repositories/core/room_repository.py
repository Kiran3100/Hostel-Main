# app/repositories/core/room_repository.py
from typing import List, Union
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.repositories.base import BaseRepository
from app.models.core import Room
from app.schemas.common.enums import RoomType, RoomStatus


class RoomRepository(BaseRepository[Room]):
    def __init__(self, session: Session):
        super().__init__(session, Room)

    def list_for_hostel(
        self,
        hostel_id: UUID,
        *,
        only_available: bool = False,
        room_type: Union[RoomType, None] = None,
    ) -> List[Room]:
        stmt = self._base_select().where(Room.hostel_id == str(hostel_id))
        if only_available:
            stmt = stmt.where(
                Room.is_available_for_booking.is_(True),
                Room.status == RoomStatus.AVAILABLE,
            )
        if room_type is not None:
            stmt = stmt.where(Room.room_type == room_type)
        stmt = stmt.order_by(Room.floor_number.asc().nulls_last(), Room.room_number.asc())
        return self.session.execute(stmt).scalars().all()