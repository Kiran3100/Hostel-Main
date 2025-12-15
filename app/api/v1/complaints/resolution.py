# api/v1/complaints/resolution.py
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
from app.schemas.complaint.complaint_resolution import (
    ResolutionRequest,
    ResolutionResponse,
    ResolutionUpdate,
    ReopenRequest,
    CloseRequest,
)
from app.services.common.unit_of_work import UnitOfWork
from app.services.complaint import ComplaintService

router = APIRouter(prefix="/resolution")


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


@router.post(
    "/{complaint_id}",
    response_model=ResolutionResponse,
    status_code=status.HTTP_200_OK,
    summary="Add resolution details to a complaint",
)
async def add_resolution(
    complaint_id: UUID = Path(..., description="Complaint ID"),
    payload: ResolutionRequest = ...,
    uow: UnitOfWork = Depends(get_uow),
) -> ResolutionResponse:
    """
    Record resolution details for a complaint and update its status.
    """
    service = ComplaintService(uow)
    try:
        return service.add_resolution(
            complaint_id=complaint_id,
            request=payload,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.patch(
    "/{complaint_id}",
    response_model=ResolutionResponse,
    summary="Update complaint resolution",
)
async def update_resolution(
    complaint_id: UUID = Path(..., description="Complaint ID"),
    payload: ResolutionUpdate = ...,
    uow: UnitOfWork = Depends(get_uow),
) -> ResolutionResponse:
    """
    Update existing resolution details for a complaint.
    """
    service = ComplaintService(uow)
    try:
        return service.update_resolution(
            complaint_id=complaint_id,
            request=payload,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.post(
    "/{complaint_id}/reopen",
    response_model=ResolutionResponse,
    summary="Reopen a resolved/closed complaint",
)
async def reopen_complaint(
    complaint_id: UUID = Path(..., description="Complaint ID"),
    payload: ReopenRequest = ...,
    uow: UnitOfWork = Depends(get_uow),
) -> ResolutionResponse:
    """
    Reopen a previously resolved or closed complaint.
    """
    service = ComplaintService(uow)
    try:
        return service.reopen_complaint(
            complaint_id=complaint_id,
            request=payload,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.post(
    "/{complaint_id}/close",
    response_model=ResolutionResponse,
    summary="Close a complaint",
)
async def close_complaint(
    complaint_id: UUID = Path(..., description="Complaint ID"),
    payload: CloseRequest = ...,
    uow: UnitOfWork = Depends(get_uow),
) -> ResolutionResponse:
    """
    Close a complaint after resolution is confirmed.
    """
    service = ComplaintService(uow)
    try:
        return service.close_complaint(
            complaint_id=complaint_id,
            request=payload,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)