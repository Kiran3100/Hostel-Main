"""
Subscription Usage Service

Manages subscription feature usage and limits.

Improvements:
- Enhanced usage tracking with better granularity
- Added usage analytics and trends
- Improved limit enforcement
- Added usage alerts and notifications
- Better handling of usage resets
- Support for different usage types (counter, quota, boolean)
"""

from __future__ import annotations

import logging
from typing import Dict, Any, List, Optional
from uuid import UUID
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.repositories.subscription import (
    SubscriptionFeatureRepository,
    SubscriptionAggregateRepository,
)
from app.schemas.subscription import UsageType, UsagePeriod
from app.core1.exceptions import ValidationException

logger = logging.getLogger(__name__)


class SubscriptionUsageService:
    """
    High-level service for subscription usage and limits.

    Responsibilities:
    - Retrieve feature usage & limit information
    - Check if a feature can be used given current usage and limits
    - Increment/decrement usage counters
    - Reset usage for billing periods
    - Track usage trends and analytics
    - Send usage alerts when approaching limits
    """

    # Constants
    USAGE_WARNING_THRESHOLD = 0.8  # Warn at 80% usage
    USAGE_CRITICAL_THRESHOLD = 0.95  # Critical at 95% usage

    def __init__(
        self,
        feature_repo: SubscriptionFeatureRepository,
        aggregate_repo: SubscriptionAggregateRepository,
    ) -> None:
        """
        Initialize the usage service.

        Args:
            feature_repo: Repository for feature usage data access
            aggregate_repo: Repository for aggregated usage data

        Raises:
            ValueError: If repositories are None
        """
        if not feature_repo:
            raise ValueError("Feature repository is required")
        if not aggregate_repo:
            raise ValueError("Aggregate repository is required")
        
        self.feature_repo = feature_repo
        self.aggregate_repo = aggregate_repo

    # -------------------------------------------------------------------------
    # Usage overview and retrieval
    # -------------------------------------------------------------------------

    def get_usage_overview(
        self,
        db: Session,
        subscription_id: UUID,
    ) -> Dict[str, Any]:
        """
        Get aggregated usage & limit overview for a subscription.

        Args:
            db: Database session
            subscription_id: UUID of the subscription

        Returns:
            Dictionary with usage overview including all features

        Raises:
            ValidationException: If no usage data available
        """
        try:
            data = self.aggregate_repo.get_subscription_usage_overview(
                db,
                subscription_id=subscription_id,
            )
            
            if not data:
                logger.warning(
                    f"No usage data available for subscription {subscription_id}"
                )
                raise ValidationException(
                    f"No usage data available for subscription {subscription_id}"
                )

            # Enrich with additional context
            enriched_data = self._enrich_usage_overview(db, data, subscription_id)

            logger.debug(f"Retrieved usage overview for subscription {subscription_id}")
            return enriched_data

        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                f"Error retrieving usage overview for subscription {subscription_id}: {str(e)}"
            )
            raise ValidationException(f"Failed to retrieve usage overview: {str(e)}")

    def get_feature_usage(
        self,
        db: Session,
        subscription_id: UUID,
        feature_key: str,
    ) -> Dict[str, Any]:
        """
        Get detailed usage information for a specific feature.

        Args:
            db: Database session
            subscription_id: UUID of the subscription
            feature_key: Feature key to retrieve usage for

        Returns:
            Dictionary with feature usage details

        Raises:
            ValidationException: If feature not found
        """
        try:
            usage_data = self.feature_repo.get_feature_usage(
                db,
                subscription_id=subscription_id,
                feature_key=feature_key,
            )

            if not usage_data:
                raise ValidationException(
                    f"Feature '{feature_key}' not found for subscription {subscription_id}"
                )

            # Calculate usage percentage
            current_usage = usage_data.get("current_usage", 0)
            limit = usage_data.get("limit")
            
            usage_percentage = None
            if limit and limit > 0:
                usage_percentage = (current_usage / limit) * 100

            result = {
                **usage_data,
                "usage_percentage": usage_percentage,
                "is_unlimited": limit is None or limit == -1,
                "is_at_limit": current_usage >= limit if limit and limit > 0 else False,
                "remaining": (limit - current_usage) if limit and limit > 0 else None,
            }

            logger.debug(
                f"Retrieved usage for feature '{feature_key}' in subscription {subscription_id}"
            )

            return result

        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                f"Error retrieving feature usage for '{feature_key}' "
                f"in subscription {subscription_id}: {str(e)}"
            )
            raise ValidationException(f"Failed to retrieve feature usage: {str(e)}")

    def list_all_feature_usage(
        self,
        db: Session,
        subscription_id: UUID,
        include_unlimited: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        List usage for all features in a subscription.

        Args:
            db: Database session
            subscription_id: UUID of the subscription
            include_unlimited: Whether to include features with no limits

        Returns:
            List of feature usage dictionaries
        """
        try:
            all_usage = self.feature_repo.list_all_feature_usage(
                db,
                subscription_id=subscription_id,
            )

            results = []
            for usage in all_usage:
                feature_key = usage.get("feature_key")
                if not feature_key:
                    continue

                # Get detailed usage for each feature
                try:
                    detailed = self.get_feature_usage(db, subscription_id, feature_key)
                    
                    # Filter unlimited features if requested
                    if not include_unlimited and detailed.get("is_unlimited"):
                        continue
                    
                    results.append(detailed)
                except ValidationException:
                    continue

            logger.debug(
                f"Retrieved usage for {len(results)} features in subscription {subscription_id}"
            )

            return results

        except Exception as e:
            logger.error(
                f"Error listing feature usage for subscription {subscription_id}: {str(e)}"
            )
            return []

    # -------------------------------------------------------------------------
    # Usage validation and checking
    # -------------------------------------------------------------------------

    def can_use_feature(
        self,
        db: Session,
        subscription_id: UUID,
        feature_key: str,
        amount: int = 1,
    ) -> bool:
        """
        Check if a feature can be used 'amount' times under current limits.

        Args:
            db: Database session
            subscription_id: UUID of the subscription
            feature_key: Feature key to check
            amount: Number of times feature will be used

        Returns:
            True if feature can be used, False otherwise
        """
        if amount <= 0:
            logger.warning(f"Invalid usage amount: {amount}")
            return False

        try:
            can_use = self.feature_repo.can_use_feature(
                db,
                subscription_id=subscription_id,
                feature_key=feature_key,
                amount=amount,
            )

            logger.debug(
                f"Feature '{feature_key}' usage check for subscription {subscription_id}: "
                f"can_use={can_use}, amount={amount}"
            )

            return can_use

        except Exception as e:
            logger.error(
                f"Error checking feature usage for '{feature_key}' "
                f"in subscription {subscription_id}: {str(e)}"
            )
            return False

    def get_usage_status(
        self,
        db: Session,
        subscription_id: UUID,
        feature_key: str,
    ) -> str:
        """
        Get usage status for a feature (normal, warning, critical, exceeded).

        Args:
            db: Database session
            subscription_id: UUID of the subscription
            feature_key: Feature key to check

        Returns:
            Usage status string
        """
        try:
            usage_data = self.get_feature_usage(db, subscription_id, feature_key)
            
            if usage_data.get("is_unlimited"):
                return "unlimited"

            usage_percentage = usage_data.get("usage_percentage", 0)
            
            if usage_percentage >= 100:
                return "exceeded"
            elif usage_percentage >= (self.USAGE_CRITICAL_THRESHOLD * 100):
                return "critical"
            elif usage_percentage >= (self.USAGE_WARNING_THRESHOLD * 100):
                return "warning"
            else:
                return "normal"

        except Exception as e:
            logger.error(
                f"Error getting usage status for '{feature_key}' "
                f"in subscription {subscription_id}: {str(e)}"
            )
            return "unknown"

    def check_multiple_features(
        self,
        db: Session,
        subscription_id: UUID,
        features: Dict[str, int],
    ) -> Dict[str, bool]:
        """
        Check if multiple features can be used.

        Args:
            db: Database session
            subscription_id: UUID of the subscription
            features: Dictionary mapping feature keys to amounts

        Returns:
            Dictionary mapping feature keys to availability (True/False)
        """
        results = {}
        
        for feature_key, amount in features.items():
            results[feature_key] = self.can_use_feature(
                db,
                subscription_id=subscription_id,
                feature_key=feature_key,
                amount=amount,
            )

        return results

    # -------------------------------------------------------------------------
    # Usage tracking and modification
    # -------------------------------------------------------------------------

    def increment_feature_usage(
        self,
        db: Session,
        subscription_id: UUID,
        feature_key: str,
        amount: int = 1,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Increment usage for a feature, raising if over the limit.

        Args:
            db: Database session
            subscription_id: UUID of the subscription
            feature_key: Feature key to increment
            amount: Amount to increment by
            metadata: Optional metadata about the usage event

        Returns:
            Updated usage information

        Raises:
            ValidationException: If usage limit exceeded or increment fails
        """
        if amount <= 0:
            raise ValidationException("Amount must be positive")

        # Check if usage is allowed
        if not self.can_use_feature(db, subscription_id, feature_key, amount):
            current_usage = self.get_feature_usage(db, subscription_id, feature_key)
            raise ValidationException(
                f"Usage limit exceeded for feature '{feature_key}'. "
                f"Current: {current_usage.get('current_usage', 0)}, "
                f"Limit: {current_usage.get('limit', 'unknown')}"
            )

        try:
            # Increment usage
            self.feature_repo.increment_usage(
                db,
                subscription_id=subscription_id,
                feature_key=feature_key,
                amount=amount,
                metadata=metadata,
            )

            # Get updated usage
            updated_usage = self.get_feature_usage(db, subscription_id, feature_key)

            logger.info(
                f"Incremented usage for feature '{feature_key}' in subscription {subscription_id} "
                f"by {amount}. New usage: {updated_usage.get('current_usage', 0)}"
            )

            # Check if warning threshold reached
            self._check_usage_warnings(db, subscription_id, feature_key, updated_usage)

            return updated_usage

        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                f"Failed to increment usage for feature '{feature_key}' "
                f"in subscription {subscription_id}: {str(e)}"
            )
            raise ValidationException(f"Failed to increment feature usage: {str(e)}")

    def decrement_feature_usage(
        self,
        db: Session,
        subscription_id: UUID,
        feature_key: str,
        amount: int = 1,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Decrement usage for a feature (e.g., for refunds or corrections).

        Args:
            db: Database session
            subscription_id: UUID of the subscription
            feature_key: Feature key to decrement
            amount: Amount to decrement by
            metadata: Optional metadata about the usage event

        Returns:
            Updated usage information

        Raises:
            ValidationException: If decrement fails
        """
        if amount <= 0:
            raise ValidationException("Amount must be positive")

        try:
            self.feature_repo.decrement_usage(
                db,
                subscription_id=subscription_id,
                feature_key=feature_key,
                amount=amount,
                metadata=metadata,
            )

            updated_usage = self.get_feature_usage(db, subscription_id, feature_key)

            logger.info(
                f"Decremented usage for feature '{feature_key}' in subscription {subscription_id} "
                f"by {amount}. New usage: {updated_usage.get('current_usage', 0)}"
            )

            return updated_usage

        except Exception as e:
            logger.error(
                f"Failed to decrement usage for feature '{feature_key}' "
                f"in subscription {subscription_id}: {str(e)}"
            )
            raise ValidationException(f"Failed to decrement feature usage: {str(e)}")

    def set_feature_usage(
        self,
        db: Session,
        subscription_id: UUID,
        feature_key: str,
        value: int,
        reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Set usage to a specific value (admin operation).

        Args:
            db: Database session
            subscription_id: UUID of the subscription
            feature_key: Feature key to set
            value: New usage value
            reason: Reason for manual adjustment

        Returns:
            Updated usage information
        """
        if value < 0:
            raise ValidationException("Usage value cannot be negative")

        try:
            self.feature_repo.set_usage(
                db,
                subscription_id=subscription_id,
                feature_key=feature_key,
                value=value,
                reason=reason,
            )

            updated_usage = self.get_feature_usage(db, subscription_id, feature_key)

            logger.warning(
                f"Manually set usage for feature '{feature_key}' in subscription {subscription_id} "
                f"to {value}. Reason: {reason or 'Not specified'}"
            )

            return updated_usage

        except Exception as e:
            logger.error(
                f"Failed to set usage for feature '{feature_key}' "
                f"in subscription {subscription_id}: {str(e)}"
            )
            raise ValidationException(f"Failed to set feature usage: {str(e)}")

    # -------------------------------------------------------------------------
    # Usage resets
    # -------------------------------------------------------------------------

    def reset_feature_usage(
        self,
        db: Session,
        subscription_id: UUID,
        feature_key: str,
        reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Reset usage counter for a feature to zero.

        Args:
            db: Database session
            subscription_id: UUID of the subscription
            feature_key: Feature key to reset
            reason: Optional reason for reset

        Returns:
            Reset usage information
        """
        try:
            self.feature_repo.reset_usage(
                db,
                subscription_id=subscription_id,
                feature_key=feature_key,
                reason=reason,
            )

            updated_usage = self.get_feature_usage(db, subscription_id, feature_key)

            logger.info(
                f"Reset usage for feature '{feature_key}' in subscription {subscription_id}. "
                f"Reason: {reason or 'Not specified'}"
            )

            return updated_usage

        except Exception as e:
            logger.error(
                f"Failed to reset usage for feature '{feature_key}' "
                f"in subscription {subscription_id}: {str(e)}"
            )
            raise ValidationException(f"Failed to reset feature usage: {str(e)}")

    def reset_all_usage(
        self,
        db: Session,
        subscription_id: UUID,
        reason: Optional[str] = None,
    ) -> int:
        """
        Reset usage for all features in a subscription (e.g., billing cycle reset).

        Args:
            db: Database session
            subscription_id: UUID of the subscription
            reason: Reason for reset (e.g., "monthly_billing_cycle")

        Returns:
            Number of features reset
        """
        try:
            count = self.feature_repo.reset_all_usage(
                db,
                subscription_id=subscription_id,
                reason=reason,
            )

            logger.info(
                f"Reset usage for {count} features in subscription {subscription_id}. "
                f"Reason: {reason or 'Not specified'}"
            )

            return count

        except Exception as e:
            logger.error(
                f"Failed to reset all usage for subscription {subscription_id}: {str(e)}"
            )
            raise ValidationException(f"Failed to reset usage: {str(e)}")

    # -------------------------------------------------------------------------
    # Usage analytics
    # -------------------------------------------------------------------------

    def get_usage_trends(
        self,
        db: Session,
        subscription_id: UUID,
        feature_key: str,
        days: int = 30,
    ) -> Dict[str, Any]:
        """
        Get usage trends for a feature over time.

        Args:
            db: Database session
            subscription_id: UUID of the subscription
            feature_key: Feature key to analyze
            days: Number of days to analyze

        Returns:
            Dictionary with trend analysis
        """
        try:
            trends = self.aggregate_repo.get_usage_trends(
                db,
                subscription_id=subscription_id,
                feature_key=feature_key,
                days=days,
            )

            logger.debug(
                f"Retrieved {days}-day usage trends for feature '{feature_key}' "
                f"in subscription {subscription_id}"
            )

            return trends

        except Exception as e:
            logger.error(
                f"Error retrieving usage trends for feature '{feature_key}' "
                f"in subscription {subscription_id}: {str(e)}"
            )
            return {}

    def get_peak_usage_periods(
        self,
        db: Session,
        subscription_id: UUID,
        feature_key: str,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Get periods of peak usage for a feature.

        Args:
            db: Database session
            subscription_id: UUID of the subscription
            feature_key: Feature key to analyze
            limit: Number of peak periods to return

        Returns:
            List of peak usage periods
        """
        try:
            peaks = self.aggregate_repo.get_peak_usage_periods(
                db,
                subscription_id=subscription_id,
                feature_key=feature_key,
                limit=limit,
            )

            logger.debug(
                f"Retrieved top {limit} peak usage periods for feature '{feature_key}' "
                f"in subscription {subscription_id}"
            )

            return peaks

        except Exception as e:
            logger.error(
                f"Error retrieving peak usage periods for feature '{feature_key}' "
                f"in subscription {subscription_id}: {str(e)}"
            )
            return []

    def predict_usage_exhaustion(
        self,
        db: Session,
        subscription_id: UUID,
        feature_key: str,
    ) -> Optional[datetime]:
        """
        Predict when a feature's usage limit will be exhausted based on trends.

        Args:
            db: Database session
            subscription_id: UUID of the subscription
            feature_key: Feature key to predict for

        Returns:
            Estimated datetime of exhaustion or None if unlimited/sufficient
        """
        try:
            usage_data = self.get_feature_usage(db, subscription_id, feature_key)
            
            if usage_data.get("is_unlimited"):
                return None

            # Get usage trends
            trends = self.get_usage_trends(db, subscription_id, feature_key, days=7)
            
            if not trends or not trends.get("daily_average"):
                return None

            daily_average = Decimal(str(trends["daily_average"]))
            remaining = usage_data.get("remaining", 0)

            if daily_average <= 0 or remaining is None:
                return None

            days_until_exhaustion = float(Decimal(str(remaining)) / daily_average)
            
            if days_until_exhaustion <= 0:
                return datetime.utcnow()

            exhaustion_date = datetime.utcnow() + timedelta(days=days_until_exhaustion)

            logger.debug(
                f"Predicted usage exhaustion for feature '{feature_key}' "
                f"in subscription {subscription_id}: {exhaustion_date}"
            )

            return exhaustion_date

        except Exception as e:
            logger.error(
                f"Error predicting usage exhaustion for feature '{feature_key}' "
                f"in subscription {subscription_id}: {str(e)}"
            )
            return None

    # -------------------------------------------------------------------------
    # Private helper methods
    # -------------------------------------------------------------------------

    def _enrich_usage_overview(
        self,
        db: Session,
        data: Dict[str, Any],
        subscription_id: UUID,
    ) -> Dict[str, Any]:
        """
        Enrich usage overview with additional context and calculations.

        Args:
            db: Database session
            data: Base usage overview data
            subscription_id: UUID of the subscription

        Returns:
            Enriched usage data
        """
        try:
            # Add overall usage status
            features_at_limit = 0
            features_in_warning = 0
            total_features = len(data.get("features", []))

            for feature in data.get("features", []):
                feature_key = feature.get("feature_key")
                if not feature_key:
                    continue

                status = self.get_usage_status(db, subscription_id, feature_key)
                feature["status"] = status

                if status == "exceeded":
                    features_at_limit += 1
                elif status in ["warning", "critical"]:
                    features_in_warning += 1

            data["summary"] = {
                "total_features": total_features,
                "features_at_limit": features_at_limit,
                "features_in_warning": features_in_warning,
                "overall_status": self._calculate_overall_status(
                    features_at_limit,
                    features_in_warning,
                    total_features
                ),
            }

            return data

        except Exception as e:
            logger.warning(f"Error enriching usage overview: {str(e)}")
            return data

    def _calculate_overall_status(
        self,
        at_limit: int,
        in_warning: int,
        total: int,
    ) -> str:
        """Calculate overall usage status for subscription."""
        if total == 0:
            return "unknown"
        
        if at_limit > 0:
            return "critical"
        elif in_warning > total * 0.3:  # More than 30% in warning
            return "warning"
        else:
            return "normal"

    def _check_usage_warnings(
        self,
        db: Session,
        subscription_id: UUID,
        feature_key: str,
        usage_data: Dict[str, Any],
    ) -> None:
        """
        Check if usage warnings should be triggered and send notifications.

        Args:
            db: Database session
            subscription_id: UUID of the subscription
            feature_key: Feature key being checked
            usage_data: Current usage data
        """
        status = self.get_usage_status(db, subscription_id, feature_key)
        
        if status in ["warning", "critical", "exceeded"]:
            logger.warning(
                f"Usage {status} for feature '{feature_key}' in subscription {subscription_id}: "
                f"{usage_data.get('usage_percentage', 0):.1f}% used"
            )
            
            # Trigger notification (placeholder for actual notification service)
            self._send_usage_alert(
                subscription_id=subscription_id,
                feature_key=feature_key,
                status=status,
                usage_data=usage_data,
            )

    def _send_usage_alert(
        self,
        subscription_id: UUID,
        feature_key: str,
        status: str,
        usage_data: Dict[str, Any],
    ) -> None:
        """
        Send usage alert notification.

        Args:
            subscription_id: UUID of the subscription
            feature_key: Feature key
            status: Usage status
            usage_data: Usage data

        Note:
            This is a placeholder for notification integration
        """
        logger.info(
            f"Usage alert triggered for subscription {subscription_id}, "
            f"feature '{feature_key}': {status}"
        )
        # Implement actual notification logic here