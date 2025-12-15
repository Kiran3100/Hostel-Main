# app/services/room/room_service.py
from __future__ import annotations

from decimal import Decimal
from typing import Callable, Dict, List, Optional, Sequence
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.core import RoomRepository, BedRepository, HostelRepository, StudentRepository
from app.schemas.common.pagination import PaginationParams, PaginatedResponse
from app.schemas.room import (
    RoomCreate,
    RoomUpdate,
    BulkRoomCreate,
    RoomResponse,
    RoomDetail,
    RoomListItem,
    RoomWithBeds,
)
from app.schemas.room.room_response import BedDetail, RoomOccupancyStats
from app.schemas.common.enums import RoomType, RoomStatus, BedStatus
from app.services.common import UnitOfWork, errors


class RoomService:
    """
    Core room service:

    - Create / update rooms (bulk + single)
    - Get room detail with bed occupancy
    - List rooms for a hostel
    - Simple occupancy stats
    """

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _get_room_repo(self, uow: UnitOfWork) -> RoomRepository:
        return uow.get_repo(RoomRepository)

    def _get_bed_repo(self, uow: UnitOfWork) -> BedRepository:
        return uow.get_repo(BedRepository)

    def _get_hostel_repo(self, uow: UnitOfWork) -> HostelRepository:
        return uow.get_repo(HostelRepository)

    def _get_student_repo(self, uow: UnitOfWork) -> StudentRepository:
        return uow.get_repo(StudentRepository)

    # ------------------------------------------------------------------ #
    # Mapping helpers
    # ------------------------------------------------------------------ #
    def _occupied_available(
        self,
        *,
        total_beds: int,
        beds: Sequence,
    ) -> tuple[int, int]:
        occupied = sum(1 for b in beds if b.current_student_id is not None)
        available = max(0, total_beds - occupied)
        return occupied, available

    def _to_room_response(
        self,
        room,
        *,
        occupied_beds: int,
        available_beds: int,
    ) -> RoomResponse:
        return RoomResponse(
            id=room.id,
            created_at=room.created_at,
            updated_at=room.updated_at,
            hostel_id=UUID(room.hostel_id) if isinstance(room.hostel_id, str) else room.hostel_id,
            room_number=room.room_number,
            floor_number=room.floor_number,
            wing=room.wing,
            room_type=room.room_type,
            total_beds=room.total_beds,
            occupied_beds=occupied_beds,
            available_beds=available_beds,
            price_monthly=room.price_monthly,
            is_ac=room.is_ac,
            has_attached_bathroom=room.has_attached_bathroom,
            status=room.status,
            is_available_for_booking=room.is_available_for_booking,
        )

    def _to_room_list_item(
        self,
        room,
        *,
        available_beds: int,
    ) -> RoomListItem:
        return RoomListItem(
            id=room.id,
            room_number=room.room_number,
            floor_number=room.floor_number,
            wing=room.wing,
            room_type=room.room_type,
            total_beds=room.total_beds,
            available_beds=available_beds,
            price_monthly=room.price_monthly,
            is_ac=room.is_ac,
            status=room.status,
            is_available_for_booking=room.is_available_for_booking,
        )

    def _to_bed_detail(self, bed, *, student_name: Optional[str]) -> BedDetail:
        return BedDetail(
            id=bed.id,
            bed_number=bed.bed_number,
            is_occupied=bed.current_student_id is not None,
            status=bed.status.value if hasattr(bed.status, "value") else str(bed.status),
            current_student_id=bed.current_student_id,
            current_student_name=student_name,
            occupied_from=bed.occupied_from,
        )

    def _to_room_detail(
        self,
        room,
        *,
        hostel_name: str,
        beds: Sequence,
        student_names: Dict[UUID, str],
    ) -> RoomDetail:
        occupied, available = self._occupied_available(
            total_beds=room.total_beds,
            beds=beds,
        )

        bed_details: List[BedDetail] = []
        for b in beds:
            s_name = student_names.get(b.current_student_id) if b.current_student_id else None
            bed_details.append(self._to_bed_detail(b, student_name=s_name))

        return RoomDetail(
            id=room.id,
            created_at=room.created_at,
            updated_at=room.updated_at,
            hostel_id=UUID(room.hostel_id) if isinstance(room.hostel_id, str) else room.hostel_id,
            hostel_name=hostel_name,
            room_number=room.room_number,
            floor_number=room.floor_number,
            wing=room.wing,
            room_type=room.room_type,
            total_beds=room.total_beds,
            occupied_beds=occupied,
            available_beds=available,
            price_monthly=room.price_monthly,
            price_quarterly=room.price_quarterly,
            price_half_yearly=room.price_half_yearly,
            price_yearly=room.price_yearly,
            room_size_sqft=room.room_size_sqft,
            is_ac=room.is_ac,
            has_attached_bathroom=room.has_attached_bathroom,
            has_balcony=room.has_balcony,
            has_wifi=room.has_wifi,
            amenities=room.amenities or [],
            furnishing=room.furnishing or [],
            status=room.status,
            is_available_for_booking=room.is_available_for_booking,
            is_under_maintenance=room.is_under_maintenance,
            maintenance_start_date=None,
            maintenance_end_date=None,
            room_images=room.room_images or [],
            beds=bed_details,
        )

    # ------------------------------------------------------------------ #
    # CRUD
    # ------------------------------------------------------------------ #
    def create_room(self, data: RoomCreate) -> RoomDetail:
        with UnitOfWork(self._session_factory) as uow:
            room_repo = self._get_room_repo(uow)
            hostel_repo = self._get_hostel_repo(uow)

            hostel = hostel_repo.get(data.hostel_id)
            if hostel is None:
                raise errors.NotFoundError(f"Hostel {data.hostel_id} not found")

            payload = data.model_dump(exclude_unset=True)
            room = room_repo.create(payload)  # type: ignore[arg-type]
            uow.commit()

            # No beds yet
            return self._to_room_detail(
                room,
                hostel_name=hostel.name,
                beds=[],
                student_names={},
            )

    def bulk_create_rooms(self, data: BulkRoomCreate) -> List[RoomDetail]:
        responses: List[RoomDetail] = []
        for rc in data.rooms:
            # enforce same hostel_id as BulkRoomCreate
            rc = RoomCreate(**{**rc.model_dump(exclude_unset=True), "hostel_id": data.hostel_id})
            responses.append(self.create_room(rc))
        return responses

    def update_room(self, room_id: UUID, data: RoomUpdate) -> RoomDetail:
        with UnitOfWork(self._session_factory) as uow:
            room_repo = self._get_room_repo(uow)
            hostel_repo = self._get_hostel_repo(uow)
            bed_repo = self._get_bed_repo(uow)
            student_repo = self._get_student_repo(uow)

            room = room_repo.get(room_id)
            if room is None:
                raise errors.NotFoundError(f"Room {room_id} not found")

            mapping = data.model_dump(exclude_unset=True)
            for field, value in mapping.items():
                if hasattr(room, field) and field != "id":
                    setattr(room, field, value)

            uow.session.flush()  # type: ignore[union-attr]
            hostel = hostel_repo.get(UUID(room.hostel_id) if isinstance(room.hostel_id, str) else room.hostel_id)
            hostel_name = hostel.name if hostel else ""
            beds = bed_repo.get_multi(filters={"room_id": room.id})
            student_names: Dict[UUID, str] = {}
            for b in beds:
                if b.current_student_id and b.current_student_id not in student_names:
                    st = student_repo.get(b.current_student_id)
                    if st and getattr(st, "user", None):
                        student_names[b.current_student_id] = st.user.full_name

            uow.commit()
            return self._to_room_detail(room, hostel_name=hostel_name, beds=beds, student_names=student_names)

    def get_room(self, room_id: UUID) -> RoomDetail:
        with UnitOfWork(self._session_factory) as uow:
            room_repo = self._get_room_repo(uow)
            bed_repo = self._get_bed_repo(uow)
            hostel_repo = self._get_hostel_repo(uow)
            student_repo = self._get_student_repo(uow)

            room = room_repo.get(room_id)
            if room is None:
                raise errors.NotFoundError(f"Room {room_id} not found")

            hostel = hostel_repo.get(UUID(room.hostel_id) if isinstance(room.hostel_id, str) else room.hostel_id)
            hostel_name = hostel.name if hostel else ""

            beds = bed_repo.get_multi(filters={"room_id": room.id})
            student_names: Dict[UUID, str] = {}
            for b in beds:
                if b.current_student_id and b.current_student_id not in student_names:
                    st = student_repo.get(b.current_student_id)
                    if st and getattr(st, "user", None):
                        student_names[b.current_student_id] = st.user.full_name

            return self._to_room_detail(room, hostel_name=hostel_name, beds=beds, student_names=student_names)

    # ------------------------------------------------------------------ #
    # Listing
    # ------------------------------------------------------------------ #
    def list_rooms_for_hostel(
        self,
        hostel_id: UUID,
        params: PaginationParams,
        *,
        room_type: Optional[RoomType] = None,
        only_available: bool = False,
    ) -> PaginatedResponse[RoomListItem]:
        with UnitOfWork(self._session_factory) as uow:
            room_repo = self._get_room_repo(uow)
            bed_repo = self._get_bed_repo(uow)

            rooms = room_repo.list_for_hostel(
                hostel_id=hostel_id,
                only_available=only_available,
                room_type=room_type,
            )

            # Preload beds grouped by room
            room_ids = [r.id for r in rooms]
            bed_map: Dict[UUID, List] = {rid: [] for rid in room_ids}
            all_beds = bed_repo.get_multi(filters={"room_id": room_ids}) if room_ids else []
            for b in all_beds:
                bed_map.setdefault(b.room_id, []).append(b)

            items: List[RoomListItem] = []
            for r in rooms:
                beds = bed_map.get(r.id, [])
                _, available = self._occupied_available(total_beds=r.total_beds, beds=beds)
                items.append(self._to_room_list_item(r, available_beds=available))

            total = len(items)
            start = params.offset
            end = start + params.limit
            page_items = items[start:end]

            return PaginatedResponse[RoomListItem].create(
                items=page_items,
                total_items=total,
                page=params.page,
                page_size=params.page_size,
            )

    # ------------------------------------------------------------------ #
    # Room with beds & stats
    # ------------------------------------------------------------------ #
    def get_room_with_beds(self, room_id: UUID) -> RoomWithBeds:
        with UnitOfWork(self._session_factory) as uow:
            room_repo = self._get_room_repo(uow)
            bed_repo = self._get_bed_repo(uow)
            student_repo = self._get_student_repo(uow)

            room = room_repo.get(room_id)
            if room is None:
                raise errors.NotFoundError(f"Room {room_id} not found")

            beds = bed_repo.get_multi(filters={"room_id": room.id})
            occupied, available = self._occupied_available(
                total_beds=room.total_beds,
                beds=beds,
            )

            from app.schemas.room.room_response import BedInfo

            student_names: Dict[UUID, str] = {}
            bed_infos: List[BedInfo] = []
            for b in beds:
                s_name = None
                if b.current_student_id:
                    if b.current_student_id not in student_names:
                        st = student_repo.get(b.current_student_id)
                        if st and getattr(st, "user", None):
                            student_names[b.current_student_id] = st.user.full_name
                    s_name = student_names.get(b.current_student_id)
                bed_infos.append(
                    BedInfo(
                        id=b.id,
                        bed_number=b.bed_number,
                        is_occupied=b.current_student_id is not None,
                        status=b.status.value if hasattr(b.status, "value") else str(b.status),
                        student_name=s_name,
                    )
                )

            return RoomWithBeds(
                id=room.id,
                created_at=room.created_at,
                updated_at=room.updated_at,
                hostel_id=UUID(room.hostel_id) if isinstance(room.hostel_id, str) else room.hostel_id,
                room_number=room.room_number,
                room_type=room.room_type,
                total_beds=room.total_beds,
                occupied_beds=occupied,
                available_beds=available,
                beds=bed_infos,
            )

    def get_room_occupancy_stats(self, room_id: UUID) -> RoomOccupancyStats:
        with UnitOfWork(self._session_factory) as uow:
            room_repo = self._get_room_repo(uow)
            bed_repo = self._get_bed_repo(uow)

            room = room_repo.get(room_id)
            if room is None:
                raise errors.NotFoundError(f"Room {room_id} not found")

            beds = bed_repo.get_multi(filters={"room_id": room.id})
            occupied, available = self._occupied_available(
                total_beds=room.total_beds,
                beds=beds,
            )

            # Very simple revenue estimates:
            current_revenue = room.price_monthly * Decimal(str(occupied))
            potential_revenue = room.price_monthly * Decimal(str(room.total_beds))

            occ_pct = (
                Decimal(str(occupied)) / Decimal(str(room.total_beds)) * Decimal("100")
                if room.total_beds > 0
                else Decimal("0")
            )

            return RoomOccupancyStats(
                room_id=room.id,
                room_number=room.room_number,
                total_beds=room.total_beds,
                occupied_beds=occupied,
                available_beds=available,
                occupancy_percentage=occ_pct,
                current_revenue=current_revenue,
                potential_revenue=potential_revenue,
            )