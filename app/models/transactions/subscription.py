# app.models/transactions/subscription.py
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Dict, Optional
from uuid import UUID

from sqlalchemy import Date, Enum as SAEnum, JSON, Numeric, String, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.schemas.common.enums import SubscriptionStatus, BillingCycle, SubscriptionPlan
from app.models.base import BaseItem


class SubscriptionPlan(BaseItem):
    """Subscription plan definition."""
    __tablename__ = "sub_plan"

    plan_name: Mapped[str] = mapped_column(String(100), unique=True)
    display_name: Mapped[str] = mapped_column(String(100))
    plan_type: Mapped[SubscriptionPlan] = mapped_column(SAEnum(SubscriptionPlan, name="subscription_plan"))

    description: Mapped[Optional[str]] = mapped_column(String(1000))

    price_monthly: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    price_yearly: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    currency: Mapped[str] = mapped_column(String(3), default="INR")

    features: Mapped[Dict[str, object]] = mapped_column(JSON, default=dict)

    max_hostels: Mapped[Optional[int]] = mapped_column()
    max_rooms_per_hostel: Mapped[Optional[int]] = mapped_column()
    max_students: Mapped[Optional[int]] = mapped_column()

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_public: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(default=0)


class Subscription(BaseItem):
    """Hostel subscription instance."""
    __tablename__ = "sub_subscription"

    hostel_id: Mapped[UUID] = mapped_column(ForeignKey("core_hostel.id"), index=True)
    plan_id: Mapped[UUID] = mapped_column(ForeignKey("sub_plan.id"), index=True)

    subscription_reference: Mapped[str] = mapped_column(String(100), unique=True)

    billing_cycle: Mapped[BillingCycle] = mapped_column(SAEnum(BillingCycle, name="billing_cycle"))
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    currency: Mapped[str] = mapped_column(String(3), default="INR")

    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)

    auto_renew: Mapped[bool] = mapped_column(Boolean, default=True)
    next_billing_date: Mapped[Optional[date]] = mapped_column(Date)

    status: Mapped[SubscriptionStatus] = mapped_column(SAEnum(SubscriptionStatus, name="subscription_status"))