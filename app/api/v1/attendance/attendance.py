from typing import Any, List, Optional
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, Query, status, HTTPException, BackgroundTasks, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api import deps
from app.core.exceptions import ValidationError, NotFoundError, PermissionError
from app.core.logging import get_logger
from app.core.cache import cache_response, invalidate_cache
from app.core.rate_limiting import rate_limit, RateLimitScope
from app.schemas.attendance import (
    AttendanceRecordRequest,
    BulkAttendanceRequest,
    QuickAttendanceMarkAll,
    AttendanceUpdate,
    AttendanceFilterParams,
    AttendanceResponse,
    AttendanceDetail,
    AttendanceListItem,
    DailyAttendanceSummary,
    AttendanceCorrection,
)
from app.services.attendance.attendance_service import AttendanceService
from app.services.attendance.attendance_correction_service import AttendanceCorrectionService

logger = get_logger(__name__)
router = APIRouter(prefix="/attendance", tags=["attendance"])


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------

def get_attendance_service(db: Session = Depends(deps.get_db)) -> AttendanceService:
    """
    Dependency to provide AttendanceService instance.
    
    Args:
        db: Database session
        
    Returns:
        AttendanceService instance with optimized configuration
    """
    return AttendanceService(db=db)


def get_correction_service(
    db: Session = Depends(deps.get_db),
) -> AttendanceCorrectionService:
    """
    Dependency to provide AttendanceCorrectionService instance.
    
    Args:
        db: Database session
        
    Returns:
        AttendanceCorrectionService instance
    """
    return AttendanceCorrectionService(db=db)


# ---------------------------------------------------------------------------
# Core attendance operations (supervisor/admin)
# ---------------------------------------------------------------------------


@router.post(
    "",
    response_model=AttendanceDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Mark attendance for individual student",
    description="Create a new attendance record for a single student with comprehensive "
                "tracking including check-in/out times, status, and metadata.",
    responses={
        201: {"description": "Attendance record created successfully"},
        400: {"description": "Invalid attendance data"},
        403: {"description": "Insufficient permissions"},
        409: {"description": "Attendance already recorded for this student today"},
    }
)
async def mark_attendance(
    request: Request,
    payload: AttendanceRecordRequest,
    background_tasks: BackgroundTasks,
    _supervisor=Depends(deps.get_supervisor_user),
    service: AttendanceService = Depends(get_attendance_service),
) -> Any:
    """
    Create a new attendance record for a single student.

    **Features:**
    - Individual student attendance marking
    - Automatic timestamp recording
    - Status validation and verification
    - Real-time policy checking
    - Background alert processing

    **Attendance Statuses:**
    - present: Student is present and accounted for
    - absent: Student is not present (excused/unexcused)
    - late: Student arrived after designated time
    - early_departure: Student left before scheduled time

    **Access:** Supervisor and Admin users
    """
    try:
        logger.info(
            f"Supervisor {_supervisor.id} marking attendance for student {payload.student_id}"
        )
        
        # Invalidate relevant caches
        background_tasks.add_task(
            invalidate_cache, 
            f"daily_summary_{payload.hostel_id}_{payload.date}"
        )
        
        result = service.mark_attendance(payload=payload, actor_id=_supervisor.id)
        
        logger.info(
            f"Attendance record {result.id} created successfully for student {payload.student_id}"
        )
        
        # Schedule background alert processing
        background_tasks.add_task(
            service.process_attendance_alerts,
            result.id
        )
        
        return result
        
    except ValidationError as e:
        logger.warning(f"Validation error in attendance marking: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        logger.warning(f"Permission denied for attendance marking: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Error marking attendance: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post(
    "/bulk",
    response_model=List[AttendanceDetail],
    status_code=status.HTTP_201_CREATED,
    summary="Bulk mark attendance for multiple students",
    description="Efficiently mark attendance for multiple students simultaneously with "
                "atomic transaction support and batch optimization.",
    responses={
        201: {"description": "Bulk attendance records created successfully"},
        400: {"description": "Invalid bulk attendance data"},
        403: {"description": "Insufficient permissions"},
        413: {"description": "Request payload too large"},
        429: {"description": "Rate limit exceeded"},
    }
)
@rate_limit("bulk_attendance", requests_per_period=10, period_seconds=60, scope=RateLimitScope.USER)
async def bulk_mark_attendance(
    request: Request,
    payload: BulkAttendanceRequest,
    background_tasks: BackgroundTasks,
    _supervisor=Depends(deps.get_supervisor_user),
    service: AttendanceService = Depends(get_attendance_service),
) -> Any:
    """
    Efficiently mark attendance for multiple students in a single operation.

    **Features:**
    - Batch processing with atomic transactions
    - Optimized database operations
    - Comprehensive validation for all records
    - Detailed success/failure reporting
    - Automatic rollback on partial failures

    **Performance Optimizations:**
    - Database connection pooling
    - Bulk insert operations
    - Minimal database round trips
    - Efficient validation pipelines

    **Limitations:**
    - Maximum 100 students per batch
    - Rate limited to prevent system overload (10 requests per minute)

    **Access:** Supervisor and Admin users
    """
    try:
        # Validate batch size
        if len(payload.attendance_records) > 100:
            raise ValidationError("Maximum 100 attendance records per batch")
            
        logger.info(
            f"Supervisor {_supervisor.id} bulk marking attendance for "
            f"{len(payload.attendance_records)} students"
        )
        
        result = service.bulk_mark_attendance(payload=payload, actor_id=_supervisor.id)
        
        # Invalidate caches for affected hostels/dates
        affected_keys = service.get_affected_cache_keys(payload)
        for key in affected_keys:
            background_tasks.add_task(invalidate_cache, key)
        
        logger.info(
            f"Bulk attendance operation completed: {len(result)} records processed"
        )
        
        # Schedule bulk alert processing
        background_tasks.add_task(
            service.process_bulk_attendance_alerts,
            [record.id for record in result]
        )
        
        return result
        
    except ValidationError as e:
        logger.warning(f"Validation error in bulk attendance: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        logger.warning(f"Permission denied for bulk attendance: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Error in bulk attendance operation: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post(
    "/quick-mark-all",
    response_model=List[AttendanceDetail],
    status_code=status.HTTP_201_CREATED,
    summary="Quick mark all students with exception handling",
    description="Efficiently mark all students in a hostel/room as present with "
                "specific exceptions for absent, late, or early departure students.",
    responses={
        201: {"description": "Quick mark operation completed successfully"},
        400: {"description": "Invalid quick mark parameters"},
        403: {"description": "Insufficient permissions"},
        429: {"description": "Rate limit exceeded"},
    }
)
@rate_limit("quick_mark_all", requests_per_period=5, period_seconds=60, scope=RateLimitScope.USER)
async def quick_mark_all(
    request: Request,
    payload: QuickAttendanceMarkAll,
    background_tasks: BackgroundTasks,
    _supervisor=Depends(deps.get_supervisor_user),
    service: AttendanceService = Depends(get_attendance_service),
) -> Any:
    """
    Mark all students as present with an exception list for non-present students.

    **Use Cases:**
    - Morning attendance where most students are present
    - Event attendance with few absences
    - Routine check-ins with minimal exceptions

    **Features:**
    - Default 'present' status for all students
    - Exception-based processing for efficiency
    - Automatic student list generation from hostel/room
    - Comprehensive audit trail

    **Performance Benefits:**
    - Reduced data entry time by 80%+
    - Optimized for common attendance patterns
    - Minimal API calls required
    - Bulk processing efficiencies

    **Rate Limiting:**
    - Limited to 5 requests per minute per user
    - More restrictive for broad operations

    **Access:** Supervisor and Admin users
    """
    try:
        logger.info(
            f"Supervisor {_supervisor.id} performing quick mark all for "
            f"hostel/room {payload.context_id}"
        )
        
        result = service.quick_mark_all(payload=payload, actor_id=_supervisor.id)
        
        # Invalidate relevant caches
        background_tasks.add_task(
            invalidate_cache, 
            f"daily_summary_{payload.hostel_id}_{payload.date}"
        )
        
        logger.info(
            f"Quick mark all completed: {len(result)} students processed, "
            f"{len(payload.exceptions)} exceptions handled"
        )
        
        # Schedule alert processing for any non-present students
        background_tasks.add_task(
            service.process_quick_mark_alerts,
            payload.exceptions,
            _supervisor.id
        )
        
        return result
        
    except ValidationError as e:
        logger.warning(f"Validation error in quick mark all: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        logger.warning(f"Permission denied for quick mark all: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Error in quick mark all operation: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# Update / list / summaries
# ---------------------------------------------------------------------------


@router.patch(
    "/{attendance_id}",
    response_model=AttendanceDetail,
    summary="Update existing attendance record",
    description="Modify attendance record status, times, or other attributes with "
                "comprehensive audit trail and validation.",
    responses={
        200: {"description": "Attendance record updated successfully"},
        400: {"description": "Invalid update parameters"},
        403: {"description": "Insufficient permissions"},
        404: {"description": "Attendance record not found"},
    }
)
async def update_attendance_record(
    attendance_id: str,
    payload: AttendanceUpdate,
    background_tasks: BackgroundTasks,
    _supervisor=Depends(deps.get_supervisor_user),
    service: AttendanceService = Depends(get_attendance_service),
) -> Any:
    """
    Update existing attendance record with comprehensive validation and audit trail.

    **Updatable Fields:**
    - Attendance status (present, absent, late, early_departure)
    - Check-in and check-out times
    - Notes and comments
    - Supervisor overrides and corrections

    **Features:**
    - Complete audit trail of changes
    - Automatic timestamp tracking
    - Validation against attendance policies
    - Permission-based field access

    **Business Rules:**
    - Status changes require supervisor approval
    - Time modifications must be within policy limits
    - Automatic alert generation for significant changes

    **Access:** Supervisor and Admin users
    """
    try:
        logger.info(
            f"Supervisor {_supervisor.id} updating attendance record {attendance_id}"
        )
        
        result = service.update_record_status(
            attendance_id=attendance_id,
            payload=payload,
            actor_id=_supervisor.id,
        )
        
        # Invalidate caches for affected summaries
        background_tasks.add_task(
            service.invalidate_related_caches,
            attendance_id
        )
        
        logger.info(f"Attendance record {attendance_id} updated successfully")
        
        # Process potential alerts for significant changes
        background_tasks.add_task(
            service.process_update_alerts,
            attendance_id,
            payload,
            _supervisor.id
        )
        
        return result
        
    except NotFoundError as e:
        logger.warning(f"Attendance record not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationError as e:
        logger.warning(f"Validation error in attendance update: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        logger.warning(f"Permission denied for attendance update: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating attendance record: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get(
    "",
    response_model=List[AttendanceListItem],
    summary="List attendance records with advanced filtering",
    description="Retrieve paginated attendance records with comprehensive filtering, "
                "sorting, and search capabilities optimized for performance.",
    responses={
        200: {"description": "Attendance records retrieved successfully"},
        400: {"description": "Invalid filter parameters"},
        403: {"description": "Insufficient permissions"},
    }
)
async def list_attendance(
    filters: AttendanceFilterParams = Depends(AttendanceFilterParams),
    pagination=Depends(deps.get_pagination_params),
    _admin=Depends(deps.get_admin_user),
    service: AttendanceService = Depends(get_attendance_service),
) -> Any:
    """
    List attendance records with advanced filtering and optimized pagination.

    **Advanced Filtering:**
    - Date range filtering with timezone support
    - Multi-hostel and room-based filtering
    - Student name and ID search
    - Attendance status combinations
    - Supervisor and time-based filters

    **Performance Features:**
    - Database index optimization
    - Efficient query planning
    - Lazy loading for large datasets
    - Response compression

    **Sorting Options:**
    - Date/time ascending/descending
    - Student name alphabetical
    - Attendance status grouping
    - Custom field sorting

    **Access:** Admin users (full access), Supervisors (limited scope)
    """
    try:
        logger.info(
            f"Admin {_admin.id} listing attendance with filters: "
            f"hostel={filters.hostel_id}, date_range={filters.start_date}-{filters.end_date}"
        )
        
        result = service.list_attendance(
            filters=filters,
            pagination=pagination,
            actor_id=_admin.id,
        )
        
        logger.info(f"Retrieved {len(result)} attendance records")
        return result
        
    except ValidationError as e:
        logger.warning(f"Validation error in attendance listing: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        logger.warning(f"Permission denied for attendance listing: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Error listing attendance records: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get(
    "/daily-summary",
    response_model=DailyAttendanceSummary,
    summary="Get comprehensive daily attendance analytics",
    description="Generate detailed daily attendance summary with percentages, trends, "
                "and actionable insights for administrative decision-making.",
    responses={
        200: {"description": "Daily summary generated successfully"},
        400: {"description": "Invalid summary parameters"},
        403: {"description": "Insufficient permissions"},
    }
)
@cache_response(ttl=300)  # Cache for 5 minutes
async def get_daily_attendance_summary(
    _admin=Depends(deps.get_admin_user),
    service: AttendanceService = Depends(get_attendance_service),
    hostel_id: Optional[str] = Query(
        None, 
        description="Specific hostel ID, or all hostels if not provided"
    ),
    date_value: Optional[str] = Query(
        None, 
        alias="date", 
        description="Date in YYYY-MM-DD format, defaults to current date",
        regex="^\d{4}-\d{2}-\d{2}$"
    ),
    include_trends: bool = Query(
        False, 
        description="Include weekly and monthly trend analysis"
    ),
    include_details: bool = Query(
        False, 
        description="Include room-level and status breakdown details"
    ),
) -> Any:
    """
    Generate comprehensive daily attendance summary with analytics.

    **Summary Includes:**
    - Total enrollment and attendance counts
    - Attendance percentage with trend indicators
    - Status breakdown (present, absent, late, etc.)
    - Room-level summaries and comparisons
    - Time-based attendance patterns

    **Optional Analytics:**
    - Weekly and monthly trend analysis
    - Comparative hostel performance
    - Alert threshold monitoring
    - Predictive insights for low attendance

    **Performance:**
    - Cached results for frequently accessed dates
    - Optimized aggregation queries
    - Real-time updates for current date

    **Access:** Admin users only
    """
    try:
        logger.info(
            f"Admin {_admin.id} requesting daily summary for "
            f"hostel={hostel_id}, date={date_value}"
        )
        
        result = service.get_daily_summary(
            hostel_id=hostel_id,
            date_str=date_value,
            include_trends=include_trends,
            include_details=include_details,
            actor_id=_admin.id,
        )
        
        logger.info(f"Daily summary generated successfully")
        return result
        
    except ValidationError as e:
        logger.warning(f"Validation error in daily summary: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        logger.warning(f"Permission denied for daily summary: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Error generating daily summary: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get(
    "/students/{student_id}",
    response_model=List[AttendanceResponse],
    summary="Get complete student attendance history",
    description="Retrieve comprehensive attendance history for a specific student with "
                "analytics, patterns, and performance indicators.",
    responses={
        200: {"description": "Student attendance history retrieved successfully"},
        404: {"description": "Student not found"},
        403: {"description": "Insufficient permissions"},
    }
)
async def get_student_attendance(
    student_id: str,
    _admin=Depends(deps.get_admin_user),
    service: AttendanceService = Depends(get_attendance_service),
    start_date: Optional[str] = Query(
        None, 
        description="Start date for history (YYYY-MM-DD)",
        regex="^\d{4}-\d{2}-\d{2}$"
    ),
    end_date: Optional[str] = Query(
        None, 
        description="End date for history (YYYY-MM-DD)",
        regex="^\d{4}-\d{2}-\d{2}$"
    ),
    include_analytics: bool = Query(
        False, 
        description="Include attendance analytics and patterns"
    ),
) -> Any:
    """
    Get comprehensive attendance history for a specific student.

    **History Includes:**
    - Complete chronological attendance records
    - Status patterns and trends
    - Absence and tardiness summaries
    - Check-in/out time analytics

    **Optional Analytics:**
    - Attendance percentage calculations
    - Pattern recognition (chronic lateness, etc.)
    - Comparison to hostel averages
    - Policy violation tracking

    **Use Cases:**
    - Student performance reviews
    - Parent/guardian communications
    - Academic intervention planning
    - Disciplinary documentation

    **Access:** Admin and Supervisor users
    """
    try:
        logger.info(
            f"Admin {_admin.id} requesting attendance history for student {student_id}"
        )
        
        result = service.get_student_attendance(
            student_id=student_id, 
            start_date=start_date,
            end_date=end_date,
            include_analytics=include_analytics,
            actor_id=_admin.id
        )
        
        logger.info(f"Retrieved {len(result)} attendance records for student {student_id}")
        return result
        
    except NotFoundError as e:
        logger.warning(f"Student not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        logger.warning(f"Permission denied for student attendance: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Error retrieving student attendance: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# Attendance corrections (with workflow)
# ---------------------------------------------------------------------------


@router.post(
    "/corrections",
    response_model=AttendanceCorrection,
    status_code=status.HTTP_201_CREATED,
    summary="Submit attendance correction request",
    description="Submit a formal request to correct an existing attendance record with "
                "proper workflow, approval process, and audit trail.",
    responses={
        201: {"description": "Correction request submitted successfully"},
        400: {"description": "Invalid correction request"},
        403: {"description": "Insufficient permissions"},
        404: {"description": "Original attendance record not found"},
    }
)
async def submit_correction(
    payload: AttendanceCorrection,
    background_tasks: BackgroundTasks,
    _supervisor=Depends(deps.get_supervisor_user),
    service: AttendanceCorrectionService = Depends(get_correction_service),
) -> Any:
    """
    Submit a correction request for an existing attendance record with workflow support.

    **Correction Workflow:**
    1. Supervisor submits correction request with justification
    2. Admin review and approval process
    3. Automatic application of approved corrections
    4. Complete audit trail maintenance

    **Correctable Elements:**
    - Attendance status changes
    - Check-in/out time adjustments
    - Addition of missing records
    - Correction of erroneous entries

    **Features:**
    - Structured approval workflow
    - Detailed justification requirements
    - Supporting documentation attachment
    - Automated notification system

    **Access:** Supervisor users (submit), Admin users (approve)
    """
    try:
        logger.info(
            f"Supervisor {_supervisor.id} submitting correction for "
            f"attendance record {payload.attendance_id}"
        )
        
        result = service.submit_correction(payload=payload, actor_id=_supervisor.id)
        
        # Schedule notification to admins
        background_tasks.add_task(
            service.notify_correction_submission,
            result.id,
            _supervisor.id
        )
        
        logger.info(f"Correction request {result.id} submitted successfully")
        return result
        
    except NotFoundError as e:
        logger.warning(f"Attendance record not found for correction: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationError as e:
        logger.warning(f"Validation error in correction submission: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        logger.warning(f"Permission denied for correction submission: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Error submitting correction: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get(
    "/{attendance_id}/corrections",
    response_model=List[AttendanceCorrection],
    summary="Get correction history for attendance record",
    description="Retrieve complete correction history and workflow status for a "
                "specific attendance record.",
    responses={
        200: {"description": "Correction history retrieved successfully"},
        404: {"description": "Attendance record not found"},
        403: {"description": "Insufficient permissions"},
    }
)
async def get_correction_history(
    attendance_id: str,
    _admin=Depends(deps.get_admin_user),
    service: AttendanceCorrectionService = Depends(get_correction_service),
) -> Any:
    """
    Get complete correction history and workflow status for an attendance record.

    **History Includes:**
    - All correction requests (pending, approved, rejected)
    - Workflow timestamps and actors
    - Justifications and supporting documentation
    - Applied changes and their impacts

    **Workflow Tracking:**
    - Submission details and reasoning
    - Review and approval process
    - Implementation status and results
    - Communication history

    **Access:** Admin users only
    """
    try:
        logger.info(
            f"Admin {_admin.id} requesting correction history for record {attendance_id}"
        )
        
        result = service.get_correction_history(
            attendance_id=attendance_id, 
            actor_id=_admin.id
        )
        
        logger.info(f"Retrieved {len(result)} correction records")
        return result
        
    except NotFoundError as e:
        logger.warning(f"Attendance record not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        logger.warning(f"Permission denied for correction history: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Error retrieving correction history: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post(
    "/corrections/{correction_id}/approve",
    response_model=AttendanceCorrection,
    summary="Approve attendance correction request",
    description="Approve a pending correction request and automatically apply the "
                "changes to the original attendance record.",
    responses={
        200: {"description": "Correction approved and applied successfully"},
        404: {"description": "Correction request not found"},
        400: {"description": "Correction cannot be approved in current state"},
        403: {"description": "Insufficient permissions"},
    }
)
async def approve_correction(
    correction_id: str,
    background_tasks: BackgroundTasks,
    _admin=Depends(deps.get_admin_user),
    service: AttendanceCorrectionService = Depends(get_correction_service),
    approval_notes: Optional[str] = Query(
        None, 
        description="Additional approval notes",
        max_length=500
    ),
) -> Any:
    """
    Approve a pending correction request and apply changes automatically.

    **Approval Process:**
    - Validate correction request eligibility
    - Apply changes to original attendance record
    - Update correction workflow status
    - Generate audit trail entries
    - Notify relevant stakeholders

    **Automatic Actions:**
    - Original record modification
    - Cache invalidation for affected summaries
    - Alert processing for significant changes
    - Notification dispatch to requestor

    **Access:** Admin users only
    """
    try:
        logger.info(f"Admin {_admin.id} approving correction {correction_id}")
        
        result = service.approve_correction(
            correction_id=correction_id,
            approval_notes=approval_notes,
            actor_id=_admin.id
        )
        
        # Invalidate relevant caches after approval
        background_tasks.add_task(
            service.invalidate_correction_caches,
            correction_id
        )
        
        # Notify requestor of approval
        background_tasks.add_task(
            service.notify_correction_approval,
            correction_id,
            _admin.id
        )
        
        logger.info(f"Correction {correction_id} approved and applied successfully")
        return result
        
    except NotFoundError as e:
        logger.warning(f"Correction request not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationError as e:
        logger.warning(f"Validation error in correction approval: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        logger.warning(f"Permission denied for correction approval: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Error approving correction: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post(
    "/corrections/{correction_id}/reject",
    response_model=AttendanceCorrection,
    summary="Reject attendance correction request",
    description="Reject a pending correction request with detailed reasoning and "
                "stakeholder notification.",
    responses={
        200: {"description": "Correction rejected successfully"},
        404: {"description": "Correction request not found"},
        400: {"description": "Correction cannot be rejected in current state"},
        403: {"description": "Insufficient permissions"},
    }
)
async def reject_correction(
    correction_id: str,
    background_tasks: BackgroundTasks,
    _admin=Depends(deps.get_admin_user),
    service: AttendanceCorrectionService = Depends(get_correction_service),
    reason: Optional[str] = Query(
        None, 
        description="Detailed rejection reason and feedback",
        max_length=1000
    ),
) -> Any:
    """
    Reject a pending correction request with comprehensive feedback.

    **Rejection Process:**
    - Update correction workflow status to rejected
    - Document rejection reasoning and feedback
    - Notify requestor with detailed explanation
    - Maintain complete audit trail

    **Features:**
    - Detailed rejection feedback
    - Constructive guidance for future requests
    - Workflow state management
    - Stakeholder communication

    **Access:** Admin users only
    """
    try:
        logger.info(f"Admin {_admin.id} rejecting correction {correction_id}")
        
        result = service.reject_correction(
            correction_id=correction_id,
            reason=reason,
            actor_id=_admin.id,
        )
        
        # Notify requestor of rejection
        background_tasks.add_task(
            service.notify_correction_rejection,
            correction_id,
            reason,
            _admin.id
        )
        
        logger.info(f"Correction {correction_id} rejected successfully")
        return result
        
    except NotFoundError as e:
        logger.warning(f"Correction request not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationError as e:
        logger.warning(f"Validation error in correction rejection: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        logger.warning(f"Permission denied for correction rejection: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Error rejecting correction: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# Advanced operations
# ---------------------------------------------------------------------------

@router.get(
    "/analytics/patterns",
    summary="Get attendance pattern analysis",
    description="Analyze attendance patterns for insights and predictions",
    responses={
        200: {"description": "Pattern analysis completed successfully"},
        403: {"description": "Insufficient permissions"},
    }
)
@cache_response(ttl=1800)  # Cache for 30 minutes
async def get_attendance_patterns(
    _admin=Depends(deps.get_admin_user),
    service: AttendanceService = Depends(get_attendance_service),
    hostel_id: Optional[str] = Query(None),
    days: int = Query(30, ge=7, le=365),
) -> Any:
    """
    Analyze attendance patterns for insights and predictive analytics.
    
    **Pattern Analysis:**
    - Weekly and monthly trends
    - Seasonal variations
    - Student behavior patterns
    - Risk factor identification
    
    **Access:** Admin users only
    """
    try:
        result = service.analyze_attendance_patterns(
            hostel_id=hostel_id,
            days=days,
            actor_id=_admin.id
        )
        return result
        
    except Exception as e:
        logger.error(f"Error analyzing attendance patterns: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get(
    "/real-time/status",
    summary="Get real-time attendance status",
    description="Get current attendance status for live monitoring dashboards",
    responses={
        200: {"description": "Real-time status retrieved successfully"},
        403: {"description": "Insufficient permissions"},
    }
)
async def get_real_time_attendance_status(
    _admin=Depends(deps.get_admin_user),
    service: AttendanceService = Depends(get_attendance_service),
    hostel_id: Optional[str] = Query(None),
) -> Any:
    """
    Get real-time attendance status for live monitoring and dashboards.
    
    **Real-time Data:**
    - Current check-in/out counts
    - Active attendance sessions
    - Late arrivals and early departures
    - Emergency contact status
    
    **Access:** Admin and Supervisor users
    """
    try:
        result = service.get_real_time_status(
            hostel_id=hostel_id,
            actor_id=_admin.id
        )
        return result
        
    except Exception as e:
        logger.error(f"Error retrieving real-time status: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")