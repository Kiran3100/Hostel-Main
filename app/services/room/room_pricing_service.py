"""
Room Pricing Service

Manages room pricing updates and effective price calculations.
"""

from __future__ import annotations

from typing import List
from uuid import UUID
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.repositories.room import RoomRepository, RoomPricingHistoryRepository
from app.repositories.fee_structure import FeeStructureRepository
from app.schemas.room import RoomPricingUpdate
from app.schemas.fee_structure import FeeStructure
from app.schemas.room import RoomResponse
from app.core.exceptions import ValidationException


class RoomPricingService:
    """
    High-level service for room pricing.

    Responsibilities:
    - Update room pricing and record history
    - Retrieve pricing history
    - Calculate effective price using fee structures
    """

    def __init__(
        self,
        room_repo: RoomRepository,
        pricing_history_repo: RoomPricingHistoryRepository,
        fee_structure_repo: FeeStructureRepository,
    ) -> None:
        self.room_repo = room_repo
        self.pricing_history_repo = pricing_history_repo
        self.fee_structure_repo = fee_structure_repo

    def update_room_pricing(
        self,
        db: Session,
        room_id: UUID,
        data: RoomPricingUpdate,
        updated_by: UUID,
    ) -> RoomResponse:
        """
        Update room pricing and store a pricing history record.
        """
        room = self.room_repo.get_by_id(db, room_id)
        if not room:
            raise ValidationException("Room not found")

        payload = data.model_dump(exclude_none=True)
        updated = self.room_repo.update(db, room, payload)

        # Record history
        self.pricing_history_repo.record_pricing_change(
            db=db,
            room_id=room_id,
            changes=payload,
            changed_by=updated_by,
            effective_from=data.effective_from,
        )

        return RoomResponse.model_validate(updated)

    def get_pricing_history(
        self,
        db: Session,
        room_id: UUID,
    ) -> List[dict]:
        """
        Return raw pricing history entries (schemas can be added as needed).
        """
        return self.pricing_history_repo.get_history_for_room(db, room_id)

    def calculate_effective_price(
        self,
        db: Session,
        room_id: UUID,
        check_in: date,
        duration_months: int,
    ) -> Decimal:
        """
        Calculate effective monthly price for a room using FeeStructure.
        """
        room = self.room_repo.get_by_id(db, room_id)
        if not room:
            raise ValidationException("Room not found")

        fee_structure = self.fee_structure_repo.get_active_for_room_type(
            db=db,
            hostel_id=room.hostel_id,
            room_type=room.room_type,
            as_of=check_in,
        )
        if not fee_structure:
            # Fallback to room's own price
            return Decimal(str(room.price_monthly or 0))

        fs = FeeStructure.model_validate(fee_structure)
        # Simple example: base rent + mandatory charges
        return Decimal(str(fs.base_rent_per_month + fs.mandatory_charges_per_month))