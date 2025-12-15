# app/api/v1/visitors/search.py

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core import get_session
from app.services import UnitOfWork
from app.services.visitor import VisitorHostelSearchService
from app.schemas.hostel.hostel_search import (
    HostelSearchRequest,
    HostelSearchResponse,
)
from . import CurrentUser, get_current_visitor

router = APIRouter(tags=["Visitor - Search"])


def _get_service(session: Session) -> VisitorHostelSearchService:
    uow = UnitOfWork(session)
    return VisitorHostelSearchService(uow)


@router.post("/", response_model=HostelSearchResponse)
def search_hostels(
    payload: HostelSearchRequest,
    session: Session = Depends(get_session),
) -> HostelSearchResponse:
    """
    Public / generic hostel search over the visitor-facing index.

    This does not require authentication; if you want to make this
    visitor-only, add get_current_visitor as a dependency.
    """
    service = _get_service(session)
    # Expected service method:
    #   search(request: HostelSearchRequest) -> HostelSearchResponse
    return service.search(request=payload)


@router.get("/recommended", response_model=HostelSearchResponse)
def recommended_hostels(
    current_user: CurrentUser = Depends(get_current_visitor),
    session: Session = Depends(get_session),
) -> HostelSearchResponse:
    """
    Recommend hostels based on the visitor's saved preferences and behavior.
    """
    service = _get_service(session)
    # Expected service method:
    #   search_by_preferences(user_id: UUID) -> HostelSearchResponse
    return service.search_by_preferences(user_id=current_user.id)