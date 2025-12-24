"""
Review Service

Core user-facing review operations:
- Eligibility checks
- Submission (create)
- Update/delete by author
- Listing and detail retrieval
- Draft handling
- Summary retrieval
"""

from __future__ import annotations

from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy.orm import Session

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
from app.core.exceptions import ValidationException, BusinessLogicException


class ReviewService:
    """
    High-level orchestration service for reviews.

    Delegates persistence and heavy querying to ReviewRepository.
    """

    def __init__(self, review_repo: ReviewRepository) -> None:
        self.review_repo = review_repo

    # -------------------------------------------------------------------------
    # Eligibility & guidelines
    # -------------------------------------------------------------------------

    def get_eligibility(
        self,
        db: Session,
        user_id: UUID,
        hostel_id: UUID,
    ) -> ReviewEligibility:
        """
        Check whether a user is allowed to leave/edit a review for a hostel.
        """
        data = self.review_repo.get_eligibility(db, user_id, hostel_id)
        if not data:
            # Repo is expected to always return something; None means hostel/user invalid
            raise ValidationException("Unable to determine review eligibility")
        return ReviewEligibility.model_validate(data)

    def get_guidelines(
        self,
        db: Session,
        hostel_id: Optional[UUID] = None,
    ) -> ReviewGuidelines:
        """
        Get review guidelines (global or hostel-specific).
        """
        data = self.review_repo.get_guidelines(db, hostel_id=hostel_id)
        if not data:
            # Fallback to default guidelines defined at repo/schema level
            data = ReviewGuidelines().model_dump()
        return ReviewGuidelines.model_validate(data)

    # -------------------------------------------------------------------------
    # Submission & editing
    # -------------------------------------------------------------------------

    def submit_review(
        self,
        db: Session,
        user_id: UUID,
        hostel_id: UUID,
        submission: ReviewSubmissionRequest,
    ) -> ReviewDetail:
        """
        Submit a new review for a hostel.

        Flow:
        - Check eligibility
        - Create review and mark as pending/moderation as per business rules.
        """
        eligibility = self.get_eligibility(db, user_id, hostel_id)
        if not eligibility.can_review:
            raise BusinessLogicException(eligibility.message or "User not eligible to review")

        payload = submission.model_dump(exclude_none=True)
        payload.update({"user_id": user_id, "hostel_id": hostel_id})

        obj = self.review_repo.create_from_submission(db, payload)
        return ReviewDetail.model_validate(obj)

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
        - Ownership
        - Eligibility to edit (time window, status)
        """
        review = self.review_repo.get_by_id(db, review_id)
        if not review:
            raise ValidationException("Review not found")

        if review.user_id != user_id:
            raise BusinessLogicException("You can only edit your own reviews")

        if not self.review_repo.can_edit_review(db, review):
            raise BusinessLogicException("Review can no longer be edited")

        updated = self.review_repo.update(
            db,
            obj=review,
            data=data.model_dump(exclude_none=True),
        )
        return ReviewDetail.model_validate(updated)

    def delete_review(
        self,
        db: Session,
        review_id: UUID,
        user_id: UUID,
    ) -> None:
        """
        Soft-delete a review authored by the user.
        """
        review = self.review_repo.get_by_id(db, review_id)
        if not review:
            return

        if review.user_id != user_id:
            raise BusinessLogicException("You can only delete your own reviews")

        self.review_repo.soft_delete(db, review)

    # -------------------------------------------------------------------------
    # Drafts
    # -------------------------------------------------------------------------

    def get_draft(
        self,
        db: Session,
        user_id: UUID,
        hostel_id: UUID,
    ) -> Optional[ReviewDraft]:
        obj = self.review_repo.get_draft_for_user_and_hostel(db, user_id, hostel_id)
        if not obj:
            return None
        return ReviewDraft.model_validate(obj)

    def save_draft(
        self,
        db: Session,
        user_id: UUID,
        hostel_id: UUID,
        draft: ReviewDraft,
    ) -> ReviewDraft:
        payload = draft.model_dump(exclude_none=True)
        payload.update({"user_id": user_id, "hostel_id": hostel_id})

        obj = self.review_repo.upsert_draft(db, payload)
        return ReviewDraft.model_validate(obj)

    def delete_draft(
        self,
        db: Session,
        draft_id: UUID,
        user_id: UUID,
    ) -> None:
        draft = self.review_repo.get_draft_by_id(db, draft_id)
        if not draft or draft.user_id != user_id:
            return
        self.review_repo.delete_draft(db, draft)

    # -------------------------------------------------------------------------
    # Retrieval & listing
    # -------------------------------------------------------------------------

    def get_review(
        self,
        db: Session,
        review_id: UUID,
    ) -> ReviewDetail:
        obj = self.review_repo.get_full_review(db, review_id)
        if not obj:
            raise ValidationException("Review not found")
        return ReviewDetail.model_validate(obj)

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
        List reviews for a hostel with filters, sorting, and pagination.

        Returns:
            (items, total_count, summary)
        """
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

        return items, total, summary

    def search_reviews(
        self,
        db: Session,
        request: ReviewSearchRequest,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[ReviewListItem], int]:
        """
        Full-text style search over reviews.
        """
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
        return items, total

    def get_hostel_summary(
        self,
        db: Session,
        hostel_id: UUID,
    ) -> ReviewSummary:
        data = self.review_repo.get_hostel_summary(db, hostel_id)
        if not data:
            # Return default empty summary instead of raising
            return ReviewSummary(
                hostel_id=hostel_id,
                total_reviews=0,
                average_rating=0.0,
                rating_distribution={},
                verified_percentage=0.0,
                recent_reviews=[],
            )
        return ReviewSummary.model_validate(data)