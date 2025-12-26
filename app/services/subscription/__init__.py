"""
Subscription services package.

Provides comprehensive services for:

- Booking commissions: Commission tracking and payment management
- Billing cycles: Billing period management and calculations
- Invoices: Invoice generation, payment tracking, and status management
- Plans: Subscription plan management and feature comparison
- Subscriptions: Core subscription lifecycle management
- Upgrades/downgrades: Plan change operations with proration
- Usage & limits: Feature usage tracking and limit enforcement

All services follow consistent patterns:
- Comprehensive validation and error handling
- Detailed logging for audit trails
- Transaction safety patterns
- Idempotency where applicable
- Rich analytics and reporting capabilities

Example usage:
    from app.services.subscription import SubscriptionService, SubscriptionPlanService
    
    plan_service = SubscriptionPlanService(plan_repo)
    subscription_service = SubscriptionService(subscription_repo, aggregate_repo)
    
    # Create a plan
    plan = plan_service.create_plan(db, plan_data)
    
    # Create a subscription
    subscription = subscription_service.create_subscription(db, subscription_data)
"""

from .booking_commission_service import BookingCommissionService
from .subscription_billing_service import SubscriptionBillingService
from .subscription_invoice_service import SubscriptionInvoiceService
from .subscription_plan_service import SubscriptionPlanService
from .subscription_service import SubscriptionService
from .subscription_upgrade_service import SubscriptionUpgradeService
from .subscription_usage_service import SubscriptionUsageService

__all__ = [
    "BookingCommissionService",
    "SubscriptionBillingService",
    "SubscriptionInvoiceService",
    "SubscriptionPlanService",
    "SubscriptionService",
    "SubscriptionUpgradeService",
    "SubscriptionUsageService",
]

__version__ = "1.0.0"

# Service descriptions for documentation
SERVICE_DESCRIPTIONS = {
    "BookingCommissionService": "Manages commission records for bookings under subscription programs",
    "SubscriptionBillingService": "Handles subscription billing cycle information and operations",
    "SubscriptionInvoiceService": "Manages invoices generated for subscription billing cycles",
    "SubscriptionPlanService": "Manages subscription plans and their feature sets",
    "SubscriptionService": "Core subscription management operations and lifecycle",
    "SubscriptionUpgradeService": "Handles plan change (upgrade/downgrade) operations",
    "SubscriptionUsageService": "Manages subscription feature usage and limits",
}