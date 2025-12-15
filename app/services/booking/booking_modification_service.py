# app/services/booking/booking_modification_service.py
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Callable, List
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.transactions import BookingRepository
from app.schemas.booking import (
    ModificationRequest,
    ModificationResponse,
    DateChangeRequest,
    DurationChangeRequest,
    RoomTypeChangeRequest,
    ModificationApproval,
)
from app.schemas.common.enums import BookingStatus, RoomType
from app.services.common import UnitOfWork, errors


class BookingModificationService:
    """
    Handle booking modification requests (date/duration/room_type):

    - Calculate price impact
    - Optionally require admin approval
    - Apply changes
    """

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    def _get_booking_repo(self, uow: UnitOfWork) -> BookingRepository:
        return uow.get_repo(BookingRepository)

    # ------------------------------------------------------------------ #
    # Core modification
    # ------------------------------------------------------------------ #
    def modify(self, data: ModificationRequest) -> ModificationResponse:
        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_booking_repo(uow)
            b = repo.get(data.booking_id)
            if b is None:
                raise errors.NotFoundError(f"Booking {data.booking_id} not found")

            original_total = b.total_amount
            new_total = b.total_amount
            modifications_applied: List[str] = []

            if data.modify_check_in_date and data.new_check_in_date:
                modifications_applied.append("check_in_date")
                b.preferred_check_in_date = data.new_check_in_date  # type: ignore[attr-defined]

            if data.modify_duration and data.new_duration_months:
                modifications_applied.append("duration")
                b.stay_duration_months = data.new_duration_months  # type: ignore[attr-defined]
                # Recompute total as a stub; real implementation uses FeeStructure
                new_total = b.quoted_rent_monthly * data.new_duration_months  # type: ignore[attr-defined]

            if data.modify_room_type and data.new_room_type:
                modifications_applied.append("room_type")
                b.room_type_requested = data.new_room_type  # type: ignore[attr-defined]
                # Price change may occur; left as-is unless you integrate FeeStructure

            price_difference = new_total - original_total
            additional_payment_required = price_difference > 0
            additional_amount = price_difference if price_difference > 0 else Decimal("0")

            requires_admin_approval = additional_payment_required and not data.accept_price_change
            auto_approved = not requires_admin_approval

            if auto_approved:
                b.total_amount = new_total  # type: ignore[attr-defined]

            uow.session.flush()  # type: ignore[union-attr]
            uow.commit()

        return ModificationResponse(
            booking_id=data.booking_id,
            booking_reference=f"BKG-{str(data.booking_id)[:8].upper()}",
            modifications_applied=modifications_applied,
            original_total=original_total,
            new_total=new_total,
            price_difference=price_difference,
            additional_payment_required=additional_payment_required,
            additional_amount=additional_amount,
            requires_admin_approval=requires_admin_approval,
            auto_approved=auto_approved,
            message="Booking modification processed",
        )

    # Convenience wrappers
    def change_date(self, data: DateChangeRequest) -> ModificationResponse:
        req = ModificationRequest(
            booking_id=data.booking_id,
            modify_check_in_date=True,
            new_check_in_date=data.new_check_in_date,
            modify_duration=False,
            new_duration_months=None,
            modify_room_type=False,
            new_room_type=None,
            modification_reason=data.reason,
            accept_price_change=True,
        )
        return self.modify(req)

    def change_duration(self, data: DurationChangeRequest) -> ModificationResponse:
        req = ModificationRequest(
            booking_id=data.booking_id,
            modify_check_in_date=False,
            new_check_in_date=None,
            modify_duration=True,
            new_duration_months=data.new_duration_months,
            modify_room_type=False,
            new_room_type=None,
            modification_reason=data.reason,
            accept_price_change=True,
        )
        return self.modify(req)

    def change_room_type(self, data: RoomTypeChangeRequest) -> ModificationResponse:
        req = ModificationRequest(
            booking_id=data.booking_id,
            modify_check_in_date=False,
            new_check_in_date=None,
            modify_duration=False,
            new_duration_months=None,
            modify_room_type=True,
            new_room_type=data.new_room_type,
            modification_reason=data.reason,
            accept_price_change=data.accept_price_difference,
        )
        return self.modify(req)

    # Admin approval payload handling
    def approve_modification(self, data: ModificationApproval) -> None:
        # In a fuller implementation, you'd look up a stored modification request,
        # apply adjusted_price, and record admin decision. Left as a stub here.
        pass