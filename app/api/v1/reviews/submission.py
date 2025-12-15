from typing import List, Union
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core import get_session
from app.services import UnitOfWork
from app.services.review import PublicReviewService
from app.schemas.review.review_submission import (
    ReviewSubmissionRequest,
    ReviewEligibility,
)
from app.schemas.review.review_response import (
    ReviewDetail,
    ReviewResponse,
)
from app.schemas.review.review_filters import ReviewSearchRequest, ReviewSortOptions
from . import CurrentUser, get_current_user

router = APIRouter(tags=["Reviews - Public Submission & Listing"])


def _get_service(session: Session) -> PublicReviewService:
    uow = UnitOfWork(session)
    return PublicReviewService(uow)


@router.post("/", response_model=ReviewDetail)
def submit_review(
    payload: ReviewSubmissionRequest,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> ReviewDetail:
    """
    Submit a public review (visitor/student). Requires authenticated user.
    """
    service = _get_service(session)
    # Expected: submit_review(user_id: UUID, data: ReviewSubmissionRequest) -> ReviewDetail
    return service.submit_review(
        user_id=current_user.id,
        data=payload,
    )


@router.get("/eligibility", response_model=ReviewEligibility)
def check_review_eligibility(
    hostel_id: UUID = Query(..., description="Hostel the user wants to review"),
    booking_id: Union[UUID, None] = Query(
        None,
        description="Optional booking id for more precise eligibility checks",
    ),
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> ReviewEligibility:
    """
    Check if the current user is eligible to submit or edit a review for a hostel.
    """
    service = _get_service(session)
    # Expected: check_eligibility(user_id: UUID, hostel_id: UUID, booking_id: Union[UUID, None]) -> ReviewEligibility
    return service.check_eligibility(
        user_id=current_user.id,
        hostel_id=hostel_id,
        booking_id=booking_id,
    )


@router.get("/hostels/{hostel_id}", response_model=List[ReviewResponse])
def list_public_reviews_for_hostel(
    hostel_id: UUID,
    search: ReviewSearchRequest = Depends(),
    sort: ReviewSortOptions = Depends(),
    session: Session = Depends(get_session),
) -> List[ReviewResponse]:
    """
    Public listing of approved reviews for a hostel (used in public profile pages).
    """
    service = _get_service(session)
    # Expected:
    #   list_public_reviews(hostel_id: UUID,
    #                       search: ReviewSearchRequest,
    #                       sort: ReviewSortOptions) -> list[ReviewResponse]
    return service.list_public_reviews(
        hostel_id=hostel_id,
        search=search,
        sort=sort,
    )