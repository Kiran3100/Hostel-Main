"""
Review Service

Core user-facing review operations with enhanced error handling,
validation, caching, and performance optimizations.
"""

from __future__ import annotations

import logging
from typing import List, Optional, Tuple, Dict, Any
from uuid import UUID
from datetime import datetime, timedelta

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.repositories.review import ReviewRepository
from app.schemas.review import (
    ReviewSubmissionRequest,
    ReviewUpdate,
    ReviewDetail,
    ReviewListItem,
    ReviewSummary,
    ReviewFilterParams,
    ReviewSearchRequest,
    ReviewSortOptions,
    ReviewEligibility,
    ReviewGuidelines,
    ReviewDraft,
)
from app.core.exceptions import (
    ValidationException,
    BusinessLogicException,
    NotFoundException,
    DatabaseException,
)
from app.core.cache import cache_result, invalidate_cache
from app.core.metrics import track_performance

logger = logging.getLogger(__name__)


class ReviewService:
    """
    High-level orchestration service for reviews.

    Provides comprehensive review management including:
    - Eligibility verification and validation
    - Review submission with draft support
    - CRUD operations with authorization
    - Advanced search and filtering
    - Performance-optimized listing with caching
    """

    # Constants for business rules
    MAX_REVIEWS_PER_USER_PER_HOSTEL = 1
    REVIEW_EDIT_WINDOW_DAYS = 7
    MIN_REVIEW_TEXT_LENGTH = 10
    MAX_REVIEW_TEXT_LENGTH = 5000
    DRAFT_EXPIRY_DAYS = 30

    def __init__(self, review_repo: ReviewRepository) -> None:
        """
        Initialize ReviewService.

        Args:
            review_repo: Repository for review data access
        """
        if not review_repo:
            raise ValueError("ReviewRepository cannot be None")
        self.review_repo = review_repo
        logger.info("ReviewService initialized")

    # -------------------------------------------------------------------------
    # Eligibility & guidelines
    # -------------------------------------------------------------------------

    @track_performance("review_service.get_eligibility")
    @cache_result(ttl=300, key_prefix="review_eligibility")
    def get_eligibility(
        self,
        db: Session,
        user_id: UUID,
        hostel_id: UUID,
    ) -> ReviewEligibility:
        """
        Check whether a user is allowed to leave/edit a review for a hostel.

        Args:
            db: Database session
            user_id: UUID of the user
            hostel_id: UUID of the hostel

        Returns:
            ReviewEligibility object with can_review flag and message

        Raises:
            ValidationException: If user or hostel is invalid
            DatabaseException: If database error occurs
        """
        try:
            logger.debug(
                f"Checking review eligibility for user {user_id} on hostel {hostel_id}"
            )

            if not self._validate_uuid(user_id):
                raise ValidationException("Invalid user ID format")
            if not self._validate_uuid(hostel_id):
                raise ValidationException("Invalid hostel ID format")

            data = self.review_repo.get_eligibility(db, user_id, hostel_id)

            if data is None:
                logger.warning(
                    f"Unable to determine eligibility for user {user_id}, hostel {hostel_id}"
                )
                raise ValidationException(
                    "Unable to determine review eligibility. "
                    "User or hostel may not exist."
                )

            eligibility = ReviewEligibility.model_validate(data)
            logger.info(
                f"Eligibility check complete: user {user_id}, "
                f"can_review={eligibility.can_review}"
            )
            return eligibility

        except SQLAlchemyError as e:
            logger.error(f"Database error during eligibility check: {str(e)}")
            raise DatabaseException("Failed to check review eligibility") from e

    @cache_result(ttl=3600, key_prefix="review_guidelines")
    def get_guidelines(
        self,
        db: Session,
        hostel_id: Optional[UUID] = None,
    ) -> ReviewGuidelines:
        """
        Get review guidelines (global or hostel-specific).

        Args:
            db: Database session
            hostel_id: Optional hostel UUID for hostel-specific guidelines

        Returns:
            ReviewGuidelines object

        Raises:
            DatabaseException: If database error occurs
        """
        try:
            logger.debug(f"Fetching review guidelines for hostel: {hostel_id}")

            data = self.review_repo.get_guidelines(db, hostel_id=hostel_id)

            if not data:
                logger.info("Using default review guidelines")
                guidelines = ReviewGuidelines()
            else:
                guidelines = ReviewGuidelines.model_validate(data)

            return guidelines

        except SQLAlchemyError as e:
            logger.error(f"Database error fetching guidelines: {str(e)}")
            raise DatabaseException("Failed to fetch review guidelines") from e

    # -------------------------------------------------------------------------
    # Submission & editing
    # -------------------------------------------------------------------------

    @track_performance("review_service.submit_review")
    @invalidate_cache(patterns=["review_eligibility:*", "hostel_summary:*"])
    def submit_review(
        self,
        db: Session,
        user_id: UUID,
        hostel_id: UUID,
        submission: ReviewSubmissionRequest,
    ) -> ReviewDetail:
        """
        Submit a new review for a hostel.

        Workflow:
        1. Validate input data
        2. Check user eligibility
        3. Validate review content
        4. Create review with appropriate status
        5. Delete associated draft if exists

        Args:
            db: Database session
            user_id: UUID of the reviewing user
            hostel_id: UUID of the hostel being reviewed
            submission: Review submission data

        Returns:
            ReviewDetail object of created review

        Raises:
            ValidationException: If validation fails
            BusinessLogicException: If user is not eligible
            DatabaseException: If database operation fails
        """
        try:
            logger.info(f"Submitting review: user {user_id}, hostel {hostel_id}")

            # Validate input
            self._validate_review_submission(submission)

            # Check eligibility
            eligibility = self.get_eligibility(db, user_id, hostel_id)
            if not eligibility.can_review:
                error_msg = eligibility.message or "User not eligible to review"
                logger.warning(
                    f"Review submission blocked: {error_msg} "
                    f"(user: {user_id}, hostel: {hostel_id})"
                )
                raise BusinessLogicException(error_msg)

            # Prepare payload
            payload = submission.model_dump(exclude_none=True)
            payload.update({
                "user_id": user_id,
                "hostel_id": hostel_id,
                "submitted_at": datetime.utcnow(),
            })

            # Create review
            obj = self.review_repo.create_from_submission(db, payload)
            review = ReviewDetail.model_validate(obj)

            # Clean up draft if exists
            self._delete_draft_if_exists(db, user_id, hostel_id)

            logger.info(
                f"Review submitted successfully: id={review.id}, "
                f"status={review.status}"
            )
            return review

        except (ValidationException, BusinessLogicException):
            raise
        except SQLAlchemyError as e:
            logger.error(f"Database error during review submission: {str(e)}")
            db.rollback()
            raise DatabaseException("Failed to submit review") from e

    @track_performance("review_service.update_review")
    @invalidate_cache(patterns=["review_detail:*", "hostel_summary:*"])
    def update_review(
        self,
        db: Session,
        review_id: UUID,
        user_id: UUID,
        data: ReviewUpdate,
    ) -> ReviewDetail:
        """
        Update an existing review authored by the user.

        Enforces:
        - Ownership verification
        - Edit window validation
        - Status eligibility
        - Content validation

        Args:
            db: Database session
            review_id: UUID of review to update
            user_id: UUID of user attempting update
            data: Update data

        Returns:
            Updated ReviewDetail object

        Raises:
            NotFoundException: If review not found
            BusinessLogicException: If user lacks permission or edit window expired
            ValidationException: If update data is invalid
            DatabaseException: If database operation fails
        """
        try:
            logger.info(f"Updating review {review_id} by user {user_id}")

            # Fetch review
            review = self.review_repo.get_by_id(db, review_id)
            if not review:
                logger.warning(f"Review not found: {review_id}")
                raise NotFoundException(f"Review {review_id} not found")

            # Verify ownership
            if review.user_id != user_id:
                logger.warning(
                    f"Unauthorized update attempt: review {review_id} by user {user_id}"
                )
                raise BusinessLogicException("You can only edit your own reviews")

            # Check if editable
            if not self._can_edit_review(review):
                logger.warning(f"Review {review_id} is no longer editable")
                raise BusinessLogicException(
                    f"Review can no longer be edited. "
                    f"Edit window is {self.REVIEW_EDIT_WINDOW_DAYS} days."
                )

            # Validate update data
            self._validate_review_update(data)

            # Perform update
            update_payload = data.model_dump(exclude_none=True)
            update_payload["updated_at"] = datetime.utcnow()

            updated = self.review_repo.update(db, obj=review, data=update_payload)
            result = ReviewDetail.model_validate(updated)

            logger.info(f"Review {review_id} updated successfully")
            return result

        except (NotFoundException, BusinessLogicException, ValidationException):
            raise
        except SQLAlchemyError as e:
            logger.error(f"Database error during review update: {str(e)}")
            db.rollback()
            raise DatabaseException("Failed to update review") from e

    @track_performance("review_service.delete_review")
    @invalidate_cache(patterns=["review_detail:*", "hostel_summary:*"])
    def delete_review(
        self,
        db: Session,
        review_id: UUID,
        user_id: UUID,
    ) -> None:
        """
        Soft-delete a review authored by the user.

        Args:
            db: Database session
            review_id: UUID of review to delete
            user_id: UUID of user attempting deletion

        Raises:
            NotFoundException: If review not found
            BusinessLogicException: If user lacks permission
            DatabaseException: If database operation fails
        """
        try:
            logger.info(f"Deleting review {review_id} by user {user_id}")

            review = self.review_repo.get_by_id(db, review_id)
            if not review:
                logger.warning(f"Review not found for deletion: {review_id}")
                raise NotFoundException(f"Review {review_id} not found")

            # Verify ownership
            if review.user_id != user_id:
                logger.warning(
                    f"Unauthorized delete attempt: review {review_id} by user {user_id}"
                )
                raise BusinessLogicException("You can only delete your own reviews")

            # Soft delete
            self.review_repo.soft_delete(db, review)

            logger.info(f"Review {review_id} deleted successfully")

        except (NotFoundException, BusinessLogicException):
            raise
        except SQLAlchemyError as e:
            logger.error(f"Database error during review deletion: {str(e)}")
            db.rollback()
            raise DatabaseException("Failed to delete review") from e

    # -------------------------------------------------------------------------
    # Drafts
    # -------------------------------------------------------------------------

    @cache_result(ttl=60, key_prefix="review_draft")
    def get_draft(
        self,
        db: Session,
        user_id: UUID,
        hostel_id: UUID,
    ) -> Optional[ReviewDraft]:
        """
        Get user's draft review for a hostel.

        Args:
            db: Database session
            user_id: UUID of user
            hostel_id: UUID of hostel

        Returns:
            ReviewDraft if exists, None otherwise

        Raises:
            DatabaseException: If database error occurs
        """
        try:
            logger.debug(f"Fetching draft for user {user_id}, hostel {hostel_id}")

            obj = self.review_repo.get_draft_for_user_and_hostel(db, user_id, hostel_id)
            if not obj:
                return None

            # Check if draft expired
            if self._is_draft_expired(obj):
                logger.info(f"Draft expired, deleting: {obj.id}")
                self.review_repo.delete_draft(db, obj)
                return None

            return ReviewDraft.model_validate(obj)

        except SQLAlchemyError as e:
            logger.error(f"Database error fetching draft: {str(e)}")
            raise DatabaseException("Failed to fetch draft") from e

    @track_performance("review_service.save_draft")
    @invalidate_cache(patterns=["review_draft:*"])
    def save_draft(
        self,
        db: Session,
        user_id: UUID,
        hostel_id: UUID,
        draft: ReviewDraft,
    ) -> ReviewDraft:
        """
        Save or update a review draft.

        Args:
            db: Database session
            user_id: UUID of user
            hostel_id: UUID of hostel
            draft: Draft data

        Returns:
            Saved ReviewDraft object

        Raises:
            ValidationException: If draft data is invalid
            DatabaseException: If database operation fails
        """
        try:
            logger.info(f"Saving draft for user {user_id}, hostel {hostel_id}")

            # Validate draft
            self._validate_draft(draft)

            payload = draft.model_dump(exclude_none=True)
            payload.update({
                "user_id": user_id,
                "hostel_id": hostel_id,
                "updated_at": datetime.utcnow(),
            })

            obj = self.review_repo.upsert_draft(db, payload)
            result = ReviewDraft.model_validate(obj)

            logger.info(f"Draft saved successfully: {result.id}")
            return result

        except ValidationException:
            raise
        except SQLAlchemyError as e:
            logger.error(f"Database error saving draft: {str(e)}")
            db.rollback()
            raise DatabaseException("Failed to save draft") from e

    @track_performance("review_service.delete_draft")
    @invalidate_cache(patterns=["review_draft:*"])
    def delete_draft(
        self,
        db: Session,
        draft_id: UUID,
        user_id: UUID,
    ) -> None:
        """
        Delete a review draft.

        Args:
            db: Database session
            draft_id: UUID of draft to delete
            user_id: UUID of user attempting deletion

        Raises:
            NotFoundException: If draft not found
            BusinessLogicException: If user lacks permission
            DatabaseException: If database operation fails
        """
        try:
            logger.info(f"Deleting draft {draft_id} by user {user_id}")

            draft = self.review_repo.get_draft_by_id(db, draft_id)
            if not draft:
                raise NotFoundException(f"Draft {draft_id} not found")

            if draft.user_id != user_id:
                logger.warning(
                    f"Unauthorized draft delete: draft {draft_id} by user {user_id}"
                )
                raise BusinessLogicException("You can only delete your own drafts")

            self.review_repo.delete_draft(db, draft)
            logger.info(f"Draft {draft_id} deleted successfully")

        except (NotFoundException, BusinessLogicException):
            raise
        except SQLAlchemyError as e:
            logger.error(f"Database error deleting draft: {str(e)}")
            db.rollback()
            raise DatabaseException("Failed to delete draft") from e

    # -------------------------------------------------------------------------
    # Retrieval & listing
    # -------------------------------------------------------------------------

    @track_performance("review_service.get_review")
    @cache_result(ttl=300, key_prefix="review_detail")
    def get_review(
        self,
        db: Session,
        review_id: UUID,
    ) -> ReviewDetail:
        """
        Get detailed review information.

        Args:
            db: Database session
            review_id: UUID of review

        Returns:
            ReviewDetail object

        Raises:
            NotFoundException: If review not found
            DatabaseException: If database error occurs
        """
        try:
            logger.debug(f"Fetching review details: {review_id}")

            obj = self.review_repo.get_full_review(db, review_id)
            if not obj:
                logger.warning(f"Review not found: {review_id}")
                raise NotFoundException(f"Review {review_id} not found")

            return ReviewDetail.model_validate(obj)

        except NotFoundException:
            raise
        except SQLAlchemyError as e:
            logger.error(f"Database error fetching review: {str(e)}")
            raise DatabaseException("Failed to fetch review") from e

    @track_performance("review_service.list_reviews_for_hostel")
    def list_reviews_for_hostel(
        self,
        db: Session,
        hostel_id: UUID,
        filters: Optional[ReviewFilterParams] = None,
        sort: Optional[ReviewSortOptions] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[ReviewListItem], int, ReviewSummary]:
        """
        List reviews for a hostel with advanced filtering and pagination.

        Args:
            db: Database session
            hostel_id: UUID of hostel
            filters: Optional filtering parameters
            sort: Optional sorting parameters
            page: Page number (1-indexed)
            page_size: Items per page

        Returns:
            Tuple of (review_items, total_count, summary)

        Raises:
            ValidationException: If pagination params are invalid
            DatabaseException: If database error occurs
        """
        try:
            # Validate pagination
            page, page_size = self._validate_pagination(page, page_size)

            logger.debug(
                f"Listing reviews for hostel {hostel_id}: "
                f"page={page}, page_size={page_size}"
            )

            filters_dict = filters.model_dump(exclude_none=True) if filters else {}
            sort_dict = sort.model_dump(exclude_none=True) if sort else {}

            result = self.review_repo.search_reviews(
                db=db,
                hostel_id=hostel_id,
                filters=filters_dict,
                sort=sort_dict,
                page=page,
                page_size=page_size,
            )

            items = [ReviewListItem.model_validate(r) for r in result["items"]]
            total = result["total"]
            summary = ReviewSummary.model_validate(result["summary"])

            logger.info(
                f"Retrieved {len(items)} reviews for hostel {hostel_id} "
                f"(total: {total})"
            )

            return items, total, summary

        except ValidationException:
            raise
        except SQLAlchemyError as e:
            logger.error(f"Database error listing reviews: {str(e)}")
            raise DatabaseException("Failed to list reviews") from e

    @track_performance("review_service.search_reviews")
    def search_reviews(
        self,
        db: Session,
        request: ReviewSearchRequest,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[ReviewListItem], int]:
        """
        Full-text search over reviews.

        Args:
            db: Database session
            request: Search request parameters
            page: Page number (1-indexed)
            page_size: Items per page

        Returns:
            Tuple of (review_items, total_count)

        Raises:
            ValidationException: If search params are invalid
            DatabaseException: If database error occurs
        """
        try:
            # Validate pagination
            page, page_size = self._validate_pagination(page, page_size)

            # Validate search query
            if not request.query or len(request.query.strip()) < 2:
                raise ValidationException(
                    "Search query must be at least 2 characters"
                )

            logger.debug(f"Searching reviews: query='{request.query}'")

            result = self.review_repo.search_by_text(
                db=db,
                query=request.query,
                hostel_id=request.hostel_id,
                filters=request.model_dump(exclude_none=True),
                page=page,
                page_size=page_size,
            )

            items = [ReviewListItem.model_validate(r) for r in result["items"]]
            total = result["total"]

            logger.info(f"Search returned {len(items)} results (total: {total})")

            return items, total

        except ValidationException:
            raise
        except SQLAlchemyError as e:
            logger.error(f"Database error during review search: {str(e)}")
            raise DatabaseException("Failed to search reviews") from e

    @track_performance("review_service.get_hostel_summary")
    @cache_result(ttl=600, key_prefix="hostel_summary")
    def get_hostel_summary(
        self,
        db: Session,
        hostel_id: UUID,
    ) -> ReviewSummary:
        """
        Get aggregate review summary for a hostel.

        Args:
            db: Database session
            hostel_id: UUID of hostel

        Returns:
            ReviewSummary object with aggregated metrics

        Raises:
            DatabaseException: If database error occurs
        """
        try:
            logger.debug(f"Fetching summary for hostel {hostel_id}")

            data = self.review_repo.get_hostel_summary(db, hostel_id)

            if not data:
                logger.info(f"No reviews found for hostel {hostel_id}, returning empty summary")
                return ReviewSummary(
                    hostel_id=hostel_id,
                    total_reviews=0,
                    average_rating=0.0,
                    rating_distribution={1: 0, 2: 0, 3: 0, 4: 0, 5: 0},
                    verified_percentage=0.0,
                    recent_reviews=[],
                )

            summary = ReviewSummary.model_validate(data)
            logger.info(
                f"Summary retrieved: {summary.total_reviews} reviews, "
                f"avg rating {summary.average_rating:.2f}"
            )
            return summary

        except SQLAlchemyError as e:
            logger.error(f"Database error fetching hostel summary: {str(e)}")
            raise DatabaseException("Failed to fetch hostel summary") from e

    # -------------------------------------------------------------------------
    # Private helper methods
    # -------------------------------------------------------------------------

    def _validate_uuid(self, value: UUID) -> bool:
        """Validate UUID format."""
        return value is not None and isinstance(value, UUID)

    def _validate_review_submission(self, submission: ReviewSubmissionRequest) -> None:
        """
        Validate review submission data.

        Args:
            submission: Review submission data

        Raises:
            ValidationException: If validation fails
        """
        if not submission.rating or not (1 <= submission.rating <= 5):
            raise ValidationException("Rating must be between 1 and 5")

        if submission.text:
            text_length = len(submission.text.strip())
            if text_length < self.MIN_REVIEW_TEXT_LENGTH:
                raise ValidationException(
                    f"Review text must be at least {self.MIN_REVIEW_TEXT_LENGTH} characters"
                )
            if text_length > self.MAX_REVIEW_TEXT_LENGTH:
                raise ValidationException(
                    f"Review text cannot exceed {self.MAX_REVIEW_TEXT_LENGTH} characters"
                )

    def _validate_review_update(self, data: ReviewUpdate) -> None:
        """
        Validate review update data.

        Args:
            data: Review update data

        Raises:
            ValidationException: If validation fails
        """
        if data.rating is not None and not (1 <= data.rating <= 5):
            raise ValidationException("Rating must be between 1 and 5")

        if data.text is not None:
            text_length = len(data.text.strip())
            if text_length > 0 and text_length < self.MIN_REVIEW_TEXT_LENGTH:
                raise ValidationException(
                    f"Review text must be at least {self.MIN_REVIEW_TEXT_LENGTH} characters"
                )
            if text_length > self.MAX_REVIEW_TEXT_LENGTH:
                raise ValidationException(
                    f"Review text cannot exceed {self.MAX_REVIEW_TEXT_LENGTH} characters"
                )

    def _validate_draft(self, draft: ReviewDraft) -> None:
        """
        Validate draft data.

        Args:
            draft: Draft data

        Raises:
            ValidationException: If validation fails
        """
        if draft.rating is not None and not (1 <= draft.rating <= 5):
            raise ValidationException("Rating must be between 1 and 5")

        if draft.text and len(draft.text) > self.MAX_REVIEW_TEXT_LENGTH:
            raise ValidationException(
                f"Draft text cannot exceed {self.MAX_REVIEW_TEXT_LENGTH} characters"
            )

    def _validate_pagination(self, page: int, page_size: int) -> Tuple[int, int]:
        """
        Validate and normalize pagination parameters.

        Args:
            page: Page number
            page_size: Items per page

        Returns:
            Tuple of (normalized_page, normalized_page_size)

        Raises:
            ValidationException: If parameters are invalid
        """
        if page < 1:
            raise ValidationException("Page number must be >= 1")

        if page_size < 1:
            raise ValidationException("Page size must be >= 1")

        if page_size > 100:
            logger.warning(f"Page size {page_size} exceeds maximum, capping at 100")
            page_size = 100

        return page, page_size

    def _can_edit_review(self, review: Any) -> bool:
        """
        Check if a review can be edited based on business rules.

        Args:
            review: Review object

        Returns:
            True if editable, False otherwise
        """
        if not hasattr(review, 'created_at') or not review.created_at:
            return False

        if hasattr(review, 'status') and review.status not in ('draft', 'pending', 'published'):
            return False

        edit_cutoff = datetime.utcnow() - timedelta(days=self.REVIEW_EDIT_WINDOW_DAYS)
        return review.created_at > edit_cutoff

    def _is_draft_expired(self, draft: Any) -> bool:
        """
        Check if a draft has expired.

        Args:
            draft: Draft object

        Returns:
            True if expired, False otherwise
        """
        if not hasattr(draft, 'updated_at') or not draft.updated_at:
            return True

        expiry_cutoff = datetime.utcnow() - timedelta(days=self.DRAFT_EXPIRY_DAYS)
        return draft.updated_at < expiry_cutoff

    def _delete_draft_if_exists(
        self,
        db: Session,
        user_id: UUID,
        hostel_id: UUID,
    ) -> None:
        """
        Delete draft for user/hostel if it exists.

        Args:
            db: Database session
            user_id: User UUID
            hostel_id: Hostel UUID
        """
        try:
            draft = self.review_repo.get_draft_for_user_and_hostel(db, user_id, hostel_id)
            if draft:
                self.review_repo.delete_draft(db, draft)
                logger.info(f"Deleted draft after review submission: {draft.id}")
        except Exception as e:
            # Don't fail review submission if draft deletion fails
            logger.error(f"Error deleting draft: {str(e)}")