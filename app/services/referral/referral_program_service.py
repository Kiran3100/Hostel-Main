# app/services/referral/referral_program_service.py
from __future__ import annotations

from datetime import date
from typing import Callable, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.transactions import ReferralProgramRepository
from app.schemas.referral.referral_program_base import (
    ProgramCreate,
    ProgramUpdate,
)
from app.schemas.referral.referral_program_response import (
    ProgramResponse,
    ProgramList,
)
from app.services.common import UnitOfWork, errors


class ReferralProgramService:
    """
    Referral program management:

    - Create / update programs
    - Get single program
    - List active programs (optionally by date)
    """

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _get_repo(self, uow: UnitOfWork) -> ReferralProgramRepository:
        return uow.get_repo(ReferralProgramRepository)

    # ------------------------------------------------------------------ #
    # Mapping
    # ------------------------------------------------------------------ #
    def _to_response(self, p) -> ProgramResponse:
        return ProgramResponse(
            id=p.id,
            created_at=p.created_at,
            updated_at=p.updated_at,
            program_name=p.program_name,
            program_type=p.program_type,
            reward_type=p.reward_type,
            referrer_reward_amount=p.referrer_reward_amount,
            referee_reward_amount=p.referee_reward_amount,
            currency=p.currency,
            min_booking_amount=p.min_booking_amount,
            min_stay_months=p.min_stay_months,
            is_active=p.is_active,
            valid_from=p.valid_from,
            valid_to=p.valid_to,
            terms_and_conditions=p.terms_and_conditions,
        )

    # ------------------------------------------------------------------ #
    # CRUD
    # ------------------------------------------------------------------ #
    def create_program(self, data: ProgramCreate) -> ProgramResponse:
        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_repo(uow)

            payload = data.model_dump(exclude_unset=True)
            p = repo.create(payload)  # type: ignore[arg-type]
            uow.commit()
            return self._to_response(p)

    def update_program(self, program_id: UUID, data: ProgramUpdate) -> ProgramResponse:
        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_repo(uow)

            p = repo.get(program_id)
            if p is None:
                raise errors.NotFoundError(f"ReferralProgram {program_id} not found")

            mapping = data.model_dump(exclude_unset=True)
            for field, value in mapping.items():
                if hasattr(p, field) and field != "id":
                    setattr(p, field, value)

            uow.session.flush()  # type: ignore[union-attr]
            uow.commit()
            return self._to_response(p)

    def get_program(self, program_id: UUID) -> ProgramResponse:
        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_repo(uow)
            p = repo.get(program_id)
            if p is None:
                raise errors.NotFoundError(f"ReferralProgram {program_id} not found")
            return self._to_response(p)

    def list_active_programs(self, as_of: Optional[date] = None) -> ProgramList:
        """
        List all active programs, optionally filtered by a date in their validity window.
        """
        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_repo(uow)
            recs = repo.list_active(as_of=as_of)

        programs: List[ProgramResponse] = [self._to_response(p) for p in recs]
        return ProgramList(programs=programs)