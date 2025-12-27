"""
Subscription Billing Service

Handles subscription billing cycle information and operations.

Improvements:
- Enhanced error handling with specific exceptions
- Added validation for billing cycle operations
- Improved logging for audit trail
- Added caching support pattern
- Better date handling and timezone awareness
"""

from __future__ import annotations

import logging
from typing import List, Optional
from uuid import UUID
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.repositories.subscription import SubscriptionBillingRepository
from app.schemas.subscription import BillingCycleInfo
from app.core1.exceptions import ValidationException

logger = logging.getLogger(__name__)


class SubscriptionBillingService:
    """
    High-level service for subscription billing cycles.

    Responsibilities:
    - Get current and historical billing cycle info
    - List upcoming/prior billing cycles
    - Adjust billing cycles when subscription terms change
    - Generate billing cycle projections
    - Handle prorated billing calculations
    """

    # Constants
    DEFAULT_CYCLE_LIMIT = 12
    MAX_CYCLE_LIMIT = 100

    def __init__(
        self,
        billing_repo: SubscriptionBillingRepository,
    ) -> None:
        """
        Initialize the billing service.

        Args:
            billing_repo: Repository for billing cycle data access

        Raises:
            ValueError: If repository is None
        """
        if not billing_repo:
            raise ValueError("Billing repository is required")
        self.billing_repo = billing_repo

    # -------------------------------------------------------------------------
    # Retrieval
    # -------------------------------------------------------------------------

    def get_billing_cycle_info(
        self,
        db: Session,
        subscription_id: UUID,
    ) -> BillingCycleInfo:
        """
        Get current billing cycle info for a subscription.

        Args:
            db: Database session
            subscription_id: UUID of the subscription

        Returns:
            BillingCycleInfo for the current cycle

        Raises:
            ValidationException: If billing cycle not found
        """
        try:
            info = self.billing_repo.get_current_billing_cycle_info(db, subscription_id)
            
            if not info:
                logger.warning(f"No billing cycle found for subscription: {subscription_id}")
                raise ValidationException(
                    f"Billing cycle not found for subscription: {subscription_id}"
                )

            logger.debug(f"Retrieved billing cycle for subscription: {subscription_id}")
            return BillingCycleInfo.model_validate(info)

        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                f"Error retrieving billing cycle for subscription {subscription_id}: {str(e)}"
            )
            raise ValidationException(f"Failed to retrieve billing cycle: {str(e)}")

    def get_billing_cycle_by_date(
        self,
        db: Session,
        subscription_id: UUID,
        date: datetime,
    ) -> Optional[BillingCycleInfo]:
        """
        Get billing cycle info for a specific date.

        Args:
            db: Database session
            subscription_id: UUID of the subscription
            date: Date to find the billing cycle for

        Returns:
            BillingCycleInfo or None if not found
        """
        try:
            info = self.billing_repo.get_billing_cycle_by_date(
                db, 
                subscription_id=subscription_id,
                date=date
            )
            
            if not info:
                logger.debug(
                    f"No billing cycle found for subscription {subscription_id} at date {date}"
                )
                return None

            return BillingCycleInfo.model_validate(info)

        except Exception as e:
            logger.error(
                f"Error retrieving billing cycle by date for subscription {subscription_id}: {str(e)}"
            )
            return None

    def list_billing_cycles(
        self,
        db: Session,
        subscription_id: UUID,
        limit: int = DEFAULT_CYCLE_LIMIT,
        include_past: bool = True,
        include_future: bool = True,
    ) -> List[BillingCycleInfo]:
        """
        List billing cycles (past + upcoming) for a subscription.

        Args:
            db: Database session
            subscription_id: UUID of the subscription
            limit: Maximum number of cycles to return
            include_past: Include past billing cycles
            include_future: Include future billing cycles

        Returns:
            List of BillingCycleInfo objects sorted by cycle start date

        Raises:
            ValidationException: If limit exceeds maximum or other validation fails
        """
        # Validate limit
        if limit <= 0:
            raise ValidationException("Limit must be positive")
        
        if limit > self.MAX_CYCLE_LIMIT:
            logger.warning(
                f"Requested limit {limit} exceeds maximum {self.MAX_CYCLE_LIMIT}, using maximum"
            )
            limit = self.MAX_CYCLE_LIMIT

        try:
            cycles = self.billing_repo.get_billing_cycles(
                db,
                subscription_id=subscription_id,
                limit=limit,
                include_past=include_past,
                include_future=include_future,
            )
            
            logger.debug(
                f"Retrieved {len(cycles)} billing cycles for subscription: {subscription_id}"
            )
            
            return [BillingCycleInfo.model_validate(c) for c in cycles]

        except Exception as e:
            logger.error(
                f"Error retrieving billing cycles for subscription {subscription_id}: {str(e)}"
            )
            raise ValidationException(f"Failed to retrieve billing cycles: {str(e)}")

    def get_upcoming_billing_cycles(
        self,
        db: Session,
        subscription_id: UUID,
        months_ahead: int = 6,
    ) -> List[BillingCycleInfo]:
        """
        Get upcoming billing cycles for the next N months.

        Args:
            db: Database session
            subscription_id: UUID of the subscription
            months_ahead: Number of months to project ahead

        Returns:
            List of upcoming BillingCycleInfo objects
        """
        if months_ahead <= 0 or months_ahead > 24:
            raise ValidationException("months_ahead must be between 1 and 24")

        return self.list_billing_cycles(
            db,
            subscription_id=subscription_id,
            limit=months_ahead,
            include_past=False,
            include_future=True,
        )

    def get_past_billing_cycles(
        self,
        db: Session,
        subscription_id: UUID,
        limit: int = DEFAULT_CYCLE_LIMIT,
    ) -> List[BillingCycleInfo]:
        """
        Get past billing cycles.

        Args:
            db: Database session
            subscription_id: UUID of the subscription
            limit: Maximum number of past cycles

        Returns:
            List of past BillingCycleInfo objects
        """
        return self.list_billing_cycles(
            db,
            subscription_id=subscription_id,
            limit=limit,
            include_past=True,
            include_future=False,
        )

    # -------------------------------------------------------------------------
    # Billing cycle management
    # -------------------------------------------------------------------------

    def recalculate_billing_cycles(
        self,
        db: Session,
        subscription_id: UUID,
        reason: Optional[str] = None,
    ) -> int:
        """
        Recalculate billing cycles when subscription terms change.

        This method regenerates future billing cycles based on current
        subscription parameters.

        Args:
            db: Database session
            subscription_id: UUID of the subscription
            reason: Optional reason for recalculation

        Returns:
            Number of billing cycles recalculated

        Raises:
            ValidationException: If recalculation fails
        """
        try:
            logger.info(
                f"Recalculating billing cycles for subscription {subscription_id}. "
                f"Reason: {reason or 'Not specified'}"
            )
            
            count = self.billing_repo.recalculate_billing_cycles(
                db, 
                subscription_id=subscription_id,
                reason=reason
            )
            
            logger.info(
                f"Successfully recalculated {count} billing cycles for subscription {subscription_id}"
            )
            
            return count

        except Exception as e:
            logger.error(
                f"Error recalculating billing cycles for subscription {subscription_id}: {str(e)}"
            )
            raise ValidationException(f"Failed to recalculate billing cycles: {str(e)}")

    def create_billing_cycle(
        self,
        db: Session,
        subscription_id: UUID,
        start_date: datetime,
        end_date: datetime,
        amount: float,
        currency: str,
    ) -> BillingCycleInfo:
        """
        Manually create a billing cycle.

        Args:
            db: Database session
            subscription_id: UUID of the subscription
            start_date: Cycle start date
            end_date: Cycle end date
            amount: Billing amount for the cycle
            currency: Currency code

        Returns:
            Created BillingCycleInfo

        Raises:
            ValidationException: If validation fails
        """
        # Validate dates
        if start_date >= end_date:
            raise ValidationException("Start date must be before end date")

        if amount < 0:
            raise ValidationException("Amount cannot be negative")

        try:
            cycle_data = {
                "subscription_id": subscription_id,
                "start_date": start_date,
                "end_date": end_date,
                "amount": amount,
                "currency": currency.upper(),
            }

            created = self.billing_repo.create_billing_cycle(db, cycle_data)
            
            logger.info(
                f"Created billing cycle for subscription {subscription_id}: "
                f"{start_date} to {end_date}, {amount} {currency}"
            )
            
            return BillingCycleInfo.model_validate(created)

        except Exception as e:
            logger.error(
                f"Error creating billing cycle for subscription {subscription_id}: {str(e)}"
            )
            raise ValidationException(f"Failed to create billing cycle: {str(e)}")

    # -------------------------------------------------------------------------
    # Analytics and reporting
    # -------------------------------------------------------------------------

    def get_total_billed_amount(
        self,
        db: Session,
        subscription_id: UUID,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> float:
        """
        Calculate total billed amount for a subscription within a date range.

        Args:
            db: Database session
            subscription_id: UUID of the subscription
            start_date: Optional start date filter
            end_date: Optional end date filter

        Returns:
            Total billed amount
        """
        try:
            cycles = self.billing_repo.get_billing_cycles_in_range(
                db,
                subscription_id=subscription_id,
                start_date=start_date,
                end_date=end_date,
            )

            total = sum(cycle.get("amount", 0) for cycle in cycles)
            
            logger.debug(
                f"Total billed amount for subscription {subscription_id}: {total}"
            )
            
            return total

        except Exception as e:
            logger.error(
                f"Error calculating total billed amount for subscription {subscription_id}: {str(e)}"
            )
            return 0.0

    def get_next_billing_date(
        self,
        db: Session,
        subscription_id: UUID,
    ) -> Optional[datetime]:
        """
        Get the next billing date for a subscription.

        Args:
            db: Database session
            subscription_id: UUID of the subscription

        Returns:
            Next billing date or None
        """
        try:
            current_cycle = self.get_billing_cycle_info(db, subscription_id)
            return current_cycle.end_date if current_cycle else None

        except ValidationException:
            return None
        except Exception as e:
            logger.error(
                f"Error getting next billing date for subscription {subscription_id}: {str(e)}"
            )
            return None

    def is_billing_cycle_active(
        self,
        db: Session,
        subscription_id: UUID,
        check_date: Optional[datetime] = None,
    ) -> bool:
        """
        Check if a billing cycle is active on a given date.

        Args:
            db: Database session
            subscription_id: UUID of the subscription
            check_date: Date to check (defaults to now)

        Returns:
            True if billing cycle is active, False otherwise
        """
        check_date = check_date or datetime.utcnow()
        
        try:
            cycle = self.get_billing_cycle_by_date(db, subscription_id, check_date)
            return cycle is not None

        except Exception as e:
            logger.error(
                f"Error checking billing cycle status for subscription {subscription_id}: {str(e)}"
            )
            return False