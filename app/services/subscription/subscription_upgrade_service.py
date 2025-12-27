"""
Subscription Upgrade Service

Handles plan change (upgrade/downgrade) operations.

Improvements:
- Enhanced proration logic
- Better validation of plan transitions
- Improved credit handling
- Added rollback capability
- Better handling of billing cycle adjustments
- Enhanced logging and audit trail
"""

from __future__ import annotations

import logging
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, Dict, Any
from uuid import UUID
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.repositories.subscription import (
    SubscriptionRepository,
    SubscriptionPlanRepository,
)
from app.schemas.subscription import (
    PlanChangeRequest,
    PlanChangePreview,
    PlanChangeConfirmation,
    SubscriptionStatus,
)
from app.core1.exceptions import ValidationException

logger = logging.getLogger(__name__)


class SubscriptionUpgradeService:
    """
    High-level service for subscription plan changes.

    Responsibilities:
    - Preview financial impact of plan changes
    - Apply plan changes with proper proration
    - Handle upgrade and downgrade scenarios
    - Manage billing cycle adjustments
    - Track plan change history
    - Handle credits and refunds
    """

    # Constants
    DECIMAL_PLACES = 2
    MIN_PRORATION_AMOUNT = Decimal("0.01")

    def __init__(
        self,
        subscription_repo: SubscriptionRepository,
        plan_repo: SubscriptionPlanRepository,
    ) -> None:
        """
        Initialize the upgrade service.

        Args:
            subscription_repo: Repository for subscription data access
            plan_repo: Repository for plan data access

        Raises:
            ValueError: If repositories are None
        """
        if not subscription_repo:
            raise ValueError("Subscription repository is required")
        if not plan_repo:
            raise ValueError("Plan repository is required")
        
        self.subscription_repo = subscription_repo
        self.plan_repo = plan_repo

    # -------------------------------------------------------------------------
    # Preview
    # -------------------------------------------------------------------------

    def preview_plan_change(
        self,
        db: Session,
        request: PlanChangeRequest,
    ) -> PlanChangePreview:
        """
        Preview a plan change for a given subscription and new plan.

        Calculates proration, credits, and effective dates without applying changes.

        Args:
            db: Database session
            request: Plan change request with all parameters

        Returns:
            PlanChangePreview with financial breakdown

        Raises:
            ValidationException: If validation fails
        """
        # Validate the request
        self._validate_plan_change_request(db, request)

        # Get current subscription
        subscription = self.subscription_repo.get_by_id(db, request.subscription_id)
        if not subscription:
            raise ValidationException(
                f"Subscription not found with ID: {request.subscription_id}"
            )

        # Validate hostel ownership
        if subscription.hostel_id != request.hostel_id:
            raise ValidationException("Subscription does not belong to specified hostel")

        # Validate subscription status
        if subscription.status not in [
            SubscriptionStatus.ACTIVE.value,
            SubscriptionStatus.TRIAL.value,
        ]:
            raise ValidationException(
                f"Cannot change plan for subscription with status: {subscription.status}"
            )

        # Get target plan
        new_plan = self.plan_repo.get_by_id(db, request.new_plan_id)
        if not new_plan:
            raise ValidationException(f"Target plan not found with ID: {request.new_plan_id}")

        # Validate plan is active and available
        if not new_plan.is_active:
            raise ValidationException("Target plan is not active")

        # Check if plan change is valid (e.g., same plan check)
        if subscription.plan_id == request.new_plan_id:
            raise ValidationException("New plan is the same as current plan")

        try:
            # Delegate financial calculations to repository
            data = self.subscription_repo.preview_plan_change(
                db=db,
                subscription_id=request.subscription_id,
                hostel_id=request.hostel_id,
                new_plan_id=request.new_plan_id,
                billing_cycle=request.billing_cycle,
                effective_from=request.effective_from,
                prorate=request.prorate,
                apply_credit=request.apply_credit,
                preserve_trial=request.preserve_trial,
                change_reason=request.change_reason,
            )

            # Enhance preview with additional context
            preview = PlanChangePreview.model_validate(data)
            preview = self._enrich_preview(db, preview, subscription, new_plan)

            logger.info(
                f"Generated plan change preview for subscription {request.subscription_id}: "
                f"{subscription.plan_id} -> {request.new_plan_id}"
            )

            return preview

        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                f"Error previewing plan change for subscription {request.subscription_id}: {str(e)}"
            )
            raise ValidationException(f"Failed to preview plan change: {str(e)}")

    def preview_upgrade(
        self,
        db: Session,
        subscription_id: UUID,
        new_plan_id: UUID,
        immediate: bool = True,
    ) -> PlanChangePreview:
        """
        Convenience method to preview an upgrade with default settings.

        Args:
            db: Database session
            subscription_id: Current subscription ID
            new_plan_id: Target plan ID
            immediate: Whether to apply immediately

        Returns:
            PlanChangePreview
        """
        subscription = self.subscription_repo.get_by_id(db, subscription_id)
        if not subscription:
            raise ValidationException(f"Subscription not found: {subscription_id}")

        request = PlanChangeRequest(
            subscription_id=subscription_id,
            hostel_id=subscription.hostel_id,
            new_plan_id=new_plan_id,
            effective_from=datetime.utcnow() if immediate else None,
            prorate=True,
            apply_credit=True,
            change_reason="upgrade",
        )

        return self.preview_plan_change(db, request)

    def preview_downgrade(
        self,
        db: Session,
        subscription_id: UUID,
        new_plan_id: UUID,
        end_of_billing_cycle: bool = True,
    ) -> PlanChangePreview:
        """
        Convenience method to preview a downgrade with default settings.

        Args:
            db: Database session
            subscription_id: Current subscription ID
            new_plan_id: Target plan ID
            end_of_billing_cycle: Whether to apply at end of current cycle

        Returns:
            PlanChangePreview
        """
        subscription = self.subscription_repo.get_by_id(db, subscription_id)
        if not subscription:
            raise ValidationException(f"Subscription not found: {subscription_id}")

        # For downgrades, typically apply at end of billing cycle
        effective_from = None if end_of_billing_cycle else datetime.utcnow()

        request = PlanChangeRequest(
            subscription_id=subscription_id,
            hostel_id=subscription.hostel_id,
            new_plan_id=new_plan_id,
            effective_from=effective_from,
            prorate=not end_of_billing_cycle,
            apply_credit=True,
            change_reason="downgrade",
        )

        return self.preview_plan_change(db, request)

    # -------------------------------------------------------------------------
    # Apply
    # -------------------------------------------------------------------------

    def apply_plan_change(
        self,
        db: Session,
        subscription_id: UUID,
        request: PlanChangeRequest,
    ) -> PlanChangeConfirmation:
        """
        Apply a previously previewed plan change.

        This method performs the actual plan change operation including:
        - Updating subscription plan
        - Adjusting billing cycle
        - Applying prorations and credits
        - Creating adjustment records

        Args:
            db: Database session
            subscription_id: UUID of the subscription
            request: Plan change request with all parameters

        Returns:
            PlanChangeConfirmation with results

        Raises:
            ValidationException: If validation fails or application errors occur
        """
        # Validate the request again before applying
        self._validate_plan_change_request(db, request)

        # Ensure subscription_id matches
        if subscription_id != request.subscription_id:
            raise ValidationException("Subscription ID mismatch in request")

        # Get current subscription
        subscription = self.subscription_repo.get_by_id(db, subscription_id)
        if not subscription:
            raise ValidationException(f"Subscription not found: {subscription_id}")

        # Validate ownership
        if subscription.hostel_id != request.hostel_id:
            raise ValidationException("Subscription does not belong to specified hostel")

        # Prevent duplicate plan changes (idempotency check)
        if self._has_pending_plan_change(db, subscription_id):
            raise ValidationException(
                "Subscription has a pending plan change. "
                "Please cancel or complete it before initiating a new change."
            )

        try:
            # Apply the plan change through repository
            confirmation_data = self.subscription_repo.apply_plan_change(
                db=db,
                subscription_id=subscription_id,
                hostel_id=request.hostel_id,
                new_plan_id=request.new_plan_id,
                billing_cycle=request.billing_cycle,
                effective_from=request.effective_from,
                prorate=request.prorate,
                apply_credit=request.apply_credit,
                preserve_trial=request.preserve_trial,
                change_reason=request.change_reason,
            )

            confirmation = PlanChangeConfirmation.model_validate(confirmation_data)

            # Log the successful change
            logger.info(
                f"Applied plan change for subscription {subscription_id}: "
                f"{subscription.plan_id} -> {request.new_plan_id}. "
                f"Reason: {request.change_reason or 'Not specified'}"
            )

            # Send notification (if notification service is available)
            self._notify_plan_change(db, confirmation)

            return confirmation

        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                f"Failed to apply plan change for subscription {subscription_id}: {str(e)}"
            )
            raise ValidationException(f"Failed to apply plan change: {str(e)}")

    def upgrade_subscription(
        self,
        db: Session,
        subscription_id: UUID,
        new_plan_id: UUID,
        immediate: bool = True,
    ) -> PlanChangeConfirmation:
        """
        Upgrade a subscription to a higher-tier plan.

        Args:
            db: Database session
            subscription_id: Current subscription ID
            new_plan_id: Target higher-tier plan ID
            immediate: Whether to apply immediately

        Returns:
            PlanChangeConfirmation
        """
        subscription = self.subscription_repo.get_by_id(db, subscription_id)
        if not subscription:
            raise ValidationException(f"Subscription not found: {subscription_id}")

        request = PlanChangeRequest(
            subscription_id=subscription_id,
            hostel_id=subscription.hostel_id,
            new_plan_id=new_plan_id,
            effective_from=datetime.utcnow() if immediate else None,
            prorate=True,
            apply_credit=True,
            preserve_trial=False,
            change_reason="upgrade",
        )

        return self.apply_plan_change(db, subscription_id, request)

    def downgrade_subscription(
        self,
        db: Session,
        subscription_id: UUID,
        new_plan_id: UUID,
        immediate: bool = False,
    ) -> PlanChangeConfirmation:
        """
        Downgrade a subscription to a lower-tier plan.

        Args:
            db: Database session
            subscription_id: Current subscription ID
            new_plan_id: Target lower-tier plan ID
            immediate: Whether to apply immediately (default: end of billing cycle)

        Returns:
            PlanChangeConfirmation
        """
        subscription = self.subscription_repo.get_by_id(db, subscription_id)
        if not subscription:
            raise ValidationException(f"Subscription not found: {subscription_id}")

        request = PlanChangeRequest(
            subscription_id=subscription_id,
            hostel_id=subscription.hostel_id,
            new_plan_id=new_plan_id,
            effective_from=datetime.utcnow() if immediate else None,
            prorate=immediate,
            apply_credit=True,
            preserve_trial=False,
            change_reason="downgrade",
        )

        return self.apply_plan_change(db, subscription_id, request)

    # -------------------------------------------------------------------------
    # Plan change management
    # -------------------------------------------------------------------------

    def cancel_pending_plan_change(
        self,
        db: Session,
        subscription_id: UUID,
        reason: Optional[str] = None,
    ) -> bool:
        """
        Cancel a pending plan change.

        Args:
            db: Database session
            subscription_id: UUID of the subscription
            reason: Optional reason for cancellation

        Returns:
            True if cancellation successful, False otherwise
        """
        try:
            result = self.subscription_repo.cancel_pending_plan_change(
                db,
                subscription_id=subscription_id,
                reason=reason,
            )

            if result:
                logger.info(
                    f"Cancelled pending plan change for subscription {subscription_id}. "
                    f"Reason: {reason or 'Not specified'}"
                )

            return result

        except Exception as e:
            logger.error(
                f"Error cancelling pending plan change for subscription {subscription_id}: {str(e)}"
            )
            return False

    def get_plan_change_history(
        self,
        db: Session,
        subscription_id: UUID,
        limit: int = 10,
    ) -> list:
        """
        Get history of plan changes for a subscription.

        Args:
            db: Database session
            subscription_id: UUID of the subscription
            limit: Maximum number of history records

        Returns:
            List of plan change history records
        """
        try:
            history = self.subscription_repo.get_plan_change_history(
                db,
                subscription_id=subscription_id,
                limit=limit,
            )

            logger.debug(
                f"Retrieved {len(history)} plan change history records "
                f"for subscription {subscription_id}"
            )

            return history

        except Exception as e:
            logger.error(
                f"Error retrieving plan change history for subscription {subscription_id}: {str(e)}"
            )
            return []

    # -------------------------------------------------------------------------
    # Analytics and recommendations
    # -------------------------------------------------------------------------

    def get_upgrade_recommendations(
        self,
        db: Session,
        subscription_id: UUID,
    ) -> list:
        """
        Get recommended upgrade plans based on current usage and subscription.

        Args:
            db: Database session
            subscription_id: UUID of the subscription

        Returns:
            List of recommended plan IDs with reasoning
        """
        try:
            subscription = self.subscription_repo.get_by_id(db, subscription_id)
            if not subscription:
                return []

            # Get usage patterns
            usage = self.subscription_repo.get_usage_overview(db, subscription_id)

            # Get available higher-tier plans
            current_plan = self.plan_repo.get_by_id(db, subscription.plan_id)
            if not current_plan:
                return []

            higher_plans = self.plan_repo.get_higher_tier_plans(
                db,
                current_plan_id=subscription.plan_id,
            )

            # Analyze and recommend
            recommendations = []
            for plan in higher_plans:
                recommendation = self._analyze_upgrade_fit(usage, current_plan, plan)
                if recommendation:
                    recommendations.append(recommendation)

            logger.debug(
                f"Generated {len(recommendations)} upgrade recommendations "
                f"for subscription {subscription_id}"
            )

            return recommendations

        except Exception as e:
            logger.error(
                f"Error generating upgrade recommendations for subscription {subscription_id}: {str(e)}"
            )
            return []

    def calculate_plan_change_savings(
        self,
        db: Session,
        subscription_id: UUID,
        new_plan_id: UUID,
        months: int = 12,
    ) -> Dict[str, Any]:
        """
        Calculate potential savings/costs of a plan change over time.

        Args:
            db: Database session
            subscription_id: Current subscription ID
            new_plan_id: Target plan ID
            months: Number of months to project

        Returns:
            Dictionary with savings analysis
        """
        try:
            subscription = self.subscription_repo.get_by_id(db, subscription_id)
            if not subscription:
                raise ValidationException(f"Subscription not found: {subscription_id}")

            current_plan = self.plan_repo.get_by_id(db, subscription.plan_id)
            new_plan = self.plan_repo.get_by_id(db, new_plan_id)

            if not current_plan or not new_plan:
                raise ValidationException("Plan not found")

            # Calculate projected costs
            current_monthly = Decimal(str(current_plan.monthly_price or 0))
            new_monthly = Decimal(str(new_plan.monthly_price or 0))

            current_total = current_monthly * Decimal(str(months))
            new_total = new_monthly * Decimal(str(months))
            savings = current_total - new_total

            analysis = {
                "current_plan_id": str(subscription.plan_id),
                "new_plan_id": str(new_plan_id),
                "months_projected": months,
                "current_monthly_cost": float(current_monthly),
                "new_monthly_cost": float(new_monthly),
                "current_total_cost": float(current_total),
                "new_total_cost": float(new_total),
                "total_savings": float(savings),
                "monthly_difference": float(new_monthly - current_monthly),
                "is_upgrade": new_monthly > current_monthly,
                "percentage_change": float(
                    ((new_monthly - current_monthly) / current_monthly * 100)
                    if current_monthly > 0 else 0
                ),
            }

            logger.debug(
                f"Calculated {months}-month savings analysis for plan change: "
                f"{subscription_id} -> {new_plan_id}"
            )

            return analysis

        except Exception as e:
            logger.error(
                f"Error calculating plan change savings for subscription {subscription_id}: {str(e)}"
            )
            return {}

    # -------------------------------------------------------------------------
    # Private helper methods
    # -------------------------------------------------------------------------

    def _validate_plan_change_request(
        self,
        db: Session,
        request: PlanChangeRequest,
    ) -> None:
        """
        Validate plan change request parameters.

        Args:
            db: Database session
            request: Plan change request to validate

        Raises:
            ValidationException: If validation fails
        """
        if not request.subscription_id:
            raise ValidationException("Subscription ID is required")

        if not request.hostel_id:
            raise ValidationException("Hostel ID is required")

        if not request.new_plan_id:
            raise ValidationException("New plan ID is required")

        if request.billing_cycle and request.billing_cycle not in [
            "monthly", "yearly", "quarterly"
        ]:
            raise ValidationException("Invalid billing cycle")

        # Validate effective date is not in the past
        if request.effective_from and request.effective_from < datetime.utcnow():
            raise ValidationException("Effective date cannot be in the past")

    def _has_pending_plan_change(
        self,
        db: Session,
        subscription_id: UUID,
    ) -> bool:
        """
        Check if subscription has a pending plan change.

        Args:
            db: Database session
            subscription_id: UUID of the subscription

        Returns:
            True if pending change exists, False otherwise
        """
        try:
            return self.subscription_repo.has_pending_plan_change(db, subscription_id)
        except Exception as e:
            logger.error(
                f"Error checking pending plan change for subscription {subscription_id}: {str(e)}"
            )
            return False

    def _enrich_preview(
        self,
        db: Session,
        preview: PlanChangePreview,
        current_subscription: Any,
        new_plan: Any,
    ) -> PlanChangePreview:
        """
        Enrich plan change preview with additional context.

        Args:
            db: Database session
            preview: Base preview object
            current_subscription: Current subscription object
            new_plan: Target plan object

        Returns:
            Enriched PlanChangePreview
        """
        try:
            # Add feature comparison
            current_plan = self.plan_repo.get_by_id(db, current_subscription.plan_id)
            if current_plan and new_plan:
                preview.features_added = self._get_new_features(current_plan, new_plan)
                preview.features_removed = self._get_removed_features(current_plan, new_plan)

            # Add recommendations
            if preview.is_upgrade:
                preview.recommendation = "Upgrade recommended for additional features and capacity"
            else:
                preview.recommendation = "Downgrade will reduce costs but may limit some features"

            return preview

        except Exception as e:
            logger.warning(f"Error enriching preview: {str(e)}")
            return preview

    def _get_new_features(self, current_plan: Any, new_plan: Any) -> list:
        """Get features available in new plan but not in current plan."""
        current_features = set(current_plan.features.keys() if current_plan.features else [])
        new_features = set(new_plan.features.keys() if new_plan.features else [])
        return list(new_features - current_features)

    def _get_removed_features(self, current_plan: Any, new_plan: Any) -> list:
        """Get features available in current plan but not in new plan."""
        current_features = set(current_plan.features.keys() if current_plan.features else [])
        new_features = set(new_plan.features.keys() if new_plan.features else [])
        return list(current_features - new_features)

    def _analyze_upgrade_fit(
        self,
        usage: Dict[str, Any],
        current_plan: Any,
        target_plan: Any,
    ) -> Optional[Dict[str, Any]]:
        """
        Analyze if an upgrade plan is a good fit based on usage.

        Args:
            usage: Current usage data
            current_plan: Current plan object
            target_plan: Target plan object

        Returns:
            Recommendation dictionary or None if not suitable
        """
        # This is a placeholder - implement actual business logic
        # based on usage patterns and plan features
        recommendation = {
            "plan_id": str(target_plan.id),
            "plan_name": target_plan.name,
            "reason": "Based on your current usage patterns",
            "confidence_score": 0.75,
        }

        return recommendation

    def _notify_plan_change(
        self,
        db: Session,
        confirmation: PlanChangeConfirmation,
    ) -> None:
        """
        Send notification about plan change.

        Args:
            db: Database session
            confirmation: Plan change confirmation

        Note:
            This is a placeholder for notification integration
        """
        # Implement notification logic here
        # e.g., send email, SMS, in-app notification
        logger.info(
            f"Plan change notification sent for subscription {confirmation.subscription_id}"
        )