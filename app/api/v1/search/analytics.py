# app/api/v1/search/analytics.py
from datetime import date as Date
from typing import Union

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core import get_session
from app.services import UnitOfWork
from app.services.search import SearchAnalyticsService
from app.schemas.search.search_analytics import SearchAnalytics
from . import CurrentUser, get_current_user

router = APIRouter(tags=["Search - Analytics"])


def _get_service(session: Session) -> SearchAnalyticsService:
    uow = UnitOfWork(session)
    return SearchAnalyticsService(uow)


@router.get("/summary", response_model=SearchAnalytics)
def get_search_analytics(
    start_date: Union[Date, None] = Query(
        None,
        description="Start Date for analytics window (inclusive). If omitted, uses a default window.",
    ),
    end_date: Union[Date, None] = Query(
        None,
        description="End Date for analytics window (inclusive). If omitted, uses today.",
    ),
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> SearchAnalytics:
    """
    Aggregated search analytics for a period.

    Expected service method:
        get_analytics(start_date: Optional[Date], end_date: Optional[Date]) -> SearchAnalytics
    """
    service = _get_service(session)
    return service.get_analytics(
        start_date=start_date,
        end_date=end_date,
    )