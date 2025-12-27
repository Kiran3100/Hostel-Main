# --- File: app/repositories/referral/referral_reward_repository.py ---
"""
Referral Reward Repository.

Manages reward tracking, payout processing, and financial reconciliation.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.models.referral.referral_reward import ReferralReward, RewardPayout
from app.models.referral.referral import Referral
from app.models.user.user import User
from app.repositories.base.base_repository import BaseRepository
from app.schemas.common.enums import RewardStatus, PaymentMethod
from app.core1.exceptions import (
    EntityNotFoundError,
    ValidationError,
    BusinessLogicError,
)

__all__ = ["ReferralRewardRepository"]


class ReferralRewardRepository(BaseRepository[ReferralReward]):
    """
    Referral Reward Repository.
    
    Provides comprehensive reward management with payout processing,
    financial tracking, and reconciliation.
    """

    def __init__(self, session: AsyncSession):
        """Initialize repository with session."""
        super().__init__(ReferralReward, session)

    # ============================================================================
    # CORE CRUD OPERATIONS - REWARDS
    # ============================================================================

    async def create_reward(
        self,
        referral_id: UUID,
        user_id: UUID,
        recipient_type: str,
        base_amount: Decimal,
        bonus_amount: Decimal = Decimal("0.00"),
        currency: str = "INR",
        tax_deduction: Decimal = Decimal("0.00"),
        processing_fee: Decimal = Decimal("0.00"),
        metadata: Optional[Dict[str, Any]] = None,
        created_by: Optional[UUID] = None,
    ) -> ReferralReward:
        """
        Create a new reward entry.
        
        Args:
            referral_id: Associated referral ID
            user_id: User receiving reward
            recipient_type: 'referrer' or 'referee'
            base_amount: Base reward amount
            bonus_amount: Bonus amount
            currency: Currency code
            tax_deduction: Tax deduction amount
            processing_fee: Processing fee
            metadata: Additional metadata
            created_by: Creator user ID
            
        Returns:
            Created reward
            
        Raises:
            ValidationError: If validation fails
        """
        if recipient_type not in ["referrer", "referee"]:
            raise ValidationError(
                "Recipient type must be 'referrer' or 'referee'"
            )

        total_amount = base_amount + bonus_amount
        net_amount = total_amount - tax_deduction - processing_fee

        if net_amount < 0:
            raise ValidationError("Net amount cannot be negative")

        reward = ReferralReward(
            referral_id=referral_id,
            user_id=user_id,
            recipient_type=recipient_type,
            base_amount=base_amount,
            bonus_amount=bonus_amount,
            total_amount=total_amount,
            currency=currency,
            tax_deduction=tax_deduction,
            processing_fee=processing_fee,
            net_amount=net_amount,
            status=RewardStatus.PENDING,
            metadata=metadata,
            created_by=created_by,
        )

        self.session.add(reward)
        await self.session.flush()
        
        return reward

    async def get_reward_by_id(
        self,
        reward_id: UUID,
        include_relationships: bool = True,
    ) -> Optional[ReferralReward]:
        """
        Get reward by ID with optional relationships.
        
        Args:
            reward_id: Reward ID
            include_relationships: Include related entities
            
        Returns:
            Reward if found, None otherwise
        """
        query = select(ReferralReward).where(ReferralReward.id == reward_id)

        if include_relationships:
            query = query.options(
                joinedload(ReferralReward.referral),
                joinedload(ReferralReward.user),
                joinedload(ReferralReward.approver),
                joinedload(ReferralReward.payer),
            )

        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    # ============================================================================
    # REWARD LOOKUP OPERATIONS
    # ============================================================================

    async def find_by_user(
        self,
        user_id: UUID,
        status: Optional[RewardStatus] = None,
        recipient_type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[List[ReferralReward], int]:
        """
        Find rewards by user.
        
        Args:
            user_id: User ID
            status: Filter by status
            recipient_type: Filter by recipient type
            limit: Maximum results
            offset: Results offset
            
        Returns:
            Tuple of (rewards, total_count)
        """
        query = select(ReferralReward).where(ReferralReward.user_id == user_id)

        if status:
            query = query.where(ReferralReward.status == status)

        if recipient_type:
            query = query.where(ReferralReward.recipient_type == recipient_type)

        # Count query
        count_query = select(func.count()).select_from(query.subquery())
        count_result = await self.session.execute(count_query)
        total = count_result.scalar_one()

        # Data query
        query = (
            query.order_by(ReferralReward.created_at.desc())
            .limit(limit)
            .offset(offset)
            .options(joinedload(ReferralReward.referral))
        )

        result = await self.session.execute(query)
        rewards = result.scalars().all()

        return list(rewards), total

    async def find_by_referral(
        self, referral_id: UUID
    ) -> List[ReferralReward]:
        """
        Find all rewards for a referral.
        
        Args:
            referral_id: Referral ID
            
        Returns:
            List of rewards
        """
        query = (
            select(ReferralReward)
            .where(ReferralReward.referral_id == referral_id)
            .options(joinedload(ReferralReward.user))
        )

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def find_pending_rewards(
        self,
        days_old: Optional[int] = None,
        limit: int = 100,
    ) -> List[ReferralReward]:
        """
        Find pending rewards.
        
        Args:
            days_old: Filter by minimum age in days
            limit: Maximum results
            
        Returns:
            List of pending rewards
        """
        query = select(ReferralReward).where(
            ReferralReward.status == RewardStatus.PENDING
        )

        if days_old:
            cutoff_date = datetime.utcnow() - timedelta(days=days_old)
            query = query.where(ReferralReward.created_at <= cutoff_date)

        query = (
            query.order_by(ReferralReward.created_at.asc())
            .limit(limit)
            .options(
                joinedload(ReferralReward.user),
                joinedload(ReferralReward.referral),
            )
        )

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def find_approved_unpaid_rewards(
        self, limit: int = 100
    ) -> List[ReferralReward]:
        """
        Find approved but unpaid rewards.
        
        Args:
            limit: Maximum results
            
        Returns:
            List of approved rewards
        """
        query = (
            select(ReferralReward)
            .where(ReferralReward.status == RewardStatus.APPROVED)
            .order_by(ReferralReward.approved_at.asc())
            .limit(limit)
            .options(
                joinedload(ReferralReward.user),
                joinedload(ReferralReward.referral),
            )
        )

        result = await self.session.execute(query)
        return list(result.scalars().all())

    # ============================================================================
    # REWARD STATUS MANAGEMENT
    # ============================================================================

    async def approve_reward(
        self,
        reward_id: UUID,
        approved_by: UUID,
    ) -> ReferralReward:
        """
        Approve a reward.
        
        Args:
            reward_id: Reward ID
            approved_by: Approver user ID
            
        Returns:
            Approved reward
            
        Raises:
            EntityNotFoundError: If reward not found
            BusinessLogicError: If reward not in pending status
        """
        reward = await self.get_reward_by_id(reward_id)
        if not reward:
            raise EntityNotFoundError(f"Reward {reward_id} not found")

        if reward.status != RewardStatus.PENDING:
            raise BusinessLogicError(
                f"Cannot approve reward in {reward.status.value} status"
            )

        reward.approve(approved_by=approved_by)
        await self.session.flush()
        return reward

    async def reject_reward(
        self,
        reward_id: UUID,
        rejected_by: UUID,
        reason: str,
    ) -> ReferralReward:
        """
        Reject a reward.
        
        Args:
            reward_id: Reward ID
            rejected_by: Rejector user ID
            reason: Rejection reason
            
        Returns:
            Rejected reward
        """
        reward = await self.get_reward_by_id(reward_id)
        if not reward:
            raise EntityNotFoundError(f"Reward {reward_id} not found")

        if reward.status not in [RewardStatus.PENDING, RewardStatus.APPROVED]:
            raise BusinessLogicError(
                f"Cannot reject reward in {reward.status.value} status"
            )

        reward.reject(rejected_by=rejected_by, reason=reason)
        await self.session.flush()
        return reward

    async def mark_reward_paid(
        self,
        reward_id: UUID,
        paid_by: UUID,
        transaction_id: str,
        payment_method: str,
    ) -> ReferralReward:
        """
        Mark reward as paid.
        
        Args:
            reward_id: Reward ID
            paid_by: Payer user ID
            transaction_id: Transaction ID
            payment_method: Payment method used
            
        Returns:
            Updated reward
        """
        reward = await self.get_reward_by_id(reward_id)
        if not reward:
            raise EntityNotFoundError(f"Reward {reward_id} not found")

        if reward.status != RewardStatus.APPROVED:
            raise BusinessLogicError(
                "Only approved rewards can be marked as paid"
            )

        reward.mark_paid(
            paid_by=paid_by,
            transaction_id=transaction_id,
            payment_method=payment_method,
        )

        await self.session.flush()
        return reward

    async def cancel_reward(
        self,
        reward_id: UUID,
        reason: Optional[str] = None,
    ) -> ReferralReward:
        """
        Cancel a reward.
        
        Args:
            reward_id: Reward ID
            reason: Cancellation reason
            
        Returns:
            Cancelled reward
        """
        reward = await self.get_reward_by_id(reward_id)
        if not reward:
            raise EntityNotFoundError(f"Reward {reward_id} not found")

        reward.cancel(reason=reason)
        await self.session.flush()
        return reward

    async def bulk_approve_rewards(
        self,
        reward_ids: List[UUID],
        approved_by: UUID,
    ) -> int:
        """
        Bulk approve multiple rewards.
        
        Args:
            reward_ids: List of reward IDs
            approved_by: Approver user ID
            
        Returns:
            Number of rewards approved
        """
        count = 0
        for reward_id in reward_ids:
            try:
                await self.approve_reward(reward_id, approved_by)
                count += 1
            except (EntityNotFoundError, BusinessLogicError):
                continue

        return count

    # ============================================================================
    # PAYOUT OPERATIONS
    # ============================================================================

    async def create_payout_request(
        self,
        user_id: UUID,
        amount: Decimal,
        payout_method: PaymentMethod,
        payout_details: Dict[str, Any],
        currency: str = "INR",
        processing_fee: Decimal = Decimal("0.00"),
        tax_deduction: Decimal = Decimal("0.00"),
        urgent_payout: bool = False,
        notes: Optional[str] = None,
    ) -> RewardPayout:
        """
        Create a payout request.
        
        Args:
            user_id: User requesting payout
            amount: Requested amount
            payout_method: Payment method
            payout_details: Payment details
            currency: Currency code
            processing_fee: Processing fee
            tax_deduction: Tax deduction
            urgent_payout: Urgent flag
            notes: User notes
            
        Returns:
            Created payout request
        """
        net_amount = amount - processing_fee - tax_deduction

        if net_amount <= 0:
            raise ValidationError("Net payout amount must be positive")

        payout = RewardPayout(
            user_id=user_id,
            amount=amount,
            processing_fee=processing_fee,
            tax_deduction=tax_deduction,
            net_amount=net_amount,
            currency=currency,
            payout_method=payout_method,
            payout_details=payout_details,
            urgent_payout=urgent_payout,
            notes=notes,
            status=RewardStatus.PENDING,
        )

        self.session.add(payout)
        await self.session.flush()
        
        return payout

    async def get_payout_by_id(
        self, payout_id: UUID
    ) -> Optional[RewardPayout]:
        """
        Get payout request by ID.
        
        Args:
            payout_id: Payout ID
            
        Returns:
            Payout if found, None otherwise
        """
        query = (
            select(RewardPayout)
            .where(RewardPayout.id == payout_id)
            .options(
                joinedload(RewardPayout.user),
                joinedload(RewardPayout.approver),
                joinedload(RewardPayout.processor),
            )
        )

        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def find_payouts_by_user(
        self,
        user_id: UUID,
        status: Optional[RewardStatus] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[List[RewardPayout], int]:
        """
        Find payout requests by user.
        
        Args:
            user_id: User ID
            status: Filter by status
            limit: Maximum results
            offset: Results offset
            
        Returns:
            Tuple of (payouts, total_count)
        """
        query = select(RewardPayout).where(RewardPayout.user_id == user_id)

        if status:
            query = query.where(RewardPayout.status == status)

        # Count query
        count_query = select(func.count()).select_from(query.subquery())
        count_result = await self.session.execute(count_query)
        total = count_result.scalar_one()

        # Data query
        query = (
            query.order_by(RewardPayout.requested_at.desc())
            .limit(limit)
            .offset(offset)
        )

        result = await self.session.execute(query)
        payouts = result.scalars().all()

        return list(payouts), total

    async def find_pending_payouts(
        self,
        urgent_only: bool = False,
        limit: int = 100,
    ) -> List[RewardPayout]:
        """
        Find pending payout requests.
        
        Args:
            urgent_only: Only urgent requests
            limit: Maximum results
            
        Returns:
            List of pending payouts
        """
        query = select(RewardPayout).where(
            RewardPayout.status == RewardStatus.PENDING
        )

        if urgent_only:
            query = query.where(RewardPayout.urgent_payout == True)

        query = (
            query.order_by(
                RewardPayout.urgent_payout.desc(),
                RewardPayout.requested_at.asc(),
            )
            .limit(limit)
            .options(joinedload(RewardPayout.user))
        )

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def approve_payout(
        self,
        payout_id: UUID,
        approved_by: UUID,
        estimated_days: int = 7,
    ) -> RewardPayout:
        """
        Approve payout request.
        
        Args:
            payout_id: Payout ID
            approved_by: Approver user ID
            estimated_days: Estimated completion days
            
        Returns:
            Approved payout
        """
        payout = await self.get_payout_by_id(payout_id)
        if not payout:
            raise EntityNotFoundError(f"Payout {payout_id} not found")

        if not payout.is_pending:
            raise BusinessLogicError(
                f"Cannot approve payout in {payout.status.value} status"
            )

        payout.approve(approved_by=approved_by, estimated_days=estimated_days)
        await self.session.flush()
        return payout

    async def process_payout(
        self,
        payout_id: UUID,
        processed_by: UUID,
    ) -> RewardPayout:
        """
        Mark payout as processing.
        
        Args:
            payout_id: Payout ID
            processed_by: Processor user ID
            
        Returns:
            Updated payout
        """
        payout = await self.get_payout_by_id(payout_id)
        if not payout:
            raise EntityNotFoundError(f"Payout {payout_id} not found")

        if payout.status != RewardStatus.APPROVED:
            raise BusinessLogicError(
                "Only approved payouts can be processed"
            )

        payout.mark_processing(processed_by=processed_by)
        await self.session.flush()
        return payout

    async def complete_payout(
        self,
        payout_id: UUID,
        transaction_id: str,
    ) -> RewardPayout:
        """
        Mark payout as completed.
        
        Args:
            payout_id: Payout ID
            transaction_id: Transaction ID
            
        Returns:
            Completed payout
        """
        payout = await self.get_payout_by_id(payout_id)
        if not payout:
            raise EntityNotFoundError(f"Payout {payout_id} not found")

        if payout.status != RewardStatus.PROCESSING:
            raise BusinessLogicError(
                "Only processing payouts can be completed"
            )

        payout.mark_completed(transaction_id=transaction_id)
        await self.session.flush()
        return payout

    async def fail_payout(
        self,
        payout_id: UUID,
        reason: str,
    ) -> RewardPayout:
        """
        Mark payout as failed.
        
        Args:
            payout_id: Payout ID
            reason: Failure reason
            
        Returns:
            Failed payout
        """
        payout = await self.get_payout_by_id(payout_id)
        if not payout:
            raise EntityNotFoundError(f"Payout {payout_id} not found")

        payout.mark_failed(reason=reason)
        await self.session.flush()
        return payout

    # ============================================================================
    # ANALYTICS & REPORTING
    # ============================================================================

    async def get_user_reward_summary(
        self, user_id: UUID
    ) -> Dict[str, Any]:
        """
        Get reward summary for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            Reward summary statistics
        """
        query = select(ReferralReward).where(ReferralReward.user_id == user_id)

        result = await self.session.execute(query)
        rewards = result.scalars().all()

        total_earned = sum(r.net_amount for r in rewards)
        total_pending = sum(
            r.net_amount for r in rewards if r.status == RewardStatus.PENDING
        )
        total_approved = sum(
            r.net_amount for r in rewards if r.status == RewardStatus.APPROVED
        )
        total_paid = sum(
            r.net_amount for r in rewards if r.status == RewardStatus.PAID
        )

        return {
            "total_rewards": len(rewards),
            "total_earned": float(total_earned),
            "total_pending": float(total_pending),
            "total_approved": float(total_approved),
            "total_paid": float(total_paid),
            "pending_count": sum(1 for r in rewards if r.is_pending),
            "approved_count": sum(1 for r in rewards if r.is_approved),
            "paid_count": sum(1 for r in rewards if r.is_paid),
        }

    async def get_reward_statistics(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Get overall reward statistics.
        
        Args:
            start_date: Start date filter
            end_date: End date filter
            
        Returns:
            Overall statistics
        """
        query = select(ReferralReward)

        if start_date:
            query = query.where(ReferralReward.created_at >= start_date)
        if end_date:
            query = query.where(ReferralReward.created_at <= end_date)

        result = await self.session.execute(query)
        rewards = result.scalars().all()

        total_rewards = len(rewards)
        total_amount = sum(r.net_amount for r in rewards)
        total_paid = sum(
            r.net_amount for r in rewards if r.status == RewardStatus.PAID
        )
        total_pending = sum(
            r.net_amount for r in rewards if r.status == RewardStatus.PENDING
        )

        avg_reward = total_amount / total_rewards if total_rewards > 0 else 0
        avg_processing_time = sum(
            r.days_since_approval or 0
            for r in rewards
            if r.status == RewardStatus.PAID
        )
        paid_count = sum(1 for r in rewards if r.status == RewardStatus.PAID)
        avg_processing_time = (
            avg_processing_time / paid_count if paid_count > 0 else 0
        )

        return {
            "total_rewards": total_rewards,
            "total_amount": float(total_amount),
            "total_paid": float(total_paid),
            "total_pending": float(total_pending),
            "average_reward": float(avg_reward),
            "average_processing_time_days": avg_processing_time,
            "pending_count": sum(1 for r in rewards if r.is_pending),
            "approved_count": sum(1 for r in rewards if r.is_approved),
            "paid_count": paid_count,
        }

    async def get_payout_statistics(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Get payout statistics.
        
        Args:
            start_date: Start date filter
            end_date: End date filter
            
        Returns:
            Payout statistics
        """
        query = select(RewardPayout)

        if start_date:
            query = query.where(RewardPayout.requested_at >= start_date)
        if end_date:
            query = query.where(RewardPayout.requested_at <= end_date)

        result = await self.session.execute(query)
        payouts = result.scalars().all()

        total_payouts = len(payouts)
        total_amount = sum(p.net_amount for p in payouts)
        total_completed = sum(
            p.net_amount for p in payouts if p.is_completed
        )

        avg_processing_time = sum(
            p.processing_time_days or 0
            for p in payouts
            if p.is_completed
        )
        completed_count = sum(1 for p in payouts if p.is_completed)
        avg_processing_time = (
            avg_processing_time / completed_count if completed_count > 0 else 0
        )

        return {
            "total_payouts": total_payouts,
            "total_amount": float(total_amount),
            "total_completed": float(total_completed),
            "pending_count": sum(1 for p in payouts if p.is_pending),
            "completed_count": completed_count,
            "average_processing_time_days": avg_processing_time,
        }


