# app/services/fee_structure/fee_structure_service.py
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Callable, List
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.transactions import FeeStructureRepository
from app.repositories.core import HostelRepository
from app.schemas.fee_structure import (
    FeeStructureCreate,
    FeeStructureUpdate,
    FeeStructureResponse,
    FeeStructureList,
    FeeDetail,
)
from app.schemas.common.enums import ChargeType
from app.services.common import UnitOfWork, errors


class FeeStructureService:
    """
    Manage fee structures per hostel & room type.

    - Create / update fee structures
    - Get single fee structure
    - List fee structures for a hostel
    - Compute FeeDetail list for UI (derived first-month & recurring totals)
    """

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _get_fee_repo(self, uow: UnitOfWork) -> FeeStructureRepository:
        return uow.get_repo(FeeStructureRepository)

    def _get_hostel_repo(self, uow: UnitOfWork) -> HostelRepository:
        return uow.get_repo(HostelRepository)

    # ------------------------------------------------------------------ #
    # Mapping helpers
    # ------------------------------------------------------------------ #
    def _to_response(self, fs, *, hostel_name: str) -> FeeStructureResponse:
        return FeeStructureResponse(
            id=fs.id,
            created_at=fs.created_at,
            updated_at=fs.updated_at,
            hostel_id=fs.hostel_id,
            hostel_name=hostel_name,
            room_type=fs.room_type,
            fee_type=fs.fee_type,
            amount=fs.amount,
            security_deposit=fs.security_deposit,
            includes_mess=fs.includes_mess,
            mess_charges_monthly=fs.mess_charges_monthly,
            electricity_charges=fs.electricity_charges,
            electricity_fixed_amount=fs.electricity_fixed_amount,
            water_charges=fs.water_charges,
            water_fixed_amount=fs.water_fixed_amount,
            effective_from=fs.effective_from,
            effective_to=fs.effective_to,
            is_active=fs.is_active,
        )

    def _to_fee_detail(self, fs) -> FeeDetail:
        """
        Compute FeeDetail from a FeeStructure row.
        """
        base = fs.amount or Decimal("0")
        mess = fs.mess_charges_monthly or Decimal("0") if fs.includes_mess else Decimal("0")

        elec = Decimal("0")
        if fs.electricity_charges == ChargeType.FIXED and fs.electricity_fixed_amount:
            elec = fs.electricity_fixed_amount

        water = Decimal("0")
        if fs.water_charges == ChargeType.FIXED and fs.water_fixed_amount:
            water = fs.water_fixed_amount

        total_recurring = base + mess + elec + water
        total_first_month = total_recurring + (fs.security_deposit or Decimal("0"))

        return FeeDetail(
            room_type=fs.room_type,
            fee_type=fs.fee_type,
            amount=fs.amount,
            security_deposit=fs.security_deposit,
            includes_mess=fs.includes_mess,
            mess_charges_monthly=fs.mess_charges_monthly,
            total_first_month_payable=total_first_month,
            total_recurring_monthly=total_recurring,
        )

    # ------------------------------------------------------------------ #
    # Core operations
    # ------------------------------------------------------------------ #
    def get_fee_structure(self, fee_id: UUID) -> FeeStructureResponse:
        with UnitOfWork(self._session_factory) as uow:
            fee_repo = self._get_fee_repo(uow)
            hostel_repo = self._get_hostel_repo(uow)

            fs = fee_repo.get(fee_id)
            if fs is None:
                raise errors.NotFoundError(f"FeeStructure {fee_id} not found")

            hostel = hostel_repo.get(fs.hostel_id)
            hostel_name = hostel.name if hostel else ""
            return self._to_response(fs, hostel_name=hostel_name)

    def list_for_hostel(self, hostel_id: UUID) -> FeeStructureList:
        with UnitOfWork(self._session_factory) as uow:
            fee_repo = self._get_fee_repo(uow)
            hostel_repo = self._get_hostel_repo(uow)

            hostel = hostel_repo.get(hostel_id)
            if hostel is None:
                raise errors.NotFoundError(f"Hostel {hostel_id} not found")
            hostel_name = hostel.name

            records = fee_repo.get_multi(
                skip=0,
                limit=None,  # type: ignore[arg-type]
                filters={"hostel_id": hostel_id},
                order_by=[fee_repo.model.room_type.asc()],  # type: ignore[attr-defined]
            )

            items: List[FeeStructureResponse] = [
                self._to_response(fs, hostel_name=hostel_name) for fs in records
            ]

            return FeeStructureList(
                hostel_id=hostel_id,
                hostel_name=hostel_name,
                items=items,
            )

    def create_fee_structure(self, data: FeeStructureCreate) -> FeeStructureResponse:
        """
        Create a new fee structure.

        NOTE: Does not enforce overlap checks between effective_from/effective_to;
        add that if needed.
        """
        with UnitOfWork(self._session_factory) as uow:
            fee_repo = self._get_fee_repo(uow)
            hostel_repo = self._get_hostel_repo(uow)

            hostel = hostel_repo.get(data.hostel_id)
            if hostel is None:
                raise errors.NotFoundError(f"Hostel {data.hostel_id} not found")

            payload = data.model_dump()
            fs = fee_repo.create(payload)  # type: ignore[arg-type]
            uow.commit()

            return self._to_response(fs, hostel_name=hostel.name)

    def update_fee_structure(
        self,
        fee_id: UUID,
        data: FeeStructureUpdate,
    ) -> FeeStructureResponse:
        """
        Update an existing fee structure.
        """
        with UnitOfWork(self._session_factory) as uow:
            fee_repo = self._get_fee_repo(uow)
            hostel_repo = self._get_hostel_repo(uow)

            fs = fee_repo.get(fee_id)
            if fs is None:
                raise errors.NotFoundError(f"FeeStructure {fee_id} not found")

            mapping = data.model_dump(exclude_unset=True)
            for field, value in mapping.items():
                if hasattr(fs, field) and field != "id":
                    setattr(fs, field, value)

            uow.session.flush()  # type: ignore[union-attr]
            uow.commit()

            hostel = hostel_repo.get(fs.hostel_id)
            hostel_name = hostel.name if hostel else ""
            return self._to_response(fs, hostel_name=hostel_name)

    def deactivate_fee_structure(self, fee_id: UUID) -> FeeStructureResponse:
        """
        Soft-deactivate a fee structure (set is_active = False, effective_to = today).
        """
        from datetime import date as _date

        with UnitOfWork(self._session_factory) as uow:
            fee_repo = self._get_fee_repo(uow)
            hostel_repo = self._get_hostel_repo(uow)

            fs = fee_repo.get(fee_id)
            if fs is None:
                raise errors.NotFoundError(f"FeeStructure {fee_id} not found")

            fs.is_active = False  # type: ignore[attr-defined]
            if not fs.effective_to:
                fs.effective_to = _date.today()  # type: ignore[attr-defined]

            uow.session.flush()  # type: ignore[union-attr]
            uow.commit()

            hostel = hostel_repo.get(fs.hostel_id)
            hostel_name = hostel.name if hostel else ""
            return self._to_response(fs, hostel_name=hostel_name)

    # ------------------------------------------------------------------ #
    # Fee details for UI
    # ------------------------------------------------------------------ #
    def get_fee_details_for_hostel(self, hostel_id: UUID) -> List[FeeDetail]:
        """
        Return FeeDetail items for all active fee structures in a hostel.
        """
        with UnitOfWork(self._session_factory) as uow:
            fee_repo = self._get_fee_repo(uow)

            records = fee_repo.get_multi(
                skip=0,
                limit=None,  # type: ignore[arg-type]
                filters={"hostel_id": hostel_id, "is_active": True},
            )

        return [self._to_fee_detail(fs) for fs in records]