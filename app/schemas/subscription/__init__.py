"""
Subscription schemas package.

This module provides comprehensive schemas for:
- Subscription plans (definition, pricing, features)
- Hostel subscriptions (lifecycle management)
- Billing and invoicing
- Plan upgrades/downgrades
- Commission tracking
"""

# Commission schemas
from app.schemas.subscription.commission import (
    BookingCommissionResponse,
    CommissionConfig,
    CommissionStatus,
    CommissionSummary,
)

# Base subscription schemas
from app.schemas.subscription.subscription_base import (
    SubscriptionBase,
    SubscriptionCreate,
    SubscriptionUpdate,
)

# Billing schemas
from app.schemas.subscription.subscription_billing import (
    BillingCycleInfo,
    GenerateInvoiceRequest,
    InvoiceInfo,
    InvoiceStatus,
)

# Cancellation schemas
from app.schemas.subscription.subscription_cancellation import (
    CancellationRequest,
    CancellationResponse,
    CancellationPreview,
)

# Plan definition schemas
from app.schemas.subscription.subscription_plan_base import (
    PlanCreate,
    PlanUpdate,
    SubscriptionPlanBase,
)

# Plan response schemas
from app.schemas.subscription.subscription_plan_response import (
    PlanComparison,
    PlanFeatures,
    PlanResponse,
)

# Subscription response schemas
from app.schemas.subscription.subscription_response import (
    BillingHistory,
    BillingHistoryItem,
    SubscriptionResponse,
    SubscriptionSummary,
)

# Upgrade/downgrade schemas
from app.schemas.subscription.subscription_upgrade import (
    PlanChangeRequest,
    PlanChangePreview,
    PlanChangeType,
    PlanChangeConfirmation,
)

__all__ = [
    # Enums
    "CommissionStatus",
    "InvoiceStatus",
    "PlanChangeType",
    # Commission
    "CommissionConfig",
    "BookingCommissionResponse",
    "CommissionSummary",
    # Subscription base
    "SubscriptionBase",
    "SubscriptionCreate",
    "SubscriptionUpdate",
    # Billing
    "BillingCycleInfo",
    "GenerateInvoiceRequest",
    "InvoiceInfo",
    # Cancellation
    "CancellationRequest",
    "CancellationResponse",
    "CancellationPreview",
    # Plan base
    "SubscriptionPlanBase",
    "PlanCreate",
    "PlanUpdate",
    # Plan response
    "PlanResponse",
    "PlanFeatures",
    "PlanComparison",
    # Subscription response
    "SubscriptionResponse",
    "SubscriptionSummary",
    "BillingHistoryItem",
    "BillingHistory",
    # Upgrade/downgrade
    "PlanChangeRequest",
    "PlanChangePreview",
    "PlanChangeConfirmation",
]