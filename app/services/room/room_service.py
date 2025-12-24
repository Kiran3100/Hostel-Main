"""
Room Service

Core CRUD and read operations for Room entity.
"""

from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.room import (
    RoomRepository,
    RoomAggregateRepository,
)
from app.schemas.room import (
    RoomCreate,
    RoomUpdate,
    RoomResponse,
    RoomDetail,
    RoomListItem,
    RoomWithBeds,
    RoomOccupancyStats,
    RoomFinancialSummary,
)
from app.core.exceptions import ValidationException


class RoomService:
    """
    High-level service for rooms.

    Responsibilities:
    - Create/update/delete rooms
    - Retrieve room details
    - List rooms for a hostel
    - Fetch occupancy and financial summaries
    """

    def __init__(
        self,
        room_repo: RoomRepository,
        aggregate_repo: RoomAggregateRepository,
    ) -> None:
        self.room_repo = room_repo
        self.aggregate_repo = aggregate_repo

    # -------------------------------------------------------------------------
    # CRUD
    # -------------------------------------------------------------------------

    def create_room(
        self,
        db: Session,
        data: RoomCreate,
    ) -> RoomResponse:
        obj = self.room_repo.create(
            db,
            data=data.model_dump(exclude_none=True),
        )
        return RoomResponse.model_validate(obj)

    def update_room(
        self,
        db: Session,
        room_id: UUID,
        data: RoomUpdate,
    ) -> RoomResponse:
        room = self.room_repo.get_by_id(db, room_id)
        if not room:
            raise ValidationException("Room not found")

        updated = self.room_repo.update(
            db,
            room,
            data=data.model_dump(exclude_none=True),
        )
        return RoomResponse.model_validate(updated)

    def delete_room(
        self,
        db: Session,
        room_id: UUID,
    ) -> None:
        room = self.room_repo.get_by_id(db, room_id)
        if not room:
            return
        self.room_repo.delete(db, room)

    # -------------------------------------------------------------------------
    # Retrieval
    # -------------------------------------------------------------------------

    def get_room(
        self,
        db: Session,
        room_id: UUID,
    ) -> RoomDetail:
        obj = self.room_repo.get_full_room(db, room_id)
        if not obj:
            raise ValidationException("Room not found")
        return RoomDetail.model_validate(obj)

    def list_rooms_for_hostel(
        self,
        db: Session,
        hostel_id: UUID,
        skip: int = 0,
        limit: int = 50,
    ) -> List[RoomListItem]:
        objs = self.room_repo.get_by_hostel(db, hostel_id, skip, limit)
        return [RoomListItem.model_validate(o) for o in objs]

    def get_room_with_beds(
        self,
        db: Session,
        room_id: UUID,
    ) -> RoomWithBeds:
        data = self.aggregate_repo.get_room_with_beds(db, room_id)
        if not data:
            raise ValidationException("Room not found")
        return RoomWithBeds.model_validate(data)

    def get_room_occupancy_stats(
        self,
        db: Session,
        room_id: UUID,
    ) -> RoomOccupancyStats:
        data = self.aggregate_repo.get_room_occupancy_stats(db, room_id)
        if not data:
            raise ValidationException("Occupancy stats not available")
        return RoomOccupancyStats.model_validate(data)

    def get_room_financial_summary(
        self,
        db: Session,
        room_id: UUID,
    ) -> RoomFinancialSummary:
        data = self.aggregate_repo.get_room_financial_summary(db, room_id)
        if not data:
            raise ValidationException("Financial summary not available")
        return RoomFinancialSummary.model_validate(data)