from typing import Any, Optional
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, Query, status, HTTPException, BackgroundTasks, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api import deps
from app.core.exceptions import ValidationError, NotFoundError, PermissionError
from app.core.logging import get_logger
from app.core.rate_limiting import rate_limiter
from app.core.security import sanitize_device_id
from app.schemas.attendance import CheckInResponse, CheckInStatus
from app.services.attendance.check_in_service import CheckInService

logger = get_logger(__name__)
router = APIRouter(prefix="/attendance/check-in", tags=["attendance:check-in"])


def get_checkin_service(db: Session = Depends(deps.get_db)) -> CheckInService:
    """
    Dependency to provide CheckInService instance with optimized configuration.
    
    Args:
        db: Database session with connection pooling
        
    Returns:
        CheckInService instance configured for high-performance operations
    """
    return CheckInService(db=db)


@router.post(
    "",
    response_model=CheckInResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Student check-in operation",
    description="Register student arrival with automatic attendance tracking, "
                "device verification, and real-time status updates.",
    responses={
        201: {"description": "Check-in recorded successfully"},
        400: {"description": "Invalid check-in parameters or duplicate operation"},
        403: {"description": "Check-in not permitted for this student"},
        429: {"description": "Too many check-in attempts"},
    }
)
@rate_limiter.limit("10/minute")  # Prevent rapid check-in/out abuse
async def check_in(
    request: Request,  # Added for rate limiting
    background_tasks: BackgroundTasks,
    _student=Depends(deps.get_student_user),
    service: CheckInService = Depends(get_checkin_service),
    device_id: Optional[str] = Query(
        None, 
        description="Unique device identifier for tracking and security",
        max_length=100
    ),
    location: Optional[str] = Query(
        None,
        description="Check-in location identifier",
        max_length=50
    ),
) -> Any:
    """
    Register student arrival with comprehensive tracking and validation.

    **Check-in Features:**
    - Automatic attendance record creation
    - Real-time status updates
    - Device and location tracking
    - Duplicate check-in prevention
    - Time zone aware timestamps

    **Security Measures:**
    - Rate limiting to prevent abuse
    - Device fingerprinting for fraud detection
    - Location verification where applicable
    - Suspicious activity monitoring

    **Integration:**
    - Automatic attendance policy enforcement
    - Real-time dashboard updates
    - Parent/guardian notifications (if enabled)
    - Emergency contact updates

    **Access:** Student users only (self check-in)
    """
    try:
        # Sanitize and validate device ID
        sanitized_device_id = sanitize_device_id(device_id) if device_id else None
        
        logger.info(
            f"Student {_student.id} initiating check-in with device {sanitized_device_id}"
        )
        
        result = service.check_in(
            student_id=_student.id, 
            device_id=sanitized_device_id,
            location=location
        )
        
        # Schedule background tasks for efficiency
        background_tasks.add_task(
            service.update_real_time_dashboards,
            _student.id,
            "check_in"
        )
        
        background_tasks.add_task(
            service.process_check_in_notifications,
            _student.id,
            result.check_in_time
        )
        
        logger.info(
            f"Check-in successful for student {_student.id} at {result.check_in_time}"
        )
        
        return result
        
    except ValidationError as e:
        logger.warning(f"Validation error in check-in: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        logger.warning(f"Permission denied for check-in: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Error in check-in operation: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post(
    "/out",
    response_model=CheckInResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Student check-out operation",
    description="Register student departure with session completion, duration tracking, "
                "and automated reporting updates.",
    responses={
        201: {"description": "Check-out recorded successfully"},
        400: {"description": "Invalid check-out parameters or no active check-in"},
        403: {"description": "Check-out not permitted for this student"},
        429: {"description": "Too many check-out attempts"},
    }
)
@rate_limiter.limit("10/minute")  # Match check-in rate limiting
async def check_out(
    request: Request,  # Added for rate limiting
    background_tasks: BackgroundTasks,
    _student=Depends(deps.get_student_user),
    service: CheckInService = Depends(get_checkin_service),
    device_id: Optional[str] = Query(
        None, 
        description="Device identifier for consistency verification",
        max_length=100
    ),
    location: Optional[str] = Query(
        None,
        description="Check-out location identifier",
        max_length=50
    ),
) -> Any:
    """
    Register student departure with comprehensive session tracking.

    **Check-out Features:**
    - Automatic session duration calculation
    - Attendance record completion
    - Real-time status updates
    - Device consistency verification
    - Late departure detection

    **Session Management:**
    - Calculate total presence duration
    - Validate against minimum stay requirements
    - Generate session summary reports
    - Update attendance compliance status

    **Automated Processing:**
    - Dashboard and report updates
    - Parent/guardian notifications
    - Policy violation checking
    - Emergency contact status updates

    **Access:** Student users only (self check-out)
    """
    try:
        # Sanitize device ID for security
        sanitized_device_id = sanitize_device_id(device_id) if device_id else None
        
        logger.info(
            f"Student {_student.id} initiating check-out with device {sanitized_device_id}"
        )
        
        result = service.check_out(
            student_id=_student.id, 
            device_id=sanitized_device_id,
            location=location
        )
        
        # Schedule background processing
        background_tasks.add_task(
            service.update_real_time_dashboards,
            _student.id,
            "check_out"
        )
        
        background_tasks.add_task(
            service.process_check_out_notifications,
            _student.id,
            result.check_out_time,
            result.session_duration
        )
        
        background_tasks.add_task(
            service.validate_session_compliance,
            _student.id,
            result.session_duration
        )
        
        logger.info(
            f"Check-out successful for student {_student.id} at {result.check_out_time}, "
            f"session duration: {result.session_duration} minutes"
        )
        
        return result
        
    except ValidationError as e:
        logger.warning(f"Validation error in check-out: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        logger.warning(f"Permission denied for check-out: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Error in check-out operation: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get(
    "/status",
    response_model=CheckInStatus,
    summary="Get current check-in status with session details",
    description="Retrieve student's current check-in status, active session information, "
                "and historical session summary.",
    responses={
        200: {"description": "Status retrieved successfully"},
        404: {"description": "Student not found or no check-in history"},
        403: {"description": "Access denied"},
    }
)
async def get_check_in_status(
    request: Request,  # Added for consistency
    _student=Depends(deps.get_student_user),
    service: CheckInService = Depends(get_checkin_service),
    include_history: bool = Query(
        False, 
        description="Include recent check-in history in response"
    ),
    include_analytics: bool = Query(
        False,
        description="Include session analytics and patterns"
    ),
) -> Any:
    """
    Get comprehensive check-in status and session information.

    **Status Information:**
    - Current check-in state (checked in/out)
    - Active session details and duration
    - Last check-in/out timestamps
    - Device and location information

    **Optional History:**
    - Recent check-in/out sessions
    - Session duration patterns
    - Compliance tracking
    - Monthly activity summary

    **Optional Analytics:**
    - Average session durations
    - Peak activity times
    - Compliance rate calculations
    - Attendance pattern insights

    **Use Cases:**
    - Student self-service portals
    - Mobile app status displays
    - Parent/guardian dashboards
    - Administrative monitoring

    **Access:** Student users (self-status only), Admin/Supervisor (all students)
    """
    try:
        logger.info(f"Student {_student.id} requesting check-in status")
        
        result = service.get_check_in_status(
            student_id=_student.id,
            include_history=include_history,
            include_analytics=include_analytics
        )
        
        logger.info(f"Check-in status retrieved for student {_student.id}")
        return result
        
    except NotFoundError as e:
        logger.warning(f"Check-in status not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        logger.warning(f"Permission denied for status check: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Error retrieving check-in status: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get(
    "/session/current",
    summary="Get detailed current session information",
    description="Retrieve comprehensive information about the student's current active session",
    responses={
        200: {"description": "Current session information retrieved"},
        404: {"description": "No active session found"},
        403: {"description": "Access denied"},
    }
)
async def get_current_session(
    request: Request,  # Added for consistency
    _student=Depends(deps.get_student_user),
    service: CheckInService = Depends(get_checkin_service),
) -> Any:
    """
    Get detailed information about the student's current active session.

    **Session Details:**
    - Session start time and duration
    - Check-in device and location
    - Real-time session metrics
    - Expected check-out time
    - Session compliance status

    **Access:** Student users only (own session)
    """
    try:
        result = service.get_current_session(student_id=_student.id)
        return result
        
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail="No active session found")
    except Exception as e:
        logger.error(f"Error retrieving current session: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post(
    "/emergency-checkout",
    summary="Emergency check-out for special circumstances",
    description="Perform emergency check-out with special handling and notifications",
    responses={
        201: {"description": "Emergency check-out completed"},
        400: {"description": "Invalid emergency check-out"},
        403: {"description": "Access denied"},
    }
)
@rate_limiter.limit("5/minute")  # More restrictive rate limit for emergency operations
async def emergency_checkout(
    request: Request,  # Added for rate limiting
    background_tasks: BackgroundTasks,
    _student=Depends(deps.get_student_user),
    service: CheckInService = Depends(get_checkin_service),
    reason: str = Query(..., description="Emergency reason", max_length=200),
    contact_emergency: bool = Query(
        True, 
        description="Whether to contact emergency contacts"
    ),
) -> Any:
    """
    Perform emergency check-out with special handling procedures.

    **Emergency Features:**
    - Immediate check-out processing
    - Emergency contact notifications
    - Special audit trail markers
    - Administrative alerts
    - Compliance override capabilities

    **Use Cases:**
    - Medical emergencies
    - Family emergencies
    - Safety concerns
    - Technical system issues

    **Access:** Student users only
    """
    try:
        logger.warning(
            f"Emergency check-out initiated by student {_student.id}: {reason}"
        )
        
        result = service.emergency_checkout(
            student_id=_student.id,
            reason=reason
        )
        
        if contact_emergency:
            background_tasks.add_task(
                service.notify_emergency_contacts,
                _student.id,
                reason,
                result.check_out_time
            )
        
        background_tasks.add_task(
            service.alert_administrators,
            _student.id,
            "emergency_checkout",
            reason
        )
        
        logger.warning(f"Emergency check-out completed for student {_student.id}")
        return result
        
    except Exception as e:
        logger.error(f"Error in emergency check-out: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get(
    "/history",
    summary="Get check-in history for student",
    description="Retrieve paginated check-in history with session analytics",
    responses={
        200: {"description": "History retrieved successfully"},
        403: {"description": "Access denied"},
    }
)
@rate_limiter.limit("30/minute")  # Rate limit for history queries
async def get_check_in_history(
    request: Request,  # Added for rate limiting
    _student=Depends(deps.get_student_user),
    service: CheckInService = Depends(get_checkin_service),
    pagination=Depends(deps.get_pagination_params),
    days: int = Query(30, ge=1, le=365, description="Number of days of history"),
    include_analytics: bool = Query(False, description="Include session analytics"),
) -> Any:
    """
    Get paginated check-in history with optional analytics.

    **History Features:**
    - Chronological session records
    - Session duration calculations
    - Compliance tracking
    - Device and location tracking

    **Analytics (Optional):**
    - Average session durations
    - Peak activity patterns
    - Compliance percentage
    - Trend analysis

    **Access:** Student users (own history)
    """
    try:
        result = service.get_check_in_history(
            student_id=_student.id,
            days=days,
            include_analytics=include_analytics,
            pagination=pagination
        )
        return result
        
    except Exception as e:
        logger.error(f"Error retrieving check-in history: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")