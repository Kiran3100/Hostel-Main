# app/services/referral/referral_service.py
from __future__ import annotations

import secrets
import string
from datetime import date
from typing import Callable, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.transactions import ReferralRepository, ReferralProgramRepository
from app.repositories.core import UserRepository
from app.schemas.common.enums import ReferralStatus
from app.schemas.referral.referral_base import ReferralCreate
from app.schemas.referral.referral_code import (
    ReferralCodeGenerate,
    ReferralCodeResponse,
    CodeValidationRequest,
    CodeValidationResponse,
)
from app.schemas.referral.referral_program_response import ProgramResponse
from app.schemas.referral.referral_response import (
    ReferralResponse,
    ReferralStats,
)
from app.services.common import UnitOfWork, errors


class ReferralService:
    """
    Referral operations:

    - Generate referral codes for users
    - Create referral records (when shared / used)
    - Validate referral codes
    - List and compute stats for referrers
    """

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _get_referral_repo(self, uow: UnitOfWork) -> ReferralRepository:
        return uow.get_repo(ReferralRepository)

    def _get_program_repo(self, uow: UnitOfWork) -> ReferralProgramRepository:
        return uow.get_repo(ReferralProgramRepository)

    def _get_user_repo(self, uow: UnitOfWork) -> UserRepository:
        return uow.get_repo(UserRepository)

    def _generate_code(self, prefix: str) -> str:
        """
        Generate a short referral code with the given prefix.
        """
        token = "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))
        return f"{prefix}-{token}"

    # ------------------------------------------------------------------ #
    # Mapping
    # ------------------------------------------------------------------ #
    def _to_response(
        self,
        r,
        *,
        program_name: str,
        referrer_name: str,
    ) -> ReferralResponse:
        return ReferralResponse(
            id=r.id,
            created_at=r.created_at,
            updated_at=r.updated_at,
            program_id=r.program_id,
            program_name=program_name,
            referrer_id=r.referrer_id,
            referrer_name=referrer_name,
            referee_email=r.referee_email,
            referee_phone=r.referee_phone,
            referee_user_id=r.referee_user_id,
            referral_code=r.referral_code,
            status=r.status,
            booking_id=r.booking_id,
            completed_at=r.completed_at,
            referrer_reward_amount=r.referrer_reward_amount,
            referee_reward_amount=r.referee_reward_amount,
            currency=r.currency,
            referrer_reward_status=r.referrer_reward_status,
            referee_reward_status=r.referee_reward_status,
        )

    # ------------------------------------------------------------------ #
    # Code generation & validation
    # ------------------------------------------------------------------ #
    def generate_code(self, data: ReferralCodeGenerate) -> ReferralCodeResponse:
        """
        Generate a unique referral code for a user in a given program and
        create a base Referral record without referee populated yet.
        """
        prefix = data.prefix.upper().strip() or "REF"

        with UnitOfWork(self._session_factory) as uow:
            program_repo = self._get_program_repo(uow)
            referral_repo = self._get_referral_repo(uow)
            user_repo = self._get_user_repo(uow)

            prog = program_repo.get(data.program_id)
            if prog is None:
                raise errors.NotFoundError(f"ReferralProgram {data.program_id} not found")

            user = user_repo.get(data.user_id)
            if user is None:
                raise errors.NotFoundError(f"User {data.user_id} not found")

            # Find a unique code
            while True:
                code = self._generate_code(prefix)
                existing = referral_repo.get_multi(
                    skip=0,
                    limit=1,
                    filters={"referral_code": code},
                )
                if not existing:
                    break

            payload = {
                "program_id": data.program_id,
                "referrer_id": data.user_id,
                "referee_email": None,
                "referee_phone": None,
                "referee_user_id": None,
                "referral_code": code,
                "status": ReferralStatus.PENDING,
            }
            referral_repo.create(payload)  # type: ignore[arg-type]
            uow.commit()

        return ReferralCodeResponse(
            user_id=data.user_id,
            program_id=data.program_id,
            referral_code=code,
        )

    def validate_code(self, data: CodeValidationRequest) -> CodeValidationResponse:
        """
        Validate a referral code and return referrer/program info if valid.

        Validation checks:
        - Code exists
        - Program is active and within validity period (if specified)
        """
        today = date.today()

        with UnitOfWork(self._session_factory) as uow:
            referral_repo = self._get_referral_repo(uow)
            program_repo = self._get_program_repo(uow)

            refs = referral_repo.get_multi(
                skip=0,
                limit=1,
                filters={"referral_code": data.referral_code},
            )
            if not refs:
                return CodeValidationResponse(
                    referral_code=data.referral_code,
                    is_valid=False,
                    program_id=None,
                    referrer_id=None,
                    message="Invalid or unknown referral code",
                )

            r = refs[0]
            prog = program_repo.get(r.program_id)
            if not prog or not prog.is_active:
                return CodeValidationResponse(
                    referral_code=data.referral_code,
                    is_valid=False,
                    program_id=r.program_id,
                    referrer_id=r.referrer_id,
                    message="Referral program is not active",
                )

            if prog.valid_from and today < prog.valid_from:
                return CodeValidationResponse(
                    referral_code=data.referral_code,
                    is_valid=False,
                    program_id=r.program_id,
                    referrer_id=r.referrer_id,
                    message="Referral program has not started yet",
                )
            if prog.valid_to and today > prog.valid_to:
                return CodeValidationResponse(
                    referral_code=data.referral_code,
                    is_valid=False,
                    program_id=r.program_id,
                    referrer_id=r.referrer_id,
                    message="Referral program has expired",
                )

            return CodeValidationResponse(
                referral_code=data.referral_code,
                is_valid=True,
                program_id=r.program_id,
                referrer_id=r.referrer_id,
                message="Referral code is valid",
            )

    # ------------------------------------------------------------------ #
    # Referral records
    # ------------------------------------------------------------------ #
    def create_referral(self, data: ReferralCreate) -> ReferralResponse:
        """
        Create a referral record (e.g. when a user shares or when booking uses a code).
        """
        with UnitOfWork(self._session_factory) as uow:
            referral_repo = self._get_referral_repo(uow)
            program_repo = self._get_program_repo(uow)
            user_repo = self._get_user_repo(uow)

            prog = program_repo.get(data.program_id)
            if prog is None:
                raise errors.NotFoundError(f"ReferralProgram {data.program_id} not found")

            referrer = user_repo.get(data.referrer_id)
            if referrer is None:
                raise errors.NotFoundError(f"Referrer user {data.referrer_id} not found")

            payload = data.model_dump(exclude_unset=True)
            r = referral_repo.create(payload)  # type: ignore[arg-type]
            uow.commit()

            return self._to_response(
                r,
                program_name=prog.program_name,
                referrer_name=referrer.full_name,
            )

    def get_referral(self, referral_id: UUID) -> ReferralResponse:
        with UnitOfWork(self._session_factory) as uow:
            referral_repo = self._get_referral_repo(uow)
            program_repo = self._get_program_repo(uow)
            user_repo = self._get_user_repo(uow)

            r = referral_repo.get(referral_id)
            if r is None:
                raise errors.NotFoundError(f"Referral {referral_id} not found")

            prog = program_repo.get(r.program_id)
            referrer = user_repo.get(r.referrer_id)

            program_name = prog.program_name if prog else ""
            referrer_name = referrer.full_name if referrer else ""

            return self._to_response(
                r,
                program_name=program_name,
                referrer_name=referrer_name,
            )

    def list_referrals_for_user(self, user_id: UUID) -> List[ReferralResponse]:
        """
        List all referrals where user_id is the referrer.
        """
        with UnitOfWork(self._session_factory) as uow:
            referral_repo = self._get_referral_repo(uow)
            program_repo = self._get_program_repo(uow)
            user_repo = self._get_user_repo(uow)

            recs = referral_repo.list_for_referrer(user_id)
            referrer = user_repo.get(user_id)
            referrer_name = referrer.full_name if referrer else ""

            # Cache programs
            prog_cache: dict[UUID, str] = {}
            results: List[ReferralResponse] = []

            for r in recs:
                if r.program_id not in prog_cache:
                    p = program_repo.get(r.program_id)
                    prog_cache[r.program_id] = p.program_name if p else ""
                program_name = prog_cache[r.program_id]
                results.append(
                    self._to_response(
                        r,
                        program_name=program_name,
                        referrer_name=referrer_name,
                    )
                )
            return results

    # ------------------------------------------------------------------ #
    # Stats
    # ------------------------------------------------------------------ #
    def get_stats_for_user(self, user_id: UUID) -> ReferralStats:
        """
        Aggregate referral statistics for a referrer.
        """
        with UnitOfWork(self._session_factory) as uow:
            referral_repo = self._get_referral_repo(uow)
            recs = referral_repo.list_for_referrer(user_id)

        total = len(recs)
        successful = sum(1 for r in recs if r.status == ReferralStatus.COMPLETED)
        pending = sum(1 for r in recs if r.status == ReferralStatus.PENDING)

        total_earned = sum(
            (r.referrer_reward_amount or Decimal("0")) for r in recs  # type: ignore[name-defined]
        )
        total_paid_out = Decimal("0")
        total_pending_rewards = total_earned - total_paid_out

        return ReferralStats(
            user_id=user_id,
            total_referrals=total,
            successful_referrals=successful,
            pending_referrals=pending,
            total_earned=total_earned,
            total_paid_out=total_paid_out,
            total_pending_rewards=total_pending_rewards,
        )