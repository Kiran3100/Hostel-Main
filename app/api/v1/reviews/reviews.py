# app/api/v1/reviews/reviews.py
from __future__ import annotations

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core import get_session
from app.services import UnitOfWork
from app.services.review import ReviewService
from app.schemas.review.review_filters import ReviewFilterParams, ReviewExportRequest
from app.schemas.review.review_response import (
    ReviewDetail,
    ReviewListItem,
    ReviewSummary,
)
from . import CurrentUser, get_current_user, get_current_staff

router = APIRouter(tags=["Reviews - Admin/Internal"])


def _get_service(session: Session) -> ReviewService:
    uow = UnitOfWork(session)
    return ReviewService(uow)


@router.get("/", response_model=List[ReviewListItem])
def list_reviews(
    filters: ReviewFilterParams = Depends(),
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_staff),
) -> List[ReviewListItem]:
    """
    List reviews with filters/search/sort (admin/internal).
    """
    service = _get_service(session)
    # Expected service method: list_reviews(filters: ReviewFilterParams) -> list[ReviewListItem]
    return service.list_reviews(filters=filters)


@router.get("/{review_id}", response_model=ReviewDetail)
def get_review(
    review_id: UUID,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_staff),
) -> ReviewDetail:
    """
    Get detailed review including moderation/override info (admin/internal).
    """
    service = _get_service(session)
    # Expected: get_review_detail(review_id: UUID) -> ReviewDetail
    return service.get_review_detail(review_id=review_id)


@router.get("/hostels/{hostel_id}/summary", response_model=ReviewSummary)
def get_hostel_review_summary(
    hostel_id: UUID,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> ReviewSummary:
    """
    Summary stats for reviews of a hostel (can be used in dashboards).
    """
    service = _get_service(session)
    # Expected: get_hostel_summary(hostel_id: UUID) -> ReviewSummary
    return service.get_hostel_summary(hostel_id=hostel_id)


@router.post("/export")
def export_reviews(
    payload: ReviewExportRequest,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_staff),
) -> dict:
    """
    Export reviews matching filters (CSV/Excel/etc. via reporting/export service).
    """
    service = _get_service(session)
    # Expected: export_reviews(request: ReviewExportRequest) -> dict | ExportResult
    result = service.export_reviews(request=payload)
    return result