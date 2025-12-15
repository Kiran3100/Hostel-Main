# app/api/v1/search/autocomplete.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core import get_session
from app.services import UnitOfWork
from app.services.search import AutocompleteService
from app.schemas.search.search_autocomplete import (
    AutocompleteRequest,
    AutocompleteResponse,
)

router = APIRouter(tags=["Search - Autocomplete"])


def _get_service(session: Session) -> AutocompleteService:
    uow = UnitOfWork(session)
    return AutocompleteService(uow)


@router.post("/", response_model=AutocompleteResponse)
def autocomplete(
    payload: AutocompleteRequest,
    session: Session = Depends(get_session),
) -> AutocompleteResponse:
    """
    Return autocomplete suggestions for hostel names, cities, and areas.

    Expected service method:
        get_suggestions(request: AutocompleteRequest) -> AutocompleteResponse
    """
    service = _get_service(session)
    return service.get_suggestions(request=payload)