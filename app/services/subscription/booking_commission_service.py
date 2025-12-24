"""
Booking Commission Service

Manages commission records for bookings under subscription programs.
"""

from __future__ import annotations

from typing import List, Optional
from uuid import UUID
from datetime import datetime

from sqlalchemy.orm import Session

from app.repositories.subscription import BookingCommissionRepository
from app.schemas.subscription import (
    BookingCommissionResponse,
    CommissionStatus,
)
from app.core.exceptions import ValidationException


class BookingCommissionService:
    """
    High-level service for booking commissions.

    Responsibilities:
    - Create commission records for bookings
    - Retrieve commissions by id/booking/subscription/hostel
    - Mark commissions as paid/waived/disputed
    """

    def __init__(
        self,
        commission_repo: BookingCommissionRepository,
    ) -> None:
        self.commission_repo = commission_repo

    # -------------------------------------------------------------------------
    # Create
    # -------------------------------------------------------------------------

    def create_commission_for_booking(
        self,
        db: Session,
        booking_id: UUID,
        subscription_id: UUID,
        hostel_id: UUID,
        booking_amount: float,
        commission_percentage: float,
        currency: str,
        due_date: Optional[datetime] = None,
    ) -> BookingCommissionResponse:
        """
        Create a commission record for a booking.

        The percentage is applied to booking_amount to compute commission_amount.
        """
        commission_amount = round(booking_amount * (commission_percentage / 100.0), 2)

        obj = self.commission_repo.create(
            db,
            data={
                "booking_id": booking_id,
                "subscription_id": subscription_id,
                "hostel_id": hostel_id,
                "booking_amount": booking_amount,
                "commission_percentage": commission_percentage,
                "commission_amount": commission_amount,
                "currency": currency,
                "status": CommissionStatus.PENDING.value,
                "due_date": due_date,
            },
        )
        return BookingCommissionResponse.model_validate(obj)

    # -------------------------------------------------------------------------
    # Retrieval
    # -------------------------------------------------------------------------

    def get_commission(
        self,
        db: Session,
        commission_id: UUID,
    ) -> BookingCommissionResponse:
        obj = self.commission_repo.get_by_id(db, commission_id)
        if not obj:
            raise ValidationException("Commission not found")
        return BookingCommissionResponse.model_validate(obj)

    def list_commissions_for_subscription(
        self,
        db: Session,
        subscription_id: UUID,
    ) -> List[BookingCommissionResponse]:
        objs = self.commission_repo.get_by_subscription_id(db, subscription_id)
        return [BookingCommissionResponse.model_validate(o) for o in objs]

    def list_commissions_for_hostel(
        self,
        db: Session,
        hostel_id: UUID,
    ) -> List[BookingCommissionResponse]:
        objs = self.commission_repo.get_by_hostel_id(db, hostel_id)
        return [BookingCommissionResponse.model_validate(o) for o in objs]

    # -------------------------------------------------------------------------
    # Status updates
    # -------------------------------------------------------------------------

    def mark_commission_paid(
        self,
        db: Session,
        commission_id: UUID,
        payment_reference: Optional[str] = None,
        paid_at: Optional[datetime] = None,
    ) -> BookingCommissionResponse:
        """
        Mark a commission as paid.
        """
        obj = self.commission_repo.get_by_id(db, commission_id)
        if not obj:
            raise ValidationException("Commission not found")

        updated = self.commission_repo.update(
            db,
            obj,
            data={
                "status": CommissionStatus.PAID.value,
                "paid_date": paid_at or datetime.utcnow(),
                "payment_reference": payment_reference,
            },
        )
        return BookingCommissionResponse.model_validate(updated)

    def update_commission_status(
        self,
        db: Session,
        commission_id: UUID,
        status: CommissionStatus,
        reason: Optional[str] = None,
    ) -> BookingCommissionResponse:
        """
        Update commission status (e.g. WAIVED, DISPUTED, INVOICED).
        """
        obj = self.commission_repo.get_by_id(db, commission_id)
        if not obj:
            raise ValidationException("Commission not found")

        updated = self.commission_repo.update(
            db,
            obj,
            data={
                "status": status.value,
                "status_reason": reason,
            },
        )
        return BookingCommissionResponse.model_validate(updated)