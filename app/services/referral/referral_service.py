"""
Referral Service

Core referral lifecycle:
- Create/update referrals
- Record conversions (booking → referral success)
- Retrieve referrals (detail/list)
- Referral stats & analytics
- Leaderboards & timelines
"""

from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.referral import ReferralRepository, ReferralAggregateRepository
from app.schemas.common import DateRangeFilter
from app.schemas.referral import (
    ReferralCreate,
    ReferralUpdate,
    ReferralConversion,
    ReferralResponse,
    ReferralDetail,
    ReferralStats,
    ReferralLeaderboard,
    ReferralAnalytics,
    ReferralTimeline,
)
from app.core.exceptions import ValidationException


class ReferralService:
    """
    High-level orchestration for referrals.

    Delegates persistence to ReferralRepository and analytics to ReferralAggregateRepository.
    """

    def __init__(
        self,
        referral_repo: ReferralRepository,
        aggregate_repo: ReferralAggregateRepository,
    ) -> None:
        self.referral_repo = referral_repo
        self.aggregate_repo = aggregate_repo

    # -------------------------------------------------------------------------
    # CRUD
    # -------------------------------------------------------------------------

    def create_referral(
        self,
        db: Session,
        request: ReferralCreate,
    ) -> ReferralResponse:
        obj = self.referral_repo.create(
            db,
            data=request.model_dump(exclude_none=True),
        )
        return ReferralResponse.model_validate(obj)

    def update_referral(
        self,
        db: Session,
        referral_id: UUID,
        request: ReferralUpdate,
    ) -> ReferralResponse:
        referral = self.referral_repo.get_by_id(db, referral_id)
        if not referral:
            raise ValidationException("Referral not found")

        updated = self.referral_repo.update(
            db,
            referral,
            data=request.model_dump(exclude_none=True),
        )
        return ReferralResponse.model_validate(updated)

    # -------------------------------------------------------------------------
    # Conversions
    # -------------------------------------------------------------------------

    def record_conversion(
        self,
        db: Session,
        request: ReferralConversion,
    ) -> ReferralDetail:
        """
        Mark a referral as converted and update reward fields.

        The repository should handle status transitions, idempotency, etc.
        """
        referral = self.referral_repo.get_by_id(db, request.referral_id)
        if not referral:
            raise ValidationException("Referral not found")

        updated = self.referral_repo.record_conversion(
            db=db,
            referral=referral,
            booking_id=request.booking_id,
            booking_amount=request.booking_amount,
            stay_duration_months=request.stay_duration_months,
            conversion_date=request.conversion_date,
        )

        full = self.referral_repo.get_full_referral(db, updated.id)
        return ReferralDetail.model_validate(full)

    # -------------------------------------------------------------------------
    # Retrieval & listing
    # -------------------------------------------------------------------------

    def get_referral(
        self,
        db: Session,
        referral_id: UUID,
    ) -> ReferralDetail:
        obj = self.referral_repo.get_full_referral(db, referral_id)
        if not obj:
            raise ValidationException("Referral not found")
        return ReferralDetail.model_validate(obj)

    def list_referrals_for_program(
        self,
        db: Session,
        program_id: UUID,
        page: int = 1,
        page_size: int = 50,
    ) -> List[ReferralResponse]:
        objs = self.referral_repo.get_by_program(
            db=db,
            program_id=program_id,
            page=page,
            page_size=page_size,
        )
        return [ReferralResponse.model_validate(o) for o in objs]

    def list_referrals_for_user(
        self,
        db: Session,
        user_id: UUID,
        page: int = 1,
        page_size: int = 50,
    ) -> List[ReferralResponse]:
        objs = self.referral_repo.get_by_referrer(
            db=db,
            user_id=user_id,
            page=page,
            page_size=page_size,
        )
        return [ReferralResponse.model_validate(o) for o in objs]

    # -------------------------------------------------------------------------
    # Stats & analytics
    # -------------------------------------------------------------------------

    def get_user_stats(
        self,
        db: Session,
        user_id: UUID,
        period: Optional[DateRangeFilter] = None,
    ) -> ReferralStats:
        data = self.aggregate_repo.get_user_referral_stats(
            db=db,
            user_id=user_id,
            start_date=period.start_date if period else None,
            end_date=period.end_date if period else None,
        )
        if not data:
            # Provide default empty stats
            return ReferralStats(
                user_id=user_id,
                total_referrals=0,
                successful_referrals=0,
                pending_referrals=0,
                failed_referrals=0,
                cancelled_referrals=0,
                conversion_rate=0.0,
                average_conversion_time_days=None,
                total_rewards_earned="0",
                total_rewards_paid="0",
                pending_rewards="0",
                currency="INR",
                referrals_by_program={},
                rewards_by_program={},
                this_month_referrals=0,
                last_month_referrals=0,
                user_rank=None,
                total_referrers=None,
                last_referral_date=None,
                most_active_program=None,
            )
        return ReferralStats.model_validate(data)

    def get_leaderboard(
        self,
        db: Session,
        program_id: Optional[UUID],
        period: DateRangeFilter,
    ) -> ReferralLeaderboard:
        data = self.aggregate_repo.get_leaderboard(
            db=db,
            program_id=program_id,
            start_date=period.start_date,
            end_date=period.end_date,
        )
        if not data:
            # Default empty leaderboard
            return ReferralLeaderboard(
                period="custom",
                total_users=0,
                top_referrers=[],
                generated_at=datetime.utcnow(),
            )
        return ReferralLeaderboard.model_validate(data)  # type: ignore[name-defined]

    def get_referral_analytics(
        self,
        db: Session,
        period: DateRangeFilter,
        program_id: Optional[UUID] = None,
    ) -> ReferralAnalytics:
        data = self.aggregate_repo.get_referral_analytics(
            db=db,
            program_id=program_id,
            start_date=period.start_date,
            end_date=period.end_date,
        )
        if not data:
            raise ValidationException("No referral analytics data available")
        return ReferralAnalytics.model_validate(data)

    def get_referral_timeline(
        self,
        db: Session,
        referral_id: UUID,
    ) -> ReferralTimeline:
        data = self.aggregate_repo.get_referral_timeline(db, referral_id)
        if not data:
            raise ValidationException("Referral not found or no timeline data")
        return ReferralTimeline.model_validate(data)