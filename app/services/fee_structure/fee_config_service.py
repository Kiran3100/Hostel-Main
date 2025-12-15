# app/services/fee_structure/fee_config_service.py
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Callable
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.transactions import FeeStructureRepository
from app.schemas.fee_structure import (
    FeeConfiguration,
    ChargesBreakdown,
)
from app.schemas.common.enums import RoomType, FeeType, ChargeType
from app.services.common import UnitOfWork, errors


class FeeConfigService:
    """
    Compute effective fee configuration & breakdown for a given hostel/room type.

    - Uses FeeStructureRepository.get_effective_fee(as_of)
    - Produces FeeConfiguration + ChargesBreakdown
    """

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    def _get_fee_repo(self, uow: UnitOfWork) -> FeeStructureRepository:
        return uow.get_repo(FeeStructureRepository)

    # ------------------------------------------------------------------ #
    # Main API
    # ------------------------------------------------------------------ #
    def get_effective_fee_configuration(
        self,
        *,
        hostel_id: UUID,
        room_type: RoomType,
        fee_type: FeeType,
        as_of: date,
    ) -> FeeConfiguration:
        """
        Get effective FeeConfiguration for a specific hostel/room_type/fee_type on a given date.
        """
        with UnitOfWork(self._session_factory) as uow:
            fee_repo = self._get_fee_repo(uow)
            fs = fee_repo.get_effective_fee(
                hostel_id=hostel_id,
                room_type=room_type,
                fee_type=fee_type,
                as_of=as_of,
            )
            if fs is None:
                raise errors.NotFoundError(
                    f"No active fee structure for hostel={hostel_id}, room_type={room_type}, fee_type={fee_type} as of {as_of}"
                )

        base = fs.amount or Decimal("0")
        security_deposit = fs.security_deposit or Decimal("0")
        mess = fs.mess_charges_monthly or Decimal("0") if fs.includes_mess else Decimal("0")

        # Electricity
        elec = Decimal("0")
        if fs.electricity_charges == ChargeType.FIXED and fs.electricity_fixed_amount:
            elec = fs.electricity_fixed_amount
        # PER_UNIT or INCLUDED: treat as 0 for base configuration; billing can happen separately.

        # Water
        water = Decimal("0")
        if fs.water_charges == ChargeType.FIXED and fs.water_fixed_amount:
            water = fs.water_fixed_amount

        other = Decimal("0")

        total_monthly = base + mess + elec + water + other
        total_first_month = total_monthly + security_deposit

        breakdown = ChargesBreakdown(
            base_rent=base,
            mess_charges=mess,
            electricity_charges=elec,
            water_charges=water,
            other_charges=other,
            total_monthly=total_monthly,
            total_first_month=total_first_month,
            security_deposit=security_deposit,
        )

        return FeeConfiguration(
            hostel_id=hostel_id,
            room_type=room_type,
            fee_type=fee_type,
            base_amount=base,
            security_deposit=security_deposit,
            includes_mess=fs.includes_mess,
            mess_charges_monthly=fs.mess_charges_monthly,
            electricity_charges=fs.electricity_charges,
            electricity_fixed_amount=fs.electricity_fixed_amount,
            water_charges=fs.water_charges,
            water_fixed_amount=fs.water_fixed_amount,
            breakdown=breakdown,
        )