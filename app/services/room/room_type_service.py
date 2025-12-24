"""
Room Type Service

Manages room type definitions, features, pricing, and comparisons.
"""

from __future__ import annotations

from typing import List
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.room import RoomTypeRepository
from app.schemas.room import (
    RoomTypeDefinition,
    RoomTypePricing,
)
from app.core.exceptions import ValidationException


class RoomTypeService:
    """
    High-level service for room types.

    Responsibilities:
    - Create/update/delete room type definitions
    - Manage room type pricing
    - Fetch type-level availability/summary
    """

    def __init__(
        self,
        room_type_repo: RoomTypeRepository,
    ) -> None:
        self.room_type_repo = room_type_repo

    def get_room_type(
        self,
        db: Session,
        room_type_id: UUID,
    ) -> RoomTypeDefinition:
        obj = self.room_type_repo.get_by_id(db, room_type_id)
        if not obj:
            raise ValidationException("Room type not found")
        return RoomTypeDefinition.model_validate(obj)

    def list_room_types_for_hostel(
        self,
        db: Session,
        hostel_id: UUID,
    ) -> List[RoomTypeDefinition]:
        objs = self.room_type_repo.get_by_hostel_id(db, hostel_id)
        return [RoomTypeDefinition.model_validate(o) for o in objs]

    def update_room_type_pricing(
        self,
        db: Session,
        room_type_id: UUID,
        pricing: RoomTypePricing,
    ) -> RoomTypeDefinition:
        """
        Update pricing attributes for a room type.
        """
        obj = self.room_type_repo.get_by_id(db, room_type_id)
        if not obj:
            raise ValidationException("Room type not found")

        updated = self.room_type_repo.update(
            db,
            obj,
            data=pricing.model_dump(exclude_none=True),
        )
        return RoomTypeDefinition.model_validate(updated)