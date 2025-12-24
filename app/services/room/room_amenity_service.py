"""
Room Amenity Service

Manages amenities attached to rooms (furniture, appliances, etc.).
"""

from __future__ import annotations

from typing import List
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.room import RoomAmenityRepository
from app.models.room.room_amenity import RoomAmenity
from app.core.exceptions import ValidationException


class RoomAmenityService:
    """
    High-level service for room amenities.

    Responsibilities:
    - List amenities in a room
    - Add/update/remove amenities
    """

    def __init__(
        self,
        amenity_repo: RoomAmenityRepository,
    ) -> None:
        self.amenity_repo = amenity_repo

    def list_amenities_for_room(
        self,
        db: Session,
        room_id: UUID,
    ) -> List[RoomAmenity]:
        return self.amenity_repo.get_by_room_id(db, room_id)

    def add_amenity_to_room(
        self,
        db: Session,
        room_id: UUID,
        amenity_type: str,
        name: str,
        condition: str | None = None,
    ) -> RoomAmenity:
        obj = self.amenity_repo.create(
            db,
            data={
                "room_id": room_id,
                "amenity_type": amenity_type,
                "name": name,
                "condition": condition,
            },
        )
        return obj

    def update_amenity(
        self,
        db: Session,
        amenity_id: UUID,
        name: str | None = None,
        condition: str | None = None,
    ) -> RoomAmenity:
        amenity = self.amenity_repo.get_by_id(db, amenity_id)
        if not amenity:
            raise ValidationException("Amenity not found")

        payload: dict = {}
        if name is not None:
            payload["name"] = name
        if condition is not None:
            payload["condition"] = condition

        updated = self.amenity_repo.update(db, amenity, payload)
        return updated

    def remove_amenity(
        self,
        db: Session,
        amenity_id: UUID,
    ) -> None:
        amenity = self.amenity_repo.get_by_id(db, amenity_id)
        if not amenity:
            return
        self.amenity_repo.delete(db, amenity)