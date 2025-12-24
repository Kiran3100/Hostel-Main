"""
Review Moderation Service

Admin-side moderation workflow:
- Approve/reject/hold reviews
- Flag/unflag
- Work with moderation queue
- View moderation stats
"""

from __future__ import annotations

from typing import List, Tuple
from uuid import UUID

from sqlalchemy.orm import Session

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
from app.core.exceptions import ValidationException, BusinessLogicException


class ReviewModerationService:
    """
    High-level moderation orchestration.

    Delegates persistence & heavy logic to ReviewModerationRepository.
    """

    def __init__(
        self,
        moderation_repo: ReviewModerationRepository,
        review_repo: ReviewRepository,
    ) -> None:
        self.moderation_repo = moderation_repo
        self.review_repo = review_repo

    # -------------------------------------------------------------------------
    # Actions
    # -------------------------------------------------------------------------

    def moderate_review(
        self,
        db: Session,
        request: ModerationRequest,
        moderator_id: UUID,
    ) -> ModerationResponse:
        """
        Process a single moderation action for a review.
        """
        review = self.review_repo.get_by_id(db, request.review_id)
        if not review:
            raise ValidationException("Review not found")

        result = self.moderation_repo.apply_moderation_action(
            db=db,
            review=review,
            moderator_id=moderator_id,
            action=request.action,
            reason=request.reason,
            notes=request.notes,
        )
        return ModerationResponse.model_validate(result)

    def flag_review(
        self,
        db: Session,
        user_id: UUID,
        request: FlagReview,
    ) -> None:
        """
        User-side flagging of a review.
        """
        review = self.review_repo.get_by_id(db, request.review_id)
        if not review:
            raise ValidationException("Review not found")

        self.moderation_repo.flag_review(
            db=db,
            review=review,
            flagged_by=user_id,
            reason=request.reason,
            details=request.details,
        )

    def bulk_moderate(
        self,
        db: Session,
        request: BulkModeration,
        moderator_id: UUID,
    ) -> List[ModerationResponse]:
        """
        Apply a moderation action to multiple reviews.
        """
        responses: List[ModerationResponse] = []

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
            except (ValidationException, BusinessLogicException):
                if not request.skip_failed:
                    raise

        return responses

    # -------------------------------------------------------------------------
    # Queue & stats
    # -------------------------------------------------------------------------

    def get_moderation_queue(
        self,
        db: Session,
        hostel_id: UUID,
        limit: int = 50,
    ) -> ModerationQueue:
        """
        Get the current moderation queue for a hostel.
        """
        data = self.moderation_repo.get_queue(db, hostel_id=hostel_id, limit=limit)
        return ModerationQueue.model_validate(data)

    def get_pending_reviews(
        self,
        db: Session,
        hostel_id: UUID,
        limit: int = 50,
    ) -> List[PendingReview]:
        """
        List individual pending reviews for moderation.
        """
        objs = self.moderation_repo.get_pending_reviews(db, hostel_id, limit)
        return [PendingReview.model_validate(o) for o in objs]

    def get_moderation_stats(
        self,
        db: Session,
        hostel_id: UUID,
    ) -> ModerationStats:
        data = self.moderation_repo.get_stats(db, hostel_id)
        if not data:
            # Default empty stats
            return ModerationStats(
                hostel_id=hostel_id,
                total_pending=0,
                total_approved=0,
                total_rejected=0,
                avg_moderation_time_hours=0.0,
                actions_by_moderator={},
            )
        return ModerationStats.model_validate(data)