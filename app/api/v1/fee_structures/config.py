# api/v1/fee_structures/config.py

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import get_uow
from app.core.exceptions import (
    ServiceError,
    NotFoundError,
    ValidationError,
    ConflictError,
)
from app.schemas.common.enums import RoomType, FeeType
from app.schemas.fee_structure.fee_config import FeeConfiguration
from app.services.common.unit_of_work import UnitOfWork
from app.services.fee_structure import FeeConfigService

router = APIRouter(prefix="/config")


def _map_service_error(exc: ServiceError) -> HTTPException:
    if isinstance(exc, NotFoundError):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    if isinstance(exc, ValidationError):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )
    if isinstance(exc, ConflictError):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=str(exc),
    )


@router.get(
    "/effective",
    response_model=FeeConfiguration,
    summary="Get effective fee configuration",
)
async def get_effective_fee_configuration(
    hostel_id: UUID = Query(..., description="Hostel ID"),
    room_type: RoomType = Query(..., description="Room type"),
    fee_type: FeeType = Query(..., description="Fee type (e.g. RENT, DEPOSIT)"),
    as_of: date = Query(..., description="Date for which to compute effective fee"),
    uow: UnitOfWork = Depends(get_uow),
) -> FeeConfiguration:
    """
    Compute the effective fee configuration for a hostel, room type, and fee type
    on a given date.

    Returns a FeeConfiguration that includes breakdown (rent, mess, utilities,
    deposit) and totals.
    """
    service = FeeConfigService(uow)
    try:
        return service.get_fee_configuration(
            hostel_id=hostel_id,
            room_type=room_type,
            fee_type=fee_type,
            as_of=as_of,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)