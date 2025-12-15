# app/services/review/public_review_service.py
from __future__ import annotations

from datetime import datetime
from typing import Callable, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.content import ReviewRepository
from app.repositories.core import HostelRepository, UserRepository, StudentRepository
from app.schemas.common.pagination import PaginationParams, PaginatedResponse
from app.schemas.review.review_submission import (
    ReviewSubmissionRequest,
    DetailedRatingsInput,
    ReviewGuidelines,
    ReviewEligibility,
)
from app.schemas.review import ReviewDetail, ReviewListItem
from app.schemas.review.review_filters import ReviewFilterParams, ReviewSortOptions
from app.services.common import UnitOfWork, errors
from .review_service import ReviewService


class PublicReviewService:
    """
    Public-facing wrapper for internal reviews:

    - Submit review (ReviewSubmissionRequest) as an internal Review
    - Check simple review eligibility
    - Provide guidelines
    - List public reviews for hostel (approved + sorted)
    """

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory
        self._review_service = ReviewService(session_factory)

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _get_review_repo(self, uow: UnitOfWork) -> ReviewRepository:
        return uow.get_repo(ReviewRepository)

    def _get_hostel_repo(self, uow: UnitOfWork) -> HostelRepository:
        return uow.get_repo(HostelRepository)

    def _get_user_repo(self, uow: UnitOfWork) -> UserRepository:
        return uow.get_repo(UserRepository)

    def _get_student_repo(self, uow: UnitOfWork) -> StudentRepository:
        return uow.get_repo(StudentRepository)

    def _now(self) -> datetime:
        return datetime.utcnow()

    # ------------------------------------------------------------------ #
    # Eligibility & guidelines
    # ------------------------------------------------------------------ #
    def get_guidelines(self) -> ReviewGuidelines:
        return ReviewGuidelines()

    def check_eligibility(self, user_id: UUID, hostel_id: UUID) -> ReviewEligibility:
        """
        Very simple eligibility:

        - can_review if the user has not already reviewed this hostel.
        - has_booking/has_stayed are not checked (no booking linkage here).
        """
        with UnitOfWork(self._session_factory) as uow:
            review_repo = self._get_review_repo(uow)

            existing = review_repo.get_multi(
                skip=0,
                limit=1,
                filters={"hostel_id": hostel_id, "reviewer_id": user_id},
            )

        already = bool(existing)
        can_review = not already
        reason = "Eligible to review" if can_review else "You have already reviewed this hostel"

        return ReviewEligibility(
            user_id=user_id,
            hostel_id=hostel_id,
            can_review=can_review,
            reason=reason,
            has_stayed=False,
            has_booking=False,
            already_reviewed=already,
            existing_review_id=existing[0].id if already else None,
            can_edit=already,
        )

    # ------------------------------------------------------------------ #
    # Submission
    # ------------------------------------------------------------------ #
    def submit_review(
        self,
        reviewer_id: UUID,
        data: ReviewSubmissionRequest,
    ) -> ReviewDetail:
        """
        Map ReviewSubmissionRequest to internal ReviewCreate and delegate to ReviewService.
        """
        # The ReviewCreate schema is similar to ReviewSubmissionRequest; we map manually.
        from app.schemas.review import ReviewCreate

        # Approximate mapping from DetailedRatings
        dr: DetailedRatingsInput = data.detailed_ratings

        create = ReviewCreate(
            hostel_id=data.hostel_id,
            reviewer_id=reviewer_id,
            student_id=data.student_id,
            booking_id=data.booking_id,
            overall_rating=data.overall_rating,
            title=data.title,
            review_text=data.review_text,
            cleanliness_rating=dr.cleanliness,
            food_quality_rating=dr.food_quality,
            staff_behavior_rating=dr.staff_behavior,
            security_rating=dr.security,
            value_for_money_rating=dr.value_for_money,
            amenities_rating=dr.amenities,
            photos=data.photos,
        )
        return self._review_service.create_review(create)

    # ------------------------------------------------------------------ #
    # Public listing
    # ------------------------------------------------------------------ #
    def list_public_reviews(
        self,
        hostel_id: UUID,
        params: PaginationParams,
        *,
        min_rating: Optional[float] = None,
    ) -> PaginatedResponse[ReviewListItem]:
        """
        Convenience wrapper: show only approved reviews for hostel,
        optionally filtered by minimum rating.
        """
        filters = ReviewFilterParams(
            hostel_id=hostel_id,
            min_rating=min_rating,
            approved_only=True,
        )
        sort = ReviewSortOptions(sort_by="helpful", verified_first=True, with_photos_first=True)
        return self._review_service.list_reviews(params, filters=filters, sort=sort)