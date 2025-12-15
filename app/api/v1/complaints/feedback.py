# api/v1/complaints/feedback.py
from __future__ import annotations

from datetime import date as Date

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from app.api.deps import get_uow
from app.core.exceptions import (
    ServiceError,
    NotFoundError,
    ValidationError,
    ConflictError,
)
from app.schemas.complaint.complaint_feedback import (
    FeedbackRequest,
    FeedbackResponse,
    FeedbackSummary,
    FeedbackAnalysis,
)
from app.services.common.unit_of_work import UnitOfWork
from app.services.complaint import ComplaintFeedbackService

router = APIRouter(prefix="/feedback")


def _map_service_error(exc: ServiceError) -> HTTPException:
    if isinstance(exc, NotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, ValidationError):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )
    if isinstance(exc, ConflictError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=str(exc),
    )


@router.post(
    "/{complaint_id}",
    response_model=FeedbackResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit feedback for a complaint",
)
async def submit_feedback(
    complaint_id: UUID = Path(..., description="Complaint ID"),
    payload: FeedbackRequest = ...,
    uow: UnitOfWork = Depends(get_uow),
) -> FeedbackResponse:
    """
    Submit post-resolution feedback for a complaint.
    """
    service = ComplaintFeedbackService(uow)
    try:
        return service.submit_feedback(
            complaint_id=complaint_id,
            request=payload,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.get(
    "/{complaint_id}",
    response_model=FeedbackResponse,
    summary="Get feedback for a complaint",
)
async def get_feedback(
    complaint_id: UUID = Path(..., description="Complaint ID"),
    uow: UnitOfWork = Depends(get_uow),
) -> FeedbackResponse:
    """
    Retrieve feedback associated with a specific complaint (if any).
    """
    service = ComplaintFeedbackService(uow)
    try:
        return service.get_feedback(complaint_id=complaint_id)
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.get(
    "/summary",
    response_model=FeedbackSummary,
    summary="Get feedback summary for a hostel",
)
async def get_feedback_summary(
    hostel_id: UUID = Query(..., description="Hostel ID"),
    period_start: Optional[Date] = Query(None, description="Start Date (inclusive)"),
    period_end: Optional[Date] = Query(None, description="End Date (inclusive)"),
    uow: UnitOfWork = Depends(get_uow),
) -> FeedbackSummary:
    """
    Summarize complaint feedback for a hostel: ratings, satisfaction, etc.
    """
    service = ComplaintFeedbackService(uow)
    try:
        return service.get_summary(
            hostel_id=hostel_id,
            period_start=period_start,
            period_end=period_end,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.get(
    "/analysis",
    response_model=FeedbackAnalysis,
    summary="Analyze complaint feedback for a hostel",
)
async def get_feedback_analysis(
    hostel_id: UUID = Query(..., description="Hostel ID"),
    period_start: Optional[Date] = Query(None, description="Start Date (inclusive)"),
    period_end: Optional[Date] = Query(None, description="End Date (inclusive)"),
    uow: UnitOfWork = Depends(get_uow),
) -> FeedbackAnalysis:
    """
    Return a more detailed analysis of complaint feedback (trends, ratings, etc.).
    """
    service = ComplaintFeedbackService(uow)
    try:
        return service.get_analysis(
            hostel_id=hostel_id,
            period_start=period_start,
            period_end=period_end,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)