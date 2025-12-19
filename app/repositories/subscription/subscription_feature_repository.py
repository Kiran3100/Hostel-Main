"""
Subscription Feature Repository.

Manages feature usage tracking, limits enforcement,
and feature availability for subscriptions.
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.models.subscription.subscription_feature import (
    SubscriptionFeatureUsage,
    SubscriptionLimit,
)


class SubscriptionFeatureRepository:
    """
    Repository for subscription feature operations.

    Provides methods for feature usage tracking,
    limit management, and feature analytics.
    """

    def __init__(self, db: Session):
        """Initialize repository with database session."""
        self.db = db

    # ==================== FEATURE USAGE - CREATE ====================

    def create_feature_usage(
        self,
        feature_data: Dict[str, Any],
    ) -> SubscriptionFeatureUsage:
        """
        Create feature usage record.

        Args:
            feature_data: Feature usage data

        Returns:
            Created feature usage record
        """
        feature_usage = SubscriptionFeatureUsage(**feature_data)
        self.db.add(feature_usage)
        self.db.flush()
        return feature_usage

    def initialize_feature_usage(
        self,
        subscription_id: UUID,
        feature_key: str,
        feature_name: str,
        usage_limit: Optional[int] = None,
        is_enabled: bool = True,
    ) -> SubscriptionFeatureUsage:
        """
        Initialize feature usage for subscription.

        Args:
            subscription_id: Subscription ID
            feature_key: Feature identifier
            feature_name: Feature display name
            usage_limit: Usage limit (None = unlimited)
            is_enabled: Feature enabled status

        Returns:
            Created feature usage record
        """
        feature_data = {
            "subscription_id": subscription_id,
            "feature_key": feature_key,
            "feature_name": feature_name,
            "current_usage": 0,
            "usage_limit": usage_limit,
            "is_enabled": is_enabled,
            "is_limit_exceeded": False,
            "period_start": datetime.utcnow(),
        }
        
        return self.create_feature_usage(feature_data)

    # ==================== FEATURE USAGE - READ ====================

    def get_feature_usage_by_id(
        self,
        usage_id: UUID,
    ) -> Optional[SubscriptionFeatureUsage]:
        """
        Get feature usage by ID.

        Args:
            usage_id: Feature usage ID

        Returns:
            Feature usage if found
        """
        query = select(SubscriptionFeatureUsage).where(
            SubscriptionFeatureUsage.id == usage_id
        )
        result = self.db.execute(query)
        return result.scalar_one_or_none()

    def get_feature_usage(
        self,
        subscription_id: UUID,
        feature_key: str,
    ) -> Optional[SubscriptionFeatureUsage]:
        """
        Get feature usage for subscription.

        Args:
            subscription_id: Subscription ID
            feature_key: Feature key

        Returns:
            Feature usage if found
        """
        query = select(SubscriptionFeatureUsage).where(
            and_(
                SubscriptionFeatureUsage.subscription_id == subscription_id,
                SubscriptionFeatureUsage.feature_key == feature_key,
            )
        )
        result = self.db.execute(query)
        return result.scalar_one_or_none()

    def get_all_feature_usage(
        self,
        subscription_id: UUID,
    ) -> List[SubscriptionFeatureUsage]:
        """
        Get all feature usage for subscription.

        Args:
            subscription_id: Subscription ID

        Returns:
            List of feature usage records
        """
        query = (
            select(SubscriptionFeatureUsage)
            .where(SubscriptionFeatureUsage.subscription_id == subscription_id)
            .order_by(SubscriptionFeatureUsage.feature_name)
        )
        result = self.db.execute(query)
        return list(result.scalars().all())

    def get_enabled_features(
        self,
        subscription_id: UUID,
    ) -> List[SubscriptionFeatureUsage]:
        """
        Get all enabled features for subscription.

        Args:
            subscription_id: Subscription ID

        Returns:
            List of enabled features
        """
        query = (
            select(SubscriptionFeatureUsage)
            .where(
                and_(
                    SubscriptionFeatureUsage.subscription_id == subscription_id,
                    SubscriptionFeatureUsage.is_enabled == True,
                )
            )
            .order_by(SubscriptionFeatureUsage.feature_name)
        )
        result = self.db.execute(query)
        return list(result.scalars().all())

    def get_exceeded_features(
        self,
        subscription_id: UUID,
    ) -> List[SubscriptionFeatureUsage]:
        """
        Get features that have exceeded limits.

        Args:
            subscription_id: Subscription ID

        Returns:
            List of features with exceeded limits
        """
        query = (
            select(SubscriptionFeatureUsage)
            .where(
                and_(
                    SubscriptionFeatureUsage.subscription_id == subscription_id,
                    SubscriptionFeatureUsage.is_limit_exceeded == True,
                )
            )
            .order_by(SubscriptionFeatureUsage.feature_name)
        )
        result = self.db.execute(query)
        return list(result.scalars().all())

    def get_near_limit_features(
        self,
        subscription_id: UUID,
        threshold: float = 0.8,
    ) -> List[SubscriptionFeatureUsage]:
        """
        Get features near their usage limit.

        Args:
            subscription_id: Subscription ID
            threshold: Threshold percentage (default 80%)

        Returns:
            List of features near limit
        """
        features = self.get_all_feature_usage(subscription_id)
        near_limit = []
        
        for feature in features:
            if feature.usage_limit is not None:
                usage_percent = feature.current_usage / feature.usage_limit
                if usage_percent >= threshold and not feature.is_limit_exceeded:
                    near_limit.append(feature)
        
        return near_limit

    # ==================== FEATURE USAGE - UPDATE ====================

    def update_feature_usage(
        self,
        usage_id: UUID,
        update_data: Dict[str, Any],
    ) -> Optional[SubscriptionFeatureUsage]:
        """
        Update feature usage.

        Args:
            usage_id: Feature usage ID
            update_data: Updated data

        Returns:
            Updated feature usage
        """
        feature_usage = self.get_feature_usage_by_id(usage_id)
        if not feature_usage:
            return None
        
        for key, value in update_data.items():
            if hasattr(feature_usage, key):
                setattr(feature_usage, key, value)
        
        feature_usage.updated_at = datetime.utcnow()
        self.db.flush()
        return feature_usage

    def increment_usage(
        self,
        subscription_id: UUID,
        feature_key: str,
        amount: int = 1,
    ) -> Optional[SubscriptionFeatureUsage]:
        """
        Increment feature usage.

        Args:
            subscription_id: Subscription ID
            feature_key: Feature key
            amount: Amount to increment

        Returns:
            Updated feature usage
        """
        feature_usage = self.get_feature_usage(subscription_id, feature_key)
        if not feature_usage:
            return None
        
        feature_usage.increment_usage(amount)
        feature_usage.updated_at = datetime.utcnow()
        
        self.db.flush()
        return feature_usage

    def decrement_usage(
        self,
        subscription_id: UUID,
        feature_key: str,
        amount: int = 1,
    ) -> Optional[SubscriptionFeatureUsage]:
        """
        Decrement feature usage.

        Args:
            subscription_id: Subscription ID
            feature_key: Feature key
            amount: Amount to decrement

        Returns:
            Updated feature usage
        """
        feature_usage = self.get_feature_usage(subscription_id, feature_key)
        if not feature_usage:
            return None
        
        feature_usage.current_usage = max(0, feature_usage.current_usage - amount)
        
        # Update exceeded status
        if feature_usage.usage_limit is not None:
            feature_usage.is_limit_exceeded = (
                feature_usage.current_usage > feature_usage.usage_limit
            )
        
        feature_usage.updated_at = datetime.utcnow()
        self.db.flush()
        return feature_usage

    def reset_usage(
        self,
        subscription_id: UUID,
        feature_key: str,
    ) -> Optional[SubscriptionFeatureUsage]:
        """
        Reset feature usage to zero.

        Args:
            subscription_id: Subscription ID
            feature_key: Feature key

        Returns:
            Updated feature usage
        """
        feature_usage = self.get_feature_usage(subscription_id, feature_key)
        if not feature_usage:
            return None
        
        feature_usage.reset_usage()
        feature_usage.updated_at = datetime.utcnow()
        
        self.db.flush()
        return feature_usage

    def update_usage_limit(
        self,
        subscription_id: UUID,
        feature_key: str,
        new_limit: Optional[int],
    ) -> Optional[SubscriptionFeatureUsage]:
        """
        Update feature usage limit.

        Args:
            subscription_id: Subscription ID
            feature_key: Feature key
            new_limit: New usage limit (None = unlimited)

        Returns:
            Updated feature usage
        """
        feature_usage = self.get_feature_usage(subscription_id, feature_key)
        if not feature_usage:
            return None
        
        feature_usage.usage_limit = new_limit
        
        # Update exceeded status
        if new_limit is not None:
            feature_usage.is_limit_exceeded = (
                feature_usage.current_usage > new_limit
            )
        else:
            feature_usage.is_limit_exceeded = False
        
        feature_usage.updated_at = datetime.utcnow()
        self.db.flush()
        return feature_usage

    def toggle_feature(
        self,
        subscription_id: UUID,
        feature_key: str,
        is_enabled: bool,
    ) -> Optional[SubscriptionFeatureUsage]:
        """
        Enable or disable feature.

        Args:
            subscription_id: Subscription ID
            feature_key: Feature key
            is_enabled: Enabled status

        Returns:
            Updated feature usage
        """
        feature_usage = self.get_feature_usage(subscription_id, feature_key)
        if not feature_usage:
            return None
        
        feature_usage.is_enabled = is_enabled
        feature_usage.updated_at = datetime.utcnow()
        
        self.db.flush()
        return feature_usage

    # ==================== FEATURE USAGE - DELETE ====================

    def delete_feature_usage(
        self,
        usage_id: UUID,
    ) -> bool:
        """
        Delete feature usage record.

        Args:
            usage_id: Feature usage ID

        Returns:
            True if deleted
        """
        feature_usage = self.get_feature_usage_by_id(usage_id)
        if not feature_usage:
            return False
        
        self.db.delete(feature_usage)
        self.db.flush()
        return True

    # ==================== SUBSCRIPTION LIMITS - CREATE ====================

    def create_subscription_limit(
        self,
        limit_data: Dict[str, Any],
    ) -> SubscriptionLimit:
        """
        Create subscription limit.

        Args:
            limit_data: Limit configuration data

        Returns:
            Created subscription limit
        """
        subscription_limit = SubscriptionLimit(**limit_data)
        self.db.add(subscription_limit)
        self.db.flush()
        return subscription_limit

    def initialize_subscription_limit(
        self,
        subscription_id: UUID,
        limit_type: str,
        limit_name: str,
        limit_value: Optional[int] = None,
        warning_threshold: Optional[int] = None,
        is_enforced: bool = True,
        description: Optional[str] = None,
    ) -> SubscriptionLimit:
        """
        Initialize subscription limit.

        Args:
            subscription_id: Subscription ID
            limit_type: Type of limit
            limit_name: Limit display name
            limit_value: Limit value (None = unlimited)
            warning_threshold: Warning threshold
            is_enforced: Whether limit is enforced
            description: Limit description

        Returns:
            Created subscription limit
        """
        limit_data = {
            "subscription_id": subscription_id,
            "limit_type": limit_type,
            "limit_name": limit_name,
            "limit_value": limit_value,
            "current_value": 0,
            "warning_threshold": warning_threshold,
            "is_enforced": is_enforced,
            "is_exceeded": False,
            "warning_sent": False,
            "description": description,
        }
        
        return self.create_subscription_limit(limit_data)

    # ==================== SUBSCRIPTION LIMITS - READ ====================

    def get_subscription_limit_by_id(
        self,
        limit_id: UUID,
    ) -> Optional[SubscriptionLimit]:
        """
        Get subscription limit by ID.

        Args:
            limit_id: Limit ID

        Returns:
            Subscription limit if found
        """
        query = select(SubscriptionLimit).where(SubscriptionLimit.id == limit_id)
        result = self.db.execute(query)
        return result.scalar_one_or_none()

    def get_subscription_limit(
        self,
        subscription_id: UUID,
        limit_type: str,
    ) -> Optional[SubscriptionLimit]:
        """
        Get subscription limit by type.

        Args:
            subscription_id: Subscription ID
            limit_type: Limit type

        Returns:
            Subscription limit if found
        """
        query = select(SubscriptionLimit).where(
            and_(
                SubscriptionLimit.subscription_id == subscription_id,
                SubscriptionLimit.limit_type == limit_type,
            )
        )
        result = self.db.execute(query)
        return result.scalar_one_or_none()

    def get_all_subscription_limits(
        self,
        subscription_id: UUID,
    ) -> List[SubscriptionLimit]:
        """
        Get all limits for subscription.

        Args:
            subscription_id: Subscription ID

        Returns:
            List of subscription limits
        """
        query = (
            select(SubscriptionLimit)
            .where(SubscriptionLimit.subscription_id == subscription_id)
            .order_by(SubscriptionLimit.limit_name)
        )
        result = self.db.execute(query)
        return list(result.scalars().all())

    def get_exceeded_limits(
        self,
        subscription_id: UUID,
    ) -> List[SubscriptionLimit]:
        """
        Get limits that have been exceeded.

        Args:
            subscription_id: Subscription ID

        Returns:
            List of exceeded limits
        """
        query = (
            select(SubscriptionLimit)
            .where(
                and_(
                    SubscriptionLimit.subscription_id == subscription_id,
                    SubscriptionLimit.is_exceeded == True,
                )
            )
            .order_by(SubscriptionLimit.limit_name)
        )
        result = self.db.execute(query)
        return list(result.scalars().all())

    def get_limits_near_threshold(
        self,
        subscription_id: UUID,
    ) -> List[SubscriptionLimit]:
        """
        Get limits near warning threshold.

        Args:
            subscription_id: Subscription ID

        Returns:
            List of limits near threshold
        """
        limits = self.get_all_subscription_limits(subscription_id)
        near_threshold = []
        
        for limit in limits:
            if limit.is_near_limit and not limit.warning_sent:
                near_threshold.append(limit)
        
        return near_threshold

    def get_enforced_limits(
        self,
        subscription_id: UUID,
    ) -> List[SubscriptionLimit]:
        """
        Get all enforced limits.

        Args:
            subscription_id: Subscription ID

        Returns:
            List of enforced limits
        """
        query = (
            select(SubscriptionLimit)
            .where(
                and_(
                    SubscriptionLimit.subscription_id == subscription_id,
                    SubscriptionLimit.is_enforced == True,
                )
            )
            .order_by(SubscriptionLimit.limit_name)
        )
        result = self.db.execute(query)
        return list(result.scalars().all())

    # ==================== SUBSCRIPTION LIMITS - UPDATE ====================

    def update_subscription_limit(
        self,
        limit_id: UUID,
        update_data: Dict[str, Any],
    ) -> Optional[SubscriptionLimit]:
        """
        Update subscription limit.

        Args:
            limit_id: Limit ID
            update_data: Updated data

        Returns:
            Updated subscription limit
        """
        subscription_limit = self.get_subscription_limit_by_id(limit_id)
        if not subscription_limit:
            return None
        
        for key, value in update_data.items():
            if hasattr(subscription_limit, key):
                setattr(subscription_limit, key, value)
        
        subscription_limit.updated_at = datetime.utcnow()
        self.db.flush()
        return subscription_limit

    def increment_limit_value(
        self,
        subscription_id: UUID,
        limit_type: str,
        amount: int = 1,
    ) -> Optional[SubscriptionLimit]:
        """
        Increment current value of limit.

        Args:
            subscription_id: Subscription ID
            limit_type: Limit type
            amount: Amount to increment

        Returns:
            Updated subscription limit
        """
        subscription_limit = self.get_subscription_limit(subscription_id, limit_type)
        if not subscription_limit:
            return None
        
        subscription_limit.increment(amount)
        subscription_limit.updated_at = datetime.utcnow()
        
        self.db.flush()
        return subscription_limit

    def decrement_limit_value(
        self,
        subscription_id: UUID,
        limit_type: str,
        amount: int = 1,
    ) -> Optional[SubscriptionLimit]:
        """
        Decrement current value of limit.

        Args:
            subscription_id: Subscription ID
            limit_type: Limit type
            amount: Amount to decrement

        Returns:
            Updated subscription limit
        """
        subscription_limit = self.get_subscription_limit(subscription_id, limit_type)
        if not subscription_limit:
            return None
        
        subscription_limit.decrement(amount)
        subscription_limit.updated_at = datetime.utcnow()
        
        self.db.flush()
        return subscription_limit

    def update_limit_threshold(
        self,
        subscription_id: UUID,
        limit_type: str,
        new_limit: Optional[int],
        new_warning_threshold: Optional[int] = None,
    ) -> Optional[SubscriptionLimit]:
        """
        Update limit and warning threshold.

        Args:
            subscription_id: Subscription ID
            limit_type: Limit type
            new_limit: New limit value
            new_warning_threshold: New warning threshold

        Returns:
            Updated subscription limit
        """
        subscription_limit = self.get_subscription_limit(subscription_id, limit_type)
        if not subscription_limit:
            return None
        
        subscription_limit.limit_value = new_limit
        
        if new_warning_threshold is not None:
            subscription_limit.warning_threshold = new_warning_threshold
        
        # Update exceeded status
        if new_limit is not None:
            subscription_limit.is_exceeded = (
                subscription_limit.current_value > new_limit
            )
        else:
            subscription_limit.is_exceeded = False
        
        # Reset warning sent if below threshold
        if subscription_limit.warning_threshold is not None:
            if subscription_limit.current_value < subscription_limit.warning_threshold:
                subscription_limit.warning_sent = False
        
        subscription_limit.updated_at = datetime.utcnow()
        self.db.flush()
        return subscription_limit

    def mark_warning_sent(
        self,
        subscription_id: UUID,
        limit_type: str,
    ) -> Optional[SubscriptionLimit]:
        """
        Mark warning as sent for limit.

        Args:
            subscription_id: Subscription ID
            limit_type: Limit type

        Returns:
            Updated subscription limit
        """
        subscription_limit = self.get_subscription_limit(subscription_id, limit_type)
        if not subscription_limit:
            return None
        
        subscription_limit.warning_sent = True
        subscription_limit.updated_at = datetime.utcnow()
        
        self.db.flush()
        return subscription_limit

    def toggle_limit_enforcement(
        self,
        subscription_id: UUID,
        limit_type: str,
        is_enforced: bool,
    ) -> Optional[SubscriptionLimit]:
        """
        Toggle limit enforcement.

        Args:
            subscription_id: Subscription ID
            limit_type: Limit type
            is_enforced: Enforcement status

        Returns:
            Updated subscription limit
        """
        subscription_limit = self.get_subscription_limit(subscription_id, limit_type)
        if not subscription_limit:
            return None
        
        subscription_limit.is_enforced = is_enforced
        subscription_limit.updated_at = datetime.utcnow()
        
        self.db.flush()
        return subscription_limit

    # ==================== SUBSCRIPTION LIMITS - DELETE ====================

    def delete_subscription_limit(
        self,
        limit_id: UUID,
    ) -> bool:
        """
        Delete subscription limit.

        Args:
            limit_id: Limit ID

        Returns:
            True if deleted
        """
        subscription_limit = self.get_subscription_limit_by_id(limit_id)
        if not subscription_limit:
            return False
        
        self.db.delete(subscription_limit)
        self.db.flush()
        return True

    # ==================== VALIDATION ====================

    def can_use_feature(
        self,
        subscription_id: UUID,
        feature_key: str,
        amount: int = 1,
    ) -> bool:
        """
        Check if feature can be used.

        Args:
            subscription_id: Subscription ID
            feature_key: Feature key
            amount: Amount to use

        Returns:
            True if feature can be used
        """
        feature_usage = self.get_feature_usage(subscription_id, feature_key)
        if not feature_usage:
            return False
        
        return feature_usage.can_use(amount)

    def can_add_to_limit(
        self,
        subscription_id: UUID,
        limit_type: str,
        amount: int = 1,
    ) -> bool:
        """
        Check if amount can be added within limit.

        Args:
            subscription_id: Subscription ID
            limit_type: Limit type
            amount: Amount to add

        Returns:
            True if can add within limit
        """
        subscription_limit = self.get_subscription_limit(subscription_id, limit_type)
        if not subscription_limit:
            return True  # No limit defined
        
        return subscription_limit.can_add(amount)

    def validate_limits(
        self,
        subscription_id: UUID,
    ) -> Dict[str, Any]:
        """
        Validate all limits for subscription.

        Args:
            subscription_id: Subscription ID

        Returns:
            Validation result with violations
        """
        limits = self.get_all_subscription_limits(subscription_id)
        violations = []
        warnings = []
        
        for limit in limits:
            if limit.is_exceeded and limit.is_enforced:
                violations.append({
                    "limit_type": limit.limit_type,
                    "limit_name": limit.limit_name,
                    "current_value": limit.current_value,
                    "limit_value": limit.limit_value,
                    "exceeded_by": limit.current_value - (limit.limit_value or 0),
                })
            
            if limit.is_near_limit and not limit.warning_sent:
                warnings.append({
                    "limit_type": limit.limit_type,
                    "limit_name": limit.limit_name,
                    "current_value": limit.current_value,
                    "limit_value": limit.limit_value,
                    "warning_threshold": limit.warning_threshold,
                })
        
        return {
            "valid": len(violations) == 0,
            "violations": violations,
            "warnings": warnings,
        }

    # ==================== ANALYTICS ====================

    def get_feature_usage_summary(
        self,
        subscription_id: UUID,
    ) -> Dict[str, Any]:
        """
        Get feature usage summary for subscription.

        Args:
            subscription_id: Subscription ID

        Returns:
            Usage summary
        """
        features = self.get_all_feature_usage(subscription_id)
        
        total_features = len(features)
        enabled_features = sum(1 for f in features if f.is_enabled)
        exceeded_features = sum(1 for f in features if f.is_limit_exceeded)
        
        # Features with limits
        limited_features = [f for f in features if f.usage_limit is not None]
        
        return {
            "total_features": total_features,
            "enabled_features": enabled_features,
            "disabled_features": total_features - enabled_features,
            "exceeded_features": exceeded_features,
            "features_with_limits": len(limited_features),
            "unlimited_features": total_features - len(limited_features),
        }

    def get_limits_summary(
        self,
        subscription_id: UUID,
    ) -> Dict[str, Any]:
        """
        Get limits summary for subscription.

        Args:
            subscription_id: Subscription ID

        Returns:
            Limits summary
        """
        limits = self.get_all_subscription_limits(subscription_id)
        
        total_limits = len(limits)
        enforced_limits = sum(1 for l in limits if l.is_enforced)
        exceeded_limits = sum(1 for l in limits if l.is_exceeded)
        near_threshold = sum(1 for l in limits if l.is_near_limit)
        
        return {
            "total_limits": total_limits,
            "enforced_limits": enforced_limits,
            "exceeded_limits": exceeded_limits,
            "limits_near_threshold": near_threshold,
            "unenforced_limits": total_limits - enforced_limits,
        }

    # ==================== BATCH OPERATIONS ====================

    def batch_reset_usage(
        self,
        subscription_id: UUID,
        feature_keys: Optional[List[str]] = None,
    ) -> int:
        """
        Batch reset feature usage.

        Args:
            subscription_id: Subscription ID
            feature_keys: Optional list of feature keys (None = all)

        Returns:
            Number of features reset
        """
        if feature_keys:
            features = [
                self.get_feature_usage(subscription_id, key)
                for key in feature_keys
            ]
            features = [f for f in features if f is not None]
        else:
            features = self.get_all_feature_usage(subscription_id)
        
        count = 0
        for feature in features:
            feature.reset_usage()
            count += 1
        
        self.db.flush()
        return count

    def batch_update_limits(
        self,
        subscription_id: UUID,
        limit_updates: Dict[str, int],
    ) -> int:
        """
        Batch update multiple limits.

        Args:
            subscription_id: Subscription ID
            limit_updates: Dictionary of limit_type: new_limit_value

        Returns:
            Number of limits updated
        """
        count = 0
        for limit_type, new_limit in limit_updates.items():
            if self.update_limit_threshold(subscription_id, limit_type, new_limit):
                count += 1
        return count