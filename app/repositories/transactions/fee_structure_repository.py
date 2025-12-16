# app/repositories/transactions/fee_structure_repository.py
from datetime import date
from typing import List, Union
from uuid import UUID

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.repositories.base import BaseRepository
from app.models.transactions import FeeStructure
from app.schemas.common.enums import RoomType, FeeType


class FeeStructureRepository(BaseRepository[FeeStructure]):
    def __init__(self, session: Session):
        super().__init__(session, FeeStructure)

    def get_effective_fee(
        self,
        hostel_id: UUID,
        room_type: RoomType,
        fee_type: FeeType,
        as_of: date,
    ) -> Union[FeeStructure, None]:
        stmt = (
            self._base_select()
            .where(
                and_(
                    FeeStructure.hostel_id == hostel_id,
                    FeeStructure.room_type == room_type,
                    FeeStructure.fee_type == fee_type,
                    FeeStructure.is_active.is_(True),
                    FeeStructure.effective_from <= as_of,
                    (FeeStructure.effective_to.is_(None) | (FeeStructure.effective_to >= as_of)),
                )
            )
            .order_by(FeeStructure.effective_from.desc())
            .limit(1)
        )
        return self.session.execute(stmt).scalar_one_or_none()