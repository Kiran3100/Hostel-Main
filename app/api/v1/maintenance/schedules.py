from typing import Any, List

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.maintenance.maintenance_schedule import (
    ScheduleCreate,
    ScheduleUpdate,
    PreventiveSchedule,
    ScheduleExecution,
)
from app.services.maintenance.maintenance_schedule_service import MaintenanceScheduleService

router = APIRouter(prefix="/schedules", tags=["maintenance:schedules"])


def get_schedule_service(db: Session = Depends(deps.get_db)) -> MaintenanceScheduleService:
    return MaintenanceScheduleService(db=db)


@router.post(
    "",
    response_model=PreventiveSchedule,
    status_code=status.HTTP_201_CREATED,
    summary="Create preventive schedule",
)
def create_schedule(
    payload: ScheduleCreate,
    _admin=Depends(deps.get_admin_user),
    service: MaintenanceScheduleService = Depends(get_schedule_service),
) -> Any:
    return service.create_schedule(payload, creator_id=_admin.id)


@router.get(
    "",
    response_model=List[PreventiveSchedule],
    summary="List schedules",
)
def list_schedules(
    hostel_id: str = Query(...),
    _admin=Depends(deps.get_admin_user),
    service: MaintenanceScheduleService = Depends(get_schedule_service),
) -> Any:
    return service.list_schedules_for_hostel(hostel_id)


@router.put(
    "/{schedule_id}",
    response_model=PreventiveSchedule,
    summary="Update schedule",
)
def update_schedule(
    schedule_id: str,
    payload: ScheduleUpdate,
    _admin=Depends(deps.get_admin_user),
    service: MaintenanceScheduleService = Depends(get_schedule_service),
) -> Any:
    return service.update_schedule(schedule_id, payload, actor_id=_admin.id)


@router.post(
    "/{schedule_id}/execute",
    response_model=ScheduleExecution,
    summary="Record schedule execution",
)
def record_execution(
    schedule_id: str,
    payload: Any,  # Execution details schema
    _supervisor=Depends(deps.get_supervisor_user),
    service: MaintenanceScheduleService = Depends(get_schedule_service),
) -> Any:
    return service.record_execution(schedule_id, payload, actor_id=_supervisor.id)