"""
Subscription Aggregate Repository.

Provides aggregated queries and complex operations across
multiple subscription-related entities.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.models.subscription.booking_commission import BookingCommission
from app.models.subscription.subscription import Subscription
from app.models.subscription.subscription_billing import SubscriptionBillingCycle
from app.models.subscription.subscription_feature import (
    SubscriptionFeatureUsage,
    SubscriptionLimit,
)
from app.models.subscription.subscription_invoice import SubscriptionInvoice
from app.models.subscription.subscription_plan import SubscriptionPlan
from app.schemas.common.enums import SubscriptionStatus
from app.schemas.subscription.subscription_billing import InvoiceStatus
from app.schemas.subscription.commission import CommissionStatus


class SubscriptionAggregateRepository:
    """
    Repository for aggregated subscription operations.

    Provides complex queries and analytics across multiple
    subscription-related tables.
    """

    def __init__(self, db: Session):
        """Initialize repository with database session."""
        self.db = db

    # ==================== DASHBOARD METRICS ====================

    def get_subscription_dashboard(
        self,
        hostel_id: Optional[UUID] = None,
    ) -> Dict[str, Any]:
        """
        Get comprehensive subscription dashboard metrics.

        Args:
            hostel_id: Optional hostel ID filter

        Returns:
            Dashboard metrics
        """
        # Subscription metrics
        subscription_query = select(Subscription).where(
            Subscription.is_deleted == False
        )
        if hostel_id:
            subscription_query = subscription_query.where(
                Subscription.hostel_id == hostel_id
            )
        
        subscriptions_result = self.db.execute(subscription_query)
        subscriptions = list(subscriptions_result.scalars().all())
        
        active_subscriptions = sum(
            1 for s in subscriptions if s.status == SubscriptionStatus.ACTIVE
        )
        trial_subscriptions = sum(1 for s in subscriptions if s.is_trial)
        expiring_soon = sum(1 for s in subscriptions if s.is_expiring_soon)
        
        # Revenue metrics
        mrr = sum(
            s.amount for s in subscriptions
            if s.status == SubscriptionStatus.ACTIVE and s.billing_cycle.value == "monthly"
        )
        arr = mrr * 12
        
        # Invoice metrics
        invoice_query = select(SubscriptionInvoice)
        if hostel_id:
            invoice_query = invoice_query.where(
                SubscriptionInvoice.hostel_id == hostel_id
            )
        
        invoices_result = self.db.execute(invoice_query)
        invoices = list(invoices_result.scalars().all())
        
        pending_invoices = sum(
            1 for i in invoices
            if i.status in [InvoiceStatus.PENDING, InvoiceStatus.SENT]
        )
        overdue_invoices = sum(1 for i in invoices if i.is_overdue)
        total_outstanding = sum(
            i.amount_due for i in invoices
            if i.status in [InvoiceStatus.PENDING, InvoiceStatus.SENT, InvoiceStatus.OVERDUE]
        )
        
        # Commission metrics
        commission_query = select(BookingCommission)
        if hostel_id:
            commission_query = commission_query.where(
                BookingCommission.hostel_id == hostel_id
            )
        
        commissions_result = self.db.execute(commission_query)
        commissions = list(commissions_result.scalars().all())
        
        pending_commissions = sum(
            c.commission_amount for c in commissions
            if c.status == CommissionStatus.PENDING
        )
        
        return {
            "subscriptions": {
                "total": len(subscriptions),
                "active": active_subscriptions,
                "trial": trial_subscriptions,
                "expiring_soon": expiring_soon,
            },
            "revenue": {
                "mrr": float(mrr),
                "arr": float(arr),
            },
            "invoices": {
                "pending": pending_invoices,
                "overdue": overdue_invoices,
                "total_outstanding": float(total_outstanding),
            },
            "commissions": {
                "pending_amount": float(pending_commissions),
                "pending_count": sum(
                    1 for c in commissions if c.status == CommissionStatus.PENDING
                ),
            },
        }

    def get_hostel_subscription_overview(
        self,
        hostel_id: UUID,
    ) -> Dict[str, Any]:
        """
        Get complete subscription overview for hostel.

        Args:
            hostel_id: Hostel ID

        Returns:
            Comprehensive subscription overview
        """
        # Active subscription
        subscription_query = (
            select(Subscription)
            .where(
                and_(
                    Subscription.hostel_id == hostel_id,
                    Subscription.status == SubscriptionStatus.ACTIVE,
                    Subscription.is_deleted == False,
                )
            )
        )
        result = self.db.execute(subscription_query)
        subscription = result.scalar_one_or_none()
        
        if not subscription:
            return {"error": "No active subscription found"}
        
        # Plan details
        plan_query = select(SubscriptionPlan).where(
            SubscriptionPlan.id == subscription.plan_id
        )
        plan_result = self.db.execute(plan_query)
        plan = plan_result.scalar_one_or_none()
        
        # Current billing cycle
        billing_query = (
            select(SubscriptionBillingCycle)
            .where(
                and_(
                    SubscriptionBillingCycle.subscription_id == subscription.id,
                    SubscriptionBillingCycle.cycle_start <= date.today(),
                    SubscriptionBillingCycle.cycle_end >= date.today(),
                )
            )
        )
        billing_result = self.db.execute(billing_query)
        current_cycle = billing_result.scalar_one_or_none()
        
        # Feature usage
        feature_query = select(SubscriptionFeatureUsage).where(
            SubscriptionFeatureUsage.subscription_id == subscription.id
        )
        features_result = self.db.execute(feature_query)
        features = list(features_result.scalars().all())
        
        # Limits
        limits_query = select(SubscriptionLimit).where(
            SubscriptionLimit.subscription_id == subscription.id
        )
        limits_result = self.db.execute(limits_query)
        limits = list(limits_result.scalars().all())
        
        # Recent invoices
        invoice_query = (
            select(SubscriptionInvoice)
            .where(SubscriptionInvoice.hostel_id == hostel_id)
            .order_by(SubscriptionInvoice.invoice_date.desc())
            .limit(5)
        )
        invoices_result = self.db.execute(invoice_query)
        recent_invoices = list(invoices_result.scalars().all())
        
        # Commissions
        commission_query = (
            select(BookingCommission)
            .where(BookingCommission.hostel_id == hostel_id)
            .order_by(BookingCommission.created_at.desc())
            .limit(5)
        )
        commissions_result = self.db.execute(commission_query)
        recent_commissions = list(commissions_result.scalars().all())
        
        return {
            "subscription": {
                "id": str(subscription.id),
                "reference": subscription.subscription_reference,
                "status": subscription.status.value,
                "start_date": str(subscription.start_date),
                "end_date": str(subscription.end_date),
                "days_until_expiry": subscription.days_until_expiry,
                "auto_renew": subscription.auto_renew,
                "is_trial": subscription.is_trial,
            },
            "plan": {
                "id": str(plan.id) if plan else None,
                "name": plan.display_name if plan else None,
                "type": plan.plan_type.value if plan else None,
            },
            "current_cycle": {
                "start": str(current_cycle.cycle_start) if current_cycle else None,
                "end": str(current_cycle.cycle_end) if current_cycle else None,
                "days_until_billing": current_cycle.days_until_billing if current_cycle else None,
                "amount": float(current_cycle.amount) if current_cycle else None,
            } if current_cycle else None,
            "features": {
                "total": len(features),
                "enabled": sum(1 for f in features if f.is_enabled),
                "exceeded": sum(1 for f in features if f.is_limit_exceeded),
            },
            "limits": {
                "total": len(limits),
                "exceeded": sum(1 for l in limits if l.is_exceeded),
            },
            "recent_invoices": [
                {
                    "invoice_number": inv.invoice_number,
                    "amount": float(inv.amount),
                    "status": inv.status.value,
                    "due_date": str(inv.due_date),
                }
                for inv in recent_invoices
            ],
            "recent_commissions": [
                {
                    "amount": float(comm.commission_amount),
                    "status": comm.status.value,
                    "due_date": str(comm.due_date) if comm.due_date else None,
                }
                for comm in recent_commissions
            ],
        }

    # ==================== FINANCIAL ANALYTICS ====================

    def get_revenue_analytics(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> Dict[str, Any]:
        """
        Get comprehensive revenue analytics.

        Args:
            start_date: Analytics period start
            end_date: Analytics period end

        Returns:
            Revenue analytics data
        """
        if not start_date:
            start_date = date.today() - timedelta(days=30)
        if not end_date:
            end_date = date.today()
        
        # Subscription revenue
        active_subs = (
            self.db.query(Subscription)
            .filter(
                and_(
                    Subscription.status == SubscriptionStatus.ACTIVE,
                    Subscription.is_deleted == False,
                )
            )
            .all()
        )
        
        monthly_revenue = sum(
            s.amount for s in active_subs
            if s.billing_cycle.value == "monthly"
        )
        yearly_revenue = sum(
            s.amount for s in active_subs
            if s.billing_cycle.value == "yearly"
        )
        
        mrr = monthly_revenue + (yearly_revenue / 12)
        arr = mrr * 12
        
        # Invoices collected in period
        collected_query = (
            select(SubscriptionInvoice)
            .where(
                and_(
                    SubscriptionInvoice.status == InvoiceStatus.PAID,
                    SubscriptionInvoice.payment_date >= start_date,
                    SubscriptionInvoice.payment_date <= end_date,
                )
            )
        )
        collected_result = self.db.execute(collected_query)
        collected_invoices = list(collected_result.scalars().all())
        
        total_collected = sum(inv.amount for inv in collected_invoices)
        
        # Commissions paid in period
        paid_commissions_query = (
            select(BookingCommission)
            .where(
                and_(
                    BookingCommission.status == CommissionStatus.PAID,
                    BookingCommission.paid_date >= start_date,
                    BookingCommission.paid_date <= end_date,
                )
            )
        )
        paid_comm_result = self.db.execute(paid_commissions_query)
        paid_commissions = list(paid_comm_result.scalars().all())
        
        total_commission_paid = sum(c.commission_amount for c in paid_commissions)
        
        # Net revenue
        net_revenue = total_collected - total_commission_paid
        
        return {
            "period": {
                "start": str(start_date),
                "end": str(end_date),
            },
            "recurring_revenue": {
                "mrr": float(mrr),
                "arr": float(arr),
            },
            "collected_revenue": {
                "total": float(total_collected),
                "invoice_count": len(collected_invoices),
                "average_invoice": float(
                    total_collected / len(collected_invoices)
                    if collected_invoices else 0
                ),
            },
            "commissions": {
                "total_paid": float(total_commission_paid),
                "commission_count": len(paid_commissions),
            },
            "net_revenue": float(net_revenue),
        }

    def get_plan_performance(self) -> List[Dict[str, Any]]:
        """
        Get performance metrics for each subscription plan.

        Returns:
            List of plan performance data
        """
        plans_query = select(SubscriptionPlan).where(
            SubscriptionPlan.is_active == True
        )
        plans_result = self.db.execute(plans_query)
        plans = list(plans_result.scalars().all())
        
        performance = []
        
        for plan in plans:
            # Get subscriptions for this plan
            subs_query = (
                select(Subscription)
                .where(
                    and_(
                        Subscription.plan_id == plan.id,
                        Subscription.is_deleted == False,
                    )
                )
            )
            subs_result = self.db.execute(subs_query)
            subscriptions = list(subs_result.scalars().all())
            
            active_count = sum(
                1 for s in subscriptions if s.status == SubscriptionStatus.ACTIVE
            )
            trial_count = sum(1 for s in subscriptions if s.is_trial)
            
            # Revenue from this plan
            monthly_revenue = sum(
                s.amount for s in subscriptions
                if s.status == SubscriptionStatus.ACTIVE and s.billing_cycle.value == "monthly"
            )
            yearly_revenue = sum(
                s.amount for s in subscriptions
                if s.status == SubscriptionStatus.ACTIVE and s.billing_cycle.value == "yearly"
            )
            
            total_revenue = monthly_revenue + (yearly_revenue / 12)
            
            performance.append({
                "plan_id": str(plan.id),
                "plan_name": plan.display_name,
                "plan_type": plan.plan_type.value,
                "total_subscriptions": len(subscriptions),
                "active_subscriptions": active_count,
                "trial_subscriptions": trial_count,
                "monthly_revenue": float(monthly_revenue),
                "yearly_revenue": float(yearly_revenue),
                "total_mrr": float(total_revenue),
            })
        
        return sorted(performance, key=lambda x: x["total_mrr"], reverse=True)

    # ==================== HEALTH CHECKS ====================

    def get_subscription_health(
        self,
        hostel_id: Optional[UUID] = None,
    ) -> Dict[str, Any]:
        """
        Get subscription health indicators.

        Args:
            hostel_id: Optional hostel ID filter

        Returns:
            Health indicators and warnings
        """
        warnings = []
        critical_issues = []
        
        # Check for expiring subscriptions
        expiring_query = select(Subscription).where(
            and_(
                Subscription.status == SubscriptionStatus.ACTIVE,
                Subscription.end_date <= date.today() + timedelta(days=7),
                Subscription.is_deleted == False,
            )
        )
        if hostel_id:
            expiring_query = expiring_query.where(Subscription.hostel_id == hostel_id)
        
        expiring_result = self.db.execute(expiring_query)
        expiring_subs = list(expiring_result.scalars().all())
        
        if expiring_subs:
            warnings.append({
                "type": "expiring_subscriptions",
                "count": len(expiring_subs),
                "message": f"{len(expiring_subs)} subscription(s) expiring within 7 days",
            })
        
        # Check for overdue invoices
        overdue_query = select(SubscriptionInvoice).where(
            and_(
                SubscriptionInvoice.status.in_([
                    InvoiceStatus.PENDING,
                    InvoiceStatus.SENT,
                ]),
                SubscriptionInvoice.due_date < date.today(),
            )
        )
        if hostel_id:
            overdue_query = overdue_query.where(SubscriptionInvoice.hostel_id == hostel_id)
        
        overdue_result = self.db.execute(overdue_query)
        overdue_invoices = list(overdue_result.scalars().all())
        
        if overdue_invoices:
            critical_issues.append({
                "type": "overdue_invoices",
                "count": len(overdue_invoices),
                "total_amount": float(sum(inv.amount_due for inv in overdue_invoices)),
                "message": f"{len(overdue_invoices)} overdue invoice(s)",
            })
        
        # Check for exceeded limits
        if hostel_id:
            # Get active subscription for hostel
            sub_query = (
                select(Subscription)
                .where(
                    and_(
                        Subscription.hostel_id == hostel_id,
                        Subscription.status == SubscriptionStatus.ACTIVE,
                        Subscription.is_deleted == False,
                    )
                )
            )
            sub_result = self.db.execute(sub_query)
            subscription = sub_result.scalar_one_or_none()
            
            if subscription:
                limits_query = (
                    select(SubscriptionLimit)
                    .where(
                        and_(
                            SubscriptionLimit.subscription_id == subscription.id,
                            SubscriptionLimit.is_exceeded == True,
                        )
                    )
                )
                limits_result = self.db.execute(limits_query)
                exceeded_limits = list(limits_result.scalars().all())
                
                if exceeded_limits:
                    critical_issues.append({
                        "type": "exceeded_limits",
                        "count": len(exceeded_limits),
                        "limits": [l.limit_type for l in exceeded_limits],
                        "message": f"{len(exceeded_limits)} limit(s) exceeded",
                    })
        
        health_score = 100
        health_score -= len(warnings) * 10
        health_score -= len(critical_issues) * 20
        health_score = max(0, health_score)
        
        return {
            "health_score": health_score,
            "status": "healthy" if health_score >= 80 else "warning" if health_score >= 50 else "critical",
            "warnings": warnings,
            "critical_issues": critical_issues,
        }

    # ==================== USAGE ANALYTICS ====================

    def get_feature_usage_analytics(
        self,
        subscription_id: UUID,
    ) -> Dict[str, Any]:
        """
        Get detailed feature usage analytics for subscription.

        Args:
            subscription_id: Subscription ID

        Returns:
            Feature usage analytics
        """
        features_query = select(SubscriptionFeatureUsage).where(
            SubscriptionFeatureUsage.subscription_id == subscription_id
        )
        features_result = self.db.execute(features_query)
        features = list(features_result.scalars().all())
        
        usage_data = []
        for feature in features:
            usage_percent = feature.usage_percentage
            
            usage_data.append({
                "feature_key": feature.feature_key,
                "feature_name": feature.feature_name,
                "current_usage": feature.current_usage,
                "usage_limit": feature.usage_limit,
                "usage_percentage": float(usage_percent) if usage_percent else None,
                "remaining": feature.remaining_usage,
                "is_enabled": feature.is_enabled,
                "is_exceeded": feature.is_limit_exceeded,
                "is_near_limit": feature.is_near_limit(),
                "last_used": feature.last_used_at.isoformat() if feature.last_used_at else None,
            })
        
        return {
            "subscription_id": str(subscription_id),
            "total_features": len(features),
            "enabled_features": sum(1 for f in features if f.is_enabled),
            "features_near_limit": sum(1 for f in features if f.is_near_limit()),
            "features_exceeded": sum(1 for f in features if f.is_limit_exceeded),
            "features": usage_data,
        }

    # ==================== RETENTION ANALYTICS ====================

    def get_retention_metrics(
        self,
        period_days: int = 90,
    ) -> Dict[str, Any]:
        """
        Get subscription retention metrics.

        Args:
            period_days: Period in days to analyze

        Returns:
            Retention metrics
        """
        start_date = date.today() - timedelta(days=period_days)
        
        # Subscriptions at start of period
        start_query = select(Subscription).where(
            and_(
                Subscription.start_date < start_date,
                Subscription.is_deleted == False,
            )
        )
        start_result = self.db.execute(start_query)
        start_subscriptions = list(start_result.scalars().all())
        
        # Still active subscriptions
        retained = sum(
            1 for s in start_subscriptions
            if s.status == SubscriptionStatus.ACTIVE
        )
        
        # Cancelled in period
        cancelled_query = select(Subscription).where(
            and_(
                Subscription.status == SubscriptionStatus.CANCELLED,
                Subscription.cancelled_at >= start_date,
                Subscription.is_deleted == False,
            )
        )
        cancelled_result = self.db.execute(cancelled_query)
        cancelled = len(list(cancelled_result.scalars().all()))
        
        retention_rate = (
            (retained / len(start_subscriptions) * 100)
            if start_subscriptions else 0
        )
        churn_rate = 100 - retention_rate
        
        return {
            "period_days": period_days,
            "start_subscriptions": len(start_subscriptions),
            "retained_subscriptions": retained,
            "cancelled_subscriptions": cancelled,
            "retention_rate": retention_rate,
            "churn_rate": churn_rate,
        }