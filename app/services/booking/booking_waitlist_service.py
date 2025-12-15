# app/services/booking/booking_waitlist_service.py
from __future__ import annotations

from datetime import datetime, timezone, date
from decimal import Decimal
from typing import Protocol, List, Dict
from uuid import UUID

from app.schemas.booking import (
    WaitlistRequest,
    WaitlistResponse,
    WaitlistNotification,
    WaitlistConversion,
    WaitlistCancellation,
    WaitlistManagement,
    WaitlistEntry,
)
from app.schemas.common.enums import WaitlistStatus as WaitlistStatusEnum, RoomType


class WaitlistStore(Protocol):
    """
    Abstract store for waitlist entries.

    Implementations can use a DB table or Redis.
    """

    def create_entry(self, data: dict) -> dict: ...
    def update_entry(self, waitlist_id: UUID, data: dict) -> dict: ...
    def get_entry(self, waitlist_id: UUID) -> dict | None: ...
    def list_for_hostel_roomtype(self, hostel_id: UUID, room_type: RoomType) -> List[dict]: ...


class BookingWaitlistService:
    """
    Manage booking waitlists when hostels are full.
    """

    def __init__(self, store: WaitlistStore) -> None:
        self._store = store

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    # ------------------------------------------------------------------ #
    # Waitlist management
    # ------------------------------------------------------------------ #
    def add_to_waitlist(self, data: WaitlistRequest, *, hostel_name: str) -> WaitlistResponse:
        record = {
            "id": None,
            "hostel_id": str(data.hostel_id),
            "hostel_name": hostel_name,
            "visitor_id": str(data.visitor_id),
            "room_type": data.room_type.value if hasattr(data.room_type, "value") else str(data.room_type),
            "preferred_check_in_date": data.preferred_check_in_date.isoformat(),
            "contact_email": data.contact_email,
            "contact_phone": data.contact_phone,
            "notes": data.notes,
            "priority": 0,
            "status": WaitlistStatusEnum.WAITING.value,
            "created_at": self._now(),
            "estimated_availability_date": None,
            "notification_count": 0,
        }
        created = self._store.create_entry(record)

        return WaitlistResponse(
            id=UUID(created["id"]),
            created_at=created["created_at"],
            updated_at=created["created_at"],
            hostel_id=data.hostel_id,
            hostel_name=hostel_name,
            visitor_id=data.visitor_id,
            room_type=data.room_type,
            preferred_check_in_date=data.preferred_check_in_date,
            contact_email=data.contact_email,
            contact_phone=data.contact_phone,
            priority=created.get("priority", 0),
            status=WaitlistStatusEnum.WAITING,
            estimated_availability_date=None,
        )

    def cancel_waitlist(self, data: WaitlistCancellation) -> None:
        entry = self._store.get_entry(data.waitlist_id)
        if not entry:
            return
        entry["status"] = WaitlistStatusEnum.CANCELLED.value
        entry["cancellation_reason"] = data.cancellation_reason
        self._store.update_entry(data.waitlist_id, entry)

    def notify_availability(
        self,
        waitlist_id: UUID,
        *,
        available_room_id: UUID,
        available_bed_id: UUID,
        response_deadline: datetime,
    ) -> WaitlistNotification:
        entry = self._store.get_entry(waitlist_id)
        if not entry:
            raise ValueError(f"Waitlist {waitlist_id} not found")

        entry["status"] = WaitlistStatusEnum.NOTIFIED.value
        entry["notification_count"] = entry.get("notification_count", 0) + 1
        self._store.update_entry(waitlist_id, entry)

        return WaitlistNotification(
            waitlist_id=waitlist_id,
            visitor_id=UUID(entry["visitor_id"]),
            hostel_id=UUID(entry["hostel_id"]),
            message="Room is available for your waitlist request",
            available_room_id=available_room_id,
            available_bed_id=available_bed_id,
            response_deadline=response_deadline,
            booking_link="",
        )

    def list_waitlist_for_hostel(
        self,
        hostel_id: UUID,
        room_type: RoomType,
        *,
        hostel_name: str,
    ) -> WaitlistManagement:
        entries = self._store.list_for_hostel_roomtype(hostel_id, room_type)
        waitlist_entries: List[WaitlistEntry] = []
        for e in entries:
            waitlist_entries.append(
                WaitlistEntry(
                    waitlist_id=UUID(e["id"]),
                    visitor_name="",
                    contact_email=e["contact_email"],
                    contact_phone=e["contact_phone"],
                    preferred_check_in_date=date.fromisoformat(e["preferred_check_in_date"]),
                    priority=e.get("priority", 0),
                    status=WaitlistStatusSchema[e["status"].upper()],
                    days_waiting=(date.today() - e["created_at"].date()).days,
                    created_at=e["created_at"],
                )
            )
        return WaitlistManagement(
            hostel_id=hostel_id,
            room_type=room_type,
            total_in_waitlist=len(waitlist_entries),
            entries=waitlist_entries,
        )

    def convert_waitlist_to_booking(self, data: WaitlistConversion) -> None:
        entry = self._store.get_entry(data.waitlist_id)
        if not entry:
            return

        if data.accept:
            entry["status"] = WaitlistStatusEnum.CONVERTED.value
        else:
            entry["status"] = WaitlistStatusEnum.CANCELLED.value

        self._store.update_entry(data.waitlist_id, entry)