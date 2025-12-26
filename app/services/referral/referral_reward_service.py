"""
Referral Reward Service

Manages referral rewards and payouts:
- Reward configuration management
- Reward tracking per user with balance management
- Reward calculation with multiple tiers
- Payout request processing with approval workflow
- Reward summary analytics with aggregations
"""

from __future__ import annotations

import logging
from typing import Optional, Dict, Any
from uuid import UUID
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.repositories.referral import (
    ReferralRewardRepository,
    RewardPayoutRepository,
    RewardTrackingRepository,
    ReferralAggregateRepository,
)
from app.schemas.common import DateRangeFilter
from app.schemas.referral import (
    RewardConfig,
    RewardTracking,
    RewardCalculation,
    PayoutRequest,
    PayoutRequestResponse,
    PayoutHistory,
    RewardSummary,
)
from app.core.exceptions import ValidationException, BusinessLogicException

logger = logging.getLogger(__name__)


class ReferralRewardService:
    """
    High-level orchestration of referral rewards and payouts.
    
    Implements:
    - Multi-tier reward calculation
    - Balance tracking with reservations
    - Payout workflow management
    - Comprehensive analytics
    """

    # Constants for reward processing
    DEFAULT_CURRENCY = "INR"
    MIN_PAYOUT_AMOUNT = Decimal("100")
    MAX_PAYOUT_AMOUNT = Decimal("100000")
    PAYOUT_PROCESSING_DAYS = 7
    MAX_PAYOUTS_PER_MONTH = 10
    MIN_DAYS_BETWEEN_PAYOUTS = 7

    def __init__(
        self,
        reward_repo: ReferralRewardRepository,
        payout_repo: RewardPayoutRepository,
        tracking_repo: RewardTrackingRepository,
        aggregate_repo: ReferralAggregateRepository,
    ) -> None:
        """
        Initialize the referral reward service.

        Args:
            reward_repo: Repository for reward configuration and calculation
            payout_repo: Repository for payout requests
            tracking_repo: Repository for reward tracking/balances
            aggregate_repo: Repository for analytics and aggregations

        Raises:
            ValueError: If any repository is None
        """
        if not all([reward_repo, payout_repo, tracking_repo, aggregate_repo]):
            raise ValueError("All repositories are required")
        
        self.reward_repo = reward_repo
        self.payout_repo = payout_repo
        self.tracking_repo = tracking_repo
        self.aggregate_repo = aggregate_repo

    # -------------------------------------------------------------------------
    # Configuration
    # -------------------------------------------------------------------------

    def get_reward_config(
        self,
        db: Session,
        program_id: Optional[UUID] = None,
    ) -> RewardConfig:
        """
        Retrieve reward configuration (global or per program).

        Args:
            db: Database session
            program_id: Optional program ID for program-specific config

        Returns:
            RewardConfig: Reward configuration with defaults if not found
        """
        try:
            obj = self.reward_repo.get_reward_config(db, program_id=program_id)
            
            if not obj:
                logger.info(
                    "No reward config found, returning defaults",
                    extra={"program_id": str(program_id) if program_id else None},
                )
                return self._get_default_reward_config()
            
            return RewardConfig.model_validate(obj)
            
        except Exception as e:
            logger.error(
                f"Failed to retrieve reward config: {str(e)}",
                extra={"program_id": str(program_id) if program_id else None},
                exc_info=True,
            )
            return self._get_default_reward_config()

    def update_reward_config(
        self,
        db: Session,
        config: RewardConfig,
        updated_by: UUID,
        program_id: Optional[UUID] = None,
    ) -> RewardConfig:
        """
        Update reward configuration.

        Args:
            db: Database session
            config: New configuration
            updated_by: ID of user updating config
            program_id: Optional program ID

        Returns:
            RewardConfig: Updated configuration

        Raises:
            ValidationException: If validation fails
        """
        self._validate_reward_config(config)
        
        try:
            data = config.model_dump(exclude_none=True)
            data["updated_by"] = updated_by
            data["updated_at"] = datetime.utcnow()
            
            obj = self.reward_repo.update_reward_config(
                db=db,
                config_data=data,
                program_id=program_id,
            )
            
            logger.info(
                "Reward config updated",
                extra={
                    "program_id": str(program_id) if program_id else "global",
                    "updated_by": str(updated_by),
                },
            )
            
            return RewardConfig.model_validate(obj)
            
        except Exception as e:
            logger.error(
                f"Failed to update reward config: {str(e)}",
                exc_info=True,
            )
            raise BusinessLogicException(f"Unable to update reward config: {str(e)}")

    # -------------------------------------------------------------------------
    # Reward Calculation & Tracking
    # -------------------------------------------------------------------------

    def calculate_reward_for_referral(
        self,
        db: Session,
        referral_id: UUID,
        override_amount: Optional[Decimal] = None,
    ) -> RewardCalculation:
        """
        Calculate reward for a single referral.

        Delegates scoring and thresholds to repository logic.
        Supports manual override for admin adjustments.

        Args:
            db: Database session
            referral_id: ID of the referral
            override_amount: Optional manual reward amount

        Returns:
            RewardCalculation: Calculated reward details

        Raises:
            ValidationException: If referral not found or calculation fails
        """
        if not referral_id:
            raise ValidationException("Referral ID is required")

        try:
            data = self.reward_repo.calculate_reward_for_referral(
                db=db,
                referral_id=referral_id,
                override_amount=override_amount,
            )
            
            if not data:
                raise ValidationException(
                    f"Unable to calculate reward for referral '{referral_id}'"
                )
            
            calculation = RewardCalculation.model_validate(data)
            
            logger.info(
                "Reward calculated",
                extra={
                    "referral_id": str(referral_id),
                    "referrer_amount": str(calculation.referrer_net_amount),
                    "referee_amount": str(calculation.referee_net_amount),
                },
            )
            
            return calculation
            
        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                f"Failed to calculate reward: {str(e)}",
                extra={"referral_id": str(referral_id)},
                exc_info=True,
            )
            raise BusinessLogicException(f"Reward calculation failed: {str(e)}")

    def apply_reward_for_referral(
        self,
        db: Session,
        referral_id: UUID,
        auto_approve: bool = False,
    ) -> RewardTracking:
        """
        Apply (book) reward for a referral and update tracking balance.

        Args:
            db: Database session
            referral_id: ID of the referral
            auto_approve: If True, immediately approve the reward

        Returns:
            RewardTracking: Updated reward tracking

        Raises:
            ValidationException: If referral not found or already rewarded
            BusinessLogicException: If application fails
        """
        if not referral_id:
            raise ValidationException("Referral ID is required")

        try:
            # Check if reward already applied
            if self.reward_repo.is_reward_applied(db, referral_id):
                raise BusinessLogicException(
                    f"Reward already applied for referral '{referral_id}'"
                )
            
            # Calculate reward
            calculation = self.calculate_reward_for_referral(db, referral_id)
            
            # Apply reward to tracking
            tracking_obj = self.tracking_repo.apply_calculated_reward(
                db=db,
                referral_id=calculation.referral_id,
                program_id=calculation.program_id,
                referrer_net_amount=calculation.referrer_net_amount,
                referee_net_amount=calculation.referee_net_amount,
                auto_approve=auto_approve,
            )
            
            logger.info(
                "Reward applied",
                extra={
                    "referral_id": str(referral_id),
                    "auto_approved": auto_approve,
                },
            )
            
            return RewardTracking.model_validate(tracking_obj)
            
        except (ValidationException, BusinessLogicException):
            raise
        except Exception as e:
            logger.error(
                f"Failed to apply reward: {str(e)}",
                extra={"referral_id": str(referral_id)},
                exc_info=True,
            )
            raise BusinessLogicException(f"Unable to apply reward: {str(e)}")

    def get_reward_tracking_for_user(
        self,
        db: Session,
        user_id: UUID,
        create_if_missing: bool = True,
    ) -> RewardTracking:
        """
        Get or create reward tracking for a user.

        Args:
            db: Database session
            user_id: User identifier
            create_if_missing: If True, create tracking record if it doesn't exist

        Returns:
            RewardTracking: User's reward tracking

        Raises:
            ValidationException: If user_id is invalid
        """
        if not user_id:
            raise ValidationException("User ID is required")

        try:
            if create_if_missing:
                obj = self.tracking_repo.get_or_create_for_user(db, user_id)
            else:
                obj = self.tracking_repo.get_for_user(db, user_id)
                if not obj:
                    raise ValidationException(
                        f"No reward tracking found for user '{user_id}'"
                    )
            
            return RewardTracking.model_validate(obj)
            
        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                f"Failed to get reward tracking: {str(e)}",
                extra={"user_id": str(user_id)},
                exc_info=True,
            )
            raise

    # -------------------------------------------------------------------------
    # Payouts
    # -------------------------------------------------------------------------

    def create_payout_request(
        self,
        db: Session,
        user_id: UUID,
        request: PayoutRequest,
    ) -> PayoutRequestResponse:
        """
        Create a payout request against a user's available reward balance.

        Validates:
        - Sufficient available balance
        - Minimum payout amount
        - Maximum payout amount
        - Monthly payout limits
        - Time between payouts

        Args:
            db: Database session
            user_id: User requesting payout
            request: Payout request details

        Returns:
            PayoutRequestResponse: Created payout request

        Raises:
            ValidationException: If validation fails
            BusinessLogicException: If business rules are violated
        """
        if not user_id:
            raise ValidationException("User ID is required")
        
        self._validate_payout_request(request)

        try:
            # Get user's reward tracking
            tracking = self.tracking_repo.get_or_create_for_user(db, user_id)
            
            # Validate balance
            if request.amount > tracking.available_for_payout:
                raise BusinessLogicException(
                    f"Requested amount ({request.amount}) exceeds available balance "
                    f"({tracking.available_for_payout})"
                )
            
            # Check monthly limits
            self._validate_payout_limits(db, user_id)
            
            # Create payout request
            payload = request.model_dump(exclude_none=True)
            payload["user_id"] = user_id
            payload["status"] = "pending"
            payload["created_at"] = datetime.utcnow()
            
            payout_obj = self.payout_repo.create_payout_request(db, payload)
            
            # Reserve amount from available balance
            self.tracking_repo.reserve_for_payout(
                db=db,
                user_id=user_id,
                amount=request.amount,
            )
            
            logger.info(
                "Payout request created",
                extra={
                    "payout_id": str(payout_obj.id),
                    "user_id": str(user_id),
                    "amount": str(request.amount),
                },
            )
            
            return PayoutRequestResponse.model_validate(payout_obj)
            
        except (ValidationException, BusinessLogicException):
            raise
        except Exception as e:
            logger.error(
                f"Failed to create payout request: {str(e)}",
                extra={"user_id": str(user_id)},
                exc_info=True,
            )
            raise BusinessLogicException(f"Unable to create payout request: {str(e)}")

    def approve_or_reject_payout(
        self,
        db: Session,
        payout_request_id: UUID,
        approved: bool,
        admin_id: UUID,
        notes: Optional[str] = None,
        transaction_id: Optional[str] = None,
    ) -> PayoutRequestResponse:
        """
        Approve or reject a payout request.

        On approval:
        - Mark payout request as approved
        - Adjust tracking balances (reserved → paid)
        - Record transaction details

        On rejection:
        - Mark payout request as rejected
        - Release reserved amounts back to available_for_payout
        - Record rejection reason

        Args:
            db: Database session
            payout_request_id: ID of payout request
            approved: True to approve, False to reject
            admin_id: ID of admin processing the request
            notes: Optional processing notes
            transaction_id: Optional external transaction ID (for approvals)

        Returns:
            PayoutRequestResponse: Updated payout request

        Raises:
            ValidationException: If payout request not found or invalid state
        """
        if not payout_request_id:
            raise ValidationException("Payout request ID is required")
        
        if not admin_id:
            raise ValidationException("Admin ID is required")

        try:
            payout = self.payout_repo.get_by_id(db, payout_request_id)
            if not payout:
                raise ValidationException(
                    f"Payout request '{payout_request_id}' not found"
                )
            
            # Validate state transition
            if payout.status != "pending":
                raise BusinessLogicException(
                    f"Cannot process payout in '{payout.status}' status"
                )

            if approved:
                updated = self._approve_payout(
                    db=db,
                    payout=payout,
                    admin_id=admin_id,
                    notes=notes,
                    transaction_id=transaction_id,
                )
            else:
                updated = self._reject_payout(
                    db=db,
                    payout=payout,
                    admin_id=admin_id,
                    notes=notes,
                )
            
            return PayoutRequestResponse.model_validate(updated)
            
        except (ValidationException, BusinessLogicException):
            raise
        except Exception as e:
            logger.error(
                f"Failed to process payout: {str(e)}",
                extra={"payout_id": str(payout_request_id)},
                exc_info=True,
            )
            raise BusinessLogicException(f"Unable to process payout: {str(e)}")

    def cancel_payout_request(
        self,
        db: Session,
        payout_request_id: UUID,
        user_id: UUID,
        reason: Optional[str] = None,
    ) -> PayoutRequestResponse:
        """
        Cancel a pending payout request (user-initiated).

        Args:
            db: Database session
            payout_request_id: ID of payout to cancel
            user_id: ID of user cancelling (must own the payout)
            reason: Optional cancellation reason

        Returns:
            PayoutRequestResponse: Cancelled payout request

        Raises:
            ValidationException: If validation fails
            BusinessLogicException: If cannot cancel
        """
        try:
            payout = self.payout_repo.get_by_id(db, payout_request_id)
            if not payout:
                raise ValidationException(
                    f"Payout request '{payout_request_id}' not found"
                )
            
            # Verify ownership
            if payout.user_id != user_id:
                raise BusinessLogicException(
                    "Cannot cancel payout request that doesn't belong to you"
                )
            
            # Validate state
            if payout.status != "pending":
                raise BusinessLogicException(
                    f"Cannot cancel payout in '{payout.status}' status"
                )
            
            # Mark as cancelled
            updated = self.payout_repo.mark_cancelled(
                db=db,
                payout=payout,
                cancelled_by=user_id,
                reason=reason,
            )
            
            # Release reserved amount
            self.tracking_repo.release_reserved_amount(
                db=db,
                user_id=user_id,
                amount=payout.amount,
            )
            
            logger.info(
                "Payout request cancelled",
                extra={
                    "payout_id": str(payout_request_id),
                    "user_id": str(user_id),
                },
            )
            
            return PayoutRequestResponse.model_validate(updated)
            
        except (ValidationException, BusinessLogicException):
            raise
        except Exception as e:
            logger.error(
                f"Failed to cancel payout: {str(e)}",
                extra={"payout_id": str(payout_request_id)},
                exc_info=True,
            )
            raise

    def get_payout_history_for_user(
        self,
        db: Session,
        user_id: UUID,
        status_filter: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> PayoutHistory:
        """
        Get payout history for a user.

        Args:
            db: Database session
            user_id: User identifier
            status_filter: Optional status filter (pending, approved, rejected, etc.)
            page: Page number (1-indexed)
            page_size: Items per page

        Returns:
            PayoutHistory: Payout history with aggregations

        Raises:
            ValidationException: If parameters are invalid
        """
        if not user_id:
            raise ValidationException("User ID is required")
        
        if page < 1:
            raise ValidationException("Page must be at least 1")
        
        if page_size < 1 or page_size > 100:
            raise ValidationException("Page size must be between 1 and 100")

        try:
            objs = self.payout_repo.get_history_for_user(
                db=db,
                user_id=user_id,
                status_filter=status_filter,
                page=page,
                page_size=page_size,
            )
            
            # Calculate totals
            total_payouts = len(objs)
            total_amount_paid = sum(
                Decimal(str(o.amount))
                for o in objs
                if o.status == "approved"
            )
            
            logger.debug(
                f"Retrieved {total_payouts} payout records",
                extra={"user_id": str(user_id)},
            )
            
            return PayoutHistory(
                user_id=user_id,
                total_payouts=total_payouts,
                total_amount_paid=str(total_amount_paid),
                payouts=[PayoutRequestResponse.model_validate(o) for o in objs],
            )
            
        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                f"Failed to get payout history: {str(e)}",
                extra={"user_id": str(user_id)},
                exc_info=True,
            )
            raise

    # -------------------------------------------------------------------------
    # Reward Summary
    # -------------------------------------------------------------------------

    def get_reward_summary(
        self,
        db: Session,
        period: DateRangeFilter,
        user_id: Optional[UUID] = None,
        program_id: Optional[UUID] = None,
    ) -> RewardSummary:
        """
        Get aggregated reward summary over a period.

        Can be filtered by user or program for detailed analytics.

        Args:
            db: Database session
            period: Date range for summary
            user_id: Optional user filter
            program_id: Optional program filter

        Returns:
            RewardSummary: Aggregated reward data

        Raises:
            ValidationException: If parameters are invalid
        """
        self._validate_date_range(period)

        try:
            data = self.aggregate_repo.get_reward_summary(
                db=db,
                start_date=period.start_date,
                end_date=period.end_date,
                user_id=user_id,
                program_id=program_id,
            )
            
            if not data:
                # Provide an empty summary with defaults
                logger.info("No reward data found, returning empty summary")
                return self._get_empty_reward_summary(period, user_id, program_id)
            
            summary = RewardSummary.model_validate(data)
            
            logger.debug(
                "Reward summary retrieved",
                extra={
                    "period": f"{period.start_date} to {period.end_date}",
                    "total_rewards": summary.total_rewards_earned,
                },
            )
            
            return summary
            
        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                f"Failed to get reward summary: {str(e)}",
                exc_info=True,
            )
            raise

    # -------------------------------------------------------------------------
    # Private Helper Methods
    # -------------------------------------------------------------------------

    def _get_default_reward_config(self) -> RewardConfig:
        """Get default reward configuration."""
        return RewardConfig(
            min_payout_amount=str(self.MIN_PAYOUT_AMOUNT),
            max_payout_amount=str(self.MAX_PAYOUT_AMOUNT),
            payout_methods=["bank_transfer", "upi"],
            auto_approve_payouts=False,
            payout_processing_time_days=self.PAYOUT_PROCESSING_DAYS,
            payout_fee_percentage="0",
            min_payout_fee="0",
            max_payout_fee="0",
            max_payouts_per_month=self.MAX_PAYOUTS_PER_MONTH,
            min_days_between_payouts=self.MIN_DAYS_BETWEEN_PAYOUTS,
            tax_deduction_applicable=False,
            tax_deduction_percentage="0",
        )

    def _validate_reward_config(self, config: RewardConfig) -> None:
        """Validate reward configuration."""
        if Decimal(config.min_payout_amount) < 0:
            raise ValidationException("Minimum payout amount cannot be negative")
        
        if Decimal(config.max_payout_amount) < Decimal(config.min_payout_amount):
            raise ValidationException(
                "Maximum payout amount must be greater than minimum"
            )
        
        if config.max_payouts_per_month < 1:
            raise ValidationException("Max payouts per month must be at least 1")
        
        if config.min_days_between_payouts < 0:
            raise ValidationException("Min days between payouts cannot be negative")

    def _validate_payout_request(self, request: PayoutRequest) -> None:
        """Validate payout request parameters."""
        if request.amount < self.MIN_PAYOUT_AMOUNT:
            raise ValidationException(
                f"Payout amount must be at least {self.MIN_PAYOUT_AMOUNT}"
            )
        
        if request.amount > self.MAX_PAYOUT_AMOUNT:
            raise ValidationException(
                f"Payout amount cannot exceed {self.MAX_PAYOUT_AMOUNT}"
            )
        
        if hasattr(request, 'payout_method') and request.payout_method:
            valid_methods = ["bank_transfer", "upi", "wallet", "check"]
            if request.payout_method not in valid_methods:
                raise ValidationException(
                    f"Invalid payout method. Must be one of: {', '.join(valid_methods)}"
                )

    def _validate_payout_limits(self, db: Session, user_id: UUID) -> None:
        """Validate payout limits for user."""
        # Check monthly limit
        current_month_start = datetime.utcnow().replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )
        
        monthly_count = self.payout_repo.get_payout_count(
            db=db,
            user_id=user_id,
            start_date=current_month_start,
        )
        
        if monthly_count >= self.MAX_PAYOUTS_PER_MONTH:
            raise BusinessLogicException(
                f"Monthly payout limit ({self.MAX_PAYOUTS_PER_MONTH}) reached"
            )
        
        # Check time between payouts
        last_payout = self.payout_repo.get_last_payout(db, user_id)
        if last_payout:
            days_since_last = (datetime.utcnow() - last_payout.created_at).days
            if days_since_last < self.MIN_DAYS_BETWEEN_PAYOUTS:
                raise BusinessLogicException(
                    f"Must wait {self.MIN_DAYS_BETWEEN_PAYOUTS} days between payouts. "
                    f"Only {days_since_last} days since last payout."
                )

    def _approve_payout(
        self,
        db: Session,
        payout: Any,
        admin_id: UUID,
        notes: Optional[str],
        transaction_id: Optional[str],
    ) -> Any:
        """Approve a payout request."""
        updated = self.payout_repo.mark_approved(
            db=db,
            payout=payout,
            approved_by=admin_id,
            notes=notes,
            transaction_id=transaction_id,
        )
        
        # Move reserved to paid in tracking
        self.tracking_repo.mark_payout_completed(
            db=db,
            user_id=payout.user_id,
            amount=payout.amount,
        )
        
        logger.info(
            "Payout approved",
            extra={
                "payout_id": str(payout.id),
                "user_id": str(payout.user_id),
                "admin_id": str(admin_id),
                "amount": str(payout.amount),
            },
        )
        
        return updated

    def _reject_payout(
        self,
        db: Session,
        payout: Any,
        admin_id: UUID,
        notes: Optional[str],
    ) -> Any:
        """Reject a payout request."""
        updated = self.payout_repo.mark_rejected(
            db=db,
            payout=payout,
            rejected_by=admin_id,
            notes=notes,
        )
        
        # Release reserved amount back to available
        self.tracking_repo.release_reserved_amount(
            db=db,
            user_id=payout.user_id,
            amount=payout.amount,
        )
        
        logger.info(
            "Payout rejected",
            extra={
                "payout_id": str(payout.id),
                "user_id": str(payout.user_id),
                "admin_id": str(admin_id),
                "reason": notes,
            },
        )
        
        return updated

    def _validate_date_range(self, period: DateRangeFilter) -> None:
        """Validate date range."""
        if not period.start_date or not period.end_date:
            raise ValidationException("Both start_date and end_date are required")
        
        if period.end_date < period.start_date:
            raise ValidationException("End date must be after or equal to start date")

    def _get_empty_reward_summary(
        self,
        period: DateRangeFilter,
        user_id: Optional[UUID],
        program_id: Optional[UUID],
    ) -> RewardSummary:
        """Get empty reward summary with defaults."""
        return RewardSummary(
            period_start=period.start_date,
            period_end=period.end_date,
            user_id=user_id,
            program_id=program_id,
            total_rewards_earned="0",
            total_rewards_approved="0",
            total_rewards_paid="0",
            pending_rewards="0",
            cancelled_rewards="0",
            rewards_by_status={},
            rewards_by_program={},
            rewards_by_month={},
            payout_request_count=0,
            successful_payouts=0,
            failed_payouts=0,
            average_reward_amount="0",
            average_payout_amount="0",
            currency=self.DEFAULT_CURRENCY,
        )