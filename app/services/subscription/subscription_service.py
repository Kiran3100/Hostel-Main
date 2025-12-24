"""
Subscription Service

Core subscription management operations.
"""

from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.subscription import (
    SubscriptionRepository,
    SubscriptionAggregateRepository,
)
from app.schemas.subscription import (
    SubscriptionCreate,
    SubscriptionUpdate,
    SubscriptionResponse,
    SubscriptionSummary,
    BillingHistory,
    CancellationRequest,
    CancellationPreview,
    CancellationResponse,
)
from app.core.exceptions import ValidationException


class SubscriptionService:
    """
    High-level service for subscriptions.

    Responsibilities:
    - Create/update subscriptions
    - Cancel and renew
    - Retrieve/list subscriptions
    - Get billing history and basic analytics
    """

    def __init__(
        self,
        subscription_repo: SubscriptionRepository,
        aggregate_repo: SubscriptionAggregateRepository,
    ) -> None:
        self.subscription_repo = subscription_repo
        self.aggregate_repo = aggregate_repo

    # -------------------------------------------------------------------------
    # CRUD
    # -------------------------------------------------------------------------

    def create_subscription(
        self,
        db: Session,
        data: SubscriptionCreate,
    ) -> SubscriptionResponse:
        obj = self.subscription_repo.create(
            db,
            data=data.model_dump(exclude_none=True),
        )
        return SubscriptionResponse.model_validate(obj)

    def update_subscription(
        self,
        db: Session,
        subscription_id: UUID,
        data: SubscriptionUpdate,
    ) -> SubscriptionResponse:
        sub = self.subscription_repo.get_by_id(db, subscription_id)
        if not sub:
            raise ValidationException("Subscription not found")

        updated = self.subscription_repo.update(
            db,
            sub,
            data=data.model_dump(exclude_none=True),
        )
        return SubscriptionResponse.model_validate(updated)

    # -------------------------------------------------------------------------
    # Retrieval
    # -------------------------------------------------------------------------

    def get_subscription(
        self,
        db: Session,
        subscription_id: UUID,
    ) -> SubscriptionResponse:
        sub = self.subscription_repo.get_by_id(db, subscription_id)
        if not sub:
            raise ValidationException("Subscription not found")
        return SubscriptionResponse.model_validate(sub)

    def list_subscriptions_for_hostel(
        self,
        db: Session,
        hostel_id: UUID,
    ) -> List[SubscriptionSummary]:
        objs = self.subscription_repo.get_by_hostel(db, hostel_id)
        return [SubscriptionSummary.model_validate(o) for o in objs]

    def list_subscriptions(
        self,
        db: Session,
        skip: int = 0,
        limit: int = 50,
    ) -> List[SubscriptionSummary]:
        objs = self.subscription_repo.get_list(db, skip, limit)
        return [SubscriptionSummary.model_validate(o) for o in objs]

    # -------------------------------------------------------------------------
    # Billing history
    # -------------------------------------------------------------------------

    def get_billing_history(
        self,
        db: Session,
        subscription_id: UUID,
        page: int = 1,
        page_size: int = 20,
    ) -> BillingHistory:
        data = self.aggregate_repo.get_billing_history(
            db,
            subscription_id=subscription_id,
            page=page,
            page_size=page_size,
        )
        if not data:
            raise ValidationException("No billing history available")

        return BillingHistory.model_validate(data)

    # -------------------------------------------------------------------------
    # Cancellation
    # -------------------------------------------------------------------------

    def preview_cancellation(
        self,
        db: Session,
        request: CancellationRequest,
    ) -> CancellationPreview:
        """
        Compute effective date and refund eligibility without applying.
        """
        data = self.subscription_repo.preview_cancellation(
            db,
            subscription_id=request.subscription_id,
            hostel_id=request.hostel_id,
            cancel_immediately=request.cancel_immediately,
        )
        return CancellationPreview.model_validate(data)

    def cancel_subscription(
        self,
        db: Session,
        request: CancellationRequest,
    ) -> CancellationResponse:
        """
        Cancel a subscription and return result with refund info.
        """
        result = self.subscription_repo.cancel_subscription(
            db,
            subscription_id=request.subscription_id,
            hostel_id=request.hostel_id,
            reason=request.cancellation_reason,
            category=request.cancellation_category,
            cancel_immediately=request.cancel_immediately,
            feedback=request.feedback,
            would_recommend=request.would_recommend,
        )
        return CancellationResponse.model_validate(result)