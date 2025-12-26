"""
Referral Service

Core referral lifecycle:
- Create/update referrals with validation
- Record conversions (booking → referral success) with idempotency
- Retrieve referrals (detail/list) with filtering
- Referral stats & analytics with caching support
- Leaderboards with ranking algorithms
- Timeline tracking for audit trails
"""

from __future__ import annotations

import logging
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime

from sqlalchemy.orm import Session

from app.repositories.referral import ReferralRepository, ReferralAggregateRepository
from app.schemas.common import DateRangeFilter
from app.schemas.referral import (
    ReferralCreate,
    ReferralUpdate,
    ReferralConversion,
    ReferralResponse,
    ReferralDetail,
    ReferralStats,
    ReferralLeaderboard,
    ReferralAnalytics,
    ReferralTimeline,
)
from app.core.exceptions import ValidationException, BusinessLogicException

logger = logging.getLogger(__name__)


class ReferralService:
    """
    High-level orchestration for referrals.

    Delegates persistence to ReferralRepository and 
    analytics to ReferralAggregateRepository.
    
    Implements comprehensive business logic for the referral lifecycle.
    """

    # Status constants
    STATUS_PENDING = "pending"
    STATUS_CONVERTED = "converted"
    STATUS_FAILED = "failed"
    STATUS_CANCELLED = "cancelled"
    
    VALID_STATUSES = [STATUS_PENDING, STATUS_CONVERTED, STATUS_FAILED, STATUS_CANCELLED]

    def __init__(
        self,
        referral_repo: ReferralRepository,
        aggregate_repo: ReferralAggregateRepository,
    ) -> None:
        """
        Initialize the referral service.

        Args:
            referral_repo: Repository for referral data operations
            aggregate_repo: Repository for analytics and aggregations

        Raises:
            ValueError: If any repository is None
        """
        if not referral_repo or not aggregate_repo:
            raise ValueError("Both repositories are required")
        
        self.referral_repo = referral_repo
        self.aggregate_repo = aggregate_repo

    # -------------------------------------------------------------------------
    # CRUD Operations
    # -------------------------------------------------------------------------

    def create_referral(
        self,
        db: Session,
        request: ReferralCreate,
    ) -> ReferralResponse:
        """
        Create a new referral.

        Validates:
        - Referrer and referee are different users
        - Referee hasn't been referred before (optional enforcement)
        - Program is active
        - Referral code is valid

        Args:
            db: Database session
            request: Referral creation request

        Returns:
            ReferralResponse: Created referral

        Raises:
            ValidationException: If validation fails
            BusinessLogicException: If business rules are violated
        """
        self._validate_referral_create(request)

        try:
            # Check for duplicate referral
            if self._is_duplicate_referral(db, request):
                raise BusinessLogicException(
                    "Referee has already been referred in this program"
                )
            
            data = request.model_dump(exclude_none=True)
            data["status"] = self.STATUS_PENDING
            data["created_at"] = datetime.utcnow()
            
            obj = self.referral_repo.create(db, data=data)
            
            logger.info(
                "Referral created",
                extra={
                    "referral_id": str(obj.id),
                    "referrer_id": str(request.referrer_id),
                    "referee_id": str(request.referee_id),
                    "program_id": str(request.program_id),
                },
            )
            
            return ReferralResponse.model_validate(obj)
            
        except (ValidationException, BusinessLogicException):
            raise
        except Exception as e:
            logger.error(
                f"Failed to create referral: {str(e)}",
                extra={
                    "referrer_id": str(request.referrer_id),
                    "referee_id": str(request.referee_id),
                },
                exc_info=True,
            )
            raise BusinessLogicException(f"Unable to create referral: {str(e)}")

    def update_referral(
        self,
        db: Session,
        referral_id: UUID,
        request: ReferralUpdate,
        updated_by: Optional[UUID] = None,
    ) -> ReferralResponse:
        """
        Update an existing referral.

        Note: Some fields like referrer_id, referee_id may be immutable
        depending on business rules.

        Args:
            db: Database session
            referral_id: ID of referral to update
            request: Referral update request
            updated_by: Optional ID of user making the update

        Returns:
            ReferralResponse: Updated referral

        Raises:
            ValidationException: If referral not found or validation fails
        """
        if not referral_id:
            raise ValidationException("Referral ID is required")

        try:
            referral = self.referral_repo.get_by_id(db, referral_id)
            if not referral:
                raise ValidationException(f"Referral '{referral_id}' not found")

            self._validate_referral_update(request, referral)
            
            data = request.model_dump(exclude_none=True)
            data["updated_at"] = datetime.utcnow()
            if updated_by:
                data["updated_by"] = updated_by
            
            updated = self.referral_repo.update(db, referral, data=data)
            
            logger.info(
                "Referral updated",
                extra={
                    "referral_id": str(referral_id),
                    "updated_by": str(updated_by) if updated_by else None,
                },
            )
            
            return ReferralResponse.model_validate(updated)
            
        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                f"Failed to update referral: {str(e)}",
                extra={"referral_id": str(referral_id)},
                exc_info=True,
            )
            raise BusinessLogicException(f"Unable to update referral: {str(e)}")

    def cancel_referral(
        self,
        db: Session,
        referral_id: UUID,
        reason: Optional[str] = None,
        cancelled_by: Optional[UUID] = None,
    ) -> ReferralResponse:
        """
        Cancel a referral.

        Args:
            db: Database session
            referral_id: ID of referral to cancel
            reason: Optional cancellation reason
            cancelled_by: Optional ID of user cancelling

        Returns:
            ReferralResponse: Cancelled referral

        Raises:
            ValidationException: If referral not found
            BusinessLogicException: If referral cannot be cancelled
        """
        try:
            referral = self.referral_repo.get_by_id(db, referral_id)
            if not referral:
                raise ValidationException(f"Referral '{referral_id}' not found")
            
            # Can't cancel converted referrals
            if referral.status == self.STATUS_CONVERTED:
                raise BusinessLogicException(
                    "Cannot cancel a converted referral"
                )
            
            data = {
                "status": self.STATUS_CANCELLED,
                "cancelled_at": datetime.utcnow(),
                "cancellation_reason": reason,
            }
            if cancelled_by:
                data["cancelled_by"] = cancelled_by
            
            updated = self.referral_repo.update(db, referral, data=data)
            
            logger.info(
                "Referral cancelled",
                extra={
                    "referral_id": str(referral_id),
                    "reason": reason,
                },
            )
            
            return ReferralResponse.model_validate(updated)
            
        except (ValidationException, BusinessLogicException):
            raise
        except Exception as e:
            logger.error(
                f"Failed to cancel referral: {str(e)}",
                extra={"referral_id": str(referral_id)},
                exc_info=True,
            )
            raise

    # -------------------------------------------------------------------------
    # Conversions
    # -------------------------------------------------------------------------

    def record_conversion(
        self,
        db: Session,
        request: ReferralConversion,
    ) -> ReferralDetail:
        """
        Mark a referral as converted and update reward fields.

        Implements idempotency - if already converted, returns existing data.
        
        The repository should handle status transitions, reward calculation, etc.

        Args:
            db: Database session
            request: Conversion details (booking info, amounts, etc.)

        Returns:
            ReferralDetail: Full referral details with conversion data

        Raises:
            ValidationException: If referral not found or validation fails
            BusinessLogicException: If conversion business rules are violated
        """
        self._validate_conversion_request(request)

        try:
            referral = self.referral_repo.get_by_id(db, request.referral_id)
            if not referral:
                raise ValidationException(
                    f"Referral '{request.referral_id}' not found"
                )
            
            # Idempotency check
            if referral.status == self.STATUS_CONVERTED:
                logger.info(
                    "Referral already converted, returning existing data",
                    extra={"referral_id": str(request.referral_id)},
                )
                full = self.referral_repo.get_full_referral(db, referral.id)
                return ReferralDetail.model_validate(full)
            
            # Validate status transition
            if referral.status not in [self.STATUS_PENDING]:
                raise BusinessLogicException(
                    f"Cannot convert referral in '{referral.status}' status"
                )
            
            # Record conversion
            updated = self.referral_repo.record_conversion(
                db=db,
                referral=referral,
                booking_id=request.booking_id,
                booking_amount=request.booking_amount,
                stay_duration_months=request.stay_duration_months,
                conversion_date=request.conversion_date or datetime.utcnow(),
            )
            
            logger.info(
                "Referral conversion recorded",
                extra={
                    "referral_id": str(request.referral_id),
                    "booking_id": str(request.booking_id),
                    "booking_amount": str(request.booking_amount),
                },
            )
            
            full = self.referral_repo.get_full_referral(db, updated.id)
            return ReferralDetail.model_validate(full)
            
        except (ValidationException, BusinessLogicException):
            raise
        except Exception as e:
            logger.error(
                f"Failed to record conversion: {str(e)}",
                extra={"referral_id": str(request.referral_id)},
                exc_info=True,
            )
            raise BusinessLogicException(f"Unable to record conversion: {str(e)}")

    # -------------------------------------------------------------------------
    # Retrieval & Listing
    # -------------------------------------------------------------------------

    def get_referral(
        self,
        db: Session,
        referral_id: UUID,
        include_timeline: bool = False,
    ) -> ReferralDetail:
        """
        Get detailed information for a specific referral.

        Args:
            db: Database session
            referral_id: ID of referral
            include_timeline: If True, include timeline events

        Returns:
            ReferralDetail: Comprehensive referral details

        Raises:
            ValidationException: If referral not found
        """
        if not referral_id:
            raise ValidationException("Referral ID is required")

        try:
            obj = self.referral_repo.get_full_referral(
                db=db,
                referral_id=referral_id,
                include_timeline=include_timeline,
            )
            
            if not obj:
                raise ValidationException(f"Referral '{referral_id}' not found")
            
            return ReferralDetail.model_validate(obj)
            
        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                f"Failed to get referral: {str(e)}",
                extra={"referral_id": str(referral_id)},
                exc_info=True,
            )
            raise

    def list_referrals_for_program(
        self,
        db: Session,
        program_id: UUID,
        status_filter: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> List[ReferralResponse]:
        """
        List all referrals for a specific program.

        Args:
            db: Database session
            program_id: Program identifier
            status_filter: Optional status filter
            page: Page number (1-indexed)
            page_size: Items per page

        Returns:
            List[ReferralResponse]: List of referrals

        Raises:
            ValidationException: If parameters are invalid
        """
        if not program_id:
            raise ValidationException("Program ID is required")
        
        self._validate_pagination(page, page_size)
        
        if status_filter and status_filter not in self.VALID_STATUSES:
            raise ValidationException(f"Invalid status: {status_filter}")

        try:
            objs = self.referral_repo.get_by_program(
                db=db,
                program_id=program_id,
                status=status_filter,
                page=page,
                page_size=page_size,
            )
            
            logger.debug(
                f"Retrieved {len(objs)} referrals for program",
                extra={"program_id": str(program_id)},
            )
            
            return [ReferralResponse.model_validate(o) for o in objs]
            
        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                f"Failed to list referrals for program: {str(e)}",
                extra={"program_id": str(program_id)},
                exc_info=True,
            )
            raise

    def list_referrals_for_user(
        self,
        db: Session,
        user_id: UUID,
        role: str = "referrer",
        status_filter: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> List[ReferralResponse]:
        """
        List all referrals for a specific user.

        Args:
            db: Database session
            user_id: User identifier
            role: User role - 'referrer' or 'referee'
            status_filter: Optional status filter
            page: Page number (1-indexed)
            page_size: Items per page

        Returns:
            List[ReferralResponse]: List of referrals

        Raises:
            ValidationException: If parameters are invalid
        """
        if not user_id:
            raise ValidationException("User ID is required")
        
        if role not in ["referrer", "referee"]:
            raise ValidationException("Role must be 'referrer' or 'referee'")
        
        self._validate_pagination(page, page_size)
        
        if status_filter and status_filter not in self.VALID_STATUSES:
            raise ValidationException(f"Invalid status: {status_filter}")

        try:
            if role == "referrer":
                objs = self.referral_repo.get_by_referrer(
                    db=db,
                    user_id=user_id,
                    status=status_filter,
                    page=page,
                    page_size=page_size,
                )
            else:
                objs = self.referral_repo.get_by_referee(
                    db=db,
                    user_id=user_id,
                    status=status_filter,
                    page=page,
                    page_size=page_size,
                )
            
            logger.debug(
                f"Retrieved {len(objs)} referrals for user",
                extra={"user_id": str(user_id), "role": role},
            )
            
            return [ReferralResponse.model_validate(o) for o in objs]
            
        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                f"Failed to list referrals for user: {str(e)}",
                extra={"user_id": str(user_id), "role": role},
                exc_info=True,
            )
            raise

    # -------------------------------------------------------------------------
    # Stats & Analytics
    # -------------------------------------------------------------------------

    def get_user_stats(
        self,
        db: Session,
        user_id: UUID,
        period: Optional[DateRangeFilter] = None,
    ) -> ReferralStats:
        """
        Get comprehensive referral statistics for a user.

        Args:
            db: Database session
            user_id: User identifier
            period: Optional date range filter

        Returns:
            ReferralStats: User's referral statistics

        Raises:
            ValidationException: If user_id is invalid
        """
        if not user_id:
            raise ValidationException("User ID is required")
        
        if period:
            self._validate_date_range(period)

        try:
            data = self.aggregate_repo.get_user_referral_stats(
                db=db,
                user_id=user_id,
                start_date=period.start_date if period else None,
                end_date=period.end_date if period else None,
            )
            
            if not data:
                # Provide default empty stats
                logger.info(
                    "No referral stats found, returning defaults",
                    extra={"user_id": str(user_id)},
                )
                return self._get_empty_user_stats(user_id)
            
            stats = ReferralStats.model_validate(data)
            
            logger.debug(
                "User stats retrieved",
                extra={
                    "user_id": str(user_id),
                    "total_referrals": stats.total_referrals,
                },
            )
            
            return stats
            
        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                f"Failed to get user stats: {str(e)}",
                extra={"user_id": str(user_id)},
                exc_info=True,
            )
            raise

    def get_leaderboard(
        self,
        db: Session,
        program_id: Optional[UUID] = None,
        period: Optional[DateRangeFilter] = None,
        limit: int = 100,
    ) -> ReferralLeaderboard:
        """
        Get referral leaderboard with top performers.

        Args:
            db: Database session
            program_id: Optional program filter
            period: Optional date range
            limit: Maximum number of top referrers to include

        Returns:
            ReferralLeaderboard: Leaderboard with rankings

        Raises:
            ValidationException: If parameters are invalid
        """
        if limit < 1 or limit > 500:
            raise ValidationException("Limit must be between 1 and 500")
        
        if period:
            self._validate_date_range(period)

        try:
            data = self.aggregate_repo.get_leaderboard(
                db=db,
                program_id=program_id,
                start_date=period.start_date if period else None,
                end_date=period.end_date if period else None,
                limit=limit,
            )
            
            if not data:
                # Default empty leaderboard
                logger.info("No leaderboard data found, returning empty")
                return ReferralLeaderboard(
                    period="all_time" if not period else "custom",
                    total_users=0,
                    top_referrers=[],
                    generated_at=datetime.utcnow(),
                )
            
            leaderboard = ReferralLeaderboard.model_validate(data)
            
            logger.debug(
                f"Leaderboard retrieved with {leaderboard.total_users} users",
                extra={"program_id": str(program_id) if program_id else None},
            )
            
            return leaderboard
            
        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                f"Failed to get leaderboard: {str(e)}",
                exc_info=True,
            )
            raise

    def get_referral_analytics(
        self,
        db: Session,
        period: DateRangeFilter,
        program_id: Optional[UUID] = None,
        granularity: str = "daily",
    ) -> ReferralAnalytics:
        """
        Get comprehensive referral analytics with trends.

        Args:
            db: Database session
            period: Date range for analytics
            program_id: Optional program filter
            granularity: Time granularity (daily, weekly, monthly)

        Returns:
            ReferralAnalytics: Detailed analytics data

        Raises:
            ValidationException: If parameters are invalid
        """
        self._validate_date_range(period)
        
        if granularity not in ["daily", "weekly", "monthly"]:
            raise ValidationException(
                "Granularity must be one of: daily, weekly, monthly"
            )

        try:
            data = self.aggregate_repo.get_referral_analytics(
                db=db,
                program_id=program_id,
                start_date=period.start_date,
                end_date=period.end_date,
                granularity=granularity,
            )
            
            if not data:
                raise ValidationException(
                    "No referral analytics data available for the specified period"
                )
            
            analytics = ReferralAnalytics.model_validate(data)
            
            logger.debug(
                "Referral analytics retrieved",
                extra={
                    "period": f"{period.start_date} to {period.end_date}",
                    "granularity": granularity,
                },
            )
            
            return analytics
            
        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                f"Failed to get referral analytics: {str(e)}",
                exc_info=True,
            )
            raise

    def get_referral_timeline(
        self,
        db: Session,
        referral_id: UUID,
    ) -> ReferralTimeline:
        """
        Get chronological timeline of events for a referral.

        Useful for audit trails and debugging.

        Args:
            db: Database session
            referral_id: Referral identifier

        Returns:
            ReferralTimeline: Timeline of events

        Raises:
            ValidationException: If referral not found
        """
        if not referral_id:
            raise ValidationException("Referral ID is required")

        try:
            data = self.aggregate_repo.get_referral_timeline(db, referral_id)
            if not data:
                raise ValidationException(
                    f"Referral '{referral_id}' not found or no timeline data"
                )
            
            timeline = ReferralTimeline.model_validate(data)
            
            logger.debug(
                f"Timeline retrieved with {len(timeline.events)} events",
                extra={"referral_id": str(referral_id)},
            )
            
            return timeline
            
        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                f"Failed to get referral timeline: {str(e)}",
                extra={"referral_id": str(referral_id)},
                exc_info=True,
            )
            raise

    # -------------------------------------------------------------------------
    # Private Validation Helpers
    # -------------------------------------------------------------------------

    def _validate_referral_create(self, request: ReferralCreate) -> None:
        """Validate referral creation request."""
        if not request.referrer_id:
            raise ValidationException("Referrer ID is required")
        
        if not request.referee_id:
            raise ValidationException("Referee ID is required")
        
        if not request.program_id:
            raise ValidationException("Program ID is required")
        
        if request.referrer_id == request.referee_id:
            raise ValidationException("Referrer and referee cannot be the same user")
        
        # Validate referral code if provided
        if hasattr(request, 'referral_code') and request.referral_code:
            code = request.referral_code.strip()
            if len(code) < 4 or len(code) > 20:
                raise ValidationException("Invalid referral code format")

    def _validate_referral_update(self, request: ReferralUpdate, existing: Any) -> None:
        """Validate referral update request."""
        # Prevent changing immutable fields
        if hasattr(request, 'referrer_id') and request.referrer_id:
            if request.referrer_id != existing.referrer_id:
                raise BusinessLogicException("Cannot change referrer")
        
        if hasattr(request, 'referee_id') and request.referee_id:
            if request.referee_id != existing.referee_id:
                raise BusinessLogicException("Cannot change referee")
        
        # Validate status transitions
        if hasattr(request, 'status') and request.status:
            self._validate_status_transition(existing.status, request.status)

    def _validate_conversion_request(self, request: ReferralConversion) -> None:
        """Validate conversion request."""
        if not request.referral_id:
            raise ValidationException("Referral ID is required")
        
        if not request.booking_id:
            raise ValidationException("Booking ID is required")
        
        if hasattr(request, 'booking_amount') and request.booking_amount:
            if float(request.booking_amount) <= 0:
                raise ValidationException("Booking amount must be positive")
        
        if hasattr(request, 'stay_duration_months') and request.stay_duration_months:
            if request.stay_duration_months <= 0:
                raise ValidationException("Stay duration must be positive")

    def _validate_status_transition(self, current: str, new: str) -> None:
        """Validate status transition is allowed."""
        if new not in self.VALID_STATUSES:
            raise ValidationException(f"Invalid status: {new}")
        
        # Define allowed transitions
        allowed_transitions = {
            self.STATUS_PENDING: [self.STATUS_CONVERTED, self.STATUS_FAILED, self.STATUS_CANCELLED],
            self.STATUS_CONVERTED: [],  # Terminal state
            self.STATUS_FAILED: [self.STATUS_PENDING],  # Allow retry
            self.STATUS_CANCELLED: [],  # Terminal state
        }
        
        if new not in allowed_transitions.get(current, []):
            raise BusinessLogicException(
                f"Cannot transition from '{current}' to '{new}'"
            )

    def _validate_pagination(self, page: int, page_size: int) -> None:
        """Validate pagination parameters."""
        if page < 1:
            raise ValidationException("Page number must be at least 1")
        
        if page_size < 1 or page_size > 100:
            raise ValidationException("Page size must be between 1 and 100")

    def _validate_date_range(self, period: DateRangeFilter) -> None:
        """Validate date range."""
        if not period.start_date or not period.end_date:
            raise ValidationException("Both start_date and end_date are required")
        
        if period.end_date < period.start_date:
            raise ValidationException("End date must be after or equal to start date")
        
        # Check if date range is too large (e.g., max 2 years)
        max_days = 730
        date_diff = (period.end_date - period.start_date).days
        
        if date_diff > max_days:
            raise ValidationException(f"Date range cannot exceed {max_days} days")

    def _is_duplicate_referral(self, db: Session, request: ReferralCreate) -> bool:
        """Check if this is a duplicate referral."""
        try:
            existing = self.referral_repo.get_by_referee_and_program(
                db=db,
                referee_id=request.referee_id,
                program_id=request.program_id,
            )
            return existing is not None
        except Exception:
            return False

    def _get_empty_user_stats(self, user_id: UUID) -> ReferralStats:
        """Get empty user stats with defaults."""
        return ReferralStats(
            user_id=user_id,
            total_referrals=0,
            successful_referrals=0,
            pending_referrals=0,
            failed_referrals=0,
            cancelled_referrals=0,
            conversion_rate=0.0,
            average_conversion_time_days=None,
            total_rewards_earned="0",
            total_rewards_paid="0",
            pending_rewards="0",
            currency="INR",
            referrals_by_program={},
            rewards_by_program={},
            this_month_referrals=0,
            last_month_referrals=0,
            user_rank=None,
            total_referrers=None,
            last_referral_date=None,
            most_active_program=None,
        )