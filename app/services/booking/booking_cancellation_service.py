# app/services/booking/booking_cancellation_service.py
from __future__ import annotations

from datetime import datetime, timezone, date
from decimal import Decimal
from typing import Callable, Optional, List, Protocol
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.transactions import BookingRepository, PaymentRepository
from app.schemas.common.enums import BookingStatus, PaymentStatus, PaymentType
from app.schemas.booking import (
    CancellationRequest,
    CancellationResponse,
    RefundCalculation,
    CancellationPolicy,
    CancellationCharge,
    BulkCancellation,
)
from app.services.common import UnitOfWork, errors


class RefundExecutor(Protocol):
    """
    Optional abstraction for actually issuing refunds via payment gateway.
    """

    def execute_refund(
        self,
        *,
        payment_id: UUID,
        amount: Decimal,
        reason: str,
    ) -> str: ...
    # returns refund reference/transaction id


class BookingCancellationService:
    """
    Booking cancellation and refund calculation:

    - Cancel bookings
    - Compute refund amounts based on CancellationPolicy
    - Optionally execute refunds via a RefundExecutor
    """

    def __init__(
        self,
        session_factory: Callable[[], Session],
        refund_executor: Optional[RefundExecutor] = None,
    ) -> None:
        self._session_factory = session_factory
        self._refund_executor = refund_executor

    def _get_booking_repo(self, uow: UnitOfWork) -> BookingRepository:
        return uow.get_repo(BookingRepository)

    def _get_payment_repo(self, uow: UnitOfWork) -> PaymentRepository:
        return uow.get_repo(PaymentRepository)

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    # ------------------------------------------------------------------ #
    # Policy evaluation
    # ------------------------------------------------------------------ #
    def _find_applicable_charge(
        self,
        policy: CancellationPolicy,
        days_before_checkin: int,
    ) -> CancellationCharge:
        """
        Given days_before_checkin, find the matching charge tier:

        Assumes policy.cancellation_before_days is sorted ascending by days_before_checkin.
        """
        # Simple approach: choose the highest days_before_checkin <= actual days_before
        best: Optional[CancellationCharge] = None
        for tier in policy.cancellation_before_days:
            if days_before_checkin >= tier.days_before_checkin:
                if best is None or tier.days_before_checkin > best.days_before_checkin:
                    best = tier
        # If none matched, choose the strictest (e.g. highest charge)
        if best is None and policy.cancellation_before_days:
            best = policy.cancellation_before_days[-1]
        if best is None:
            # default: no charge
            return CancellationCharge(
                days_before_checkin=0,
                charge_percentage=Decimal("0"),
                description="No policy; full refund",
            )
        return best

    def _calculate_refund(
        self,
        booking,
        payment_amount: Decimal,
        policy: CancellationPolicy,
        cancel_date: date,
    ) -> RefundCalculation:
        check_in = booking.preferred_check_in_date
        days_before = (check_in - cancel_date).days if check_in > cancel_date else 0
        tier = self._find_applicable_charge(policy, days_before)

        cancellation_charge = (payment_amount * tier.charge_percentage) / 100
        refundable = max(Decimal("0"), payment_amount - cancellation_charge)

        return RefundCalculation(
            advance_paid=payment_amount,
            cancellation_charge=cancellation_charge,
            cancellation_charge_percentage=tier.charge_percentage,
            refundable_amount=refundable,
            refund_processing_time_days=policy.refund_processing_days,
            refund_method="original_source",
            breakdown={
                "days_before_checkin": days_before,
                "applied_tier": tier.description,
            },
        )

    # ------------------------------------------------------------------ #
    # Cancel a booking
    # ------------------------------------------------------------------ #
    def cancel(
        self,
        data: CancellationRequest,
        *,
        policy: CancellationPolicy,
    ) -> CancellationResponse:
        with UnitOfWork(self._session_factory) as uow:
            booking_repo = self._get_booking_repo(uow)
            payment_repo = self._get_payment_repo(uow)

            b = booking_repo.get(data.booking_id)
            if b is None:
                raise errors.NotFoundError(f"Booking {data.booking_id} not found")

            # Only pending/confirmed/checked_in bookings are cancellable here
            if b.booking_status not in (
                BookingStatus.PENDING,
                BookingStatus.CONFIRMED,
                BookingStatus.CHECKED_IN,
            ):
                raise errors.ValidationError(f"Booking {data.booking_id} cannot be cancelled in status {b.booking_status}")

            # For simplicity, look for a single booking_advance payment
            payments = payment_repo.list_for_booking(b.id)
            advance_payment = None
            for p in payments:
                if p.payment_type == PaymentType.BOOKING_ADVANCE:
                    advance_payment = p
                    break

            payment_amount = advance_payment.amount if advance_payment else Decimal("0")
            refund = self._calculate_refund(
                booking=b,
                payment_amount=payment_amount,
                policy=policy,
                cancel_date=date.today(),
            )

            # Optionally execute refund via gateway
            if data.request_refund and self._refund_executor and advance_payment:
                refund_ref = self._refund_executor.execute_refund(
                    payment_id=advance_payment.id,
                    amount=refund.refundable_amount,
                    reason=data.cancellation_reason,
                )
                refund.breakdown["refund_reference"] = refund_ref

            # Update booking status
            b.booking_status = BookingStatus.CANCELLED  # type: ignore[attr-defined]
            # For full semantics, you'd also set cancelled_by/at fields via another store.

            uow.session.flush()  # type: ignore[union-attr]
            uow.commit()

        return CancellationResponse(
            booking_id=b.id,
            booking_reference=f"BKG-{str(b.id)[:8].upper()}",
            cancelled=True,
            cancelled_at=self._now(),
            refund=refund,
            message="Booking cancelled successfully",
            confirmation_sent=False,
        )

    def bulk_cancel(
        self,
        data: BulkCancellation,
        *,
        policy: CancellationPolicy,
    ) -> List[CancellationResponse]:
        responses: List[CancellationResponse] = []
        for bid in data.booking_ids:
            req = CancellationRequest(
                booking_id=bid,
                cancelled_by_role="admin",
                cancellation_reason=data.reason,
                request_refund=data.process_refunds,
                additional_comments=None,
            )
            responses.append(self.cancel(req, policy=policy))
        return responses