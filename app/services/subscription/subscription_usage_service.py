"""
Subscription Usage Service

Manages subscription feature usage and limits.
"""

from __future__ import annotations

from typing import Dict, Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.subscription import SubscriptionFeatureRepository, SubscriptionAggregateRepository
from app.core.exceptions import ValidationException


class SubscriptionUsageService:
    """
    High-level service for subscription usage and limits.

    Responsibilities:
    - Retrieve feature usage & limit info
    - Check if a feature can be used given current usage and limits
    - Increment/decrement usage
    """

    def __init__(
        self,
        feature_repo: SubscriptionFeatureRepository,
        aggregate_repo: SubscriptionAggregateRepository,
    ) -> None:
        self.feature_repo = feature_repo
        self.aggregate_repo = aggregate_repo

    def get_usage_overview(
        self,
        db: Session,
        subscription_id: UUID,
    ) -> Dict[str, Any]:
        """
        Get aggregated usage & limit overview for a subscription.
        """
        data = self.aggregate_repo.get_subscription_usage_overview(
            db,
            subscription_id=subscription_id,
        )
        if not data:
            raise ValidationException("No usage data available for subscription")
        return data

    def can_use_feature(
        self,
        db: Session,
        subscription_id: UUID,
        feature_key: str,
        amount: int = 1,
    ) -> bool:
        """
        Check if a feature can be used 'amount' times under current limits.
        """
        return self.feature_repo.can_use_feature(
            db,
            subscription_id=subscription_id,
            feature_key=feature_key,
            amount=amount,
        )

    def increment_feature_usage(
        self,
        db: Session,
        subscription_id: UUID,
        feature_key: str,
        amount: int = 1,
    ) -> None:
        """
        Increment usage for a feature, raising if over the limit.
        """
        if not self.can_use_feature(db, subscription_id, feature_key, amount):
            raise ValidationException(
                f"Usage limit exceeded for feature '{feature_key}'"
            )

        self.feature_repo.increment_usage(
            db,
            subscription_id=subscription_id,
            feature_key=feature_key,
            amount=amount,
        )

    def reset_feature_usage(
        self,
        db: Session,
        subscription_id: UUID,
        feature_key: str,
    ) -> None:
        """
        Reset usage counter for a feature.
        """
        self.feature_repo.reset_usage(
            db,
            subscription_id=subscription_id,
            feature_key=feature_key,
        )