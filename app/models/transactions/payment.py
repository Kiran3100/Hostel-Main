# app.models/transactions/payment.py
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import Date, DateTime, Enum as SAEnum, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.schemas.common.enums import PaymentType, PaymentMethod, PaymentStatus
from app.models.base import BaseEntity


class Payment(BaseEntity):
    """Unified Payment model."""
    __tablename__ = "txn_payment"

    payer_id: Mapped[UUID] = mapped_column(ForeignKey("core_user.id"), index=True)
    hostel_id: Mapped[UUID] = mapped_column(ForeignKey("core_hostel.id"), index=True)
    student_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("core_student.id"), nullable=True)
    booking_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("txn_booking.id"), nullable=True)

    payment_type: Mapped[PaymentType] = mapped_column(SAEnum(PaymentType, name="payment_type"))
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    currency: Mapped[str] = mapped_column(String(3), default="INR")

    payment_period_start: Mapped[Optional[date]] = mapped_column(Date)
    payment_period_end: Mapped[Optional[date]] = mapped_column(Date)

    payment_method: Mapped[PaymentMethod] = mapped_column(SAEnum(PaymentMethod, name="payment_method"))
    payment_gateway: Mapped[Optional[str]] = mapped_column(String(50))

    payment_status: Mapped[PaymentStatus] = mapped_column(SAEnum(PaymentStatus, name="payment_status"))
    transaction_id: Mapped[Optional[str]] = mapped_column(String(100))

    due_date: Mapped[Optional[date]] = mapped_column(Date)
    paid_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    failed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    failure_reason: Mapped[Optional[str]] = mapped_column(String(500))

    receipt_number: Mapped[Optional[str]] = mapped_column(String(100))
    receipt_url: Mapped[Optional[str]] = mapped_column(String(500))

    # Relationships
    booking: Mapped[Optional["Booking"]] = relationship(back_populates="payments")