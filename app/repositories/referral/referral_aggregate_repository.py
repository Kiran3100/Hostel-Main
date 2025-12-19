# --- File: app/repositories/referral/referral_aggregate_repository.py ---
"""
Referral Aggregate Repository.

Provides aggregated analytics, cross-module reporting, and comprehensive
insights across the referral system.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.referral.referral import Referral
from app.models.referral.referral_code import ReferralCode
from app.models.referral.referral_program import ReferralProgram
from app.models.referral.referral_reward import ReferralReward, RewardPayout
from app.schemas.common.enums import ReferralStatus, RewardStatus

__all__ = ["ReferralAggregateRepository"]


class ReferralAggregateRepository:
    """
    Referral Aggregate Repository.
    
    Provides cross-entity analytics, reporting, and insights across
    the entire referral system.
    """

    def __init__(self, session: AsyncSession):
        """Initialize repository with session."""
        self.session = session

    # ============================================================================
    # DASHBOARD & OVERVIEW
    # ============================================================================

    async def get_system_overview(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Get comprehensive system overview.
        
        Args:
            start_date: Start date filter
            end_date: End date filter
            
        Returns:
            System-wide statistics
        """
        # Programs
        programs_query = select(func.count()).select_from(ReferralProgram).where(
            ReferralProgram.is_deleted == False
        )
        programs_result = await self.session.execute(programs_query)
        total_programs = programs_result.scalar_one()

        active_programs_query = select(func.count()).select_from(ReferralProgram).where(
            and_(
                ReferralProgram.is_active == True,
                ReferralProgram.is_deleted == False,
            )
        )
        active_programs_result = await self.session.execute(active_programs_query)
        active_programs = active_programs_result.scalar_one()

        # Codes
        codes_query = select(func.count()).select_from(ReferralCode).where(
            ReferralCode.is_deleted == False
        )
        codes_result = await self.session.execute(codes_query)
        total_codes = codes_result.scalar_one()

        # Referrals
        referrals_query = select(Referral)
        if start_date:
            referrals_query = referrals_query.where(Referral.created_at >= start_date)
        if end_date:
            referrals_query = referrals_query.where(Referral.created_at <= end_date)

        referrals_result = await self.session.execute(referrals_query)
        referrals = referrals_result.scalars().all()

        total_referrals = len(referrals)
        completed_referrals = sum(
            1 for r in referrals if r.status == ReferralStatus.COMPLETED
        )
        pending_referrals = sum(
            1 for r in referrals if r.status == ReferralStatus.PENDING
        )

        conversion_rate = (
            (completed_referrals / total_referrals * 100)
            if total_referrals > 0
            else 0
        )

        # Rewards
        rewards_query = select(ReferralReward)
        if start_date:
            rewards_query = rewards_query.where(ReferralReward.created_at >= start_date)
        if end_date:
            rewards_query = rewards_query.where(ReferralReward.created_at <= end_date)

        rewards_result = await self.session.execute(rewards_query)
        rewards = rewards_result.scalars().all()

        total_rewards_value = sum(r.net_amount for r in rewards)
        total_paid_rewards = sum(
            r.net_amount for r in rewards if r.status == RewardStatus.PAID
        )
        pending_rewards_value = sum(
            r.net_amount for r in rewards if r.status == RewardStatus.PENDING
        )

        return {
            "programs": {
                "total": total_programs,
                "active": active_programs,
            },
            "codes": {
                "total": total_codes,
            },
            "referrals": {
                "total": total_referrals,
                "completed": completed_referrals,
                "pending": pending_referrals,
                "conversion_rate": round(conversion_rate, 2),
            },
            "rewards": {
                "total_value": float(total_rewards_value),
                "total_paid": float(total_paid_rewards),
                "pending_value": float(pending_rewards_value),
                "count": len(rewards),
            },
        }

    async def get_performance_dashboard(
        self, program_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """
        Get performance dashboard metrics.
        
        Args:
            program_id: Filter by program
            
        Returns:
            Performance metrics
        """
        # Referral metrics
        referrals_query = select(Referral)
        if program_id:
            referrals_query = referrals_query.where(Referral.program_id == program_id)

        referrals_result = await self.session.execute(referrals_query)
        referrals = referrals_result.scalars().all()

        # Calculate metrics
        total_clicks = 0
        total_registrations = 0
        total_bookings = 0

        codes_query = select(ReferralCode)
        if program_id:
            codes_query = codes_query.where(ReferralCode.program_id == program_id)

        codes_result = await self.session.execute(codes_query)
        codes = codes_result.scalars().all()

        for code in codes:
            total_clicks += code.times_clicked
            total_registrations += code.total_registrations
            total_bookings += code.total_bookings

        # Conversion funnel
        click_to_registration = (
            (total_registrations / total_clicks * 100) if total_clicks > 0 else 0
        )
        registration_to_booking = (
            (total_bookings / total_registrations * 100)
            if total_registrations > 0
            else 0
        )
        click_to_booking = (
            (total_bookings / total_clicks * 100) if total_clicks > 0 else 0
        )

        # Revenue metrics
        total_booking_value = sum(
            r.booking_amount or Decimal("0.00") for r in referrals
        )
        total_rewards = sum(r.total_reward_amount for r in referrals)

        return {
            "funnel": {
                "total_clicks": total_clicks,
                "total_registrations": total_registrations,
                "total_bookings": total_bookings,
                "click_to_registration_rate": round(click_to_registration, 2),
                "registration_to_booking_rate": round(registration_to_booking, 2),
                "click_to_booking_rate": round(click_to_booking, 2),
            },
            "revenue": {
                "total_booking_value": float(total_booking_value),
                "total_rewards": float(total_rewards),
                "roi": (
                    round(
                        (float(total_booking_value) / float(total_rewards) * 100),
                        2,
                    )
                    if total_rewards > 0
                    else 0
                ),
            },
        }

    # ============================================================================
    # TREND ANALYSIS
    # ============================================================================

    async def get_referral_trends(
        self,
        days: int = 30,
        program_id: Optional[UUID] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get daily referral trends.
        
        Args:
            days: Number of days to analyze
            program_id: Filter by program
            
        Returns:
            Daily trend data
        """
        start_date = datetime.utcnow() - timedelta(days=days)

        query = select(Referral).where(Referral.created_at >= start_date)

        if program_id:
            query = query.where(Referral.program_id == program_id)

        result = await self.session.execute(query)
        referrals = result.scalars().all()

        # Group by date
        trends = {}
        for referral in referrals:
            date_key = referral.created_at.date().isoformat()

            if date_key not in trends:
                trends[date_key] = {
                    "date": date_key,
                    "total": 0,
                    "completed": 0,
                    "pending": 0,
                }

            trends[date_key]["total"] += 1

            if referral.status == ReferralStatus.COMPLETED:
                trends[date_key]["completed"] += 1
            elif referral.status == ReferralStatus.PENDING:
                trends[date_key]["pending"] += 1

        return sorted(trends.values(), key=lambda x: x["date"])

    async def get_conversion_trends(
        self,
        days: int = 30,
        program_id: Optional[UUID] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get conversion rate trends over time.
        
        Args:
            days: Number of days to analyze
            program_id: Filter by program
            
        Returns:
            Conversion trend data
        """
        start_date = datetime.utcnow() - timedelta(days=days)

        query = select(Referral).where(Referral.created_at >= start_date)

        if program_id:
            query = query.where(Referral.program_id == program_id)

        result = await self.session.execute(query)
        referrals = result.scalars().all()

        # Group by week
        trends = {}
        for referral in referrals:
            week_key = referral.created_at.strftime("%Y-W%W")

            if week_key not in trends:
                trends[week_key] = {
                    "week": week_key,
                    "total": 0,
                    "completed": 0,
                    "conversion_rate": 0,
                }

            trends[week_key]["total"] += 1

            if referral.status == ReferralStatus.COMPLETED:
                trends[week_key]["completed"] += 1

        # Calculate conversion rates
        for trend in trends.values():
            if trend["total"] > 0:
                trend["conversion_rate"] = round(
                    (trend["completed"] / trend["total"] * 100), 2
                )

        return sorted(trends.values(), key=lambda x: x["week"])

    # ============================================================================
    # COMPARATIVE ANALYSIS
    # ============================================================================

    async def compare_programs(
        self,
        program_ids: Optional[List[UUID]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Compare performance across programs.
        
        Args:
            program_ids: Specific programs to compare (all if None)
            
        Returns:
            Comparative metrics
        """
        programs_query = select(ReferralProgram).where(
            ReferralProgram.is_deleted == False
        )

        if program_ids:
            programs_query = programs_query.where(
                ReferralProgram.id.in_(program_ids)
            )

        programs_result = await self.session.execute(programs_query)
        programs = programs_result.scalars().all()

        comparison = []
        for program in programs:
            # Get referrals for this program
            referrals_query = select(Referral).where(
                Referral.program_id == program.id
            )
            referrals_result = await self.session.execute(referrals_query)
            referrals = referrals_result.scalars().all()

            # Calculate metrics
            total_booking_value = sum(
                r.booking_amount or Decimal("0.00") for r in referrals
            )
            total_rewards = sum(r.total_reward_amount for r in referrals)

            avg_conversion_time = [
                r.conversion_time_days
                for r in referrals
                if r.conversion_time_days is not None
            ]
            avg_conversion_time = (
                sum(avg_conversion_time) / len(avg_conversion_time)
                if avg_conversion_time
                else 0
            )

            comparison.append({
                "program_id": str(program.id),
                "program_name": program.program_name,
                "total_referrals": program.total_referrals,
                "successful_referrals": program.successful_referrals,
                "conversion_rate": float(program.conversion_rate),
                "total_booking_value": float(total_booking_value),
                "total_rewards": float(total_rewards),
                "avg_conversion_time_days": avg_conversion_time,
                "roi": (
                    round((float(total_booking_value) / float(total_rewards)), 2)
                    if total_rewards > 0
                    else 0
                ),
            })

        return sorted(
            comparison,
            key=lambda x: x["successful_referrals"],
            reverse=True,
        )

    # ============================================================================
    # USER INSIGHTS
    # ============================================================================

    async def get_top_referrers_leaderboard(
        self,
        limit: int = 20,
        program_id: Optional[UUID] = None,
        timeframe_days: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get top referrers leaderboard.
        
        Args:
            limit: Maximum results
            program_id: Filter by program
            timeframe_days: Days to look back
            
        Returns:
            Leaderboard data
        """
        query = select(
            Referral.referrer_id,
            func.count(Referral.id).label("total_referrals"),
            func.sum(
                func.cast(
                    Referral.status == ReferralStatus.COMPLETED,
                    Decimal,
                )
            ).label("successful_referrals"),
            func.sum(Referral.booking_amount).label("total_revenue"),
            func.sum(Referral.referrer_reward_amount).label("total_earnings"),
        ).group_by(Referral.referrer_id)

        if program_id:
            query = query.where(Referral.program_id == program_id)

        if timeframe_days:
            start_date = datetime.utcnow() - timedelta(days=timeframe_days)
            query = query.where(Referral.created_at >= start_date)

        query = query.order_by(
            func.sum(
                func.cast(
                    Referral.status == ReferralStatus.COMPLETED,
                    Decimal,
                )
            ).desc()
        ).limit(limit)

        result = await self.session.execute(query)
        rows = result.all()

        leaderboard = []
        rank = 1
        for row in rows:
            conversion_rate = (
                (row.successful_referrals / row.total_referrals * 100)
                if row.total_referrals > 0
                else 0
            )

            leaderboard.append({
                "rank": rank,
                "referrer_id": str(row.referrer_id),
                "total_referrals": row.total_referrals,
                "successful_referrals": row.successful_referrals or 0,
                "conversion_rate": round(conversion_rate, 2),
                "total_revenue": float(row.total_revenue or 0),
                "total_earnings": float(row.total_earnings or 0),
            })
            rank += 1

        return leaderboard

    async def get_user_lifetime_value(
        self, user_id: UUID
    ) -> Dict[str, Any]:
        """
        Calculate lifetime value for a referrer.
        
        Args:
            user_id: User ID
            
        Returns:
            Lifetime value metrics
        """
        # Get all referrals
        referrals_query = select(Referral).where(Referral.referrer_id == user_id)
        referrals_result = await self.session.execute(referrals_query)
        referrals = referrals_result.scalars().all()

        # Get all rewards
        rewards_query = select(ReferralReward).where(
            and_(
                ReferralReward.user_id == user_id,
                ReferralReward.recipient_type == "referrer",
            )
        )
        rewards_result = await self.session.execute(rewards_query)
        rewards = rewards_result.scalars().all()

        # Calculate metrics
        total_referrals = len(referrals)
        successful_referrals = sum(
            1 for r in referrals if r.status == ReferralStatus.COMPLETED
        )
        total_revenue_generated = sum(
            r.booking_amount or Decimal("0.00") for r in referrals
        )
        total_earnings = sum(r.net_amount for r in rewards)
        total_paid = sum(
            r.net_amount for r in rewards if r.status == RewardStatus.PAID
        )
        total_pending = sum(
            r.net_amount for r in rewards if r.status == RewardStatus.PENDING
        )

        # Calculate engagement metrics
        codes_query = select(ReferralCode).where(ReferralCode.user_id == user_id)
        codes_result = await self.session.execute(codes_query)
        codes = codes_result.scalars().all()

        total_shares = sum(c.times_shared for c in codes)
        total_clicks = sum(c.times_clicked for c in codes)

        # Time-based metrics
        if referrals:
            first_referral = min(r.created_at for r in referrals)
            days_active = (datetime.utcnow() - first_referral).days
            avg_referrals_per_month = (
                (total_referrals / (days_active / 30))
                if days_active > 0
                else 0
            )
        else:
            days_active = 0
            avg_referrals_per_month = 0

        return {
            "referrals": {
                "total": total_referrals,
                "successful": successful_referrals,
                "conversion_rate": (
                    round((successful_referrals / total_referrals * 100), 2)
                    if total_referrals > 0
                    else 0
                ),
            },
            "revenue": {
                "total_generated": float(total_revenue_generated),
                "total_earnings": float(total_earnings),
                "total_paid": float(total_paid),
                "total_pending": float(total_pending),
            },
            "engagement": {
                "total_shares": total_shares,
                "total_clicks": total_clicks,
                "days_active": days_active,
                "avg_referrals_per_month": round(avg_referrals_per_month, 2),
            },
        }

    # ============================================================================
    # FINANCIAL RECONCILIATION
    # ============================================================================

    async def get_financial_summary(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Get financial summary for reconciliation.
        
        Args:
            start_date: Start date filter
            end_date: End date filter
            
        Returns:
            Financial summary
        """
        # Rewards
        rewards_query = select(ReferralReward)
        if start_date:
            rewards_query = rewards_query.where(ReferralReward.created_at >= start_date)
        if end_date:
            rewards_query = rewards_query.where(ReferralReward.created_at <= end_date)

        rewards_result = await self.session.execute(rewards_query)
        rewards = rewards_result.scalars().all()

        total_rewards_value = sum(r.total_amount for r in rewards)
        total_deductions = sum(r.tax_deduction + r.processing_fee for r in rewards)
        net_rewards = sum(r.net_amount for r in rewards)

        # By status
        pending_rewards = sum(
            r.net_amount for r in rewards if r.status == RewardStatus.PENDING
        )
        approved_rewards = sum(
            r.net_amount for r in rewards if r.status == RewardStatus.APPROVED
        )
        paid_rewards = sum(
            r.net_amount for r in rewards if r.status == RewardStatus.PAID
        )

        # Payouts
        payouts_query = select(RewardPayout)
        if start_date:
            payouts_query = payouts_query.where(RewardPayout.requested_at >= start_date)
        if end_date:
            payouts_query = payouts_query.where(RewardPayout.requested_at <= end_date)

        payouts_result = await self.session.execute(payouts_query)
        payouts = payouts_result.scalars().all()

        total_payout_requests = sum(p.amount for p in payouts)
        total_payout_fees = sum(p.processing_fee + p.tax_deduction for p in payouts)
        net_payouts = sum(p.net_amount for p in payouts)
        completed_payouts = sum(
            p.net_amount for p in payouts if p.status == RewardStatus.PAID
        )

        return {
            "rewards": {
                "total_value": float(total_rewards_value),
                "total_deductions": float(total_deductions),
                "net_value": float(net_rewards),
                "pending": float(pending_rewards),
                "approved": float(approved_rewards),
                "paid": float(paid_rewards),
            },
            "payouts": {
                "total_requested": float(total_payout_requests),
                "total_fees": float(total_payout_fees),
                "net_payouts": float(net_payouts),
                "completed": float(completed_payouts),
            },
            "reconciliation": {
                "total_liability": float(pending_rewards + approved_rewards),
                "total_paid": float(paid_rewards),
            },
        }


