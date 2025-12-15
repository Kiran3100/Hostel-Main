# app/api/v1/reviews/response.py
from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core import get_session
from app.services import UnitOfWork
from app.services.review import HostelResponseService
from app.schemas.review.review_response_schema import (
    HostelResponseCreate,
    OwnerResponse,
    HostelResponseUpdate,
    ResponseGuidelines,
    ResponseStats,
)
from . import CurrentUser, get_current_staff

router = APIRouter(tags=["Reviews - Hostel Responses"])


def _get_service(session: Session) -> HostelResponseService:
    uow = UnitOfWork(session)
    return HostelResponseService(uow)


@router.get("/guidelines", response_model=ResponseGuidelines)
def get_response_guidelines(
    session: Session = Depends(get_session),
) -> ResponseGuidelines:
    """
    Public guidelines for responding to reviews.
    """
    service = _get_service(session)
    # Expected: get_guidelines() -> ResponseGuidelines
    return service.get_guidelines()


@router.get("/{review_id}", response_model=Optional[OwnerResponse])
def get_hostel_response_for_review(
    review_id: UUID,
    session: Session = Depends(get_session),
) -> Optional[OwnerResponse]:
    """
    Get hostel/owner response for a specific review (if any).
    """
    service = _get_service(session)
    # Expected: get_response_for_review(review_id: UUID) -> Optional[OwnerResponse]
    return service.get_response_for_review(review_id=review_id)


@router.post("/{review_id}", response_model=OwnerResponse)
def create_hostel_response(
    review_id: UUID,
    payload: HostelResponseCreate,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_staff),
) -> OwnerResponse:
    """
    Create a hostel/owner response for a review (staff only).
    """
    service = _get_service(session)
    # Expected: create_response(review_id: UUID, user_id: UUID, data: HostelResponseCreate) -> OwnerResponse
    return service.create_response(
        review_id=review_id,
        user_id=current_user.id,
        data=payload,
    )


@router.patch("/{review_id}", response_model=OwnerResponse)
def update_hostel_response(
    review_id: UUID,
    payload: HostelResponseUpdate,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_staff),
) -> OwnerResponse:
    """
    Update an existing hostel/owner response (staff only).
    """
    service = _get_service(session)
    # Expected: update_response(review_id: UUID, user_id: UUID, data: HostelResponseUpdate) -> OwnerResponse
    return service.update_response(
        review_id=review_id,
        user_id=current_user.id,
        data=payload,
    )


@router.get("/hostels/{hostel_id}/stats", response_model=ResponseStats)
def get_response_stats_for_hostel(
    hostel_id: UUID,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_staff),
) -> ResponseStats:
    """
    Stats about how promptly/often a hostel responds to reviews.
    """
    service = _get_service(session)
    # Expected: get_stats_for_hostel(hostel_id: UUID) -> ResponseStats
    return service.get_stats_for_hostel(hostel_id=hostel_id)