# app/api/v1/reviews/moderation.py
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core import get_session
from app.services import UnitOfWork
from app.services.review import ReviewModerationService
from app.schemas.review.review_moderation import (
    ModerationRequest,
    ModerationResponse,
    ModerationQueue,
    PendingReview,
    BulkModeration,
    ModerationStats,
)
from . import CurrentUser, get_current_staff

router = APIRouter(tags=["Reviews - Moderation"])


def _get_service(session: Session) -> ReviewModerationService:
    uow = UnitOfWork(session)
    return ReviewModerationService(uow)


@router.get("/queue", response_model=ModerationQueue)
def get_moderation_queue(
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_staff),
) -> ModerationQueue:
    """
    Get the pending moderation queue for staff.
    """
    service = _get_service(session)
    # Expected: get_moderation_queue() -> ModerationQueue
    return service.get_moderation_queue()


@router.get("/pending", response_model=List[PendingReview])
def list_pending_reviews(
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_staff),
) -> List[PendingReview]:
    """
    List pending reviews (flat list).
    """
    service = _get_service(session)
    # Expected: list_pending_reviews() -> list[PendingReview]
    return service.list_pending_reviews()


@router.post("/{review_id}", response_model=ModerationResponse)
def moderate_review(
    review_id: UUID,
    payload: ModerationRequest,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_staff),
) -> ModerationResponse:
    """
    Approve/reject/flag a single review.
    """
    service = _get_service(session)
    # Expected: moderate_review(review_id: UUID, data: ModerationRequest) -> ModerationResponse
    return service.moderate_review(
        review_id=review_id,
        data=payload,
    )


@router.post("/bulk", response_model=ModerationStats)
def bulk_moderate_reviews(
    payload: BulkModeration,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_staff),
) -> ModerationStats:
    """
    Bulk moderation of multiple reviews.
    """
    service = _get_service(session)
    # Expected: bulk_moderate(data: BulkModeration) -> ModerationStats
    return service.bulk_moderate(data=payload)


@router.get("/stats", response_model=ModerationStats)
def get_moderation_stats(
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_staff),
) -> ModerationStats:
    """
    Moderation stats (actions, time-to-moderate, per-user counts).
    """
    service = _get_service(session)
    # Expected: get_stats() -> ModerationStats
    return service.get_stats()