"""
Enhanced announcement scheduling with advanced timing and recurrence capabilities.
"""
from typing import Any, Optional, Dict
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status, HTTPException
from sqlalchemy.orm import Session

from app.api import deps
from app.core.logging import get_logger, log_endpoint_call
from app.core.security import require_permissions
from app.schemas.announcement import (
    ScheduleRequest,
    ScheduleConfig,
    RecurringAnnouncement,
    ScheduleUpdate,
    ScheduleCancel,
    PublishNow,
    ScheduledAnnouncementItem,
    ScheduledAnnouncementsList,
)
from app.services.announcement.announcement_scheduling_service import AnnouncementSchedulingService
from .deps import get_scheduling_service

logger = get_logger(__name__)
router = APIRouter(
    prefix="/announcements/scheduling",
    tags=["announcements:scheduling"],
    responses={
        404: {"description": "Schedule not found"},
        409: {"description": "Scheduling conflict or invalid state"},
        422: {"description": "Invalid scheduling parameters"}
    }
)


# ---------------------------------------------------------------------------
# Schedule Creation and Management
# ---------------------------------------------------------------------------

@router.post(
    "/{announcement_id}",
    response_model=ScheduleConfig,
    status_code=status.HTTP_201_CREATED,
    summary="Schedule announcement for publication",
    description="""
    Create a publication schedule for an approved announcement.
    
    **Scheduling options:**
    - Immediate: Publish as soon as possible
    - Specific date/time: Schedule for exact moment
    - Conditional: Publish when criteria are met
    - Time zone aware: Supports multiple time zones
    
    **Validation checks:**
    - Announcement must be approved
    - Schedule time must be in future
    - No conflicts with existing schedules
    - Target audience availability verification
    
    **Automatic features:**
    - Pre-publication validation
    - Delivery optimization timing
    - Failure retry mechanisms
    - Success confirmation tracking
    """,
    response_description="Schedule configuration with timing and status details"
)
@require_permissions(["announcement:schedule"])
@log_endpoint_call
async def schedule_announcement(
    announcement_id: UUID,
    payload: ScheduleRequest,
    current_user=Depends(deps.get_current_user_with_roles),
    service: AnnouncementSchedulingService = Depends(get_scheduling_service),
) -> ScheduleConfig:
    """
    Create announcement schedule with comprehensive validation and conflict detection.
    """
    try:
        logger.info(
            f"Creating schedule for announcement {announcement_id}",
            extra={
                "actor_id": current_user.id,
                "announcement_id": str(announcement_id),
                "scheduled_for": getattr(payload, 'scheduled_for', None),
                "timezone": getattr(payload, 'timezone', None)
            }
        )
        
        result = await service.schedule(
            announcement_id=str(announcement_id),
            payload=payload,
            actor_id=current_user.id,
        )
        
        logger.info(
            f"Successfully created schedule",
            extra={
                "actor_id": current_user.id,
                "announcement_id": str(announcement_id),
                "schedule_id": result.id,
                "execution_time": result.scheduled_for
            }
        )
        
        return result
        
    except ValueError as e:
        logger.warning(f"Invalid schedule parameters: {str(e)}", extra={"announcement_id": str(announcement_id)})
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except PermissionError as e:
        logger.warning(f"Permission denied for scheduling", extra={"actor_id": current_user.id, "announcement_id": str(announcement_id)})
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient scheduling permissions")
    except Exception as e:
        logger.error(f"Schedule creation failed: {str(e)}", extra={"announcement_id": str(announcement_id)})
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Schedule creation failed")


@router.post(
    "/{announcement_id}/recurring",
    response_model=ScheduleConfig,
    summary="Create recurring announcement schedule",
    description="""
    Set up recurring publication schedule for template announcements.
    
    **Recurrence patterns:**
    - Daily: Every N days at specific time
    - Weekly: Specific days of week
    - Monthly: Specific dates or day patterns
    - Custom: Complex patterns using cron expressions
    
    **Smart features:**
    - Holiday awareness and skipping
    - Business day only options
    - Automatic content updates
    - Audience availability optimization
    
    **Management capabilities:**
    - Individual occurrence editing
    - Bulk pattern modifications
    - Temporary suspensions
    - Performance analytics tracking
    """,
    responses={
        201: {"description": "Recurring schedule created successfully"},
        409: {"description": "Conflicting schedule or invalid recurrence pattern"}
    }
)
@require_permissions(["announcement:schedule_recurring"])
@log_endpoint_call
async def create_recurring_schedule(
    announcement_id: UUID,
    payload: RecurringAnnouncement,
    current_user=Depends(deps.get_current_user_with_roles),
    service: AnnouncementSchedulingService = Depends(get_scheduling_service),
) -> ScheduleConfig:
    """
    Create sophisticated recurring schedule with pattern validation and conflict detection.
    """
    try:
        logger.info(
            f"Creating recurring schedule for announcement {announcement_id}",
            extra={
                "actor_id": current_user.id,
                "announcement_id": str(announcement_id),
                "pattern": getattr(payload, 'recurrence_pattern', None),
                "start_date": getattr(payload, 'start_date', None)
            }
        )
        
        result = await service.create_recurring(
            announcement_id=str(announcement_id),
            payload=payload,
            actor_id=current_user.id,
        )
        
        logger.info(
            f"Successfully created recurring schedule",
            extra={
                "actor_id": current_user.id,
                "announcement_id": str(announcement_id),
                "schedule_id": result.id,
                "next_execution": result.next_execution_time
            }
        )
        
        return result
        
    except ValueError as e:
        logger.warning(f"Invalid recurrence pattern: {str(e)}", extra={"announcement_id": str(announcement_id)})
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception as e:
        logger.error(f"Recurring schedule creation failed: {str(e)}", extra={"announcement_id": str(announcement_id)})
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Recurring schedule creation failed")


# ---------------------------------------------------------------------------
# Schedule Modifications
# ---------------------------------------------------------------------------

@router.put(
    "/schedule/{schedule_id}",
    response_model=ScheduleConfig,
    summary="Update existing schedule",
    description="""
    Modify an existing publication schedule with safety checks.
    
    **Updateable properties:**
    - Publication date/time
    - Time zone settings
    - Delivery preferences
    - Retry configuration
    - Notification settings
    
    **Safety restrictions:**
    - Cannot modify schedules within 1 hour of execution
    - Published schedules have limited modification options
    - Recurring schedules require special handling
    
    **Automatic adjustments:**
    - Conflict resolution
    - Optimal timing suggestions
    - Cascade updates for recurring schedules
    """,
    responses={
        200: {"description": "Schedule updated successfully"},
        409: {"description": "Update conflict or timing restriction"},
        423: {"description": "Schedule locked for imminent execution"}
    }
)
@require_permissions(["announcement:modify_schedule"])
@log_endpoint_call
async def update_schedule(
    schedule_id: UUID,
    payload: ScheduleUpdate,
    current_user=Depends(deps.get_current_user_with_roles),
    service: AnnouncementSchedulingService = Depends(get_scheduling_service),
) -> ScheduleConfig:
    """
    Update schedule with comprehensive validation and conflict resolution.
    """
    try:
        logger.info(
            f"Updating schedule {schedule_id}",
            extra={
                "actor_id": current_user.id,
                "schedule_id": str(schedule_id),
                "new_schedule_time": getattr(payload, 'scheduled_for', None)
            }
        )
        
        result = await service.update_schedule(
            schedule_id=str(schedule_id),
            payload=payload,
            actor_id=current_user.id,
        )
        
        logger.info(
            f"Successfully updated schedule {schedule_id}",
            extra={
                "actor_id": current_user.id,
                "schedule_id": str(schedule_id),
                "new_execution_time": result.scheduled_for
            }
        )
        
        return result
        
    except ValueError as e:
        logger.warning(f"Invalid schedule update: {str(e)}", extra={"schedule_id": str(schedule_id)})
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except PermissionError as e:
        logger.warning(f"Permission denied for schedule update", extra={"actor_id": current_user.id, "schedule_id": str(schedule_id)})
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    except Exception as e:
        logger.error(f"Schedule update failed: {str(e)}", extra={"schedule_id": str(schedule_id)})
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Schedule update failed")


# ---------------------------------------------------------------------------
# Schedule Control Actions
# ---------------------------------------------------------------------------

@router.post(
    "/schedule/{schedule_id}/cancel",
    status_code=status.HTTP_200_OK,
    summary="Cancel scheduled publication",
    description="""
    Cancel a pending scheduled publication with reason tracking.
    
    **Cancellation effects:**
    - Removes from execution queue
    - Notifies relevant stakeholders
    - Preserves audit trail
    - Returns announcement to previous state
    
    **Cancellation restrictions:**
    - Cannot cancel schedules in progress
    - Some schedules may have cooling-off periods
    - Recurring schedules require special handling
    
    **Recovery options:**
    - Schedule can be recreated
    - Alternative timing suggestions provided
    - Automatic rescheduling available
    """,
    responses={
        200: {"description": "Schedule cancelled successfully"},
        409: {"description": "Cannot cancel schedule in current state"},
        423: {"description": "Schedule locked for execution"}
    }
)
@require_permissions(["announcement:cancel_schedule"])
@log_endpoint_call
async def cancel_schedule(
    schedule_id: UUID,
    payload: ScheduleCancel,
    current_user=Depends(deps.get_current_user_with_roles),
    service: AnnouncementSchedulingService = Depends(get_scheduling_service),
) -> Dict[str, str]:
    """
    Cancel scheduled publication with state validation and audit logging.
    """
    try:
        logger.warning(
            f"Cancelling schedule {schedule_id}",
            extra={
                "actor_id": current_user.id,
                "schedule_id": str(schedule_id),
                "reason": getattr(payload, 'reason', 'Not specified')
            }
        )
        
        await service.cancel(
            schedule_id=str(schedule_id),
            payload=payload,
            actor_id=current_user.id,
        )
        
        logger.warning(
            f"Successfully cancelled schedule {schedule_id}",
            extra={"actor_id": current_user.id, "schedule_id": str(schedule_id)}
        )
        
        return {"detail": "Schedule cancelled successfully"}
        
    except ValueError as e:
        logger.warning(f"Invalid cancellation request: {str(e)}", extra={"schedule_id": str(schedule_id)})
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except Exception as e:
        logger.error(f"Schedule cancellation failed: {str(e)}", extra={"schedule_id": str(schedule_id)})
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Cancellation failed")


@router.post(
    "/{announcement_id}/publish-now",
    response_model=ScheduleConfig,
    summary="Override schedule and publish now",
    description="""
    Override existing schedule and publish announcement immediately.
    
    **Emergency publication:**
    - Bypasses normal scheduling queue
    - Validates announcement readiness
    - Sends priority notifications
    - Creates expedited delivery
    
    **Override conditions:**
    - Urgent announcements only
    - Special admin permissions required
    - Content must pass safety checks
    - Target audience availability verified
    
    **Automatic actions:**
    - Cancels existing schedules
    - Updates audit trail with override reason
    - Activates high-priority delivery
    - Initiates immediate tracking
    """,
    responses={
        200: {"description": "Published immediately, schedule updated"},
        400: {"description": "Announcement not ready for publication"},
        409: {"description": "Override not permitted in current state"}
    }
)
@require_permissions(["announcement:emergency_publish"])
@log_endpoint_call
async def publish_now(
    announcement_id: UUID,
    payload: PublishNow,
    current_user=Depends(deps.get_current_user_with_roles),
    service: AnnouncementSchedulingService = Depends(get_scheduling_service),
) -> ScheduleConfig:
    """
    Emergency publication with schedule override and priority processing.
    """
    try:
        logger.warning(
            f"Emergency publish override for announcement {announcement_id}",
            extra={
                "actor_id": current_user.id,
                "announcement_id": str(announcement_id),
                "override_reason": getattr(payload, 'reason', 'Not specified')
            }
        )
        
        result = await service.publish_now(
            announcement_id=str(announcement_id),
            payload=payload,
            actor_id=current_user.id,
        )
        
        logger.warning(
            f"Successfully published announcement {announcement_id} immediately",
            extra={
                "actor_id": current_user.id,
                "announcement_id": str(announcement_id),
                "schedule_id": result.id
            }
        )
        
        return result
        
    except ValueError as e:
        logger.warning(f"Invalid emergency publish: {str(e)}", extra={"announcement_id": str(announcement_id)})
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except PermissionError as e:
        logger.warning(f"Permission denied for emergency publish", extra={"actor_id": current_user.id, "announcement_id": str(announcement_id)})
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Emergency publish not authorized")
    except Exception as e:
        logger.error(f"Emergency publish failed: {str(e)}", extra={"announcement_id": str(announcement_id)})
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Emergency publish failed")


# ---------------------------------------------------------------------------
# Schedule Information and Management
# ---------------------------------------------------------------------------

@router.get(
    "",
    response_model=ScheduledAnnouncementsList,
    summary="List scheduled announcements for hostel",
    description="""
    Retrieve all scheduled announcements with filtering and status information.
    
    **List includes:**
    - Pending scheduled publications
    - Recurring schedule instances
    - Execution status and history
    - Performance metrics summary
    
    **Filtering options:**
    - Date range constraints
    - Schedule status (pending, executing, completed, failed)
    - Announcement priority levels
    - Recurrence pattern types
    
    **Management insights:**
    - Queue load and timing distribution
    - Success/failure rate trends
    - Optimal timing recommendations
    - Capacity planning data
    """,
    response_description="Comprehensive list of scheduled announcements with status"
)
@log_endpoint_call
async def list_scheduled_announcements(
    hostel_id: Optional[UUID] = Query(None, description="Filter by hostel ID"),
    include_completed: bool = Query(False, description="Include completed schedules"),
    date_range_days: int = Query(30, description="Date range in days for schedule lookup", ge=1, le=365),
    current_user=Depends(deps.get_current_user_with_roles),
    service: AnnouncementSchedulingService = Depends(get_scheduling_service),
) -> ScheduledAnnouncementsList:
    """
    List scheduled announcements with comprehensive filtering and status information.
    """
    try:
        logger.debug(
            f"Listing scheduled announcements",
            extra={
                "actor_id": current_user.id,
                "hostel_id": str(hostel_id) if hostel_id else "all",
                "include_completed": include_completed,
                "date_range_days": date_range_days
            }
        )
        
        result = await service.list_scheduled(
            hostel_id=str(hostel_id) if hostel_id else None,
            actor_id=current_user.id,
            include_completed=include_completed,
            date_range_days=date_range_days,
        )
        
        logger.debug(
            f"Retrieved {len(result.items)} scheduled announcements",
            extra={"actor_id": current_user.id, "hostel_id": str(hostel_id) if hostel_id else "all"}
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Schedule listing failed: {str(e)}", extra={"actor_id": current_user.id})
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Schedule listing failed")