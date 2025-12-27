from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.maintenance.maintenance_base import (
    MaintenanceCreate,
    MaintenanceUpdate,
    MaintenanceStatusUpdate,
)
from app.schemas.maintenance.maintenance_request import (
    MaintenanceRequest,
    EmergencyRequest,
)
from app.schemas.maintenance.maintenance_response import (
    MaintenanceDetail,
    MaintenanceListItem,
    MaintenanceResponse,
)
from app.services.maintenance.maintenance_request_service import MaintenanceRequestService

router = APIRouter(prefix="/requests", tags=["maintenance:requests"])


def get_request_service(db: Session = Depends(deps.get_db)) -> MaintenanceRequestService:
    return MaintenanceRequestService(db=db)


@router.post(
    "",
    response_model=MaintenanceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create maintenance request (resident)",
)
def create_request(
    payload: MaintenanceCreate,
    current_user=Depends(deps.get_current_user),
    service: MaintenanceRequestService = Depends(get_request_service),
) -> Any:
    return service.create_resident_request(payload, creator_id=current_user.id)


@router.post(
    "/supervisor",
    response_model=MaintenanceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create maintenance request (supervisor)",
)
def create_supervisor_request(
    payload: MaintenanceCreate,
    _supervisor=Depends(deps.get_supervisor_user),
    service: MaintenanceRequestService = Depends(get_request_service),
) -> Any:
    return service.create_supervisor_submission(payload, creator_id=_supervisor.id)


@router.post(
    "/emergency",
    response_model=MaintenanceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create emergency maintenance request",
)
def create_emergency_request(
    payload: EmergencyRequest,
    current_user=Depends(deps.get_current_user),
    service: MaintenanceRequestService = Depends(get_request_service),
) -> Any:
    return service.create_emergency_request(payload, creator_id=current_user.id)


@router.get(
    "/{request_id}",
    response_model=MaintenanceDetail,
    summary="Get request details",
)
def get_request(
    request_id: str,
    current_user=Depends(deps.get_current_user),
    service: MaintenanceRequestService = Depends(get_request_service),
) -> Any:
    request = service.get_request(request_id)
    if not request:
        raise HTTPException(status_code=404, detail="Request not found")
    return request


@router.get(
    "",
    response_model=List[MaintenanceListItem],
    summary="List maintenance requests",
)
def list_requests(
    hostel_id: str = Query(...),
    status_filter: Optional[str] = Query(None, alias="status"),
    pagination=Depends(deps.get_pagination_params),
    _admin=Depends(deps.get_admin_user),
    service: MaintenanceRequestService = Depends(get_request_service),
) -> Any:
    if status_filter:
        return service.get_requests_by_status(
            hostel_id=hostel_id, status=status_filter, pagination=pagination
        )
    return service.list_requests_for_hostel(hostel_id=hostel_id, pagination=pagination)


@router.patch(
    "/{request_id}/status",
    response_model=MaintenanceResponse,
    summary="Update request status",
)
def update_status(
    request_id: str,
    payload: MaintenanceStatusUpdate,
    _supervisor=Depends(deps.get_supervisor_user),
    service: MaintenanceRequestService = Depends(get_request_service),
) -> Any:
    # Logic to update status via service (often part of update or specialized method)
    # Using generic update here or a specific status change method if service exposes one.
    return service.update_status(request_id, payload, actor_id=_supervisor.id)