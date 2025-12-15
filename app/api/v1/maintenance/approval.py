from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, status

from app.api.deps import get_uow
from app.core.exceptions import ServiceError, NotFoundError, ValidationError, ConflictError
from app.schemas.maintenance.maintenance_approval import (
    ApprovalRequest,
    ApprovalResponse,
    ThresholdConfig,
    ApprovalWorkflow,
    RejectionRequest,
)
from app.services.common.unit_of_work import UnitOfWork
from app.services.maintenance import MaintenanceApprovalService

router = APIRouter(prefix="/approval")


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


@router.get(
    "/hostels/{hostel_id}/thresholds",
    response_model=ThresholdConfig,
    summary="Get maintenance approval thresholds for a hostel",
)
async def get_threshold_config(
    hostel_id: UUID = Path(..., description="Hostel ID"),
    uow: UnitOfWork = Depends(get_uow),
) -> ThresholdConfig:
    """
    Fetch cost approval thresholds per hostel (e.g. supervisor/admin limits).
    """
    service = MaintenanceApprovalService(uow)
    try:
        return service.get_threshold_config(hostel_id=hostel_id)
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.put(
    "/hostels/{hostel_id}/thresholds",
    response_model=ThresholdConfig,
    summary="Update maintenance approval thresholds for a hostel",
)
async def update_threshold_config(
    hostel_id: UUID = Path(..., description="Hostel ID"),
    payload: ThresholdConfig = ...,
    uow: UnitOfWork = Depends(get_uow),
) -> ThresholdConfig:
    """
    Update cost approval thresholds for a hostel.
    """
    service = MaintenanceApprovalService(uow)
    try:
        return service.update_threshold_config(
            hostel_id=hostel_id,
            config=payload,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.post(
    "/{maintenance_id}",
    response_model=ApprovalResponse,
    summary="Approve a maintenance request",
)
async def approve_maintenance(
    maintenance_id: UUID = Path(..., description="Maintenance request ID"),
    payload: ApprovalRequest = ...,
    uow: UnitOfWork = Depends(get_uow),
) -> ApprovalResponse:
    """
    Approve a maintenance request, recording cost approval workflow and flags.
    """
    service = MaintenanceApprovalService(uow)
    try:
        return service.approve_maintenance(
            maintenance_id=maintenance_id,
            request=payload,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.post(
    "/{maintenance_id}/reject",
    response_model=ApprovalResponse,
    summary="Reject a maintenance request approval",
)
async def reject_maintenance_approval(
    maintenance_id: UUID = Path(..., description="Maintenance request ID"),
    payload: RejectionRequest = ...,
    uow: UnitOfWork = Depends(get_uow),
) -> ApprovalResponse:
    """
    Reject or decline approval for a maintenance request.
    """
    service = MaintenanceApprovalService(uow)
    try:
        return service.reject_maintenance(
            maintenance_id=maintenance_id,
            request=payload,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.get(
    "/{maintenance_id}/workflow",
    response_model=ApprovalWorkflow,
    summary="Get approval workflow for a maintenance request",
)
async def get_approval_workflow(
    maintenance_id: UUID = Path(..., description="Maintenance request ID"),
    uow: UnitOfWork = Depends(get_uow),
) -> ApprovalWorkflow:
    """
    Retrieve the approval workflow state for a maintenance request.
    """
    service = MaintenanceApprovalService(uow)
    try:
        return service.get_workflow(maintenance_id=maintenance_id)
    except ServiceError as exc:
        raise _map_service_error(exc)