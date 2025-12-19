"""
Subscription Repository.

Manages subscription lifecycle including creation, activation,
renewal, cancellation, and status management.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.models.subscription.subscription import (
    Subscription,
    SubscriptionCancellation,
    SubscriptionHistory,
)
from app.schemas.common.enums import BillingCycle, SubscriptionStatus


class SubscriptionRepository:
    """
    Repository for subscription operations.

    Provides methods for subscription lifecycle management,
    renewal processing, and subscription analytics.
    """

    def __init__(self, db: Session):
        """Initialize repository with database session."""
        self.db = db

    # ==================== CREATE OPERATIONS ====================

    def create_subscription(
        self,
        subscription_data: Dict[str, Any],
        created_by: Optional[UUID] = None,
    ) -> Subscription:
        """
        Create new subscription.

        Args:
            subscription_data: Subscription configuration data
            created_by: User ID who created subscription

        Returns:
            Created subscription
        """
        subscription = Subscription(**subscription_data)
        if created_by:
            subscription.created_by = created_by

        self.db.add(subscription)
        self.db.flush()
        return subscription

    def create_subscription_history(
        self,
        subscription_id: UUID,
        change_type: str,
        old_value: Optional[str] = None,
        new_value: Optional[str] = None,
        reason: Optional[str] = None,
        changed_by: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> SubscriptionHistory:
        """
        Create subscription history record.

        Args:
            subscription_id: Subscription ID
            change_type: Type of change
            old_value: Previous value
            new_value: New value
            reason: Reason for change
            changed_by: User who made change
            ip_address: IP address
            user_agent: User agent

        Returns:
            Created history record
        """
        history = SubscriptionHistory(
            subscription_id=subscription_id,
            change_type=change_type,
            old_value=old_value,
            new_value=new_value,
            reason=reason,
            changed_by=changed_by,
            changed_at=datetime.utcnow(),
            ip_address=ip_address,
            user_agent=user_agent,
        )

        self.db.add(history)
        self.db.flush()
        return history

    def create_cancellation_record(
        self,
        cancellation_data: Dict[str, Any],
    ) -> SubscriptionCancellation:
        """
        Create subscription cancellation record.

        Args:
            cancellation_data: Cancellation details

        Returns:
            Created cancellation record
        """
        cancellation = SubscriptionCancellation(**cancellation_data)
        self.db.add(cancellation)
        self.db.flush()
        return cancellation

    # ==================== READ OPERATIONS ====================

    def get_by_id(
        self,
        subscription_id: UUID,
        include_deleted: bool = False,
    ) -> Optional[Subscription]:
        """
        Get subscription by ID.

        Args:
            subscription_id: Subscription ID
            include_deleted: Include soft-deleted subscriptions

        Returns:
            Subscription if found
        """
        query = (
            select(Subscription)
            .where(Subscription.id == subscription_id)
            .options(joinedload(Subscription.plan))
        )

        if not include_deleted:
            query = query.where(Subscription.is_deleted == False)

        result = self.db.execute(query)
        return result.scalar_one_or_none()

    def get_by_reference(
        self,
        subscription_reference: str,
    ) -> Optional[Subscription]:
        """
        Get subscription by reference number.

        Args:
            subscription_reference: Subscription reference

        Returns:
            Subscription if found
        """
        query = (
            select(Subscription)
            .where(Subscription.subscription_reference == subscription_reference)
            .where(Subscription.is_deleted == False)
            .options(joinedload(Subscription.plan))
        )

        result = self.db.execute(query)
        return result.scalar_one_or_none()

    def get_active_by_hostel(
        self,
        hostel_id: UUID,
    ) -> Optional[Subscription]:
        """
        Get active subscription for hostel.

        Args:
            hostel_id: Hostel ID

        Returns:
            Active subscription if exists
        """
        query = (
            select(Subscription)
            .where(
                and_(
                    Subscription.hostel_id == hostel_id,
                    Subscription.status == SubscriptionStatus.ACTIVE,
                    Subscription.is_deleted == False,
                )
            )
            .options(joinedload(Subscription.plan))
        )

        result = self.db.execute(query)
        return result.scalar_one_or_none()

    def get_all_by_hostel(
        self,
        hostel_id: UUID,
        include_deleted: bool = False,
    ) -> List[Subscription]:
        """
        Get all subscriptions for hostel.

        Args:
            hostel_id: Hostel ID
            include_deleted: Include soft-deleted subscriptions

        Returns:
            List of subscriptions
        """
        query = (
            select(Subscription)
            .where(Subscription.hostel_id == hostel_id)
            .options(joinedload(Subscription.plan))
            .order_by(Subscription.created_at.desc())
        )

        if not include_deleted:
            query = query.where(Subscription.is_deleted == False)

        result = self.db.execute(query)
        return list(result.scalars().all())

    def get_by_status(
        self,
        status: SubscriptionStatus,
        limit: Optional[int] = None,
    ) -> List[Subscription]:
        """
        Get subscriptions by status.

        Args:
            status: Subscription status
            limit: Maximum number of results

        Returns:
            List of subscriptions
        """
        query = (
            select(Subscription)
            .where(
                and_(
                    Subscription.status == status,
                    Subscription.is_deleted == False,
                )
            )
            .options(joinedload(Subscription.plan))
            .order_by(Subscription.created_at.desc())
        )

        if limit:
            query = query.limit(limit)

        result = self.db.execute(query)
        return list(result.scalars().all())

    def get_expiring_soon(
        self,
        days: int = 7,
    ) -> List[Subscription]:
        """
        Get subscriptions expiring within specified days.

        Args:
            days: Number of days to check

        Returns:
            List of expiring subscriptions
        """
        expiry_date = date.today() + timedelta(days=days)

        query = (
            select(Subscription)
            .where(
                and_(
                    Subscription.status == SubscriptionStatus.ACTIVE,
                    Subscription.end_date <= expiry_date,
                    Subscription.end_date >= date.today(),
                    Subscription.is_deleted == False,
                )
            )
            .options(joinedload(Subscription.plan))
            .order_by(Subscription.end_date)
        )

        result = self.db.execute(query)
        return list(result.scalars().all())

    def get_expired_subscriptions(self) -> List[Subscription]:
        """
        Get all expired subscriptions that need status update.

        Returns:
            List of expired subscriptions
        """
        query = (
            select(Subscription)
            .where(
                and_(
                    Subscription.status == SubscriptionStatus.ACTIVE,
                    Subscription.end_date < date.today(),
                    Subscription.is_deleted == False,
                )
            )
            .options(joinedload(Subscription.plan))
            .order_by(Subscription.end_date)
        )

        result = self.db.execute(query)
        return list(result.scalars().all())

    def get_trial_subscriptions(
        self,
        active_only: bool = True,
    ) -> List[Subscription]:
        """
        Get subscriptions in trial period.

        Args:
            active_only: Only return active trials

        Returns:
            List of trial subscriptions
        """
        query = (
            select(Subscription)
            .where(
                and_(
                    Subscription.is_trial == True,
                    Subscription.is_deleted == False,
                )
            )
            .options(joinedload(Subscription.plan))
        )

        if active_only:
            query = query.where(Subscription.status == SubscriptionStatus.ACTIVE)

        result = self.db.execute(query)
        return list(result.scalars().all())

    def get_trial_ending_soon(
        self,
        days: int = 3,
    ) -> List[Subscription]:
        """
        Get trial subscriptions ending soon.

        Args:
            days: Number of days to check

        Returns:
            List of subscriptions with ending trials
        """
        end_date = date.today() + timedelta(days=days)

        query = (
            select(Subscription)
            .where(
                and_(
                    Subscription.is_trial == True,
                    Subscription.status == SubscriptionStatus.ACTIVE,
                    Subscription.trial_end_date <= end_date,
                    Subscription.trial_end_date >= date.today(),
                    Subscription.is_deleted == False,
                )
            )
            .options(joinedload(Subscription.plan))
            .order_by(Subscription.trial_end_date)
        )

        result = self.db.execute(query)
        return list(result.scalars().all())

    def get_auto_renewable_subscriptions(
        self,
        days_ahead: int = 7,
    ) -> List[Subscription]:
        """
        Get subscriptions eligible for auto-renewal.

        Args:
            days_ahead: Days ahead to check for renewal

        Returns:
            List of subscriptions for auto-renewal
        """
        renewal_date = date.today() + timedelta(days=days_ahead)

        query = (
            select(Subscription)
            .where(
                and_(
                    Subscription.status == SubscriptionStatus.ACTIVE,
                    Subscription.auto_renew == True,
                    Subscription.next_billing_date <= renewal_date,
                    Subscription.next_billing_date >= date.today(),
                    Subscription.is_deleted == False,
                )
            )
            .options(joinedload(Subscription.plan))
            .order_by(Subscription.next_billing_date)
        )

        result = self.db.execute(query)
        return list(result.scalars().all())

    def get_by_plan(
        self,
        plan_id: UUID,
        active_only: bool = False,
    ) -> List[Subscription]:
        """
        Get all subscriptions for a specific plan.

        Args:
            plan_id: Plan ID
            active_only: Only return active subscriptions

        Returns:
            List of subscriptions
        """
        query = (
            select(Subscription)
            .where(
                and_(
                    Subscription.plan_id == plan_id,
                    Subscription.is_deleted == False,
                )
            )
            .options(joinedload(Subscription.plan))
            .order_by(Subscription.created_at.desc())
        )

        if active_only:
            query = query.where(Subscription.status == SubscriptionStatus.ACTIVE)

        result = self.db.execute(query)
        return list(result.scalars().all())

    def get_subscription_history(
        self,
        subscription_id: UUID,
        change_type: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[SubscriptionHistory]:
        """
        Get subscription change history.

        Args:
            subscription_id: Subscription ID
            change_type: Filter by change type
            limit: Maximum number of records

        Returns:
            List of history records
        """
        query = (
            select(SubscriptionHistory)
            .where(SubscriptionHistory.subscription_id == subscription_id)
            .order_by(SubscriptionHistory.changed_at.desc())
        )

        if change_type:
            query = query.where(SubscriptionHistory.change_type == change_type)

        if limit:
            query = query.limit(limit)

        result = self.db.execute(query)
        return list(result.scalars().all())

    def get_cancellation_record(
        self,
        subscription_id: UUID,
    ) -> Optional[SubscriptionCancellation]:
        """
        Get cancellation record for subscription.

        Args:
            subscription_id: Subscription ID

        Returns:
            Cancellation record if exists
        """
        query = select(SubscriptionCancellation).where(
            SubscriptionCancellation.subscription_id == subscription_id
        )

        result = self.db.execute(query)
        return result.scalar_one_or_none()

    # ==================== UPDATE OPERATIONS ====================

    def update_subscription(
        self,
        subscription_id: UUID,
        update_data: Dict[str, Any],
        updated_by: Optional[UUID] = None,
    ) -> Optional[Subscription]:
        """
        Update subscription details.

        Args:
            subscription_id: Subscription ID
            update_data: Updated data
            updated_by: User ID who updated

        Returns:
            Updated subscription
        """
        subscription = self.get_by_id(subscription_id)
        if not subscription:
            return None

        for key, value in update_data.items():
            if hasattr(subscription, key):
                setattr(subscription, key, value)

        if updated_by:
            subscription.updated_by = updated_by
        subscription.updated_at = datetime.utcnow()

        self.db.flush()
        return subscription

    def update_status(
        self,
        subscription_id: UUID,
        status: SubscriptionStatus,
        reason: Optional[str] = None,
        updated_by: Optional[UUID] = None,
    ) -> Optional[Subscription]:
        """
        Update subscription status.

        Args:
            subscription_id: Subscription ID
            status: New status
            reason: Reason for status change
            updated_by: User ID who updated

        Returns:
            Updated subscription
        """
        subscription = self.get_by_id(subscription_id)
        if not subscription:
            return None

        old_status = subscription.status
        subscription.status = status

        if updated_by:
            subscription.updated_by = updated_by
        subscription.updated_at = datetime.utcnow()

        # Create history record
        self.create_subscription_history(
            subscription_id=subscription_id,
            change_type="status_change",
            old_value=old_status.value,
            new_value=status.value,
            reason=reason,
            changed_by=updated_by,
        )

        self.db.flush()
        return subscription

    def activate_subscription(
        self,
        subscription_id: UUID,
        updated_by: Optional[UUID] = None,
    ) -> Optional[Subscription]:
        """
        Activate subscription.

        Args:
            subscription_id: Subscription ID
            updated_by: User ID who activated

        Returns:
            Updated subscription
        """
        return self.update_status(
            subscription_id=subscription_id,
            status=SubscriptionStatus.ACTIVE,
            reason="Subscription activated",
            updated_by=updated_by,
        )

    def suspend_subscription(
        self,
        subscription_id: UUID,
        reason: str,
        updated_by: Optional[UUID] = None,
    ) -> Optional[Subscription]:
        """
        Suspend subscription.

        Args:
            subscription_id: Subscription ID
            reason: Suspension reason
            updated_by: User ID who suspended

        Returns:
            Updated subscription
        """
        return self.update_status(
            subscription_id=subscription_id,
            status=SubscriptionStatus.SUSPENDED,
            reason=reason,
            updated_by=updated_by,
        )

    def expire_subscription(
        self,
        subscription_id: UUID,
        updated_by: Optional[UUID] = None,
    ) -> Optional[Subscription]:
        """
        Mark subscription as expired.

        Args:
            subscription_id: Subscription ID
            updated_by: User ID who updated

        Returns:
            Updated subscription
        """
        return self.update_status(
            subscription_id=subscription_id,
            status=SubscriptionStatus.EXPIRED,
            reason="Subscription expired",
            updated_by=updated_by,
        )

    def cancel_subscription(
        self,
        subscription_id: UUID,
        cancellation_data: Dict[str, Any],
        cancel_immediately: bool = False,
    ) -> Optional[Subscription]:
        """
        Cancel subscription.

        Args:
            subscription_id: Subscription ID
            cancellation_data: Cancellation details
            cancel_immediately: Cancel immediately vs end of term

        Returns:
            Updated subscription
        """
        subscription = self.get_by_id(subscription_id)
        if not subscription:
            return None

        # Create cancellation record
        cancellation_record = self.create_cancellation_record(cancellation_data)

        # Update subscription
        subscription.cancelled_at = datetime.utcnow()
        subscription.cancelled_by = cancellation_data.get("cancelled_by")
        subscription.cancellation_reason = cancellation_data.get("cancellation_reason")
        subscription.cancellation_effective_date = cancellation_data.get(
            "cancellation_effective_date"
        )

        if cancel_immediately:
            subscription.status = SubscriptionStatus.CANCELLED
            subscription.end_date = date.today()
        else:
            # Will cancel at end of current period
            subscription.auto_renew = False

        subscription.updated_at = datetime.utcnow()

        # Create history record
        self.create_subscription_history(
            subscription_id=subscription_id,
            change_type="cancellation",
            new_value=subscription.status.value,
            reason=cancellation_data.get("cancellation_reason"),
            changed_by=cancellation_data.get("cancelled_by"),
        )

        self.db.flush()
        return subscription

    def renew_subscription(
        self,
        subscription_id: UUID,
        billing_cycle: BillingCycle,
        amount: Decimal,
        renewed_by: Optional[UUID] = None,
    ) -> Optional[Subscription]:
        """
        Renew subscription for next period.

        Args:
            subscription_id: Subscription ID
            billing_cycle: Billing cycle for renewal
            amount: Renewal amount
            renewed_by: User ID who renewed

        Returns:
            Updated subscription
        """
        subscription = self.get_by_id(subscription_id)
        if not subscription:
            return None

        # Calculate new period
        old_end_date = subscription.end_date
        if billing_cycle == BillingCycle.MONTHLY:
            new_end_date = old_end_date + timedelta(days=30)
            new_billing_date = old_end_date + timedelta(days=30)
        else:  # YEARLY
            new_end_date = old_end_date + timedelta(days=365)
            new_billing_date = old_end_date + timedelta(days=365)

        # Update subscription
        subscription.end_date = new_end_date
        subscription.next_billing_date = new_billing_date
        subscription.status = SubscriptionStatus.ACTIVE
        subscription.amount = amount
        subscription.billing_cycle = billing_cycle

        if renewed_by:
            subscription.updated_by = renewed_by
        subscription.updated_at = datetime.utcnow()

        # Create history record
        self.create_subscription_history(
            subscription_id=subscription_id,
            change_type="renewal",
            old_value=str(old_end_date),
            new_value=str(new_end_date),
            reason=f"Subscription renewed for {billing_cycle.value} period",
            changed_by=renewed_by,
        )

        self.db.flush()
        return subscription

    def update_payment_info(
        self,
        subscription_id: UUID,
        payment_date: date,
        payment_amount: Decimal,
    ) -> Optional[Subscription]:
        """
        Update last payment information.

        Args:
            subscription_id: Subscription ID
            payment_date: Payment date
            payment_amount: Payment amount

        Returns:
            Updated subscription
        """
        subscription = self.get_by_id(subscription_id)
        if not subscription:
            return None

        subscription.last_payment_date = payment_date
        subscription.last_payment_amount = payment_amount
        subscription.updated_at = datetime.utcnow()

        self.db.flush()
        return subscription

    def toggle_auto_renew(
        self,
        subscription_id: UUID,
        auto_renew: bool,
        updated_by: Optional[UUID] = None,
    ) -> Optional[Subscription]:
        """
        Toggle auto-renewal setting.

        Args:
            subscription_id: Subscription ID
            auto_renew: Auto-renew status
            updated_by: User ID who updated

        Returns:
            Updated subscription
        """
        subscription = self.get_by_id(subscription_id)
        if not subscription:
            return None

        old_value = subscription.auto_renew
        subscription.auto_renew = auto_renew

        if updated_by:
            subscription.updated_by = updated_by
        subscription.updated_at = datetime.utcnow()

        # Create history record
        self.create_subscription_history(
            subscription_id=subscription_id,
            change_type="auto_renew_toggle",
            old_value=str(old_value),
            new_value=str(auto_renew),
            reason=f"Auto-renewal {'enabled' if auto_renew else 'disabled'}",
            changed_by=updated_by,
        )

        self.db.flush()
        return subscription

    def change_plan(
        self,
        subscription_id: UUID,
        new_plan_id: UUID,
        new_amount: Decimal,
        effective_date: date,
        changed_by: Optional[UUID] = None,
    ) -> Optional[Subscription]:
        """
        Change subscription plan (upgrade/downgrade).

        Args:
            subscription_id: Subscription ID
            new_plan_id: New plan ID
            new_amount: New subscription amount
            effective_date: When change takes effect
            changed_by: User ID who changed

        Returns:
            Updated subscription
        """
        subscription = self.get_by_id(subscription_id)
        if not subscription:
            return None

        old_plan_id = subscription.plan_id

        subscription.plan_id = new_plan_id
        subscription.amount = new_amount

        if changed_by:
            subscription.updated_by = changed_by
        subscription.updated_at = datetime.utcnow()

        # Create history record
        self.create_subscription_history(
            subscription_id=subscription_id,
            change_type="plan_change",
            old_value=str(old_plan_id),
            new_value=str(new_plan_id),
            reason=f"Plan changed effective {effective_date}",
            changed_by=changed_by,
        )

        self.db.flush()
        return subscription

    def end_trial_period(
        self,
        subscription_id: UUID,
    ) -> Optional[Subscription]:
        """
        End trial period for subscription.

        Args:
            subscription_id: Subscription ID

        Returns:
            Updated subscription
        """
        subscription = self.get_by_id(subscription_id)
        if not subscription:
            return None

        subscription.is_trial = False
        subscription.trial_end_date = None
        subscription.updated_at = datetime.utcnow()

        # Create history record
        self.create_subscription_history(
            subscription_id=subscription_id,
            change_type="trial_ended",
            reason="Trial period ended",
        )

        self.db.flush()
        return subscription

    def update_cancellation_record(
        self,
        subscription_id: UUID,
        update_data: Dict[str, Any],
    ) -> Optional[SubscriptionCancellation]:
        """
        Update cancellation record.

        Args:
            subscription_id: Subscription ID
            update_data: Updated cancellation data

        Returns:
            Updated cancellation record
        """
        cancellation = self.get_cancellation_record(subscription_id)
        if not cancellation:
            return None

        for key, value in update_data.items():
            if hasattr(cancellation, key):
                setattr(cancellation, key, value)

        cancellation.updated_at = datetime.utcnow()
        self.db.flush()
        return cancellation

    # ==================== DELETE OPERATIONS ====================

    def soft_delete_subscription(
        self,
        subscription_id: UUID,
        deleted_by: Optional[UUID] = None,
    ) -> bool:
        """
        Soft delete subscription.

        Args:
            subscription_id: Subscription ID
            deleted_by: User ID who deleted

        Returns:
            True if deleted successfully
        """
        subscription = self.get_by_id(subscription_id)
        if not subscription:
            return False

        subscription.is_deleted = True
        subscription.deleted_at = datetime.utcnow()
        if deleted_by:
            subscription.deleted_by = deleted_by

        # Create history record
        self.create_subscription_history(
            subscription_id=subscription_id,
            change_type="soft_delete",
            reason="Subscription soft deleted",
            changed_by=deleted_by,
        )

        self.db.flush()
        return True

    def restore_subscription(
        self,
        subscription_id: UUID,
        restored_by: Optional[UUID] = None,
    ) -> Optional[Subscription]:
        """
        Restore soft-deleted subscription.

        Args:
            subscription_id: Subscription ID
            restored_by: User ID who restored

        Returns:
            Restored subscription
        """
        subscription = self.get_by_id(subscription_id, include_deleted=True)
        if not subscription or not subscription.is_deleted:
            return None

        subscription.is_deleted = False
        subscription.deleted_at = None
        subscription.deleted_by = None
        subscription.updated_at = datetime.utcnow()

        # Create history record
        self.create_subscription_history(
            subscription_id=subscription_id,
            change_type="restore",
            reason="Subscription restored",
            changed_by=restored_by,
        )

        self.db.flush()
        return subscription

    # ==================== ANALYTICS & REPORTING ====================

    def get_subscription_statistics(self) -> Dict[str, Any]:
        """
        Get overall subscription statistics.

        Returns:
            Dictionary with subscription statistics
        """
        total = (
            self.db.query(func.count(Subscription.id))
            .filter(Subscription.is_deleted == False)
            .scalar()
        )

        active = (
            self.db.query(func.count(Subscription.id))
            .filter(
                and_(
                    Subscription.status == SubscriptionStatus.ACTIVE,
                    Subscription.is_deleted == False,
                )
            )
            .scalar()
        )

        trial = (
            self.db.query(func.count(Subscription.id))
            .filter(
                and_(
                    Subscription.is_trial == True,
                    Subscription.status == SubscriptionStatus.ACTIVE,
                    Subscription.is_deleted == False,
                )
            )
            .scalar()
        )

        expired = (
            self.db.query(func.count(Subscription.id))
            .filter(
                and_(
                    Subscription.status == SubscriptionStatus.EXPIRED,
                    Subscription.is_deleted == False,
                )
            )
            .scalar()
        )

        cancelled = (
            self.db.query(func.count(Subscription.id))
            .filter(
                and_(
                    Subscription.status == SubscriptionStatus.CANCELLED,
                    Subscription.is_deleted == False,
                )
            )
            .scalar()
        )

        suspended = (
            self.db.query(func.count(Subscription.id))
            .filter(
                and_(
                    Subscription.status == SubscriptionStatus.SUSPENDED,
                    Subscription.is_deleted == False,
                )
            )
            .scalar()
        )

        auto_renew_count = (
            self.db.query(func.count(Subscription.id))
            .filter(
                and_(
                    Subscription.status == SubscriptionStatus.ACTIVE,
                    Subscription.auto_renew == True,
                    Subscription.is_deleted == False,
                )
            )
            .scalar()
        )

        return {
            "total_subscriptions": total,
            "active_subscriptions": active,
            "trial_subscriptions": trial,
            "expired_subscriptions": expired,
            "cancelled_subscriptions": cancelled,
            "suspended_subscriptions": suspended,
            "auto_renew_enabled": auto_renew_count,
            "active_rate": (active / total * 100) if total > 0 else 0,
        }

    def get_revenue_summary(self) -> Dict[str, Any]:
        """
        Get subscription revenue summary.

        Returns:
            Dictionary with revenue metrics
        """
        active_subscriptions = self.get_by_status(SubscriptionStatus.ACTIVE)

        monthly_revenue = sum(
            sub.amount
            for sub in active_subscriptions
            if sub.billing_cycle == BillingCycle.MONTHLY
        )

        yearly_revenue = sum(
            sub.amount
            for sub in active_subscriptions
            if sub.billing_cycle == BillingCycle.YEARLY
        )

        # Normalize to monthly recurring revenue (MRR)
        mrr = monthly_revenue + (yearly_revenue / 12)

        # Annual recurring revenue (ARR)
        arr = mrr * 12

        return {
            "monthly_recurring_revenue": float(mrr),
            "annual_recurring_revenue": float(arr),
            "active_monthly_subscriptions": sum(
                1
                for sub in active_subscriptions
                if sub.billing_cycle == BillingCycle.MONTHLY
            ),
            "active_yearly_subscriptions": sum(
                1
                for sub in active_subscriptions
                if sub.billing_cycle == BillingCycle.YEARLY
            ),
            "total_monthly_revenue": float(monthly_revenue),
            "total_yearly_revenue": float(yearly_revenue),
        }

    def get_churn_statistics(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> Dict[str, Any]:
        """
        Calculate churn statistics.

        Args:
            start_date: Start date for analysis
            end_date: End date for analysis

        Returns:
            Dictionary with churn metrics
        """
        if not start_date:
            start_date = date.today() - timedelta(days=30)
        if not end_date:
            end_date = date.today()

        # Cancelled subscriptions in period
        cancelled_query = select(func.count(Subscription.id)).where(
            and_(
                Subscription.status == SubscriptionStatus.CANCELLED,
                Subscription.cancelled_at >= start_date,
                Subscription.cancelled_at <= end_date,
                Subscription.is_deleted == False,
            )
        )
        cancelled_count = self.db.execute(cancelled_query).scalar()

        # Active at start of period
        active_start_query = select(func.count(Subscription.id)).where(
            and_(
                Subscription.status == SubscriptionStatus.ACTIVE,
                Subscription.start_date < start_date,
                Subscription.is_deleted == False,
            )
        )
        active_start = self.db.execute(active_start_query).scalar()

        churn_rate = (
            (cancelled_count / active_start * 100) if active_start > 0 else 0
        )

        return {
            "cancelled_count": cancelled_count,
            "active_at_period_start": active_start,
            "churn_rate": churn_rate,
            "period_start": start_date,
            "period_end": end_date,
        }

    def get_renewal_statistics(self) -> Dict[str, Any]:
        """
        Get renewal statistics.

        Returns:
            Dictionary with renewal metrics
        """
        # Subscriptions renewed in last 30 days
        thirty_days_ago = date.today() - timedelta(days=30)

        renewed_query = (
            select(SubscriptionHistory)
            .where(
                and_(
                    SubscriptionHistory.change_type == "renewal",
                    SubscriptionHistory.changed_at >= thirty_days_ago,
                )
            )
        )
        result = self.db.execute(renewed_query)
        renewed_count = len(list(result.scalars().all()))

        # Subscriptions that expired without renewal
        expired_query = select(func.count(Subscription.id)).where(
            and_(
                Subscription.status == SubscriptionStatus.EXPIRED,
                Subscription.end_date >= thirty_days_ago,
                Subscription.auto_renew == False,
                Subscription.is_deleted == False,
            )
        )
        expired_count = self.db.execute(expired_query).scalar()

        total_eligible = renewed_count + expired_count
        renewal_rate = (
            (renewed_count / total_eligible * 100) if total_eligible > 0 else 0
        )

        return {
            "renewed_count": renewed_count,
            "expired_count": expired_count,
            "renewal_rate": renewal_rate,
            "period_days": 30,
        }

    def get_trial_conversion_rate(self) -> Dict[str, Any]:
        """
        Calculate trial to paid conversion rate.

        Returns:
            Dictionary with trial conversion metrics
        """
        # All trial subscriptions that ended
        ended_trials_query = (
            select(SubscriptionHistory)
            .where(SubscriptionHistory.change_type == "trial_ended")
        )
        result = self.db.execute(ended_trials_query)
        ended_trials = list(result.scalars().all())

        # Of those, how many converted to paid
        converted = 0
        for trial_end in ended_trials:
            subscription = self.get_by_id(trial_end.subscription_id)
            if subscription and subscription.status == SubscriptionStatus.ACTIVE:
                converted += 1

        total_trials = len(ended_trials)
        conversion_rate = (converted / total_trials * 100) if total_trials > 0 else 0

        return {
            "total_trials_ended": total_trials,
            "converted_to_paid": converted,
            "conversion_rate": conversion_rate,
        }

    # ==================== SEARCH & FILTERING ====================

    def search_subscriptions(
        self,
        search_term: Optional[str] = None,
        status: Optional[SubscriptionStatus] = None,
        plan_id: Optional[UUID] = None,
        billing_cycle: Optional[BillingCycle] = None,
        is_trial: Optional[bool] = None,
        auto_renew: Optional[bool] = None,
        start_date_from: Optional[date] = None,
        start_date_to: Optional[date] = None,
        end_date_from: Optional[date] = None,
        end_date_to: Optional[date] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> List[Subscription]:
        """
        Search subscriptions with multiple filters.

        Args:
            search_term: Search in reference
            status: Filter by status
            plan_id: Filter by plan
            billing_cycle: Filter by billing cycle
            is_trial: Filter by trial status
            auto_renew: Filter by auto-renew setting
            start_date_from: Start date range begin
            start_date_to: Start date range end
            end_date_from: End date range begin
            end_date_to: End date range end
            limit: Maximum results
            offset: Results offset

        Returns:
            List of matching subscriptions
        """
        query = select(Subscription).where(Subscription.is_deleted == False).options(
            joinedload(Subscription.plan)
        )

        conditions = []

        if search_term:
            search_pattern = f"%{search_term}%"
            conditions.append(
                Subscription.subscription_reference.ilike(search_pattern)
            )

        if status:
            conditions.append(Subscription.status == status)

        if plan_id:
            conditions.append(Subscription.plan_id == plan_id)

        if billing_cycle:
            conditions.append(Subscription.billing_cycle == billing_cycle)

        if is_trial is not None:
            conditions.append(Subscription.is_trial == is_trial)

        if auto_renew is not None:
            conditions.append(Subscription.auto_renew == auto_renew)

        if start_date_from:
            conditions.append(Subscription.start_date >= start_date_from)

        if start_date_to:
            conditions.append(Subscription.start_date <= start_date_to)

        if end_date_from:
            conditions.append(Subscription.end_date >= end_date_from)

        if end_date_to:
            conditions.append(Subscription.end_date <= end_date_to)

        if conditions:
            query = query.where(and_(*conditions))

        query = query.order_by(Subscription.created_at.desc())

        if limit:
            query = query.limit(limit)

        if offset:
            query = query.offset(offset)

        result = self.db.execute(query)
        return list(result.scalars().all())

    def count_subscriptions(
        self,
        status: Optional[SubscriptionStatus] = None,
        plan_id: Optional[UUID] = None,
    ) -> int:
        """
        Count subscriptions with filters.

        Args:
            status: Filter by status
            plan_id: Filter by plan

        Returns:
            Count of matching subscriptions
        """
        query = select(func.count(Subscription.id)).where(
            Subscription.is_deleted == False
        )

        conditions = []

        if status:
            conditions.append(Subscription.status == status)

        if plan_id:
            conditions.append(Subscription.plan_id == plan_id)

        if conditions:
            query = query.where(and_(*conditions))

        return self.db.execute(query).scalar()

    # ==================== BATCH OPERATIONS ====================

    def batch_expire_subscriptions(
        self,
        subscription_ids: List[UUID],
    ) -> int:
        """
        Batch expire subscriptions.

        Args:
            subscription_ids: List of subscription IDs

        Returns:
            Number of subscriptions expired
        """
        count = 0
        for subscription_id in subscription_ids:
            if self.expire_subscription(subscription_id):
                count += 1
        return count

    def batch_update_status(
        self,
        subscription_ids: List[UUID],
        status: SubscriptionStatus,
        reason: Optional[str] = None,
    ) -> int:
        """
        Batch update subscription status.

        Args:
            subscription_ids: List of subscription IDs
            status: New status
            reason: Reason for change

        Returns:
            Number of subscriptions updated
        """
        count = 0
        for subscription_id in subscription_ids:
            if self.update_status(subscription_id, status, reason):
                count += 1
        return count