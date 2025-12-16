# app.models/transactions/payment.py
from datetime import date, datetime
from decimal import Decimal
from typing import Union, TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Date, DateTime, Enum as SAEnum, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.schemas.common.enums import PaymentType, PaymentMethod, PaymentStatus
from app.models.base import BaseEntity

if TYPE_CHECKING:
    from app.models.transactions.booking import Booking


class Payment(BaseEntity):
    """Unified Payment model."""
    __tablename__ = "txn_payment"

    payer_id: Mapped[UUID] = mapped_column(ForeignKey("core_user.id"), index=True)
    hostel_id: Mapped[UUID] = mapped_column(ForeignKey("core_hostel.id"), index=True)
    student_id: Mapped[Union[UUID, None]] = mapped_column(ForeignKey("core_student.id"), nullable=True)
    booking_id: Mapped[Union[UUID, None]] = mapped_column(ForeignKey("txn_booking.id"), nullable=True)

    payment_type: Mapped[PaymentType] = mapped_column(SAEnum(PaymentType, name="payment_type"))
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    currency: Mapped[str] = mapped_column(String(3), default="INR")

    payment_period_start: Mapped[Union[date, None]] = mapped_column(Date)
    payment_period_end: Mapped[Union[date, None]] = mapped_column(Date)

    payment_method: Mapped[PaymentMethod] = mapped_column(SAEnum(PaymentMethod, name="payment_method"))
    payment_gateway: Mapped[Union[str, None]] = mapped_column(String(50))

    payment_status: Mapped[PaymentStatus] = mapped_column(SAEnum(PaymentStatus, name="payment_status"))
    transaction_id: Mapped[Union[str, None]] = mapped_column(String(100))

    due_date: Mapped[Union[date, None]] = mapped_column(Date)
    paid_at: Mapped[Union[datetime, None]] = mapped_column(DateTime(timezone=True))
    failed_at: Mapped[Union[datetime, None]] = mapped_column(DateTime(timezone=True))
    failure_reason: Mapped[Union[str, None]] = mapped_column(String(500))

    receipt_number: Mapped[Union[str, None]] = mapped_column(String(100))
    receipt_url: Mapped[Union[str, None]] = mapped_column(String(500))

    # Relationships
    booking: Mapped[Union["Booking", None]] = relationship(back_populates="payments")