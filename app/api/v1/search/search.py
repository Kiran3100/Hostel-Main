# app/api/v1/search/search.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core import get_session
from app.services import UnitOfWork
from app.services.search import SearchService
from app.schemas.search.search_request import (
    BasicSearchRequest,
    AdvancedSearchRequest,
)
from app.schemas.search.search_response import FacetedSearchResponse

router = APIRouter(tags=["Search"])


def _get_service(session: Session) -> SearchService:
    uow = UnitOfWork(session)
    return SearchService(uow)


@router.post("/basic", response_model=FacetedSearchResponse)
def basic_search(
    payload: BasicSearchRequest,
    session: Session = Depends(get_session),
) -> FacetedSearchResponse:
    """
    Public basic search endpoint.

    Expected service method:
        basic_search(request: BasicSearchRequest) -> FacetedSearchResponse
    """
    service = _get_service(session)
    return service.basic_search(request=payload)


@router.post("/advanced", response_model=FacetedSearchResponse)
def advanced_search(
    payload: AdvancedSearchRequest,
    session: Session = Depends(get_session),
) -> FacetedSearchResponse:
    """
    Public advanced search endpoint with richer filters and sorting.

    Expected service method:
        advanced_search(request: AdvancedSearchRequest) -> FacetedSearchResponse
    """
    service = _get_service(session)
    return service.advanced_search(request=payload)