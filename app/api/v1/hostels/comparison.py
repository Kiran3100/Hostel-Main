from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_uow
from app.core.exceptions import ServiceError, NotFoundError, ValidationError, ConflictError
from app.schemas.hostel.hostel_comparison import (
    HostelComparisonRequest,
    ComparisonResult,
)
from app.services.common.unit_of_work import UnitOfWork
from app.services.hostel import HostelComparisonService

router = APIRouter(prefix="/comparison")


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
    response_model=ComparisonResult,
    summary="Compare multiple hostels",
)
async def compare_hostels(
    payload: HostelComparisonRequest,
    uow: UnitOfWork = Depends(get_uow),
) -> ComparisonResult:
    """
    Compare up to 4 hostels on capacity, pricing, ratings, amenities, room types, and availability.
    """
    service = HostelComparisonService(uow)
    try:
        return service.compare_hostels(request=payload)
    except ServiceError as exc:
        raise _map_service_error(exc)