# app/services/transactions/commission_service.py
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, Tuple
from uuid import UUID

from sqlalchemy import select

from app.repositories.transactions import (
    BookingRepository,
    ReferralProgramRepository,
    ReferralRepository,
)
from app.schemas.common.enums import ReferralStatus, RewardStatus
from models.transactions import Booking, Referral, ReferralProgram


class CommissionService:
    """
    Business logic for handling referral-based commissions/rewards.

    Responsibilities:
    - Attach completed bookings to matching referrals (via referral_code).
    - Validate that a booking qualifies for a referral program (date/amount/duration).
    - Calculate reward amounts for referrer and referee.
    - Update Referral records with amounts, currency, and statuses.

    Notes:
    - This service does NOT commit the DB session; the caller must manage
      transactions (commit/rollback) around its usage.
    - It relies on the repositories' underlying SQLAlchemy session.
    """

    def __init__(
        self,
        *,
        booking_repo: BookingRepository,
        referral_repo: ReferralRepository,
        referral_program_repo: ReferralProgramRepository,
        completed_status: Optional[ReferralStatus] = None,
        earned_reward_status: Optional[RewardStatus] = None,
    ) -> None:
        """
        :param completed_status:
            Optional enum value to set on Referral.status when a referral
            is successfully completed. If None, status is not changed.
        :param earned_reward_status:
            Optional enum value to set on referrer_reward_status and
            referee_reward_status when rewards are calculated. If None,
            reward statuses are not changed.
        """
        self.booking_repo = booking_repo
        self.referral_repo = referral_repo
        self.referral_program_repo = referral_program_repo

        self.completed_status = completed_status
        self.earned_reward_status = earned_reward_status

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def process_booking_commission(self, booking_id: UUID) -> Optional[Referral]:
        """
        Main entry point: process referral commission for a given booking.

        Steps:
          1. Load booking.
          2. If booking has a referral_code, find matching Referral.
          3. Load associated ReferralProgram.
          4. Verify booking meets program criteria.
          5. Calculate reward amounts.
          6. Update Referral (booking_id, completed_at, amounts, statuses).

        Returns the updated Referral, or None if:
          - Booking not found,
          - Booking has no referral_code,
          - No matching Referral,
          - Program not found or not active,
          - Booking does not meet program criteria.
        """
        booking = self.booking_repo.get(booking_id)
        if booking is None:
            return None

        if not booking.referral_code:
            return None

        referral = self._get_referral_by_code(booking.referral_code)
        if referral is None:
            return None

        program = self.referral_program_repo.get(referral.program_id)
        if program is None or not program.is_active:
            return None

        if not self._booking_meets_program_criteria(program, booking):
            return None

        referrer_amount, referee_amount = self._calculate_reward_amounts(
            booking_total=booking.total_amount,
            program=program,
        )

        # Apply updates on Referral
        self._apply_commission_to_referral(
            referral=referral,
            program=program,
            booking=booking,
            referrer_amount=referrer_amount,
            referee_amount=referee_amount,
        )
        # Repositories do not commit; caller must commit.
        return referral

    def recalculate_commission_for_referral(self, referral_id: UUID) -> Optional[Referral]:
        """
        Recalculate commission for an existing Referral (e.g. if program
        rules changed). Uses current program configuration and linked booking.

        Returns updated Referral or None if missing data / fails validation.
        """
        referral = self.referral_repo.get(referral_id)
        if referral is None or referral.booking_id is None:
            return None

        booking = self.booking_repo.get(referral.booking_id)
        if booking is None:
            return None

        program = self.referral_program_repo.get(referral.program_id)
        if program is None or not program.is_active:
            return None

        if not self._booking_meets_program_criteria(program, booking):
            return None

        referrer_amount, referee_amount = self._calculate_reward_amounts(
            booking_total=booking.total_amount,
            program=program,
        )

        self._apply_commission_to_referral(
            referral=referral,
            program=program,
            booking=booking,
            referrer_amount=referrer_amount,
            referee_amount=referee_amount,
        )
        return referral

    def mark_referrer_reward_status(
        self,
        referral_id: UUID,
        new_status: RewardStatus,
    ) -> Optional[Referral]:
        """
        Generic helper to update the referrer's reward status.
        Does not commit; caller must commit.
        """
        referral = self.referral_repo.get(referral_id)
        if referral is None:
            return None

        referral.referrer_reward_status = new_status
        self.referral_repo.session.flush()
        return referral

    def mark_referee_reward_status(
        self,
        referral_id: UUID,
        new_status: RewardStatus,
    ) -> Optional[Referral]:
        """
        Generic helper to update the referee's reward status.
        Does not commit; caller must commit.
        """
        referral = self.referral_repo.get(referral_id)
        if referral is None:
            return None

        referral.referee_reward_status = new_status
        self.referral_repo.session.flush()
        return referral

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    def _get_referral_by_code(self, referral_code: str) -> Optional[Referral]:
        """
        Look up a Referral by its referral_code.

        This uses the underlying SQLAlchemy session since the repository
        does not currently expose a dedicated 'get_by_code' method.
        """
        stmt = (
            select(Referral)
            .where(Referral.referral_code == referral_code)
            .limit(1)
        )
        return self.referral_repo.session.execute(stmt).scalar_one_or_none()

    def _booking_meets_program_criteria(
        self,
        program: ReferralProgram,
        booking: Booking,
    ) -> bool:
        """
        Check if the booking satisfies the ReferralProgram constraints:
        - valid_from / valid_to date window
        - min_booking_amount
        - min_stay_months
        """
        booking_date = booking.booking_date.date()

        if program.valid_from and booking_date < program.valid_from:
            return False
        if program.valid_to and booking_date > program.valid_to:
            return False

        if program.min_booking_amount is not None:
            if booking.total_amount < program.min_booking_amount:
                return False

        if program.min_stay_months is not None:
            if booking.stay_duration_months < program.min_stay_months:
                return False

        return True

    def _calculate_reward_amounts(
        self,
        *,
        booking_total: Decimal,
        program: ReferralProgram,
    ) -> Tuple[Decimal, Decimal]:
        """
        Calculate reward amounts for referrer and referee based on program.

        Conventions:
        - If program.reward_type == "percentage":
            * referrer_reward_amount and referee_reward_amount are treated
              as percentage values (e.g., 5 means 5% of booking_total).
        - Otherwise:
            * referrer_reward_amount and referee_reward_amount are treated
              as flat amounts in program.currency.
        """
        reward_type = (program.reward_type or "").lower()

        referrer_base = program.referrer_reward_amount or Decimal("0")
        referee_base = program.referee_reward_amount or Decimal("0")

        if reward_type == "percentage":
            referrer_amount = (booking_total * referrer_base) / Decimal("100")
            referee_amount = (booking_total * referee_base) / Decimal("100")
        else:
            # flat amounts
            referrer_amount = referrer_base
            referee_amount = referee_base

        # Ensure non-negative amounts
        if referrer_amount < 0:
            referrer_amount = Decimal("0")
        if referee_amount < 0:
            referee_amount = Decimal("0")

        return referrer_amount, referee_amount

    def _apply_commission_to_referral(
        self,
        *,
        referral: Referral,
        program: ReferralProgram,
        booking: Booking,
        referrer_amount: Decimal,
        referee_amount: Decimal,
    ) -> None:
        """
        Mutate the Referral object with computed commission data and
        flush changes via the repository session.
        """
        now = datetime.now(timezone.utc)

        referral.booking_id = booking.id
        referral.completed_at = now

        referral.referrer_reward_amount = referrer_amount
        referral.referee_reward_amount = referee_amount
        referral.currency = program.currency

        if self.completed_status is not None:
            referral.status = self.completed_status

        if self.earned_reward_status is not None:
            referral.referrer_reward_status = self.earned_reward_status
            referral.referee_reward_status = self.earned_reward_status

        self.referral_repo.session.flush()