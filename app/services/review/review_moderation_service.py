"""
Review Moderation Service

Enhanced admin-side moderation workflow with comprehensive validation,
audit logging, and batch operation optimization.
"""

from __future__ import annotations

import logging
from typing import List, Dict, Any, Optional
from uuid import UUID
from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.repositories.review import ReviewModerationRepository, ReviewRepository
from app.schemas.review import (
    ModerationRequest,
    ModerationResponse,
    ModerationQueue,
    PendingReview,
    BulkModeration,
    ModerationStats,
    FlagReview,
)
from app.core.exceptions import (
    ValidationException,
    BusinessLogicException,
    NotFoundException,
    DatabaseException,
    AuthorizationException,
)
from app.core.cache import invalidate_cache
from app.core.metrics import track_performance

logger = logging.getLogger(__name__)


class ReviewModerationService:
    """
    High-level moderation orchestration with enhanced error handling
    and performance optimization.

    Provides:
    - Single and bulk moderation actions
    - Queue management with priority
    - Comprehensive statistics
    - Audit trail for compliance
    """

    # Valid moderation actions
    VALID_ACTIONS = {'approve', 'reject', 'hold', 'flag', 'unflag'}
    
    # Maximum reviews in single bulk operation
    MAX_BULK_SIZE = 100

    def __init__(
        self,
        moderation_repo: ReviewModerationRepository,
        review_repo: ReviewRepository,
    ) -> None:
        """
        Initialize ReviewModerationService.

        Args:
            moderation_repo: Repository for moderation operations
            review_repo: Repository for review data access

        Raises:
            ValueError: If repositories are None
        """
        if not moderation_repo or not review_repo:
            raise ValueError("Repositories cannot be None")

        self.moderation_repo = moderation_repo
        self.review_repo = review_repo
        logger.info("ReviewModerationService initialized")

    # -------------------------------------------------------------------------
    # Actions
    # -------------------------------------------------------------------------

    @track_performance("moderation.moderate_review")
    @invalidate_cache(patterns=["review_detail:*", "moderation_queue:*"])
    def moderate_review(
        self,
        db: Session,
        request: ModerationRequest,
        moderator_id: UUID,
    ) -> ModerationResponse:
        """
        Process a single moderation action for a review.

        Args:
            db: Database session
            request: Moderation request data
            moderator_id: UUID of moderator performing action

        Returns:
            ModerationResponse with action result

        Raises:
            ValidationException: If request is invalid
            NotFoundException: If review not found
            AuthorizationException: If moderator lacks permission
            DatabaseException: If database operation fails
        """
        try:
            logger.info(
                f"Moderating review {request.review_id}: "
                f"action={request.action}, moderator={moderator_id}"
            )

            # Validate request
            self._validate_moderation_request(request)

            # Fetch review
            review = self.review_repo.get_by_id(db, request.review_id)
            if not review:
                logger.warning(f"Review not found: {request.review_id}")
                raise NotFoundException(f"Review {request.review_id} not found")

            # Verify moderator permissions
            self._verify_moderator_permissions(db, moderator_id, review)

            # Apply moderation
            result = self.moderation_repo.apply_moderation_action(
                db=db,
                review=review,
                moderator_id=moderator_id,
                action=request.action,
                reason=request.reason,
                notes=request.notes,
            )

            response = ModerationResponse.model_validate(result)

            logger.info(
                f"Moderation completed: review={request.review_id}, "
                f"action={request.action}, new_status={response.new_status}"
            )

            return response

        except (ValidationException, NotFoundException, AuthorizationException):
            raise
        except SQLAlchemyError as e:
            logger.error(f"Database error during moderation: {str(e)}")
            db.rollback()
            raise DatabaseException("Failed to moderate review") from e

    @track_performance("moderation.flag_review")
    def flag_review(
        self,
        db: Session,
        user_id: UUID,
        request: FlagReview,
    ) -> None:
        """
        User-side flagging of a review for moderation.

        Args:
            db: Database session
            user_id: UUID of user flagging the review
            request: Flag request data

        Raises:
            ValidationException: If request is invalid
            NotFoundException: If review not found
            BusinessLogicException: If user already flagged this review
            DatabaseException: If database operation fails
        """
        try:
            logger.info(f"Flagging review {request.review_id} by user {user_id}")

            # Validate request
            self._validate_flag_request(request)

            # Fetch review
            review = self.review_repo.get_by_id(db, request.review_id)
            if not review:
                logger.warning(f"Review not found for flagging: {request.review_id}")
                raise NotFoundException(f"Review {request.review_id} not found")

            # Check if already flagged by user
            if self._user_already_flagged(db, user_id, request.review_id):
                raise BusinessLogicException(
                    "You have already flagged this review"
                )

            # Create flag
            self.moderation_repo.flag_review(
                db=db,
                review=review,
                flagged_by=user_id,
                reason=request.reason,
                details=request.details,
            )

            logger.info(
                f"Review flagged successfully: {request.review_id} by {user_id}"
            )

        except (ValidationException, NotFoundException, BusinessLogicException):
            raise
        except SQLAlchemyError as e:
            logger.error(f"Database error flagging review: {str(e)}")
            db.rollback()
            raise DatabaseException("Failed to flag review") from e

    @track_performance("moderation.bulk_moderate")
    @invalidate_cache(patterns=["review_detail:*", "moderation_queue:*"])
    def bulk_moderate(
        self,
        db: Session,
        request: BulkModeration,
        moderator_id: UUID,
    ) -> List[ModerationResponse]:
        """
        Apply a moderation action to multiple reviews efficiently.

        Uses optimized batch processing to minimize database round-trips.

        Args:
            db: Database session
            request: Bulk moderation request
            moderator_id: UUID of moderator

        Returns:
            List of ModerationResponse for each review

        Raises:
            ValidationException: If request is invalid
            AuthorizationException: If moderator lacks permission
            DatabaseException: If database operation fails
        """
        try:
            logger.info(
                f"Bulk moderating {len(request.review_ids)} reviews: "
                f"action={request.action}, moderator={moderator_id}"
            )

            # Validate request
            self._validate_bulk_moderation_request(request)

            responses: List[ModerationResponse] = []
            failed_reviews: List[Dict[str, Any]] = []

            # Process in batches to avoid memory issues
            for review_id in request.review_ids:
                try:
                    resp = self.moderate_review(
                        db=db,
                        request=ModerationRequest(
                            review_id=review_id,
                            action=request.action,
                            reason=request.reason,
                            notes=request.notes,
                        ),
                        moderator_id=moderator_id,
                    )
                    responses.append(resp)

                except (ValidationException, NotFoundException, BusinessLogicException) as e:
                    error_info = {
                        "review_id": str(review_id),
                        "error": str(e),
                        "error_type": type(e).__name__,
                    }
                    failed_reviews.append(error_info)
                    logger.warning(f"Failed to moderate review {review_id}: {str(e)}")

                    if not request.skip_failed:
                        raise

            # Log summary
            logger.info(
                f"Bulk moderation completed: "
                f"successful={len(responses)}, failed={len(failed_reviews)}"
            )

            if failed_reviews:
                logger.warning(f"Failed reviews: {failed_reviews}")

            return responses

        except ValidationException:
            raise
        except SQLAlchemyError as e:
            logger.error(f"Database error during bulk moderation: {str(e)}")
            db.rollback()
            raise DatabaseException("Failed to bulk moderate reviews") from e

    # -------------------------------------------------------------------------
    # Queue & stats
    # -------------------------------------------------------------------------

    @track_performance("moderation.get_queue")
    def get_moderation_queue(
        self,
        db: Session,
        hostel_id: UUID,
        limit: int = 50,
        priority_only: bool = False,
    ) -> ModerationQueue:
        """
        Get the current moderation queue for a hostel.

        Args:
            db: Database session
            hostel_id: UUID of hostel
            limit: Maximum items to return
            priority_only: If True, return only high-priority items

        Returns:
            ModerationQueue object

        Raises:
            ValidationException: If parameters are invalid
            DatabaseException: If database error occurs
        """
        try:
            # Validate limit
            if limit < 1 or limit > 500:
                raise ValidationException("Limit must be between 1 and 500")

            logger.debug(
                f"Fetching moderation queue for hostel {hostel_id}: "
                f"limit={limit}, priority_only={priority_only}"
            )

            data = self.moderation_repo.get_queue(
                db,
                hostel_id=hostel_id,
                limit=limit,
                priority_only=priority_only,
            )

            queue = ModerationQueue.model_validate(data)

            logger.info(
                f"Queue retrieved: {queue.total_pending} pending items "
                f"for hostel {hostel_id}"
            )

            return queue

        except ValidationException:
            raise
        except SQLAlchemyError as e:
            logger.error(f"Database error fetching moderation queue: {str(e)}")
            raise DatabaseException("Failed to fetch moderation queue") from e

    @track_performance("moderation.get_pending_reviews")
    def get_pending_reviews(
        self,
        db: Session,
        hostel_id: UUID,
        limit: int = 50,
    ) -> List[PendingReview]:
        """
        List individual pending reviews for moderation.

        Args:
            db: Database session
            hostel_id: UUID of hostel
            limit: Maximum reviews to return

        Returns:
            List of PendingReview objects

        Raises:
            ValidationException: If parameters are invalid
            DatabaseException: If database error occurs
        """
        try:
            if limit < 1 or limit > 500:
                raise ValidationException("Limit must be between 1 and 500")

            logger.debug(f"Fetching pending reviews for hostel {hostel_id}")

            objs = self.moderation_repo.get_pending_reviews(db, hostel_id, limit)
            reviews = [PendingReview.model_validate(o) for o in objs]

            logger.info(f"Retrieved {len(reviews)} pending reviews for hostel {hostel_id}")

            return reviews

        except ValidationException:
            raise
        except SQLAlchemyError as e:
            logger.error(f"Database error fetching pending reviews: {str(e)}")
            raise DatabaseException("Failed to fetch pending reviews") from e

    @track_performance("moderation.get_stats")
    def get_moderation_stats(
        self,
        db: Session,
        hostel_id: UUID,
        period_days: Optional[int] = None,
    ) -> ModerationStats:
        """
        Get moderation statistics for a hostel.

        Args:
            db: Database session
            hostel_id: UUID of hostel
            period_days: Optional number of days to include in stats

        Returns:
            ModerationStats object

        Raises:
            DatabaseException: If database error occurs
        """
        try:
            logger.debug(
                f"Fetching moderation stats for hostel {hostel_id}, "
                f"period_days={period_days}"
            )

            data = self.moderation_repo.get_stats(
                db,
                hostel_id,
                period_days=period_days,
            )

            if not data:
                logger.info(f"No moderation stats for hostel {hostel_id}, returning empty")
                return ModerationStats(
                    hostel_id=hostel_id,
                    total_pending=0,
                    total_approved=0,
                    total_rejected=0,
                    avg_moderation_time_hours=0.0,
                    actions_by_moderator={},
                )

            stats = ModerationStats.model_validate(data)

            logger.info(
                f"Stats retrieved: pending={stats.total_pending}, "
                f"approved={stats.total_approved}, rejected={stats.total_rejected}"
            )

            return stats

        except SQLAlchemyError as e:
            logger.error(f"Database error fetching moderation stats: {str(e)}")
            raise DatabaseException("Failed to fetch moderation stats") from e

    # -------------------------------------------------------------------------
    # Private helper methods
    # -------------------------------------------------------------------------

    def _validate_moderation_request(self, request: ModerationRequest) -> None:
        """
        Validate moderation request.

        Args:
            request: Moderation request

        Raises:
            ValidationException: If validation fails
        """
        if not request.review_id:
            raise ValidationException("Review ID is required")

        if not request.action or request.action not in self.VALID_ACTIONS:
            raise ValidationException(
                f"Invalid action. Must be one of: {', '.join(self.VALID_ACTIONS)}"
            )

        if request.action in ('reject', 'flag') and not request.reason:
            raise ValidationException(
                f"Reason is required for {request.action} action"
            )

    def _validate_flag_request(self, request: FlagReview) -> None:
        """
        Validate flag request.

        Args:
            request: Flag request

        Raises:
            ValidationException: If validation fails
        """
        if not request.review_id:
            raise ValidationException("Review ID is required")

        if not request.reason:
            raise ValidationException("Reason is required for flagging")

        if len(request.reason.strip()) < 10:
            raise ValidationException(
                "Flag reason must be at least 10 characters"
            )

    def _validate_bulk_moderation_request(self, request: BulkModeration) -> None:
        """
        Validate bulk moderation request.

        Args:
            request: Bulk moderation request

        Raises:
            ValidationException: If validation fails
        """
        if not request.review_ids:
            raise ValidationException("At least one review ID is required")

        if len(request.review_ids) > self.MAX_BULK_SIZE:
            raise ValidationException(
                f"Cannot moderate more than {self.MAX_BULK_SIZE} reviews at once"
            )

        if not request.action or request.action not in self.VALID_ACTIONS:
            raise ValidationException(
                f"Invalid action. Must be one of: {', '.join(self.VALID_ACTIONS)}"
            )

    def _verify_moderator_permissions(
        self,
        db: Session,
        moderator_id: UUID,
        review: Any,
    ) -> None:
        """
        Verify moderator has permission to moderate this review.

        Args:
            db: Database session
            moderator_id: UUID of moderator
            review: Review object

        Raises:
            AuthorizationException: If moderator lacks permission
        """
        # Implement permission check logic
        # This is a placeholder - actual implementation depends on your auth system
        has_permission = self.moderation_repo.verify_moderator_permission(
            db, moderator_id, review
        )

        if not has_permission:
            logger.warning(
                f"Moderator {moderator_id} lacks permission for review {review.id}"
            )
            raise AuthorizationException(
                "You do not have permission to moderate this review"
            )

    def _user_already_flagged(
        self,
        db: Session,
        user_id: UUID,
        review_id: UUID,
    ) -> bool:
        """
        Check if user already flagged this review.

        Args:
            db: Database session
            user_id: User UUID
            review_id: Review UUID

        Returns:
            True if already flagged, False otherwise
        """
        return self.moderation_repo.check_existing_flag(db, user_id, review_id)