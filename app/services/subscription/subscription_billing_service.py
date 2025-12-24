"""
Subscription Billing Service

Handles subscription billing cycle information and operations.
"""

from __future__ import annotations

from typing import List
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.subscription import SubscriptionBillingRepository
from app.schemas.subscription import BillingCycleInfo
from app.core.exceptions import ValidationException


class SubscriptionBillingService:
    """
    High-level service for subscription billing cycles.

    Responsibilities:
    - Get current billing cycle info
    - List upcoming/prior billing cycles
    - Adjust billing cycles if subscription terms change
    """

    def __init__(
        self,
        billing_repo: SubscriptionBillingRepository,
    ) -> None:
        self.billing_repo = billing_repo

    def get_billing_cycle_info(
        self,
        db: Session,
        subscription_id: UUID,
    ) -> BillingCycleInfo:
        """
        Get current billing cycle info for a subscription.
        """
        info = self.billing_repo.get_current_billing_cycle_info(db, subscription_id)
        if not info:
            raise ValidationException("Billing cycle not found for subscription")

        return BillingCycleInfo.model_validate(info)

    def list_billing_cycles(
        self,
        db: Session,
        subscription_id: UUID,
        limit: int = 12,
    ) -> List[BillingCycleInfo]:
        """
        List recent billing cycles (past + upcoming) for a subscription.
        """
        cycles = self.billing_repo.get_billing_cycles(
            db,
            subscription_id=subscription_id,
            limit=limit,
        )
        return [BillingCycleInfo.model_validate(c) for c in cycles]

    def recalculate_billing_cycles(
        self,
        db: Session,
        subscription_id: UUID,
    ) -> None:
        """
        Recalculate billing cycles when subscription terms change.

        Delegates to repository logic.
        """
        self.billing_repo.recalculate_billing_cycles(db, subscription_id)