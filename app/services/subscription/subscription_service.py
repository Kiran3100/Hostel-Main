"""
Subscription Service

Core subscription management operations.

Improvements:
- Enhanced lifecycle management
- Better renewal logic
- Improved cancellation workflow
- Added grace period handling
- Better trial period management
- Enhanced error handling and logging
"""

from __future__ import annotations

import logging
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime, timedelta

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
    SubscriptionStatus,
)
from app.core1.exceptions import ValidationException

logger = logging.getLogger(__name__)


class SubscriptionService:
    """
    High-level service for subscriptions.

    Responsibilities:
    - Create/update subscriptions with validation
    - Cancel and renew subscriptions
    - Retrieve/list subscriptions with filters
    - Get billing history and analytics
    - Handle trial periods and grace periods
    - Manage subscription lifecycle
    """

    # Constants
    DEFAULT_GRACE_PERIOD_DAYS = 7
    DEFAULT_PAGE_SIZE = 50
    MAX_PAGE_SIZE = 100

    def __init__(
        self,
        subscription_repo: SubscriptionRepository,
        aggregate_repo: SubscriptionAggregateRepository,
    ) -> None:
        """
        Initialize the subscription service.

        Args:
            subscription_repo: Repository for subscription data access
            aggregate_repo: Repository for aggregated subscription data

        Raises:
            ValueError: If repositories are None
        """
        if not subscription_repo:
            raise ValueError("Subscription repository is required")
        if not aggregate_repo:
            raise ValueError("Aggregate repository is required")
        
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
        """
        Create a new subscription with validation.

        Args:
            db: Database session
            data: Subscription creation data

        Returns:
            Created SubscriptionResponse

        Raises:
            ValidationException: If validation fails
        """
        # Validate subscription data
        self._validate_subscription_data(data)

        # Check for existing active subscription
        if self._has_active_subscription(db, data.hostel_id, data.plan_id):
            raise ValidationException(
                f"Hostel {data.hostel_id} already has an active subscription for this plan"
            )

        try:
            subscription_dict = data.model_dump(exclude_none=True)
            
            # Set initial status
            subscription_dict["status"] = SubscriptionStatus.PENDING.value
            subscription_dict["created_at"] = datetime.utcnow()
            
            # Handle trial period
            if data.trial_period_days and data.trial_period_days > 0:
                subscription_dict["trial_start_date"] = datetime.utcnow()
                subscription_dict["trial_end_date"] = datetime.utcnow() + timedelta(
                    days=data.trial_period_days
                )
            
            obj = self.subscription_repo.create(db, data=subscription_dict)
            
            logger.info(
                f"Created subscription for hostel {data.hostel_id}, "
                f"plan {data.plan_id} (ID: {obj.id})"
            )
            
            return SubscriptionResponse.model_validate(obj)

        except Exception as e:
            logger.error(
                f"Failed to create subscription for hostel {data.hostel_id}: {str(e)}"
            )
            raise ValidationException(f"Failed to create subscription: {str(e)}")

    def update_subscription(
        self,
        db: Session,
        subscription_id: UUID,
        data: SubscriptionUpdate,
    ) -> SubscriptionResponse:
        """
        Update an existing subscription.

        Args:
            db: Database session
            subscription_id: UUID of the subscription to update
            data: Subscription update data

        Returns:
            Updated SubscriptionResponse

        Raises:
            ValidationException: If subscription not found or validation fails
        """
        sub = self.subscription_repo.get_by_id(db, subscription_id)
        if not sub:
            raise ValidationException(f"Subscription not found with ID: {subscription_id}")

        # Validate status transitions if status is being updated
        if data.status and data.status != sub.status:
            self._validate_status_transition(
                current_status=SubscriptionStatus(sub.status),
                new_status=SubscriptionStatus(data.status),
            )

        try:
            update_dict = data.model_dump(exclude_none=True)
            update_dict["updated_at"] = datetime.utcnow()
            
            updated = self.subscription_repo.update(db, sub, data=update_dict)
            
            logger.info(f"Updated subscription {subscription_id}")
            return SubscriptionResponse.model_validate(updated)

        except Exception as e:
            logger.error(f"Failed to update subscription {subscription_id}: {str(e)}")
            raise ValidationException(f"Failed to update subscription: {str(e)}")

    # -------------------------------------------------------------------------
    # Retrieval
    # -------------------------------------------------------------------------

    def get_subscription(
        self,
        db: Session,
        subscription_id: UUID,
    ) -> SubscriptionResponse:
        """
        Retrieve a subscription by ID.

        Args:
            db: Database session
            subscription_id: UUID of the subscription

        Returns:
            SubscriptionResponse

        Raises:
            ValidationException: If subscription not found
        """
        sub = self.subscription_repo.get_by_id(db, subscription_id)
        if not sub:
            raise ValidationException(f"Subscription not found with ID: {subscription_id}")
        
        return SubscriptionResponse.model_validate(sub)

    def list_subscriptions_for_hostel(
        self,
        db: Session,
        hostel_id: UUID,
        status: Optional[SubscriptionStatus] = None,
        include_cancelled: bool = False,
    ) -> List[SubscriptionSummary]:
        """
        List all subscriptions for a hostel.

        Args:
            db: Database session
            hostel_id: UUID of the hostel
            status: Optional status filter
            include_cancelled: Whether to include cancelled subscriptions

        Returns:
            List of SubscriptionSummary objects
        """
        try:
            objs = self.subscription_repo.get_by_hostel(
                db,
                hostel_id=hostel_id,
                status=status.value if status else None,
                include_cancelled=include_cancelled,
            )
            
            logger.debug(f"Retrieved {len(objs)} subscriptions for hostel {hostel_id}")
            return [SubscriptionSummary.model_validate(o) for o in objs]

        except Exception as e:
            logger.error(
                f"Error retrieving subscriptions for hostel {hostel_id}: {str(e)}"
            )
            return []

    def get_active_subscription_for_hostel(
        self,
        db: Session,
        hostel_id: UUID,
    ) -> Optional[SubscriptionResponse]:
        """
        Get the active subscription for a hostel.

        Args:
            db: Database session
            hostel_id: UUID of the hostel

        Returns:
            SubscriptionResponse or None if no active subscription
        """
        try:
            obj = self.subscription_repo.get_active_subscription(db, hostel_id)
            return SubscriptionResponse.model_validate(obj) if obj else None

        except Exception as e:
            logger.error(
                f"Error retrieving active subscription for hostel {hostel_id}: {str(e)}"
            )
            return None

    def list_subscriptions(
        self,
        db: Session,
        skip: int = 0,
        limit: int = DEFAULT_PAGE_SIZE,
        status: Optional[SubscriptionStatus] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[SubscriptionSummary]:
        """
        List subscriptions with pagination and filters.

        Args:
            db: Database session
            skip: Number of results to skip
            limit: Maximum number of results
            status: Optional status filter
            start_date: Optional start date filter
            end_date: Optional end date filter

        Returns:
            List of SubscriptionSummary objects
        """
        # Validate and cap limit
        if limit > self.MAX_PAGE_SIZE:
            logger.warning(
                f"Requested limit {limit} exceeds maximum {self.MAX_PAGE_SIZE}"
            )
            limit = self.MAX_PAGE_SIZE

        try:
            objs = self.subscription_repo.get_list(
                db,
                skip=skip,
                limit=limit,
                status=status.value if status else None,
                start_date=start_date,
                end_date=end_date,
            )
            
            logger.debug(f"Retrieved {len(objs)} subscriptions (skip={skip}, limit={limit})")
            return [SubscriptionSummary.model_validate(o) for o in objs]

        except Exception as e:
            logger.error(f"Error listing subscriptions: {str(e)}")
            return []

    def get_expiring_subscriptions(
        self,
        db: Session,
        days_until_expiry: int = 30,
    ) -> List[SubscriptionSummary]:
        """
        Get subscriptions expiring within a specified number of days.

        Args:
            db: Database session
            days_until_expiry: Number of days to look ahead

        Returns:
            List of expiring SubscriptionSummary objects
        """
        try:
            cutoff_date = datetime.utcnow() + timedelta(days=days_until_expiry)
            
            objs = self.subscription_repo.get_expiring_subscriptions(
                db,
                cutoff_date=cutoff_date,
            )
            
            logger.info(f"Found {len(objs)} subscriptions expiring within {days_until_expiry} days")
            return [SubscriptionSummary.model_validate(o) for o in objs]

        except Exception as e:
            logger.error(f"Error retrieving expiring subscriptions: {str(e)}")
            return []

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
        """
        Get billing history for a subscription.

        Args:
            db: Database session
            subscription_id: UUID of the subscription
            page: Page number (1-indexed)
            page_size: Number of items per page

        Returns:
            BillingHistory object

        Raises:
            ValidationException: If subscription not found or no billing history
        """
        # Validate pagination
        if page < 1:
            raise ValidationException("Page number must be >= 1")
        
        if page_size < 1 or page_size > 100:
            raise ValidationException("Page size must be between 1 and 100")

        try:
            data = self.aggregate_repo.get_billing_history(
                db,
                subscription_id=subscription_id,
                page=page,
                page_size=page_size,
            )
            
            if not data:
                raise ValidationException(
                    f"No billing history available for subscription {subscription_id}"
                )

            logger.debug(
                f"Retrieved billing history for subscription {subscription_id} "
                f"(page {page}, size {page_size})"
            )
            
            return BillingHistory.model_validate(data)

        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                f"Error retrieving billing history for subscription {subscription_id}: {str(e)}"
            )
            raise ValidationException(f"Failed to retrieve billing history: {str(e)}")

    # -------------------------------------------------------------------------
    # Subscription lifecycle
    # -------------------------------------------------------------------------

    def activate_subscription(
        self,
        db: Session,
        subscription_id: UUID,
    ) -> SubscriptionResponse:
        """
        Activate a pending or trial subscription.

        Args:
            db: Database session
            subscription_id: UUID of the subscription

        Returns:
            Activated SubscriptionResponse
        """
        sub = self.subscription_repo.get_by_id(db, subscription_id)
        if not sub:
            raise ValidationException(f"Subscription not found with ID: {subscription_id}")

        current_status = SubscriptionStatus(sub.status)
        if current_status not in [SubscriptionStatus.PENDING, SubscriptionStatus.TRIAL]:
            raise ValidationException(
                f"Cannot activate subscription with status {current_status.value}"
            )

        try:
            updated = self.subscription_repo.update(
                db,
                sub,
                data={
                    "status": SubscriptionStatus.ACTIVE.value,
                    "activated_at": datetime.utcnow(),
                }
            )
            
            logger.info(f"Activated subscription {subscription_id}")
            return SubscriptionResponse.model_validate(updated)

        except Exception as e:
            logger.error(f"Failed to activate subscription {subscription_id}: {str(e)}")
            raise ValidationException(f"Failed to activate subscription: {str(e)}")

    def suspend_subscription(
        self,
        db: Session,
        subscription_id: UUID,
        reason: Optional[str] = None,
    ) -> SubscriptionResponse:
        """
        Suspend an active subscription.

        Args:
            db: Database session
            subscription_id: UUID of the subscription
            reason: Optional reason for suspension

        Returns:
            Suspended SubscriptionResponse
        """
        sub = self.subscription_repo.get_by_id(db, subscription_id)
        if not sub:
            raise ValidationException(f"Subscription not found with ID: {subscription_id}")

        if sub.status != SubscriptionStatus.ACTIVE.value:
            raise ValidationException(
                f"Can only suspend active subscriptions, current status: {sub.status}"
            )

        try:
            updated = self.subscription_repo.update(
                db,
                sub,
                data={
                    "status": SubscriptionStatus.SUSPENDED.value,
                    "suspended_at": datetime.utcnow(),
                    "suspension_reason": reason,
                }
            )
            
            logger.info(
                f"Suspended subscription {subscription_id}. Reason: {reason or 'N/A'}"
            )
            return SubscriptionResponse.model_validate(updated)

        except Exception as e:
            logger.error(f"Failed to suspend subscription {subscription_id}: {str(e)}")
            raise ValidationException(f"Failed to suspend subscription: {str(e)}")

    def renew_subscription(
        self,
        db: Session,
        subscription_id: UUID,
        extend_by_days: Optional[int] = None,
    ) -> SubscriptionResponse:
        """
        Renew an expiring or expired subscription.

        Args:
            db: Database session
            subscription_id: UUID of the subscription
            extend_by_days: Optional custom extension period

        Returns:
            Renewed SubscriptionResponse
        """
        sub = self.subscription_repo.get_by_id(db, subscription_id)
        if not sub:
            raise ValidationException(f"Subscription not found with ID: {subscription_id}")

        try:
            renewed = self.subscription_repo.renew_subscription(
                db,
                subscription_id=subscription_id,
                extend_by_days=extend_by_days,
            )
            
            logger.info(f"Renewed subscription {subscription_id}")
            return SubscriptionResponse.model_validate(renewed)

        except Exception as e:
            logger.error(f"Failed to renew subscription {subscription_id}: {str(e)}")
            raise ValidationException(f"Failed to renew subscription: {str(e)}")

    # -------------------------------------------------------------------------
    # Cancellation
    # -------------------------------------------------------------------------

    def preview_cancellation(
        self,
        db: Session,
        request: CancellationRequest,
    ) -> CancellationPreview:
        """
        Compute effective date and refund eligibility without applying cancellation.

        Args:
            db: Database session
            request: Cancellation request with parameters

        Returns:
            CancellationPreview with estimated impact

        Raises:
            ValidationException: If validation fails
        """
        # Validate subscription exists
        sub = self.subscription_repo.get_by_id(db, request.subscription_id)
        if not sub:
            raise ValidationException(
                f"Subscription not found with ID: {request.subscription_id}"
            )

        # Verify hostel ownership
        if sub.hostel_id != request.hostel_id:
            raise ValidationException("Subscription does not belong to specified hostel")

        try:
            data = self.subscription_repo.preview_cancellation(
                db,
                subscription_id=request.subscription_id,
                hostel_id=request.hostel_id,
                cancel_immediately=request.cancel_immediately,
            )
            
            logger.debug(f"Generated cancellation preview for subscription {request.subscription_id}")
            return CancellationPreview.model_validate(data)

        except Exception as e:
            logger.error(
                f"Error previewing cancellation for subscription {request.subscription_id}: {str(e)}"
            )
            raise ValidationException(f"Failed to preview cancellation: {str(e)}")

    def cancel_subscription(
        self,
        db: Session,
        request: CancellationRequest,
    ) -> CancellationResponse:
        """
        Cancel a subscription and return result with refund info.

        Args:
            db: Database session
            request: Cancellation request with all parameters

        Returns:
            CancellationResponse with cancellation details

        Raises:
            ValidationException: If validation fails
        """
        # Validate subscription exists
        sub = self.subscription_repo.get_by_id(db, request.subscription_id)
        if not sub:
            raise ValidationException(
                f"Subscription not found with ID: {request.subscription_id}"
            )

        # Verify hostel ownership
        if sub.hostel_id != request.hostel_id:
            raise ValidationException("Subscription does not belong to specified hostel")

        # Check if already cancelled
        if sub.status == SubscriptionStatus.CANCELLED.value:
            raise ValidationException("Subscription is already cancelled")

        try:
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
            
            logger.info(
                f"Cancelled subscription {request.subscription_id}. "
                f"Reason: {request.cancellation_reason or 'Not specified'}"
            )
            
            return CancellationResponse.model_validate(result)

        except Exception as e:
            logger.error(
                f"Failed to cancel subscription {request.subscription_id}: {str(e)}"
            )
            raise ValidationException(f"Failed to cancel subscription: {str(e)}")

    # -------------------------------------------------------------------------
    # Analytics
    # -------------------------------------------------------------------------

    def get_subscription_metrics(
        self,
        db: Session,
        hostel_id: Optional[UUID] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Get subscription metrics and statistics.

        Args:
            db: Database session
            hostel_id: Optional hostel filter
            start_date: Optional start date filter
            end_date: Optional end date filter

        Returns:
            Dictionary with subscription metrics
        """
        try:
            metrics = self.aggregate_repo.get_subscription_metrics(
                db,
                hostel_id=hostel_id,
                start_date=start_date,
                end_date=end_date,
            )
            
            logger.debug(f"Retrieved subscription metrics for hostel {hostel_id or 'all'}")
            return metrics

        except Exception as e:
            logger.error(f"Error retrieving subscription metrics: {str(e)}")
            return {}

    # -------------------------------------------------------------------------
    # Private helper methods
    # -------------------------------------------------------------------------

    def _validate_subscription_data(self, data: SubscriptionCreate) -> None:
        """
        Validate subscription creation data.

        Args:
            data: Subscription creation data

        Raises:
            ValidationException: If validation fails
        """
        if data.trial_period_days is not None and data.trial_period_days < 0:
            raise ValidationException("Trial period cannot be negative")

        if data.billing_interval not in ["monthly", "yearly", "quarterly"]:
            raise ValidationException("Invalid billing interval")

    def _has_active_subscription(
        self,
        db: Session,
        hostel_id: UUID,
        plan_id: UUID,
    ) -> bool:
        """
        Check if hostel has an active subscription for the plan.

        Args:
            db: Database session
            hostel_id: UUID of the hostel
            plan_id: UUID of the plan

        Returns:
            True if active subscription exists, False otherwise
        """
        active = self.subscription_repo.get_active_subscription(
            db,
            hostel_id=hostel_id,
            plan_id=plan_id,
        )
        return active is not None

    def _validate_status_transition(
        self,
        current_status: SubscriptionStatus,
        new_status: SubscriptionStatus,
    ) -> None:
        """
        Validate subscription status transition.

        Args:
            current_status: Current subscription status
            new_status: Desired new status

        Raises:
            ValidationException: If transition is not allowed
        """
        # Define allowed transitions
        allowed_transitions = {
            SubscriptionStatus.PENDING: {
                SubscriptionStatus.ACTIVE,
                SubscriptionStatus.TRIAL,
                SubscriptionStatus.CANCELLED,
            },
            SubscriptionStatus.TRIAL: {
                SubscriptionStatus.ACTIVE,
                SubscriptionStatus.CANCELLED,
            },
            SubscriptionStatus.ACTIVE: {
                SubscriptionStatus.SUSPENDED,
                SubscriptionStatus.PAST_DUE,
                SubscriptionStatus.CANCELLED,
            },
            SubscriptionStatus.PAST_DUE: {
                SubscriptionStatus.ACTIVE,
                SubscriptionStatus.SUSPENDED,
                SubscriptionStatus.CANCELLED,
            },
            SubscriptionStatus.SUSPENDED: {
                SubscriptionStatus.ACTIVE,
                SubscriptionStatus.CANCELLED,
            },
            SubscriptionStatus.CANCELLED: set(),  # Terminal state
        }

        if new_status not in allowed_transitions.get(current_status, set()):
            raise ValidationException(
                f"Invalid subscription status transition from {current_status.value} "
                f"to {new_status.value}"
            )