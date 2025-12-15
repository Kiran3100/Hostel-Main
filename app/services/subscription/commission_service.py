# app/services/subscription/commission_service.py
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Protocol
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.transactions import (
    BookingRepository,
    SubscriptionRepository,
    SubscriptionPlanRepository,
)
from app.schemas.subscription.commission import (
    CommissionConfig,
    BookingCommissionResponse,
    CommissionSummary,
)
from app.schemas.common.filters import DateRangeFilter
from app.services.common import UnitOfWork, errors


class CommissionConfigStore(Protocol):
    """
    Storage abstraction for CommissionConfig.
    """

    def get_config(self) -> Optional[dict]: ...
    def save_config(self, data: dict) -> None: ...


class CommissionStore(Protocol):
    """
    Storage abstraction for booking commission records.

    Expected record shape:

        {
            "id": UUID,
            "booking_id": UUID,
            "hostel_id": UUID,
            "subscription_id": UUID,
            "booking_amount": Decimal,
            "commission_percentage": Decimal,
            "commission_amount": Decimal,
            "currency": str,
            "status": str,       # pending|calculated|paid|waived
            "due_date": date | None,
            "paid_date": date | None,
            "payment_reference": str | None,
            "created_at": datetime,
        }
    """

    def save_commission(self, record: dict) -> dict: ...
    def get_by_booking(self, booking_id: UUID) -> Optional[dict]: ...
    def list_commissions(
        self,
        *,
        hostel_id: Optional[UUID],
        start_date: date,
        end_date: date,
    ) -> List[dict]: ...


class CommissionService:
    """
    Booking commission management:

    - Global/platform commission config
    - Calculate commission for a booking based on subscription plan
    - Commission summary per platform/hostel & period
    """

    def __init__(
        self,
        session_factory: Callable[[], Session],
        config_store: CommissionConfigStore,
        commission_store: CommissionStore,
    ) -> None:
        self._session_factory = session_factory
        self._config_store = config_store
        self._commission_store = commission_store

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _get_booking_repo(self, uow: UnitOfWork) -> BookingRepository:
        return uow.get_repo(BookingRepository)

    def _get_sub_repo(self, uow: UnitOfWork) -> SubscriptionRepository:
        return uow.get_repo(SubscriptionRepository)

    def _get_plan_repo(self, uow: UnitOfWork) -> SubscriptionPlanRepository:
        return uow.get_repo(SubscriptionPlanRepository)

    def _default_config(self) -> CommissionConfig:
        cfg = CommissionConfig()
        self._config_store.save_config(cfg.model_dump())
        return cfg

    # ------------------------------------------------------------------ #
    # Config
    # ------------------------------------------------------------------ #
    def get_config(self) -> CommissionConfig:
        record = self._config_store.get_config()
        if record:
            return CommissionConfig.model_validate(record)
        return self._default_config()

    def set_config(self, cfg: CommissionConfig) -> None:
        self._config_store.save_config(cfg.model_dump())

    # ------------------------------------------------------------------ #
    # Commission calculation
    # ------------------------------------------------------------------ #
    def calculate_for_booking(self, booking_id: UUID) -> BookingCommissionResponse:
        """
        Calculate and persist commission for a single booking.

        Uses:
        - CommissionConfig (default or per plan_type override)
        - Active Subscription for the booking's hostel (if any)
        """
        cfg = self.get_config()

        with UnitOfWork(self._session_factory) as uow:
            booking_repo = self._get_booking_repo(uow)
            sub_repo = self._get_sub_repo(uow)
            plan_repo = self._get_plan_repo(uow)

            booking = booking_repo.get(booking_id)
            if booking is None:
                raise errors.NotFoundError(f"Booking {booking_id} not found")

            booking_amount = getattr(booking, "total_amount", None)
            if booking_amount is None:
                raise errors.ValidationError("Booking has no total_amount set")

            booking_date = booking.booking_date.date() if booking.booking_date else date.today()

            sub = sub_repo.get_active_for_hostel(booking.hostel_id, as_of=booking_date)
            subscription_id: UUID
            plan_type_key = "default"

            if sub:
                subscription_id = sub.id
                plan = plan_repo.get(sub.plan_id)
                if plan and getattr(plan, "plan_type", None):
                    plan_type_key = getattr(plan.plan_type, "value", str(plan.plan_type))
            else:
                subscription_id = UUID(int=0)

            # Determine commission percentage
            pct = cfg.default_commission_percentage
            override = cfg.commission_by_plan.get(plan_type_key)
            if override is not None:
                pct = override

            # Clamp between min/max
            pct = max(cfg.min_commission_percentage, min(cfg.max_commission_percentage, pct))

            commission_amount = (booking_amount * pct / Decimal("100")).quantize(Decimal("0.01"))
            due_date = booking_date + timedelta(days=30)

            record = {
                "id": UUID(int=0),
                "booking_id": booking.id,
                "hostel_id": booking.hostel_id,
                "subscription_id": subscription_id,
                "booking_amount": booking_amount,
                "commission_percentage": pct,
                "commission_amount": commission_amount,
                "currency": "INR",
                "status": "calculated",
                "due_date": due_date,
                "paid_date": None,
                "payment_reference": None,
            }
            saved = self._commission_store.save_commission(record)

        return BookingCommissionResponse.model_validate(saved)

    # ------------------------------------------------------------------ #
    # Summary
    # ------------------------------------------------------------------ #
    def get_commission_summary(
        self,
        scope_type: str,      # "platform" | "hostel"
        *,
        hostel_id: Optional[UUID],
        period: DateRangeFilter,
    ) -> CommissionSummary:
        if scope_type not in {"platform", "hostel"}:
            raise errors.ValidationError("scope_type must be 'platform' or 'hostel'")

        if scope_type == "platform":
            hostel_id_filter = None
        else:
            hostel_id_filter = hostel_id

        start = period.start_date or date.min
        end = period.end_date or date.max

        records = self._commission_store.list_commissions(
            hostel_id=hostel_id_filter,
            start_date=start,
            end_date=end,
        )

        total_due = Decimal("0")
        total_paid = Decimal("0")
        total_bookings = len(records)
        bookings_with_commission = 0

        for r in records:
            amt = Decimal(str(r.get("commission_amount", "0")))
            if amt > 0:
                bookings_with_commission += 1

            status = (r.get("status") or "").lower()
            if status in {"pending", "calculated"}:
                total_due += amt
            elif status == "paid":
                total_paid += amt

        return CommissionSummary(
            scope_type=scope_type,
            hostel_id=hostel_id_filter,
            period_start=start,
            period_end=end,
            total_commission_due=total_due,
            total_commission_paid=total_paid,
            total_bookings_count=total_bookings,
            bookings_with_commission_count=bookings_with_commission,
        )