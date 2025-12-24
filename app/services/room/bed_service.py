"""
Bed Service

Core CRUD and read operations for Bed entity.
"""

from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.room import BedRepository
from app.schemas.room import (
    BedBase,
    BedCreate,
    BedUpdate,
    BedResponse,
)
from app.core.exceptions import ValidationException


class BedService:
    """
    High-level service for beds.

    Responsibilities:
    - Create/update/delete beds
    - Get bed by id
    - List beds in a room or hostel
    """

    def __init__(
        self,
        bed_repo: BedRepository,
    ) -> None:
        self.bed_repo = bed_repo

    def create_bed(
        self,
        db: Session,
        data: BedCreate,
    ) -> BedResponse:
        obj = self.bed_repo.create(
            db,
            data=data.model_dump(exclude_none=True),
        )
        return BedResponse.model_validate(obj)

    def update_bed(
        self,
        db: Session,
        bed_id: UUID,
        data: BedUpdate,
    ) -> BedResponse:
        bed = self.bed_repo.get_by_id(db, bed_id)
        if not bed:
            raise ValidationException("Bed not found")

        updated = self.bed_repo.update(
            db,
            bed,
            data=data.model_dump(exclude_none=True),
        )
        return BedResponse.model_validate(updated)

    def delete_bed(
        self,
        db: Session,
        bed_id: UUID,
    ) -> None:
        bed = self.bed_repo.get_by_id(db, bed_id)
        if not bed:
            return
        self.bed_repo.delete(db, bed)

    def get_bed(
        self,
        db: Session,
        bed_id: UUID,
    ) -> BedResponse:
        bed = self.bed_repo.get_by_id(db, bed_id)
        if not bed:
            raise ValidationException("Bed not found")
        return BedResponse.model_validate(bed)

    def list_beds_for_room(
        self,
        db: Session,
        room_id: UUID,
    ) -> List[BedResponse]:
        objs = self.bed_repo.get_by_room_id(db, room_id)
        return [BedResponse.model_validate(o) for o in objs]

    def list_beds_for_hostel(
        self,
        db: Session,
        hostel_id: UUID,
    ) -> List[BedResponse]:
        objs = self.bed_repo.get_by_hostel_id(db, hostel_id)
        return [BedResponse.model_validate(o) for o in objs]