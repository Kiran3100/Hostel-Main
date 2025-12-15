# app/api/v1/reviews/analytics.py
from datetime import date as Date
from uuid import UUID
from typing import Union

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core import get_session
from app.services import UnitOfWork
from app.services.review import ReviewAnalyticsService
from app.schemas.review.review_analytics import ReviewAnalytics
from . import CurrentUser, get_current_user

router = APIRouter(tags=["Reviews - Analytics"])


def _get_service(session: Session) -> ReviewAnalyticsService:
    uow = UnitOfWork(session)
    return ReviewAnalyticsService(uow)


@router.get("/hostels/{hostel_id}", response_model=ReviewAnalytics)
def get_hostel_review_analytics(
    hostel_id: UUID,
    start_date: Union[Date, None] = Query(
        None,
        description="Start Date (inclusive) for analytics period",
    ),
    end_date: Union[Date, None] = Query(
        None,
        description="End Date (inclusive) for analytics period",
    ),
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> ReviewAnalytics:
    """
    Get review analytics for a hostel over a period.

    Includes rating distribution, trends, aspect analysis, etc.
    """
    service = _get_service(session)
    # Expected:
    #   get_analytics_for_hostel(
    #       hostel_id: UUID,
    #       start_date: Optional[Date],
    #       end_date: Optional[Date],
    #   ) -> ReviewAnalytics
    return service.get_analytics_for_hostel(
        hostel_id=hostel_id,
        start_date=start_date,
        end_date=end_date,
    )