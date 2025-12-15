from typing import List, Union
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from app.api.deps import get_uow
from app.core.exceptions import (
    ServiceError,
    NotFoundError,
    ValidationError,
    ConflictError,
)
from app.schemas.common.enums import InquiryStatus
from app.schemas.inquiry.inquiry_base import InquiryCreate
from app.schemas.inquiry.inquiry_response import (
    InquiryResponse,
    InquiryDetail,
    InquiryListItem,
)
from app.services.common.unit_of_work import UnitOfWork
from app.services.inquiry import InquiryService

router = APIRouter()


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


@router.post(
    "/",
    response_model=InquiryDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new inquiry",
)
async def create_inquiry(
    payload: InquiryCreate,
    uow: UnitOfWork = Depends(get_uow),
) -> InquiryDetail:
    """
    Create a visitor inquiry for a hostel.

    Can be used by public visitor flows or internal/admin tools.
    """
    service = InquiryService(uow)
    try:
        return service.create_inquiry(data=payload)
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.get(
    "/{inquiry_id}",
    response_model=InquiryDetail,
    summary="Get inquiry details",
)
async def get_inquiry(
    inquiry_id: UUID = Path(..., description="Inquiry ID"),
    uow: UnitOfWork = Depends(get_uow),
) -> InquiryDetail:
    """
    Retrieve detailed information about a specific inquiry.
    """
    service = InquiryService(uow)
    try:
        return service.get_inquiry(inquiry_id=inquiry_id)
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.get(
    "/",
    response_model=List[InquiryListItem],
    summary="List inquiries for a hostel",
)
async def list_inquiries(
    hostel_id: UUID = Query(..., description="Hostel ID"),
    status_filter: Union[InquiryStatus, None] = Query(
        None,
        alias="status",
        description="Optional inquiry status filter",
    ),
    uow: UnitOfWork = Depends(get_uow),
) -> List[InquiryListItem]:
    """
    List inquiries for a given hostel, optionally filtered by status.
    """
    service = InquiryService(uow)
    try:
        return service.list_inquiries(
            hostel_id=hostel_id,
            status=status_filter,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.get(
    "/hostels/{hostel_id}/open",
    response_model=List[InquiryListItem],
    summary="List open inquiries for a hostel",
)
async def list_open_inquiries_for_hostel(
    hostel_id: UUID = Path(..., description="Hostel ID"),
    uow: UnitOfWork = Depends(get_uow),
) -> List[InquiryListItem]:
    """
    List open/pending inquiries for a given hostel.
    """
    service = InquiryService(uow)
    try:
        return service.list_open_inquiries(hostel_id=hostel_id)
    except ServiceError as exc:
        raise _map_service_error(exc)