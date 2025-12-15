# app/services/room/bed_service.py
from __future__ import annotations

from datetime import date
from typing import Callable, Dict, List, Optional, Sequence
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.core import BedRepository, RoomRepository, StudentRepository
from app.schemas.room import (
    BedCreate,
    BedUpdate,
    BulkBedCreate,
    BedResponse,
)
from app.schemas.room.bed_response import BedAvailability
from app.schemas.common.enums import BedStatus
from app.services.common import UnitOfWork, errors


class BedService:
    """
    Bed lifecycle service:

    - Create/update beds (bulk & single)
    - Get bed detail
    - List beds for a room
    - Simple availability info
    """

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _get_bed_repo(self, uow: UnitOfWork) -> BedRepository:
        return uow.get_repo(BedRepository)

    def _get_room_repo(self, uow: UnitOfWork) -> RoomRepository:
        return uow.get_repo(RoomRepository)

    def _get_student_repo(self, uow: UnitOfWork) -> StudentRepository:
        return uow.get_repo(StudentRepository)

    # ------------------------------------------------------------------ #
    # Mapping
    # ------------------------------------------------------------------ #
    def _to_bed_response(self, bed) -> BedResponse:
        return BedResponse(
            id=bed.id,
            created_at=bed.created_at,
            updated_at=bed.updated_at,
            room_id=bed.room_id,
            bed_number=bed.bed_number,
            is_occupied=bed.current_student_id is not None,
            status=bed.status,
            current_student_id=bed.current_student_id,
            occupied_from=bed.occupied_from,
        )

    # ------------------------------------------------------------------ #
    # CRUD
    # ------------------------------------------------------------------ #
    def create_bed(self, data: BedCreate) -> BedResponse:
        with UnitOfWork(self._session_factory) as uow:
            bed_repo = self._get_bed_repo(uow)
            room_repo = self._get_room_repo(uow)

            room = room_repo.get(data.room_id)
            if room is None:
                raise errors.NotFoundError(f"Room {data.room_id} not found")

            payload = data.model_dump(exclude_unset=True)
            bed = bed_repo.create(payload)  # type: ignore[arg-type]
            uow.commit()
            return self._to_bed_response(bed)

    def bulk_create_beds(self, data: BulkBedCreate) -> List[BedResponse]:
        """
        Create a sequence of beds (e.g. B1..B4) for a given room.
        """
        with UnitOfWork(self._session_factory) as uow:
            bed_repo = self._get_bed_repo(uow)
            room_repo = self._get_room_repo(uow)

            room = room_repo.get(data.room_id)
            if room is None:
                raise errors.NotFoundError(f"Room {data.room_id} not found")

            payloads = []
            for i in range(data.start_number, data.start_number + data.bed_count):
                bed_number = f"{data.bed_prefix}{i}"
                payloads.append(
                    {
                        "hostel_id": room.hostel_id,
                        "room_id": data.room_id,
                        "bed_number": bed_number,
                        "status": BedStatus.AVAILABLE,
                    }
                )
            beds = bed_repo.bulk_create(payloads)  # type: ignore[arg-type]
            uow.commit()
            return [self._to_bed_response(b) for b in beds]

    def update_bed(self, bed_id: UUID, data: BedUpdate) -> BedResponse:
        with UnitOfWork(self._session_factory) as uow:
            bed_repo = self._get_bed_repo(uow)

            bed = bed_repo.get(bed_id)
            if bed is None:
                raise errors.NotFoundError(f"Bed {bed_id} not found")

            mapping = data.model_dump(exclude_unset=True)
            for field, value in mapping.items():
                if hasattr(bed, field) and field != "id":
                    setattr(bed, field, value)

            uow.session.flush()  # type: ignore[union-attr]
            uow.commit()
            return self._to_bed_response(bed)

    def get_bed(self, bed_id: UUID) -> BedResponse:
        with UnitOfWork(self._session_factory) as uow:
            bed_repo = self._get_bed_repo(uow)
            bed = bed_repo.get(bed_id)
            if bed is None:
                raise errors.NotFoundError(f"Bed {bed_id} not found")
            return self._to_bed_response(bed)

    # ------------------------------------------------------------------ #
    # Listing & availability
    # ------------------------------------------------------------------ #
    def list_beds_for_room(self, room_id: UUID) -> List[BedResponse]:
        with UnitOfWork(self._session_factory) as uow:
            bed_repo = self._get_bed_repo(uow)
            beds = bed_repo.get_multi(filters={"room_id": room_id})
            return [self._to_bed_response(b) for b in beds]

    def list_available_beds_for_room(self, room_id: UUID) -> List[BedAvailability]:
        with UnitOfWork(self._session_factory) as uow:
            bed_repo = self._get_bed_repo(uow)
            room_repo = self._get_room_repo(uow)
            student_repo = self._get_student_repo(uow)

            room = room_repo.get(room_id)
            if room is None:
                raise errors.NotFoundError(f"Room {room_id} not found")

            beds = bed_repo.list_available_beds_for_room(room_id)

            avail: List[BedAvailability] = []
            for b in beds:
                student_name = None
                if b.current_student_id:
                    st = student_repo.get(b.current_student_id)
                    if st and getattr(st, "user", None):
                        student_name = st.user.full_name

                avail.append(
                    BedAvailability(
                        bed_id=b.id,
                        room_id=room_id,
                        room_number=room.room_number,
                        bed_number=b.bed_number,
                        is_available=b.current_student_id is None and b.status == BedStatus.AVAILABLE,
                        status=b.status,
                        available_from=b.occupied_from if b.current_student_id else date.today(),
                        current_student_name=student_name,
                    )
                )

            return avail