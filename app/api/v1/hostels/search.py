# api/v1/hostels/search.py
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_uow
from app.core.exceptions import ServiceError, NotFoundError, ValidationError, ConflictError
from app.schemas.hostel.hostel_search import (
    HostelSearchRequest,
    HostelSearchResponse,
)
from app.services.common.unit_of_work import UnitOfWork
from app.services.hostel_public import HostelSearchService

router = APIRouter(prefix="/search")


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
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post(
    "/",
    response_model=HostelSearchResponse,
    summary="Search hostels (public)",
)
async def search_hostels(
    payload: HostelSearchRequest,
    uow: UnitOfWork = Depends(get_uow),
) -> HostelSearchResponse:
    """
    Public hostel search using rich filters, sorting, and facet generation.
    """
    service = HostelSearchService(uow)
    try:
        return service.search(request=payload)
    except ServiceError as exc:
        raise _map_service_error(exc)