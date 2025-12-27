from typing import Any

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.maintenance.maintenance_approval import (
    ApprovalRequest,
    ApprovalResponse,
    RejectionRequest,
    ThresholdConfig,
)
from app.services.maintenance.maintenance_approval_service import MaintenanceApprovalService

router = APIRouter(prefix="/approvals", tags=["maintenance:approval"])


def get_approval_service(db: Session = Depends(deps.get_db)) -> MaintenanceApprovalService:
    return MaintenanceApprovalService(db=db)


@router.post(
    "/{request_id}/approve",
    response_model=ApprovalResponse,
    summary="Approve maintenance request",
)
def approve_request(
    request_id: str,
    _admin=Depends(deps.get_admin_user),
    service: MaintenanceApprovalService = Depends(get_approval_service),
) -> Any:
    return service.approve_maintenance_request(request_id, approver_id=_admin.id)


@router.post(
    "/{request_id}/reject",
    response_model=ApprovalResponse,
    summary="Reject maintenance request",
)
def reject_request(
    request_id: str,
    payload: RejectionRequest,
    _admin=Depends(deps.get_admin_user),
    service: MaintenanceApprovalService = Depends(get_approval_service),
) -> Any:
    return service.reject_maintenance_request(
        request_id, payload, rejector_id=_admin.id
    )


@router.get(
    "/thresholds",
    response_model=ThresholdConfig,
    summary="Get approval thresholds",
)
def get_threshold_config(
    hostel_id: str = Query(...),
    _admin=Depends(deps.get_admin_user),
    service: MaintenanceApprovalService = Depends(get_approval_service),
) -> Any:
    return service.get_threshold_config_for_hostel(hostel_id)


@router.put(
    "/thresholds",
    response_model=ThresholdConfig,
    summary="Update approval thresholds",
)
def update_threshold_config(
    payload: ThresholdConfig,
    _admin=Depends(deps.get_admin_user),
    service: MaintenanceApprovalService = Depends(get_approval_service),
) -> Any:
    return service.update_threshold_config(payload, actor_id=_admin.id)