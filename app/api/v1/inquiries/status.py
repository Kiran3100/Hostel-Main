from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, status

from app.api.deps import get_uow
from app.core.exceptions import (
    ServiceError,
    NotFoundError,
    ValidationError,
    ConflictError,
)
from app.schemas.inquiry.inquiry_status import (
    InquiryStatusUpdate,
    InquiryAssignment,
    InquiryTimelineEntry,
)
from app.schemas.inquiry.inquiry_response import InquiryDetail
from app.services.common.unit_of_work import UnitOfWork
from app.services.inquiry import InquiryService, InquiryAssignmentService

router = APIRouter(prefix="/status")


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
    "/{inquiry_id}",
    response_model=InquiryDetail,
    summary="Update inquiry status",
)
async def update_inquiry_status(
    inquiry_id: UUID = Path(..., description="Inquiry ID"),
    payload: InquiryStatusUpdate = ...,
    uow: UnitOfWork = Depends(get_uow),
) -> InquiryDetail:
    """
    Update the status of an inquiry (pending, contacted, closed, etc.)
    and optionally add notes.
    """
    service = InquiryService(uow)
    try:
        return service.update_status(
            inquiry_id=inquiry_id,
            data=payload,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.post(
    "/{inquiry_id}/assign",
    response_model=InquiryDetail,
    summary="Assign an inquiry to an admin/staff member",
)
async def assign_inquiry(
    inquiry_id: UUID = Path(..., description="Inquiry ID"),
    payload: InquiryAssignment = ...,
    uow: UnitOfWork = Depends(get_uow),
) -> InquiryDetail:
    """
    Assign an inquiry to a specific admin/staff member and update
    contact status/notes as needed.
    """
    service = InquiryAssignmentService(uow)
    try:
        return service.assign_inquiry(
            inquiry_id=inquiry_id,
            request=payload,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.get(
    "/{inquiry_id}/timeline",
    response_model=List[InquiryTimelineEntry],
    summary="Get inquiry status/assignment timeline",
)
async def get_inquiry_timeline(
    inquiry_id: UUID = Path(..., description="Inquiry ID"),
    uow: UnitOfWork = Depends(get_uow),
) -> List[InquiryTimelineEntry]:
    """
    Return a timeline of status changes, assignments, and notes
    for a given inquiry.
    """
    service = InquiryService(uow)
    try:
        return service.get_timeline(inquiry_id=inquiry_id)
    except ServiceError as exc:
        raise _map_service_error(exc)