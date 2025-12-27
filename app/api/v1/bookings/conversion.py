from typing import Any

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.booking.booking_conversion import (
    ConvertToStudentRequest,
    ConversionResponse,
    ConversionChecklist,
    ConversionRollback,
)
from app.services.booking.booking_conversion_service import BookingConversionService

router = APIRouter(prefix="/bookings/conversion", tags=["bookings:conversion"])


def get_conversion_service(db: Session = Depends(deps.get_db)) -> BookingConversionService:
    return BookingConversionService(db=db)


@router.post(
    "/{booking_id}",
    response_model=ConversionResponse,
    summary="Convert booking to student",
)
def convert_booking(
    booking_id: str,
    payload: ConvertToStudentRequest,
    _admin=Depends(deps.get_admin_user),
    service: BookingConversionService = Depends(get_conversion_service),
) -> Any:
    return service.convert(booking_id, payload, actor_id=_admin.id)


@router.get(
    "/{booking_id}/checklist",
    response_model=ConversionChecklist,
    summary="Get conversion checklist",
)
def get_conversion_checklist(
    booking_id: str,
    _admin=Depends(deps.get_admin_user),
    service: BookingConversionService = Depends(get_conversion_service),
) -> Any:
    return service.get_checklist(booking_id)


@router.post(
    "/{booking_id}/rollback",
    status_code=status.HTTP_200_OK,
    summary="Rollback conversion",
)
def rollback_conversion(
    booking_id: str,
    payload: ConversionRollback,
    _super_admin=Depends(deps.get_super_admin_user),
    service: BookingConversionService = Depends(get_conversion_service),
) -> Any:
    service.rollback(booking_id, payload, actor_id=_super_admin.id)
    return {"detail": "Conversion rolled back successfully"}