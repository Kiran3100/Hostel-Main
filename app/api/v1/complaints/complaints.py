# api/v1/complaints/complaints.py
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, status

from app.api.deps import get_uow
from app.core.exceptions import (
    ServiceError,
    NotFoundError,
    ValidationError,
    ConflictError,
)
from app.schemas.complaint.complaint_base import (
    ComplaintCreate,
    ComplaintUpdate,
    ComplaintStatusUpdate,
)
from app.schemas.complaint.complaint_response import (
    ComplaintDetail,
    ComplaintListItem,
    ComplaintSummary,
)
from app.schemas.complaint.complaint_filters import ComplaintFilterParams, ComplaintSearchRequest
from app.schemas.common.pagination import PaginatedResponse
from app.services.common.unit_of_work import UnitOfWork
from app.services.complaint import ComplaintService

router = APIRouter()


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
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=str(exc),
    )


@router.get(
    "/",
    response_model=PaginatedResponse[ComplaintListItem],
    summary="List complaints",
)
async def list_complaints(
    filters: ComplaintFilterParams = Depends(),
    uow: UnitOfWork = Depends(get_uow),
) -> PaginatedResponse[ComplaintListItem]:
    """
    List complaints using filters (hostel, status, category, priority, date range, etc.)
    with pagination and sorting.
    """
    service = ComplaintService(uow)
    try:
        return service.list_complaints(filters=filters)
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.post(
    "/",
    response_model=ComplaintDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new complaint",
)
async def create_complaint(
    payload: ComplaintCreate,
    uow: UnitOfWork = Depends(get_uow),
) -> ComplaintDetail:
    """
    Create a new complaint record.
    """
    service = ComplaintService(uow)
    try:
        return service.create_complaint(data=payload)
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.get(
    "/{complaint_id}",
    response_model=ComplaintDetail,
    summary="Get complaint details",
)
async def get_complaint(
    complaint_id: UUID = Path(..., description="Complaint ID"),
    uow: UnitOfWork = Depends(get_uow),
) -> ComplaintDetail:
    """
    Retrieve detailed complaint information, including room/student context if available.
    """
    service = ComplaintService(uow)
    try:
        return service.get_complaint(complaint_id=complaint_id)
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.patch(
    "/{complaint_id}",
    response_model=ComplaintDetail,
    summary="Update a complaint",
)
async def update_complaint(
    complaint_id: UUID = Path(..., description="Complaint ID"),
    payload: ComplaintUpdate = ...,
    uow: UnitOfWork = Depends(get_uow),
) -> ComplaintDetail:
    """
    Partially update complaint fields (title, description, category, priority, location, etc.).
    """
    service = ComplaintService(uow)
    try:
        return service.update_complaint(
            complaint_id=complaint_id,
            data=payload,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.patch(
    "/{complaint_id}/status",
    response_model=ComplaintDetail,
    summary="Update complaint status",
)
async def update_complaint_status(
    complaint_id: UUID = Path(..., description="Complaint ID"),
    payload: ComplaintStatusUpdate = ...,
    uow: UnitOfWork = Depends(get_uow),
) -> ComplaintDetail:
    """
    Update the status of a complaint (open, in_progress, resolved, closed, escalated, etc.).
    """
    service = ComplaintService(uow)
    try:
        return service.update_status(
            complaint_id=complaint_id,
            data=payload,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.post(
    "/search",
    response_model=PaginatedResponse[ComplaintListItem],
    summary="Search complaints",
)
async def search_complaints(
    payload: ComplaintSearchRequest,
    uow: UnitOfWork = Depends(get_uow),
) -> PaginatedResponse[ComplaintListItem]:
    """
    Perform a structured search over complaints with richer query criteria.
    """
    service = ComplaintService(uow)
    try:
        return service.search_complaints(request=payload)
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.get(
    "/hostels/{hostel_id}/summary",
    response_model=ComplaintSummary,
    summary="Get complaint summary for a hostel",
)
async def get_complaint_summary_for_hostel(
    hostel_id: UUID = Path(..., description="Hostel ID"),
    uow: UnitOfWork = Depends(get_uow),
) -> ComplaintSummary:
    """
    Summarize complaints for a hostel: counts by status, average resolution time, etc.
    """
    service = ComplaintService(uow)
    try:
        return service.get_hostel_summary(hostel_id=hostel_id)
    except ServiceError as exc:
        raise _map_service_error(exc)