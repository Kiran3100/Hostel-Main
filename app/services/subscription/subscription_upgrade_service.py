"""
Subscription Upgrade Service

Handles plan change (upgrade/downgrade) operations.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.subscription import SubscriptionRepository, SubscriptionPlanRepository
from app.schemas.subscription import (
    PlanChangeRequest,
    PlanChangePreview,
    PlanChangeConfirmation,
)
from app.core.exceptions import ValidationException


class SubscriptionUpgradeService:
    """
    High-level service for subscription plan changes.

    Responsibilities:
    - Preview financial impact of plan change
    - Apply plan change and record adjustments
    """

    def __init__(
        self,
        subscription_repo: SubscriptionRepository,
        plan_repo: SubscriptionPlanRepository,
    ) -> None:
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
        """
        # Validate target plan exists
        new_plan = self.plan_repo.get_by_id(db, request.new_plan_id)
        if not new_plan:
            raise ValidationException("Target plan not found")

        # Delegate financial calculations to repository
        data = self.subscription_repo.preview_plan_change(
            db=db,
            subscription_id=request.current_plan_id,  # or separate subscription_id field if defined
            hostel_id=request.hostel_id,
            new_plan_id=request.new_plan_id,
            billing_cycle=request.billing_cycle,
            effective_from=request.effective_from,
            prorate=request.prorate,
            apply_credit=request.apply_credit,
            preserve_trial=request.preserve_trial,
            change_reason=request.change_reason,
        )

        return PlanChangePreview.model_validate(data)

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
        """
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

        return PlanChangeConfirmation.model_validate(confirmation_data)