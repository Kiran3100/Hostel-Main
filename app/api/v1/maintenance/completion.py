from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, status

from app.api.deps import get_uow
from app.core.exceptions import ServiceError, NotFoundError, ValidationError, ConflictError
from app.schemas.maintenance.maintenance_completion import (
    CompletionRequest,
    CompletionResponse,
    CompletionCertificate,
)
from app.services.common.unit_of_work import UnitOfWork
from app.services.maintenance import MaintenanceCompletionService

router = APIRouter(prefix="/completion")


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
    "/{maintenance_id}",
    response_model=CompletionResponse,
    summary="Mark a maintenance request as completed",
)
async def complete_maintenance(
    maintenance_id: UUID = Path(..., description="Maintenance request ID"),
    payload: CompletionRequest = ...,
    uow: UnitOfWork = Depends(get_uow),
) -> CompletionResponse:
    """
    Mark a maintenance request as completed, recording work done, materials, costs,
    and quality checks.
    """
    service = MaintenanceCompletionService(uow)
    try:
        return service.complete_maintenance(
            maintenance_id=maintenance_id,
            request=payload,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.get(
    "/{maintenance_id}",
    response_model=CompletionResponse,
    summary="Get completion details for a maintenance request",
)
async def get_completion_details(
    maintenance_id: UUID = Path(..., description="Maintenance request ID"),
    uow: UnitOfWork = Depends(get_uow),
) -> CompletionResponse:
    """
    Retrieve completion details for a maintenance request.
    """
    service = MaintenanceCompletionService(uow)
    try:
        return service.get_completion(maintenance_id=maintenance_id)
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.get(
    "/{maintenance_id}/certificate",
    response_model=CompletionCertificate,
    summary="Get completion certificate for a maintenance request",
)
async def get_completion_certificate(
    maintenance_id: UUID = Path(..., description="Maintenance request ID"),
    uow: UnitOfWork = Depends(get_uow),
) -> CompletionCertificate:
    """
    Return a completion certificate payload (for downloads/printing).
    """
    service = MaintenanceCompletionService(uow)
    try:
        return service.get_completion_certificate(maintenance_id=maintenance_id)
    except ServiceError as exc:
        raise _map_service_error(exc)