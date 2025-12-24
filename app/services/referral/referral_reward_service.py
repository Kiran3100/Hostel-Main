"""
Referral Reward Service

Manages referral rewards and payouts:
- Reward configuration
- Reward tracking (per user)
- Reward calculation
- Payout requests and history
- Reward summary analytics
"""

from __future__ import annotations

from typing import Optional
from uuid import UUID
from datetime import datetime

from sqlalchemy.orm import Session

from app.repositories.referral import (
    ReferralRewardRepository,
    RewardPayoutRepository,
    RewardTrackingRepository,
    ReferralAggregateRepository,
)
from app.schemas.common import DateRangeFilter
from app.schemas.referral import (
    RewardConfig,
    RewardTracking,
    RewardCalculation,
    PayoutRequest,
    PayoutRequestResponse,
    PayoutHistory,
    RewardSummary,
)
from app.core.exceptions import ValidationException, BusinessLogicException


class ReferralRewardService:
    """
    High-level orchestration of referral rewards and payouts.
    """

    def __init__(
        self,
        reward_repo: ReferralRewardRepository,
        payout_repo: RewardPayoutRepository,
        tracking_repo: RewardTrackingRepository,
        aggregate_repo: ReferralAggregateRepository,
    ) -> None:
        self.reward_repo = reward_repo
        self.payout_repo = payout_repo
        self.tracking_repo = tracking_repo
        self.aggregate_repo = aggregate_repo

    # -------------------------------------------------------------------------
    # Configuration
    # -------------------------------------------------------------------------

    def get_reward_config(
        self,
        db: Session,
        program_id: Optional[UUID] = None,
    ) -> RewardConfig:
        """
        Retrieve reward configuration (global or per program).
        """
        obj = self.reward_repo.get_reward_config(db, program_id=program_id)
        if not obj:
            # Provide safe defaults if no config found
            return RewardConfig(
                min_payout_amount="100",
                max_payout_amount="100000",
                payout_methods=[],
                auto_approve_payouts=False,
                payout_processing_time_days=7,
                payout_fee_percentage="0",
                min_payout_fee="0",
                max_payout_fee="0",
                max_payouts_per_month=10,
                min_days_between_payouts=7,
                tax_deduction_applicable=False,
                tax_deduction_percentage="0",
            )
        return RewardConfig.model_validate(obj)

    # -------------------------------------------------------------------------
    # Reward calculation & tracking
    # -------------------------------------------------------------------------

    def calculate_reward_for_referral(
        self,
        db: Session,
        referral_id: UUID,
    ) -> RewardCalculation:
        """
        Calculate reward for a single referral.

        Delegates scoring and thresholds to repository logic.
        """
        data = self.reward_repo.calculate_reward_for_referral(db, referral_id)
        if not data:
            raise ValidationException("Unable to calculate reward for referral")
        return RewardCalculation.model_validate(data)

    def apply_reward_for_referral(
        self,
        db: Session,
        referral_id: UUID,
    ) -> RewardTracking:
        """
        Apply (book) reward for a referral and update tracking balance.
        """
        calculation = self.calculate_reward_for_referral(db, referral_id)
        tracking_obj = self.tracking_repo.apply_calculated_reward(
            db=db,
            referral_id=calculation.referral_id,
            program_id=calculation.program_id,
            referrer_net_amount=calculation.referrer_net_amount,
            referee_net_amount=calculation.referee_net_amount,
        )
        return RewardTracking.model_validate(tracking_obj)

    def get_reward_tracking_for_user(
        self,
        db: Session,
        user_id: UUID,
    ) -> RewardTracking:
        obj = self.tracking_repo.get_or_create_for_user(db, user_id)
        return RewardTracking.model_validate(obj)

    # -------------------------------------------------------------------------
    # Payouts
    # -------------------------------------------------------------------------

    def create_payout_request(
        self,
        db: Session,
        user_id: UUID,
        request: PayoutRequest,
    ) -> PayoutRequestResponse:
        """
        Create a payout request against a user's available reward balance.

        Ensures the requested amount is ≤ available_for_payout.
        """
        tracking = self.tracking_repo.get_or_create_for_user(db, user_id)
        if request.amount > tracking.available_for_payout:
            raise BusinessLogicException("Requested amount exceeds available rewards")

        payload = request.model_dump(exclude_none=True)
        payload["user_id"] = user_id

        payout_obj = self.payout_repo.create_payout_request(db, payload)

        # Optionally lock/reduce available_for_payout immediately
        self.tracking_repo.reserve_for_payout(
            db=db,
            user_id=user_id,
            amount=request.amount,
        )

        return PayoutRequestResponse.model_validate(payout_obj)

    def approve_or_reject_payout(
        self,
        db: Session,
        payout_request_id: UUID,
        approved: bool,
        admin_id: UUID,
        notes: Optional[str] = None,
    ) -> PayoutRequestResponse:
        """
        Approve or reject a payout request.

        On approval:
        - Mark payout request status
        - Adjust tracking balances as paid
        On rejection:
        - Release reserved amounts back to available_for_payout
        """
        payout = self.payout_repo.get_by_id(db, payout_request_id)
        if not payout:
            raise ValidationException("Payout request not found")

        if approved:
            updated = self.payout_repo.mark_approved(
                db=db,
                payout=payout,
                approved_by=admin_id,
                notes=notes,
            )
            # Move reserved to paid
            self.tracking_repo.mark_payout_completed(
                db=db,
                user_id=payout.user_id,
                amount=payout.amount,
            )
        else:
            updated = self.payout_repo.mark_rejected(
                db=db,
                payout=payout,
                rejected_by=admin_id,
                notes=notes,
            )
            # Release reserved
            self.tracking_repo.release_reserved_amount(
                db=db,
                user_id=payout.user_id,
                amount=payout.amount,
            )

        return PayoutRequestResponse.model_validate(updated)

    def get_payout_history_for_user(
        self,
        db: Session,
        user_id: UUID,
    ) -> PayoutHistory:
        objs = self.payout_repo.get_history_for_user(db, user_id)
        return PayoutHistory(
            user_id=user_id,
            total_payouts=len(objs),
            total_amount_paid=str(
                sum(o.amount for o in objs)
            ),  # actual schema expects string/Decimal
            payouts=[PayoutRequestResponse.model_validate(o) for o in objs],
        )

    # -------------------------------------------------------------------------
    # Reward summary
    # -------------------------------------------------------------------------

    def get_reward_summary(
        self,
        db: Session,
        period: DateRangeFilter,
        user_id: Optional[UUID] = None,
        program_id: Optional[UUID] = None,
    ) -> RewardSummary:
        """
        Get aggregated reward summary over a period, optionally for a user or program.
        """
        data = self.aggregate_repo.get_reward_summary(
            db=db,
            start_date=period.start_date,
            end_date=period.end_date,
            user_id=user_id,
            program_id=program_id,
        )
        if not data:
            # Provide an empty summary
            return RewardSummary(
                period_start=period.start_date,
                period_end=period.end_date,
                user_id=user_id,
                program_id=program_id,
                total_rewards_earned="0",
                total_rewards_approved="0",
                total_rewards_paid="0",
                pending_rewards="0",
                cancelled_rewards="0",
                rewards_by_status={},
                rewards_by_program={},
                rewards_by_month={},
                payout_request_count=0,
                successful_payouts=0,
                failed_payouts=0,
                average_reward_amount="0",
                average_payout_amount="0",
                currency="INR",
            )
        return RewardSummary.model_validate(data)