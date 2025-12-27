from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.booking.booking_filters import (
    BookingFilterParams,
    BookingSearchRequest,
    BookingExportRequest,
)
from app.schemas.booking.booking_response import BookingListItem
from app.services.booking.booking_search_service import BookingSearchService

router = APIRouter(prefix="/bookings/search", tags=["bookings:search"])


def get_search_service(db: Session = Depends(deps.get_db)) -> BookingSearchService:
    return BookingSearchService(db=db)


@router.post(
    "",
    response_model=Any,  # Typically List[BookingListItem] with metadata
    summary="Advanced booking search",
)
def search_bookings(
    payload: BookingSearchRequest,
    pagination=Depends(deps.get_pagination_params),
    _admin=Depends(deps.get_admin_user),
    service: BookingSearchService = Depends(get_search_service),
) -> Any:
    return service.search(payload, pagination)


@router.post(
    "/export",
    summary="Export bookings",
)
def export_bookings(
    payload: BookingExportRequest,
    _admin=Depends(deps.get_admin_user),
    service: BookingSearchService = Depends(get_search_service),
) -> Any:
    """
    Export booking data (CSV/Excel/PDF).
    """
    return service.export_bookings(payload)