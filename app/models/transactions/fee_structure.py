# app.models/transactions/fee_structure.py
from datetime import date
from decimal import Decimal
from typing import Union
from uuid import UUID

from sqlalchemy import Date, Enum as SAEnum, ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from app.schemas.common.enums import RoomType, FeeType, ChargeType
from app.models.base import BaseEntity


class FeeStructure(BaseEntity):
    """Fee configuration per hostel & room type."""
    __tablename__ = "cfg_fee_structure"

    hostel_id: Mapped[UUID] = mapped_column(ForeignKey("core_hostel.id"), index=True)
    room_type: Mapped[RoomType] = mapped_column(SAEnum(RoomType, name="room_type"))
    fee_type: Mapped[FeeType] = mapped_column(SAEnum(FeeType, name="fee_type"))

    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    security_deposit: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)

    includes_mess: Mapped[bool] = mapped_column(default=False)
    mess_charges_monthly: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)

    electricity_charges: Mapped[ChargeType] = mapped_column(SAEnum(ChargeType, name="charge_type"))
    electricity_fixed_amount: Mapped[Union[Decimal, None]] = mapped_column(Numeric(10, 2))

    water_charges: Mapped[ChargeType] = mapped_column(SAEnum(ChargeType, name="water_charge_type"))
    water_fixed_amount: Mapped[Union[Decimal, None]] = mapped_column(Numeric(10, 2))

    effective_from: Mapped[date] = mapped_column(Date)
    effective_to: Mapped[Union[date, None]] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(default=True)