from datetime import date
from typing import Union
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from app.api.deps import get_uow
from app.core.exceptions import ServiceError, NotFoundError, ValidationError, ConflictError
from app.schemas.mess.menu_feedback import (
    FeedbackRequest,
    FeedbackResponse,
    RatingsSummary,
    QualityMetrics,
    FeedbackAnalysis,
)
from app.services.common.unit_of_work import UnitOfWork
from app.services.mess import MessFeedbackService

router = APIRouter(prefix="/feedback")


def _map_service_error(exc: ServiceError) -> HTTPException:
    if isinstance(exc, NotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, ValidationError):
        return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    if isinstance(exc, ConflictError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post(
    "/menus/{menu_id}",
    response_model=FeedbackResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit feedback for a mess menu",
)
async def submit_menu_feedback(
    menu_id: UUID = Path(..., description="Mess menu ID"),
    payload: FeedbackRequest = ...,
    uow: UnitOfWork = Depends(get_uow),
) -> FeedbackResponse:
    """
    Submit feedback and ratings for a specific mess menu.
    """
    service = MessFeedbackService(uow)
    try:
        return service.submit_feedback(
            menu_id=menu_id,
            request=payload,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.get(
    "/menus/{menu_id}",
    response_model=FeedbackResponse,
    summary="Get feedback for a mess menu",
)
async def get_menu_feedback(
    menu_id: UUID = Path(..., description="Mess menu ID"),
    uow: UnitOfWork = Depends(get_uow),
) -> FeedbackResponse:
    """
    Retrieve aggregated feedback for a specific mess menu.
    """
    service = MessFeedbackService(uow)
    try:
        return service.get_feedback(menu_id=menu_id)
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.get(
    "/hostels/{hostel_id}/ratings",
    response_model=RatingsSummary,
    summary="Get ratings summary for a hostel's mess",
)
async def get_ratings_summary(
    hostel_id: UUID = Path(..., description="Hostel ID"),
    period_start: Union[date, None] = Query(None, description="Start date (inclusive)"),
    period_end: Union[date, None] = Query(None, description="End date (inclusive)"),
    uow: UnitOfWork = Depends(get_uow),
) -> RatingsSummary:
    """
    Get overall and per-meal ratings summary for a hostel's mess over a period.
    """
    service = MessFeedbackService(uow)
    try:
        return service.get_ratings_summary(
            hostel_id=hostel_id,
            period_start=period_start,
            period_end=period_end,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.get(
    "/hostels/{hostel_id}/analysis",
    response_model=FeedbackAnalysis,
    summary="Get detailed feedback analysis for a hostel's mess",
)
async def get_feedback_analysis(
    hostel_id: UUID = Path(..., description="Hostel ID"),
    period_start: Union[date, None] = Query(None, description="Start date (inclusive)"),
    period_end: Union[date, None] = Query(None, description="End date (inclusive)"),
    uow: UnitOfWork = Depends(get_uow),
) -> FeedbackAnalysis:
    """
    Detailed analysis of mess feedback (trends, quality metrics, item-level ratings, etc.).
    """
    service = MessFeedbackService(uow)
    try:
        return service.get_feedback_analysis(
            hostel_id=hostel_id,
            period_start=period_start,
            period_end=period_end,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)