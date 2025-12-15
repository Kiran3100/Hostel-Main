from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, status

from app.api.deps import get_uow
from app.core.exceptions import ServiceError, NotFoundError, ValidationError, ConflictError
from app.schemas.maintenance.maintenance_schedule import (
    PreventiveSchedule,
    ScheduleCreate,
    ScheduleUpdate,
    ScheduleExecution,
    ChecklistResult,
    ScheduleHistory,
)
from app.services.common.unit_of_work import UnitOfWork
from app.services.maintenance import MaintenanceScheduleService

router = APIRouter(prefix="/schedule")


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
    "/hostels/{hostel_id}",
    response_model=List[PreventiveSchedule],
    summary="List preventive maintenance schedules for a hostel",
)
async def list_preventive_schedules(
    hostel_id: UUID = Path(..., description="Hostel ID"),
    uow: UnitOfWork = Depends(get_uow),
) -> List[PreventiveSchedule]:
    """
    List all preventive maintenance schedules configured for a hostel.
    """
    service = MaintenanceScheduleService(uow)
    try:
        return service.list_schedules(hostel_id=hostel_id)
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.post(
    "/hostels/{hostel_id}",
    response_model=PreventiveSchedule,
    status_code=status.HTTP_201_CREATED,
    summary="Create a preventive maintenance schedule",
)
async def create_preventive_schedule(
    hostel_id: UUID = Path(..., description="Hostel ID"),
    payload: ScheduleCreate = ...,
    uow: UnitOfWork = Depends(get_uow),
) -> PreventiveSchedule:
    """
    Create a new preventive maintenance schedule for a hostel.
    """
    service = MaintenanceScheduleService(uow)
    try:
        return service.create_schedule(
            hostel_id=hostel_id,
            request=payload,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.patch(
    "/{schedule_id}",
    response_model=PreventiveSchedule,
    summary="Update a preventive maintenance schedule",
)
async def update_preventive_schedule(
    schedule_id: UUID = Path(..., description="Schedule ID"),
    payload: ScheduleUpdate = ...,
    uow: UnitOfWork = Depends(get_uow),
) -> PreventiveSchedule:
    """
    Partially update a preventive maintenance schedule.
    """
    service = MaintenanceScheduleService(uow)
    try:
        return service.update_schedule(
            schedule_id=schedule_id,
            request=payload,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.post(
    "/{schedule_id}/execute",
    response_model=ChecklistResult,
    summary="Record schedule execution",
)
async def execute_schedule(
    schedule_id: UUID = Path(..., description="Schedule ID"),
    payload: ScheduleExecution = ...,
    uow: UnitOfWork = Depends(get_uow),
) -> ChecklistResult:
    """
    Record an execution instance for a preventive maintenance schedule.
    """
    service = MaintenanceScheduleService(uow)
    try:
        return service.record_execution(
            schedule_id=schedule_id,
            request=payload,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.get(
    "/{schedule_id}/history",
    response_model=ScheduleHistory,
    summary="Get schedule execution history",
)
async def get_schedule_history(
    schedule_id: UUID = Path(..., description="Schedule ID"),
    uow: UnitOfWork = Depends(get_uow),
) -> ScheduleHistory:
    """
    Retrieve execution history for a preventive maintenance schedule.
    """
    service = MaintenanceScheduleService(uow)
    try:
        return service.get_history(schedule_id=schedule_id)
    except ServiceError as exc:
        raise _map_service_error(exc)