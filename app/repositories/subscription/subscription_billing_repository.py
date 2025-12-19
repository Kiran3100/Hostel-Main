"""
Subscription Billing Repository.

Manages billing cycles, schedules, and billing-related
operations for subscriptions.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.models.subscription.subscription_billing import SubscriptionBillingCycle
from app.schemas.common.enums import BillingCycle


class SubscriptionBillingRepository:
    """
    Repository for subscription billing operations.

    Provides methods for billing cycle management,
    billing schedule tracking, and billing analytics.
    """

    def __init__(self, db: Session):
        """Initialize repository with database session."""
        self.db = db

    # ==================== CREATE OPERATIONS ====================

    def create_billing_cycle(
        self,
        billing_data: Dict[str, Any],
    ) -> SubscriptionBillingCycle:
        """
        Create new billing cycle record.

        Args:
            billing_data: Billing cycle data

        Returns:
            Created billing cycle
        """
        billing_cycle = SubscriptionBillingCycle(**billing_data)
        self.db.add(billing_cycle)
        self.db.flush()
        return billing_cycle

    def create_billing_cycles_for_subscription(
        self,
        subscription_id: UUID,
        hostel_id: UUID,
        plan_name: str,
        plan_display_name: str,
        start_date: date,
        end_date: date,
        billing_cycle: BillingCycle,
        amount: Decimal,
        auto_renew: bool,
        is_trial: bool = False,
        trial_days_remaining: Optional[int] = None,
    ) -> List[SubscriptionBillingCycle]:
        """
        Create all billing cycles for subscription period.

        Args:
            subscription_id: Subscription ID
            hostel_id: Hostel ID
            plan_name: Plan name
            plan_display_name: Plan display name
            start_date: Subscription start date
            end_date: Subscription end date
            billing_cycle: Billing cycle type
            amount: Billing amount
            auto_renew: Auto-renewal status
            is_trial: Trial status
            trial_days_remaining: Remaining trial days

        Returns:
            List of created billing cycles
        """
        cycles = []
        current_date = start_date

        if billing_cycle == BillingCycle.MONTHLY:
            cycle_days = 30
        else:  # YEARLY
            cycle_days = 365

        while current_date < end_date:
            cycle_end = min(current_date + timedelta(days=cycle_days - 1), end_date)
            next_billing = cycle_end + timedelta(days=1)
            days_until = (next_billing - date.today()).days

            billing_data = {
                "subscription_id": subscription_id,
                "hostel_id": hostel_id,
                "plan_name": plan_name,
                "plan_display_name": plan_display_name,
                "cycle_start": current_date,
                "cycle_end": cycle_end,
                "billing_cycle": billing_cycle.value,
                "amount": amount,
                "next_billing_date": next_billing,
                "days_until_billing": max(0, days_until),
                "auto_renew": auto_renew,
                "is_in_trial": is_trial and current_date <= start_date + timedelta(days=trial_days_remaining or 0),
                "trial_days_remaining": trial_days_remaining if is_trial else None,
                "is_billed": False,
            }

            cycle = self.create_billing_cycle(billing_data)
            cycles.append(cycle)

            current_date = next_billing

        return cycles

    # ==================== READ OPERATIONS ====================

    def get_by_id(
        self,
        billing_cycle_id: UUID,
    ) -> Optional[SubscriptionBillingCycle]:
        """
        Get billing cycle by ID.

        Args:
            billing_cycle_id: Billing cycle ID

        Returns:
            Billing cycle if found
        """
        query = select(SubscriptionBillingCycle).where(
            SubscriptionBillingCycle.id == billing_cycle_id
        )
        result = self.db.execute(query)
        return result.scalar_one_or_none()

    def get_by_subscription(
        self,
        subscription_id: UUID,
    ) -> List[SubscriptionBillingCycle]:
        """
        Get all billing cycles for subscription.

        Args:
            subscription_id: Subscription ID

        Returns:
            List of billing cycles
        """
        query = (
            select(SubscriptionBillingCycle)
            .where(SubscriptionBillingCycle.subscription_id == subscription_id)
            .order_by(SubscriptionBillingCycle.cycle_start)
        )

        result = self.db.execute(query)
        return list(result.scalars().all())

    def get_current_cycle(
        self,
        subscription_id: UUID,
    ) -> Optional[SubscriptionBillingCycle]:
        """
        Get current active billing cycle for subscription.

        Args:
            subscription_id: Subscription ID

        Returns:
            Current billing cycle if found
        """
        today = date.today()

        query = select(SubscriptionBillingCycle).where(
            and_(
                SubscriptionBillingCycle.subscription_id == subscription_id,
                SubscriptionBillingCycle.cycle_start <= today,
                SubscriptionBillingCycle.cycle_end >= today,
            )
        )

        result = self.db.execute(query)
        return result.scalar_one_or_none()

    def get_upcoming_cycles(
        self,
        subscription_id: UUID,
    ) -> List[SubscriptionBillingCycle]:
        """
        Get upcoming billing cycles for subscription.

        Args:
            subscription_id: Subscription ID

        Returns:
            List of upcoming billing cycles
        """
        today = date.today()

        query = (
            select(SubscriptionBillingCycle)
            .where(
                and_(
                    SubscriptionBillingCycle.subscription_id == subscription_id,
                    SubscriptionBillingCycle.cycle_start > today,
                )
            )
            .order_by(SubscriptionBillingCycle.cycle_start)
        )

        result = self.db.execute(query)
        return list(result.scalars().all())

    def get_past_cycles(
        self,
        subscription_id: UUID,
        limit: Optional[int] = None,
    ) -> List[SubscriptionBillingCycle]:
        """
        Get past billing cycles for subscription.

        Args:
            subscription_id: Subscription ID
            limit: Maximum number of cycles to return

        Returns:
            List of past billing cycles
        """
        today = date.today()

        query = (
            select(SubscriptionBillingCycle)
            .where(
                and_(
                    SubscriptionBillingCycle.subscription_id == subscription_id,
                    SubscriptionBillingCycle.cycle_end < today,
                )
            )
            .order_by(SubscriptionBillingCycle.cycle_end.desc())
        )

        if limit:
            query = query.limit(limit)

        result = self.db.execute(query)
        return list(result.scalars().all())

    def get_cycles_by_hostel(
        self,
        hostel_id: UUID,
        active_only: bool = True,
    ) -> List[SubscriptionBillingCycle]:
        """
        Get billing cycles for hostel.

        Args:
            hostel_id: Hostel ID
            active_only: Only return current/future cycles

        Returns:
            List of billing cycles
        """
        query = select(SubscriptionBillingCycle).where(
            SubscriptionBillingCycle.hostel_id == hostel_id
        )

        if active_only:
            today = date.today()
            query = query.where(SubscriptionBillingCycle.cycle_end >= today)

        query = query.order_by(SubscriptionBillingCycle.cycle_start)

        result = self.db.execute(query)
        return list(result.scalars().all())

    def get_billing_due_today(self) -> List[SubscriptionBillingCycle]:
        """
        Get billing cycles due for billing today.

        Returns:
            List of cycles due for billing
        """
        today = date.today()

        query = (
            select(SubscriptionBillingCycle)
            .where(
                and_(
                    SubscriptionBillingCycle.next_billing_date == today,
                    SubscriptionBillingCycle.is_billed == False,
                    SubscriptionBillingCycle.auto_renew == True,
                )
            )
            .order_by(SubscriptionBillingCycle.hostel_id)
        )

        result = self.db.execute(query)
        return list(result.scalars().all())

    def get_billing_due_within_days(
        self,
        days: int,
    ) -> List[SubscriptionBillingCycle]:
        """
        Get billing cycles due within specified days.

        Args:
            days: Number of days to look ahead

        Returns:
            List of upcoming billing cycles
        """
        today = date.today()
        end_date = today + timedelta(days=days)

        query = (
            select(SubscriptionBillingCycle)
            .where(
                and_(
                    SubscriptionBillingCycle.next_billing_date >= today,
                    SubscriptionBillingCycle.next_billing_date <= end_date,
                    SubscriptionBillingCycle.is_billed == False,
                )
            )
            .order_by(SubscriptionBillingCycle.next_billing_date)
        )

        result = self.db.execute(query)
        return list(result.scalars().all())

    def get_trial_cycles(
        self,
        active_only: bool = True,
    ) -> List[SubscriptionBillingCycle]:
        """
        Get billing cycles in trial period.

        Args:
            active_only: Only return current trial cycles

        Returns:
            List of trial billing cycles
        """
        query = select(SubscriptionBillingCycle).where(
            SubscriptionBillingCycle.is_in_trial == True
        )

        if active_only:
            today = date.today()
            query = query.where(
                and_(
                    SubscriptionBillingCycle.cycle_start <= today,
                    SubscriptionBillingCycle.cycle_end >= today,
                )
            )

        query = query.order_by(SubscriptionBillingCycle.cycle_start)

        result = self.db.execute(query)
        return list(result.scalars().all())

    def get_unbilled_cycles(
        self,
        past_only: bool = False,
    ) -> List[SubscriptionBillingCycle]:
        """
        Get cycles that haven't been billed yet.

        Args:
            past_only: Only return overdue unbilled cycles

        Returns:
            List of unbilled cycles
        """
        query = select(SubscriptionBillingCycle).where(
            SubscriptionBillingCycle.is_billed == False
        )

        if past_only:
            today = date.today()
            query = query.where(SubscriptionBillingCycle.next_billing_date < today)

        query = query.order_by(SubscriptionBillingCycle.next_billing_date)

        result = self.db.execute(query)
        return list(result.scalars().all())

    # ==================== UPDATE OPERATIONS ====================

    def update_billing_cycle(
        self,
        billing_cycle_id: UUID,
        update_data: Dict[str, Any],
    ) -> Optional[SubscriptionBillingCycle]:
        """
        Update billing cycle.

        Args:
            billing_cycle_id: Billing cycle ID
            update_data: Updated data

        Returns:
            Updated billing cycle
        """
        billing_cycle = self.get_by_id(billing_cycle_id)
        if not billing_cycle:
            return None

        for key, value in update_data.items():
            if hasattr(billing_cycle, key):
                setattr(billing_cycle, key, value)

        billing_cycle.updated_at = datetime.utcnow()
        self.db.flush()
        return billing_cycle

    def mark_as_billed(
        self,
        billing_cycle_id: UUID,
        billing_date: Optional[date] = None,
    ) -> Optional[SubscriptionBillingCycle]:
        """
        Mark billing cycle as billed.

        Args:
            billing_cycle_id: Billing cycle ID
            billing_date: Date of billing

        Returns:
            Updated billing cycle
        """
        billing_cycle = self.get_by_id(billing_cycle_id)
        if not billing_cycle:
            return None

        billing_cycle.is_billed = True
        billing_cycle.billing_date = billing_date or date.today()
        billing_cycle.updated_at = datetime.utcnow()

        self.db.flush()
        return billing_cycle

    def update_days_until_billing(
        self,
        billing_cycle_id: UUID,
    ) -> Optional[SubscriptionBillingCycle]:
        """
        Recalculate and update days until billing.

        Args:
            billing_cycle_id: Billing cycle ID

        Returns:
            Updated billing cycle
        """
        billing_cycle = self.get_by_id(billing_cycle_id)
        if not billing_cycle:
            return None

        today = date.today()
        days_until = (billing_cycle.next_billing_date - today).days
        billing_cycle.days_until_billing = max(0, days_until)
        billing_cycle.updated_at = datetime.utcnow()

        self.db.flush()
        return billing_cycle

    def update_trial_days(
        self,
        billing_cycle_id: UUID,
        trial_days_remaining: int,
    ) -> Optional[SubscriptionBillingCycle]:
        """
        Update trial days remaining.

        Args:
            billing_cycle_id: Billing cycle ID
            trial_days_remaining: Remaining trial days

        Returns:
            Updated billing cycle
        """
        billing_cycle = self.get_by_id(billing_cycle_id)
        if not billing_cycle:
            return None

        billing_cycle.trial_days_remaining = trial_days_remaining
        billing_cycle.is_in_trial = trial_days_remaining > 0
        billing_cycle.updated_at = datetime.utcnow()

        self.db.flush()
        return billing_cycle

    def end_trial_period(
        self,
        billing_cycle_id: UUID,
    ) -> Optional[SubscriptionBillingCycle]:
        """
        End trial period for billing cycle.

        Args:
            billing_cycle_id: Billing cycle ID

        Returns:
            Updated billing cycle
        """
        billing_cycle = self.get_by_id(billing_cycle_id)
        if not billing_cycle:
            return None

        billing_cycle.is_in_trial = False
        billing_cycle.trial_days_remaining = None
        billing_cycle.updated_at = datetime.utcnow()

        self.db.flush()
        return billing_cycle

    def update_auto_renew(
        self,
        subscription_id: UUID,
        auto_renew: bool,
    ) -> int:
        """
        Update auto-renew status for all cycles of subscription.

        Args:
            subscription_id: Subscription ID
            auto_renew: New auto-renew status

        Returns:
            Number of cycles updated
        """
        cycles = self.get_by_subscription(subscription_id)
        count = 0

        for cycle in cycles:
            cycle.auto_renew = auto_renew
            cycle.updated_at = datetime.utcnow()
            count += 1

        self.db.flush()
        return count

    # ==================== DELETE OPERATIONS ====================

    def delete_billing_cycle(
        self,
        billing_cycle_id: UUID,
    ) -> bool:
        """
        Delete billing cycle.

        Args:
            billing_cycle_id: Billing cycle ID

        Returns:
            True if deleted
        """
        billing_cycle = self.get_by_id(billing_cycle_id)
        if not billing_cycle:
            return False

        self.db.delete(billing_cycle)
        self.db.flush()
        return True

    def delete_cycles_for_subscription(
        self,
        subscription_id: UUID,
    ) -> int:
        """
        Delete all billing cycles for subscription.

        Args:
            subscription_id: Subscription ID

        Returns:
            Number of cycles deleted
        """
        cycles = self.get_by_subscription(subscription_id)
        count = len(cycles)

        for cycle in cycles:
            self.db.delete(cycle)

        self.db.flush()
        return count

    def delete_future_cycles(
        self,
        subscription_id: UUID,
    ) -> int:
        """
        Delete future unbilled cycles for subscription.

        Args:
            subscription_id: Subscription ID

        Returns:
            Number of cycles deleted
        """
        today = date.today()
        cycles = self.get_by_subscription(subscription_id)
        count = 0

        for cycle in cycles:
            if cycle.cycle_start > today and not cycle.is_billed:
                self.db.delete(cycle)
                count += 1

        self.db.flush()
        return count

    # ==================== ANALYTICS & REPORTING ====================

    def get_billing_statistics(self) -> Dict[str, Any]:
        """
        Get overall billing statistics.

        Returns:
            Dictionary with billing statistics
        """
        total_cycles = self.db.query(
            func.count(SubscriptionBillingCycle.id)
        ).scalar()

        billed_cycles = (
            self.db.query(func.count(SubscriptionBillingCycle.id))
            .filter(SubscriptionBillingCycle.is_billed == True)
            .scalar()
        )

        trial_cycles = (
            self.db.query(func.count(SubscriptionBillingCycle.id))
            .filter(SubscriptionBillingCycle.is_in_trial == True)
            .scalar()
        )

        auto_renew_cycles = (
            self.db.query(func.count(SubscriptionBillingCycle.id))
            .filter(SubscriptionBillingCycle.auto_renew == True)
            .scalar()
        )

        # Current cycles
        today = date.today()
        current_cycles = (
            self.db.query(func.count(SubscriptionBillingCycle.id))
            .filter(
                and_(
                    SubscriptionBillingCycle.cycle_start <= today,
                    SubscriptionBillingCycle.cycle_end >= today,
                )
            )
            .scalar()
        )

        return {
            "total_billing_cycles": total_cycles,
            "billed_cycles": billed_cycles,
            "unbilled_cycles": total_cycles - billed_cycles,
            "trial_cycles": trial_cycles,
            "auto_renew_enabled": auto_renew_cycles,
            "current_active_cycles": current_cycles,
        }

    def get_revenue_forecast(
        self,
        days_ahead: int = 30,
    ) -> Dict[str, Any]:
        """
        Forecast revenue from upcoming billing cycles.

        Args:
            days_ahead: Number of days to forecast

        Returns:
            Revenue forecast data
        """
        today = date.today()
        end_date = today + timedelta(days=days_ahead)

        query = select(SubscriptionBillingCycle).where(
            and_(
                SubscriptionBillingCycle.next_billing_date >= today,
                SubscriptionBillingCycle.next_billing_date <= end_date,
                SubscriptionBillingCycle.is_billed == False,
                SubscriptionBillingCycle.auto_renew == True,
            )
        )

        result = self.db.execute(query)
        upcoming_cycles = list(result.scalars().all())

        total_revenue = sum(cycle.amount for cycle in upcoming_cycles)
        cycle_count = len(upcoming_cycles)

        # Group by billing date
        by_date = {}
        for cycle in upcoming_cycles:
            date_key = str(cycle.next_billing_date)
            if date_key not in by_date:
                by_date[date_key] = {"count": 0, "amount": Decimal("0")}
            by_date[date_key]["count"] += 1
            by_date[date_key]["amount"] += cycle.amount

        return {
            "forecast_period_days": days_ahead,
            "total_expected_revenue": float(total_revenue),
            "total_billing_cycles": cycle_count,
            "by_date": {
                k: {"count": v["count"], "amount": float(v["amount"])}
                for k, v in by_date.items()
            },
        }

    def get_billing_summary_by_hostel(
        self,
        hostel_id: UUID,
    ) -> Dict[str, Any]:
        """
        Get billing summary for specific hostel.

        Args:
            hostel_id: Hostel ID

        Returns:
            Billing summary data
        """
        cycles = self.get_cycles_by_hostel(hostel_id, active_only=False)

        total_cycles = len(cycles)
        billed_cycles = sum(1 for cycle in cycles if cycle.is_billed)
        total_billed_amount = sum(
            cycle.amount for cycle in cycles if cycle.is_billed
        )

        current_cycle = self.get_current_cycle(
            cycles[0].subscription_id if cycles else None
        )
        upcoming_cycles = [
            cycle for cycle in cycles if cycle.cycle_start > date.today()
        ]

        return {
            "hostel_id": str(hostel_id),
            "total_cycles": total_cycles,
            "billed_cycles": billed_cycles,
            "unbilled_cycles": total_cycles - billed_cycles,
            "total_billed_amount": float(total_billed_amount),
            "current_cycle": {
                "cycle_start": str(current_cycle.cycle_start),
                "cycle_end": str(current_cycle.cycle_end),
                "amount": float(current_cycle.amount),
                "days_until_billing": current_cycle.days_until_billing,
            }
            if current_cycle
            else None,
            "upcoming_cycles_count": len(upcoming_cycles),
        }

    # ==================== BATCH OPERATIONS ====================

    def batch_update_days_until_billing(
        self,
        subscription_ids: Optional[List[UUID]] = None,
    ) -> int:
        """
        Batch update days until billing for multiple subscriptions.

        Args:
            subscription_ids: Optional list of subscription IDs, None for all

        Returns:
            Number of cycles updated
        """
        if subscription_ids:
            query = select(SubscriptionBillingCycle).where(
                SubscriptionBillingCycle.subscription_id.in_(subscription_ids)
            )
        else:
            query = select(SubscriptionBillingCycle)

        result = self.db.execute(query)
        cycles = list(result.scalars().all())

        today = date.today()
        count = 0

        for cycle in cycles:
            days_until = (cycle.next_billing_date - today).days
            cycle.days_until_billing = max(0, days_until)
            count += 1

        self.db.flush()
        return count

    def batch_mark_as_billed(
        self,
        billing_cycle_ids: List[UUID],
        billing_date: Optional[date] = None,
    ) -> int:
        """
        Batch mark cycles as billed.

        Args:
            billing_cycle_ids: List of billing cycle IDs
            billing_date: Date of billing

        Returns:
            Number of cycles marked as billed
        """
        count = 0
        for cycle_id in billing_cycle_ids:
            if self.mark_as_billed(cycle_id, billing_date):
                count += 1
        return count