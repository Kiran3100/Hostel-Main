from typing import Any, Optional
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, Query, status, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api import deps
from app.core.exceptions import ValidationError, NotFoundError, PermissionError
from app.core.logging import get_logger
from app.core.cache import cache_response
from app.schemas.attendance import (
    AlertConfig,
    AttendanceAlert,
    AlertList,
    AlertSummary,
    AlertAcknowledgment,
)
from app.services.attendance.attendance_alert_service import AttendanceAlertService

logger = get_logger(__name__)
router = APIRouter(prefix="/attendance/alerts", tags=["attendance:alerts"])


def get_alert_service(db: Session = Depends(deps.get_db)) -> AttendanceAlertService:
    """
    Dependency to provide AttendanceAlertService instance.
    
    Args:
        db: Database session
        
    Returns:
        AttendanceAlertService instance
    """
    return AttendanceAlertService(db=db)


@router.put(
    "/config",
    response_model=AlertConfig,
    status_code=status.HTTP_200_OK,
    summary="Configure attendance alert thresholds",
    description="Configure alert thresholds including low attendance percentages, "
                "consecutive absence limits, and notification preferences for a hostel.",
    responses={
        200: {"description": "Alert configuration saved successfully"},
        400: {"description": "Invalid configuration parameters"},
        403: {"description": "Insufficient permissions"},
        404: {"description": "Hostel not found"},
    }
)
async def save_alert_configuration(
    payload: AlertConfig,
    _admin=Depends(deps.get_admin_user),
    service: AttendanceAlertService = Depends(get_alert_service),
) -> Any:
    """
    Configure comprehensive alert thresholds for hostel attendance monitoring.
    
    **Features:**
    - Low attendance percentage thresholds
    - Consecutive absence day limits
    - Escalation rules and notification preferences
    - Custom alert severity levels
    
    **Access:** Admin users only
    """
    try:
        logger.info(
            f"Admin {_admin.id} configuring alerts for hostel {payload.hostel_id}"
        )
        
        result = service.save_configuration(payload=payload, actor_id=_admin.id)
        
        logger.info(
            f"Alert configuration saved successfully for hostel {payload.hostel_id}"
        )
        return result
        
    except ValidationError as e:
        logger.warning(f"Validation error in alert config: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        logger.warning(f"Permission denied for alert config: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error saving alert config: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get(
    "/config",
    response_model=AlertConfig,
    summary="Retrieve current alert configuration",
    description="Get the current alert configuration settings for a specific hostel.",
    responses={
        200: {"description": "Alert configuration retrieved successfully"},
        404: {"description": "Alert configuration not found"},
        403: {"description": "Insufficient permissions"},
    }
)
@cache_response(ttl=300)  # Cache for 5 minutes
async def get_alert_configuration(
    hostel_id: str = Query(
        ..., 
        description="Unique identifier for the hostel",
        min_length=1,
        max_length=50
    ),
    _admin=Depends(deps.get_admin_user),
    service: AttendanceAlertService = Depends(get_alert_service),
) -> Any:
    """
    Retrieve current alert configuration for the specified hostel.
    
    **Returns:**
    - Current alert thresholds and rules
    - Notification preferences
    - Escalation settings
    
    **Access:** Admin users only
    """
    try:
        logger.info(f"Admin {_admin.id} requesting alert config for hostel {hostel_id}")
        
        result = service.get_configuration(hostel_id=hostel_id, actor_id=_admin.id)
        return result
        
    except NotFoundError as e:
        logger.warning(f"Alert config not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        logger.warning(f"Permission denied for alert config: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Error retrieving alert config: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post(
    "/trigger",
    response_model=AttendanceAlert,
    status_code=status.HTTP_201_CREATED,
    summary="Manually trigger attendance alert",
    description="Create a manual attendance alert for specific attendance concerns "
                "or administrative purposes.",
    responses={
        201: {"description": "Alert triggered successfully"},
        400: {"description": "Invalid alert parameters"},
        403: {"description": "Insufficient permissions"},
    }
)
async def trigger_alert(
    payload: AttendanceAlert,
    _admin=Depends(deps.get_admin_user),
    service: AttendanceAlertService = Depends(get_alert_service),
) -> Any:
    """
    Manually create an attendance alert for specific concerns.
    
    **Use Cases:**
    - Report unusual attendance patterns
    - Flag specific students for attention
    - Create administrative notices
    - Escalate attendance issues
    
    **Access:** Admin users only
    """
    try:
        logger.info(
            f"Admin {_admin.id} triggering manual alert for student {payload.student_id}"
        )
        
        result = service.trigger_alert(payload=payload, actor_id=_admin.id)
        
        logger.info(f"Manual alert {result.id} created successfully")
        return result
        
    except ValidationError as e:
        logger.warning(f"Validation error in manual alert: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        logger.warning(f"Permission denied for manual alert: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating manual alert: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post(
    "/{alert_id}/acknowledge",
    response_model=AttendanceAlert,
    summary="Acknowledge attendance alert",
    description="Mark an alert as acknowledged with optional comments and action plans.",
    responses={
        200: {"description": "Alert acknowledged successfully"},
        404: {"description": "Alert not found"},
        400: {"description": "Alert cannot be acknowledged in current state"},
        403: {"description": "Insufficient permissions"},
    }
)
async def acknowledge_alert(
    alert_id: str = Query(..., description="Unique alert identifier"),
    payload: AlertAcknowledgment,
    _admin=Depends(deps.get_admin_user),
    service: AttendanceAlertService = Depends(get_alert_service),
) -> Any:
    """
    Acknowledge an active attendance alert.
    
    **Features:**
    - Mark alert as seen and understood
    - Add acknowledgment comments
    - Set action plans and follow-up dates
    - Track acknowledgment history
    
    **Access:** Admin users only
    """
    try:
        logger.info(f"Admin {_admin.id} acknowledging alert {alert_id}")
        
        result = service.acknowledge(
            alert_id=alert_id, 
            payload=payload, 
            actor_id=_admin.id
        )
        
        logger.info(f"Alert {alert_id} acknowledged successfully")
        return result
        
    except NotFoundError as e:
        logger.warning(f"Alert not found for acknowledgment: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationError as e:
        logger.warning(f"Validation error in acknowledgment: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        logger.warning(f"Permission denied for acknowledgment: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Error acknowledging alert: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post(
    "/{alert_id}/resolve",
    response_model=AttendanceAlert,
    summary="Resolve attendance alert",
    description="Mark an alert as resolved with resolution notes and outcome documentation.",
    responses={
        200: {"description": "Alert resolved successfully"},
        404: {"description": "Alert not found"},
        400: {"description": "Alert cannot be resolved in current state"},
        403: {"description": "Insufficient permissions"},
    }
)
async def resolve_alert(
    alert_id: str = Query(..., description="Unique alert identifier"),
    resolution_notes: Optional[str] = Query(
        None, 
        description="Detailed resolution notes and actions taken",
        max_length=1000
    ),
    _admin=Depends(deps.get_admin_user),
    service: AttendanceAlertService = Depends(get_alert_service),
) -> Any:
    """
    Mark an attendance alert as resolved.
    
    **Features:**
    - Final resolution of alert lifecycle
    - Document resolution actions and outcomes
    - Track resolution metrics
    - Close alert workflow
    
    **Access:** Admin users only
    """
    try:
        logger.info(f"Admin {_admin.id} resolving alert {alert_id}")
        
        result = service.resolve_alert(
            alert_id=alert_id,
            resolution_notes=resolution_notes,
            actor_id=_admin.id,
        )
        
        logger.info(f"Alert {alert_id} resolved successfully")
        return result
        
    except NotFoundError as e:
        logger.warning(f"Alert not found for resolution: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationError as e:
        logger.warning(f"Validation error in resolution: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        logger.warning(f"Permission denied for resolution: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Error resolving alert: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get(
    "",
    response_model=AlertList,
    summary="List attendance alerts with advanced filtering",
    description="Retrieve paginated list of attendance alerts with comprehensive filtering "
                "and sorting capabilities.",
    responses={
        200: {"description": "Alerts retrieved successfully"},
        400: {"description": "Invalid filter parameters"},
        403: {"description": "Insufficient permissions"},
    }
)
async def list_alerts(
    hostel_id: Optional[str] = Query(
        None, 
        description="Filter by specific hostel ID"
    ),
    severity: Optional[str] = Query(
        None, 
        description="Filter by alert severity (low, medium, high, critical)",
        regex="^(low|medium|high|critical)$"
    ),
    status_filter: Optional[str] = Query(
        None, 
        alias="status",
        description="Filter by alert status (active, acknowledged, resolved)",
        regex="^(active|acknowledged|resolved)$"
    ),
    student_id: Optional[str] = Query(
        None,
        description="Filter by specific student ID"
    ),
    date_from: Optional[str] = Query(
        None,
        description="Start date filter (YYYY-MM-DD)",
        regex="^\d{4}-\d{2}-\d{2}$"
    ),
    date_to: Optional[str] = Query(
        None,
        description="End date filter (YYYY-MM-DD)",
        regex="^\d{4}-\d{2}-\d{2}$"
    ),
    pagination=Depends(deps.get_pagination_params),
    _admin=Depends(deps.get_admin_user),
    service: AttendanceAlertService = Depends(get_alert_service),
) -> Any:
    """
    List attendance alerts with advanced filtering and pagination.
    
    **Filtering Options:**
    - Hostel-specific alerts
    - Alert severity levels
    - Alert status workflow
    - Student-specific alerts
    - Date range filtering
    
    **Features:**
    - Optimized pagination
    - Multi-field sorting
    - Real-time counts
    - Performance optimized queries
    
    **Access:** Admin users only
    """
    try:
        logger.info(
            f"Admin {_admin.id} listing alerts with filters: "
            f"hostel={hostel_id}, severity={severity}, status={status_filter}"
        )
        
        result = service.list_alerts(
            hostel_id=hostel_id,
            severity=severity,
            status=status_filter,
            student_id=student_id,
            date_from=date_from,
            date_to=date_to,
            pagination=pagination,
            actor_id=_admin.id,
        )
        
        logger.info(f"Retrieved {len(result.items)} alerts")
        return result
        
    except ValidationError as e:
        logger.warning(f"Validation error in alert listing: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        logger.warning(f"Permission denied for alert listing: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Error listing alerts: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get(
    "/summary",
    response_model=AlertSummary,
    summary="Get comprehensive alert analytics summary",
    description="Retrieve high-level alert analytics and metrics for dashboard displays "
                "and administrative oversight.",
    responses={
        200: {"description": "Alert summary retrieved successfully"},
        400: {"description": "Invalid summary parameters"},
        403: {"description": "Insufficient permissions"},
    }
)
@cache_response(ttl=180)  # Cache for 3 minutes
async def get_alert_summary(
    hostel_id: Optional[str] = Query(
        None, 
        description="Filter summary by specific hostel"
    ),
    days: int = Query(
        30, 
        ge=1, 
        le=365, 
        description="Number of days to include in summary analysis"
    ),
    _admin=Depends(deps.get_admin_user),
    service: AttendanceAlertService = Depends(get_alert_service),
) -> Any:
    """
    Generate comprehensive attendance alert analytics summary.
    
    **Metrics Included:**
    - Total alert counts by severity
    - Alert resolution rates and times
    - Trending analysis
    - Top alert categories
    - Student and hostel breakdowns
    
    **Performance:**
    - Cached results for improved response times
    - Optimized aggregation queries
    - Real-time critical alerts
    
    **Access:** Admin users only
    """
    try:
        logger.info(
            f"Admin {_admin.id} requesting alert summary for "
            f"hostel={hostel_id}, days={days}"
        )
        
        result = service.get_summary(
            hostel_id=hostel_id,
            days=days,
            actor_id=_admin.id,
        )
        
        logger.info(f"Alert summary generated successfully")
        return result
        
    except ValidationError as e:
        logger.warning(f"Validation error in alert summary: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        logger.warning(f"Permission denied for alert summary: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Error generating alert summary: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get(
    "/metrics",
    summary="Get real-time alert metrics",
    description="Get real-time alert metrics for monitoring dashboards",
    responses={
        200: {"description": "Metrics retrieved successfully"},
        403: {"description": "Insufficient permissions"},
    }
)
async def get_alert_metrics(
    hostel_id: Optional[str] = Query(None),
    _admin=Depends(deps.get_admin_user),
    service: AttendanceAlertService = Depends(get_alert_service),
) -> Any:
    """
    Get real-time alert metrics for monitoring and dashboards.
    
    **Real-time Metrics:**
    - Active alert count
    - Critical alerts requiring immediate attention
    - Average resolution time
    - Alert trend indicators
    
    **Access:** Admin users only
    """
    try:
        result = service.get_real_time_metrics(
            hostel_id=hostel_id,
            actor_id=_admin.id
        )
        return result
        
    except Exception as e:
        logger.error(f"Error retrieving alert metrics: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post(
    "/bulk-acknowledge",
    summary="Bulk acknowledge multiple alerts",
    description="Acknowledge multiple alerts simultaneously for efficient processing",
    responses={
        200: {"description": "Alerts acknowledged successfully"},
        400: {"description": "Invalid bulk operation parameters"},
        403: {"description": "Insufficient permissions"},
    }
)
async def bulk_acknowledge_alerts(
    alert_ids: list[str],
    payload: AlertAcknowledgment,
    _admin=Depends(deps.get_admin_user),
    service: AttendanceAlertService = Depends(get_alert_service),
) -> Any:
    """
    Bulk acknowledge multiple alerts for efficient processing.
    
    **Features:**
    - Process multiple alerts simultaneously
    - Atomic operation with rollback capability
    - Performance optimized for large batches
    - Detailed operation results
    
    **Access:** Admin users only
    """
    try:
        logger.info(f"Admin {_admin.id} bulk acknowledging {len(alert_ids)} alerts")
        
        result = service.bulk_acknowledge(
            alert_ids=alert_ids,
            payload=payload,
            actor_id=_admin.id
        )
        
        logger.info(f"Bulk acknowledgment completed for {len(alert_ids)} alerts")
        return result
        
    except ValidationError as e:
        logger.warning(f"Validation error in bulk acknowledgment: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        logger.warning(f"Permission denied for bulk acknowledgment: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Error in bulk acknowledgment: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")