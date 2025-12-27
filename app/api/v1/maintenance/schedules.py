"""
Maintenance Schedules API Endpoints
Handles preventive maintenance scheduling, execution tracking, and schedule management.
"""

from typing import Any, List, Optional
from datetime import date

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Path,
    Body,
    status,
)
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.maintenance.maintenance_schedule import (
    ScheduleCreate,
    ScheduleUpdate,
    PreventiveSchedule,
    ScheduleExecution,
    ScheduleExecutionCreate,
    UpcomingSchedule,
    ScheduleHistory,
)
from app.services.maintenance.maintenance_schedule_service import (
    MaintenanceScheduleService,
)

# Initialize router with prefix and tags
router = APIRouter(prefix="/schedules", tags=["maintenance:schedules"])


def get_schedule_service(
    db: Session = Depends(deps.get_db),
) -> MaintenanceScheduleService:
    """
    Dependency to get maintenance schedule service instance.
    
    Args:
        db: Database session dependency
        
    Returns:
        MaintenanceScheduleService: Service instance for schedule operations
    """
    return MaintenanceScheduleService(db=db)


@router.post(
    "",
    response_model=PreventiveSchedule,
    status_code=status.HTTP_201_CREATED,
    summary="Create preventive maintenance schedule",
    description="Create a new preventive maintenance schedule for recurring tasks",
    response_description="Created schedule details",
)
def create_schedule(
    payload: ScheduleCreate = Body(..., description="Schedule creation details"),
    admin=Depends(deps.get_admin_user),
    service: MaintenanceScheduleService = Depends(get_schedule_service),
) -> Any:
    """
    Create a preventive maintenance schedule.
    
    Preventive schedules automate recurring maintenance tasks like
    inspections, servicing, and routine checks.
    
    Args:
        payload: Schedule creation details including frequency and tasks
        admin: Authenticated admin user creating the schedule
        service: Maintenance schedule service instance
        
    Returns:
        PreventiveSchedule: Created schedule details
        
    Raises:
        HTTPException: If schedule creation fails or conflicts with existing schedule
    """
    try:
        return service.create_schedule(payload, creator_id=admin.id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create preventive maintenance schedule",
        )


@router.get(
    "",
    response_model=List[PreventiveSchedule],
    summary="List preventive maintenance schedules",
    description="Retrieve all preventive maintenance schedules for a hostel",
    response_description="List of active schedules",
)
def list_schedules(
    hostel_id: str = Query(..., description="Hostel ID to filter schedules"),
    active_only: bool = Query(
        True,
        description="Show only active schedules",
    ),
    category: Optional[str] = Query(
        None,
        description="Filter by maintenance category",
    ),
    admin=Depends(deps.get_admin_user),
    service: MaintenanceScheduleService = Depends(get_schedule_service),
) -> Any:
    """
    List all preventive maintenance schedules.
    
    Args:
        hostel_id: Hostel ID to filter schedules
        active_only: Whether to show only active schedules
        category: Optional category filter
        admin: Authenticated admin user
        service: Maintenance schedule service instance
        
    Returns:
        List[PreventiveSchedule]: List of schedules
        
    Raises:
        HTTPException: If retrieval fails
    """
    try:
        return service.list_schedules_for_hostel(
            hostel_id,
            active_only=active_only,
            category=category,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve maintenance schedules",
        )


@router.get(
    "/{schedule_id}",
    response_model=PreventiveSchedule,
    summary="Get schedule details",
    description="Retrieve detailed information about a specific schedule",
    response_description="Schedule details",
)
def get_schedule(
    schedule_id: str = Path(..., description="Unique identifier of the schedule"),
    admin=Depends(deps.get_admin_user),
    service: MaintenanceScheduleService = Depends(get_schedule_service),
) -> Any:
    """
    Get detailed information about a maintenance schedule.
    
    Args:
        schedule_id: Unique identifier of the schedule
        admin: Authenticated admin user
        service: Maintenance schedule service instance
        
    Returns:
        PreventiveSchedule: Schedule details
        
    Raises:
        HTTPException: If schedule not found
    """
    try:
        schedule = service.get_schedule(schedule_id)
        if not schedule:
            raise LookupError(f"Schedule with ID {schedule_id} not found")
        return schedule
    except LookupError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve schedule details",
        )


@router.put(
    "/{schedule_id}",
    response_model=PreventiveSchedule,
    summary="Update preventive schedule",
    description="Update details of an existing preventive maintenance schedule",
    response_description="Updated schedule details",
)
def update_schedule(
    schedule_id: str = Path(..., description="Unique identifier of the schedule"),
    payload: ScheduleUpdate = Body(..., description="Schedule update details"),
    admin=Depends(deps.get_admin_user),
    service: MaintenanceScheduleService = Depends(get_schedule_service),
) -> Any:
    """
    Update a preventive maintenance schedule.
    
    Allows modifying frequency, tasks, assignments, and other schedule parameters.
    
    Args:
        schedule_id: Unique identifier of the schedule
        payload: Update details
        admin: Authenticated admin user
        service: Maintenance schedule service instance
        
    Returns:
        PreventiveSchedule: Updated schedule details
        
    Raises:
        HTTPException: If update fails or schedule not found
    """
    try:
        return service.update_schedule(schedule_id, payload, actor_id=admin.id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except LookupError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update schedule",
        )


@router.delete(
    "/{schedule_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete/deactivate schedule",
    description="Deactivate a preventive maintenance schedule",
)
def deactivate_schedule(
    schedule_id: str = Path(..., description="Unique identifier of the schedule"),
    admin=Depends(deps.get_admin_user),
    service: MaintenanceScheduleService = Depends(get_schedule_service),
) -> None:
    """
    Deactivate a preventive maintenance schedule.
    
    Schedules are soft-deleted to maintain historical records.
    
    Args:
        schedule_id: Unique identifier of the schedule
        admin: Authenticated admin user
        service: Maintenance schedule service instance
        
    Raises:
        HTTPException: If deactivation fails or schedule not found
    """
    try:
        service.deactivate_schedule(schedule_id, actor_id=admin.id)
    except LookupError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to deactivate schedule",
        )


@router.post(
    "/{schedule_id}/execute",
    response_model=ScheduleExecution,
    status_code=status.HTTP_201_CREATED,
    summary="Record schedule execution",
    description="Record the execution of a scheduled preventive maintenance task",
    response_description="Execution record details",
)
def record_execution(
    schedule_id: str = Path(..., description="Unique identifier of the schedule"),
    payload: ScheduleExecutionCreate = Body(..., description="Execution details"),
    supervisor=Depends(deps.get_supervisor_user),
    service: MaintenanceScheduleService = Depends(get_schedule_service),
) -> Any:
    """
    Record execution of a scheduled preventive maintenance task.
    
    Captures details of completed preventive maintenance including
    findings, actions taken, and next scheduled date.
    
    Args:
        schedule_id: Unique identifier of the schedule
        payload: Execution details and findings
        supervisor: Authenticated supervisor recording execution
        service: Maintenance schedule service instance
        
    Returns:
        ScheduleExecution: Execution record
        
    Raises:
        HTTPException: If recording fails or schedule not found
    """
    try:
        return service.record_execution(schedule_id, payload, actor_id=supervisor.id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except LookupError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to record schedule execution",
        )


@router.get(
    "/upcoming",
    response_model=List[UpcomingSchedule],
    summary="Get upcoming scheduled tasks",
    description="Retrieve preventive maintenance tasks scheduled for the upcoming period",
    response_description="List of upcoming scheduled tasks",
)
def get_upcoming_schedules(
    hostel_id: str = Query(..., description="Hostel ID to filter schedules"),
    days_ahead: int = Query(
        30,
        ge=1,
        le=365,
        description="Number of days to look ahead",
    ),
    supervisor=Depends(deps.get_supervisor_user),
    service: MaintenanceScheduleService = Depends(get_schedule_service),
) -> Any:
    """
    Get upcoming scheduled preventive maintenance tasks.
    
    Helps plan and prepare for upcoming maintenance activities.
    
    Args:
        hostel_id: Hostel ID to filter schedules
        days_ahead: Number of days to look ahead (1-365)
        supervisor: Authenticated supervisor user
        service: Maintenance schedule service instance
        
    Returns:
        List[UpcomingSchedule]: Upcoming scheduled tasks
        
    Raises:
        HTTPException: If retrieval fails
    """
    try:
        return service.get_upcoming_schedules(
            hostel_id=hostel_id,
            days_ahead=days_ahead,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve upcoming schedules",
        )


@router.get(
    "/overdue",
    response_model=List[UpcomingSchedule],
    summary="Get overdue scheduled tasks",
    description="Retrieve preventive maintenance tasks that are past their scheduled date",
    response_description="List of overdue scheduled tasks",
)
def get_overdue_schedules(
    hostel_id: str = Query(..., description="Hostel ID to filter schedules"),
    supervisor=Depends(deps.get_supervisor_user),
    service: MaintenanceScheduleService = Depends(get_schedule_service),
) -> Any:
    """
    Get overdue scheduled preventive maintenance tasks.
    
    Identifies tasks that have passed their scheduled execution date.
    
    Args:
        hostel_id: Hostel ID to filter schedules
        supervisor: Authenticated supervisor user
        service: Maintenance schedule service instance
        
    Returns:
        List[UpcomingSchedule]: Overdue scheduled tasks
        
    Raises:
        HTTPException: If retrieval fails
    """
    try:
        return service.get_overdue_schedules(hostel_id=hostel_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve overdue schedules",
        )


@router.get(
    "/{schedule_id}/history",
    response_model=List[ScheduleHistory],
    summary="Get schedule execution history",
    description="Retrieve execution history for a preventive maintenance schedule",
    response_description="Chronological execution history",
)
def get_schedule_history(
    schedule_id: str = Path(..., description="Unique identifier of the schedule"),
    start_date: Optional[date] = Query(
        None,
        description="Filter history from this date",
    ),
    end_date: Optional[date] = Query(
        None,
        description="Filter history up to this date",
    ),
    supervisor=Depends(deps.get_supervisor_user),
    service: MaintenanceScheduleService = Depends(get_schedule_service),
) -> Any:
    """
    Get execution history for a preventive maintenance schedule.
    
    Shows all past executions with details for trend analysis and compliance tracking.
    
    Args:
        schedule_id: Unique identifier of the schedule
        start_date: Optional start date filter
        end_date: Optional end date filter
        supervisor: Authenticated supervisor user
        service: Maintenance schedule service instance
        
    Returns:
        List[ScheduleHistory]: Execution history records
        
    Raises:
        HTTPException: If retrieval fails or schedule not found
    """
    try:
        return service.get_schedule_history(
            schedule_id,
            start_date=start_date,
            end_date=end_date,
        )
    except LookupError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve schedule history",
        )


@router.post(
    "/{schedule_id}/skip",
    response_model=PreventiveSchedule,
    summary="Skip scheduled occurrence",
    description="Skip the next scheduled occurrence with a reason",
    response_description="Updated schedule with next occurrence",
)
def skip_occurrence(
    schedule_id: str = Path(..., description="Unique identifier of the schedule"),
    reason: str = Body(..., embed=True, description="Reason for skipping"),
    admin=Depends(deps.get_admin_user),
    service: MaintenanceScheduleService = Depends(get_schedule_service),
) -> Any:
    """
    Skip the next scheduled occurrence.
    
    Used when scheduled maintenance is not needed or must be postponed.
    Reason is recorded for audit purposes.
    
    Args:
        schedule_id: Unique identifier of the schedule
        reason: Detailed reason for skipping
        admin: Authenticated admin user
        service: Maintenance schedule service instance
        
    Returns:
        PreventiveSchedule: Updated schedule with next occurrence
        
    Raises:
        HTTPException: If operation fails or schedule not found
    """
    try:
        return service.skip_occurrence(
            schedule_id,
            reason=reason,
            actor_id=admin.id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except LookupError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to skip occurrence",
        )