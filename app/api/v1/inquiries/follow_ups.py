"""
Inquiry Follow-up API Endpoints

Provides REST API endpoints for managing inquiry follow-ups including:
- Recording follow-up interactions
- Viewing inquiry timeline
- Scheduling future follow-ups
- Follow-up reminders and notifications
"""

from typing import Any, List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api import deps
from app.core.logging import get_logger
from app.schemas.inquiry.inquiry_status import (
    InquiryFollowUp,
    InquiryTimelineEntry,
)
from app.services.inquiry.inquiry_follow_up_service import InquiryFollowUpService

# Initialize logger
logger = get_logger(__name__)

# Initialize router with prefix and tags
router = APIRouter(
    prefix="/inquiries/follow-ups",
    tags=["inquiries:follow-ups"],
    responses={
        404: {"description": "Inquiry or follow-up not found"},
        400: {"description": "Invalid request"},
        500: {"description": "Internal server error"},
    },
)


# ============================================================================
# Dependency Injection
# ============================================================================


def get_followup_service(
    db: Session = Depends(deps.get_db)
) -> InquiryFollowUpService:
    """
    Dependency injection for InquiryFollowUpService.
    
    Args:
        db: Database session
        
    Returns:
        InquiryFollowUpService instance
    """
    return InquiryFollowUpService(db=db)


# ============================================================================
# Follow-up Management Endpoints
# ============================================================================


@router.post(
    "/{inquiry_id}",
    response_model=InquiryTimelineEntry,
    status_code=status.HTTP_201_CREATED,
    summary="Record follow-up interaction",
    description="""
    Record a follow-up interaction for an inquiry.
    
    This creates a timeline entry documenting:
    - Type of interaction (call, email, meeting, etc.)
    - Interaction details and notes
    - Outcome and next steps
    - Timestamp and user who performed the follow-up
    """,
    response_description="Created timeline entry",
)
async def record_follow_up(
    inquiry_id: str,
    payload: InquiryFollowUp,
    service: InquiryFollowUpService = Depends(get_followup_service),
    current_user: Any = Depends(deps.get_current_user),
) -> InquiryTimelineEntry:
    """
    Record a follow-up interaction.
    
    Args:
        inquiry_id: Unique identifier of the inquiry
        payload: Follow-up details (type, notes, outcome, etc.)
        service: Follow-up service instance
        current_user: Authenticated user recording the follow-up
        
    Returns:
        Created timeline entry
        
    Raises:
        HTTPException: If recording fails or inquiry not found
    """
    try:
        logger.info(
            f"Recording follow-up for inquiry {inquiry_id}",
            extra={
                "inquiry_id": inquiry_id,
                "user_id": current_user.id,
                "interaction_type": payload.interaction_type if hasattr(payload, 'interaction_type') else None
            }
        )
        
        timeline_entry = service.record(
            inquiry_id=inquiry_id,
            payload=payload,
            user_id=current_user.id
        )
        
        if not timeline_entry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Inquiry with ID {inquiry_id} not found"
            )
        
        logger.info(
            f"Successfully recorded follow-up for inquiry {inquiry_id}",
            extra={"timeline_entry_id": timeline_entry.id if hasattr(timeline_entry, 'id') else None}
        )
        
        return timeline_entry
        
    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(
            f"Validation error recording follow-up for inquiry {inquiry_id}: {str(e)}"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(
            f"Error recording follow-up for inquiry {inquiry_id}: {str(e)}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to record follow-up"
        )


@router.get(
    "/{inquiry_id}/timeline",
    response_model=List[InquiryTimelineEntry],
    summary="Get inquiry timeline",
    description="""
    Retrieve the complete timeline of an inquiry.
    
    The timeline includes:
    - All follow-up interactions
    - Status changes
    - Assignments
    - Notes and comments
    - System events
    
    Entries are sorted chronologically (newest first by default).
    """,
    response_description="List of timeline entries",
)
async def get_timeline(
    inquiry_id: str,
    order: str = Query(
        "desc",
        description="Sort order: 'asc' for chronological, 'desc' for reverse chronological",
        regex="^(asc|desc)$"
    ),
    limit: Optional[int] = Query(
        None,
        description="Maximum number of entries to return",
        ge=1,
        le=1000
    ),
    service: InquiryFollowUpService = Depends(get_followup_service),
    current_user: Any = Depends(deps.get_current_user),
) -> List[InquiryTimelineEntry]:
    """
    Get inquiry timeline.
    
    Args:
        inquiry_id: Unique identifier of the inquiry
        order: Sort order (asc or desc)
        limit: Optional limit on number of entries
        service: Follow-up service instance
        current_user: Authenticated user
        
    Returns:
        List of timeline entries
        
    Raises:
        HTTPException: If inquiry not found or retrieval fails
    """
    try:
        logger.info(
            f"Fetching timeline for inquiry {inquiry_id}",
            extra={
                "inquiry_id": inquiry_id,
                "user_id": current_user.id,
                "order": order,
                "limit": limit
            }
        )
        
        timeline = service.timeline(
            inquiry_id=inquiry_id,
            order=order,
            limit=limit
        )
        
        if timeline is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Inquiry with ID {inquiry_id} not found"
            )
        
        logger.info(
            f"Retrieved {len(timeline)} timeline entries for inquiry {inquiry_id}"
        )
        
        return timeline
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error fetching timeline for inquiry {inquiry_id}: {str(e)}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve inquiry timeline"
        )


@router.post(
    "/{inquiry_id}/schedule",
    status_code=status.HTTP_201_CREATED,
    summary="Schedule next follow-up",
    description="""
    Schedule a future follow-up for an inquiry.
    
    This creates a reminder/task for the assigned user to follow up 
    at the specified date and time. Notifications will be sent based 
    on configured reminder settings.
    """,
    response_description="Scheduled follow-up details",
)
async def schedule_follow_up(
    inquiry_id: str,
    follow_up_date: str = Query(
        ...,
        description="Follow-up date and time in ISO 8601 format (e.g., 2024-01-15T14:30:00Z)"
    ),
    notes: Optional[str] = Query(
        None,
        description="Optional notes or context for the scheduled follow-up",
        max_length=1000
    ),
    reminder_minutes: Optional[int] = Query(
        None,
        description="Minutes before follow-up to send reminder (default: 60)",
        ge=0,
        le=10080  # Max 1 week
    ),
    service: InquiryFollowUpService = Depends(get_followup_service),
    current_user: Any = Depends(deps.get_current_user),
) -> dict:
    """
    Schedule a follow-up.
    
    Args:
        inquiry_id: Unique identifier of the inquiry
        follow_up_date: ISO 8601 formatted datetime for the follow-up
        notes: Optional notes for the follow-up
        reminder_minutes: Minutes before to send reminder
        service: Follow-up service instance
        current_user: Authenticated user scheduling the follow-up
        
    Returns:
        Scheduled follow-up details
        
    Raises:
        HTTPException: If scheduling fails or date is invalid
    """
    try:
        # Validate and parse the follow-up date
        try:
            parsed_date = datetime.fromisoformat(follow_up_date.replace('Z', '+00:00'))
        except ValueError as e:
            raise ValueError(
                f"Invalid date format. Expected ISO 8601 format: {str(e)}"
            )
        
        # Ensure follow-up date is in the future
        if parsed_date <= datetime.now(parsed_date.tzinfo):
            raise ValueError("Follow-up date must be in the future")
        
        logger.info(
            f"Scheduling follow-up for inquiry {inquiry_id} at {follow_up_date}",
            extra={
                "inquiry_id": inquiry_id,
                "user_id": current_user.id,
                "follow_up_date": follow_up_date,
                "reminder_minutes": reminder_minutes
            }
        )
        
        scheduled_followup = service.schedule_follow_up(
            inquiry_id=inquiry_id,
            follow_up_date=follow_up_date,
            notes=notes,
            scheduler_id=current_user.id,
            reminder_minutes=reminder_minutes
        )
        
        if not scheduled_followup:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Inquiry with ID {inquiry_id} not found"
            )
        
        logger.info(
            f"Successfully scheduled follow-up for inquiry {inquiry_id}",
            extra={"scheduled_id": scheduled_followup.get("id")}
        )
        
        return scheduled_followup
        
    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(
            f"Validation error scheduling follow-up for inquiry {inquiry_id}: {str(e)}"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(
            f"Error scheduling follow-up for inquiry {inquiry_id}: {str(e)}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to schedule follow-up"
        )


@router.get(
    "/{inquiry_id}/scheduled",
    response_model=List[dict],
    summary="Get scheduled follow-ups",
    description="""
    Retrieve all scheduled follow-ups for an inquiry.
    
    Returns both pending and completed scheduled follow-ups,
    with their current status and reminder information.
    """,
    response_description="List of scheduled follow-ups",
)
async def get_scheduled_follow_ups(
    inquiry_id: str,
    status_filter: Optional[str] = Query(
        None,
        description="Filter by status: 'pending', 'completed', or 'cancelled'",
        regex="^(pending|completed|cancelled)$"
    ),
    service: InquiryFollowUpService = Depends(get_followup_service),
    current_user: Any = Depends(deps.get_current_user),
) -> List[dict]:
    """
    Get scheduled follow-ups for an inquiry.
    
    Args:
        inquiry_id: Unique identifier of the inquiry
        status_filter: Optional status filter
        service: Follow-up service instance
        current_user: Authenticated user
        
    Returns:
        List of scheduled follow-ups
        
    Raises:
        HTTPException: If inquiry not found or retrieval fails
    """
    try:
        logger.info(
            f"Fetching scheduled follow-ups for inquiry {inquiry_id}",
            extra={
                "inquiry_id": inquiry_id,
                "user_id": current_user.id,
                "status_filter": status_filter
            }
        )
        
        scheduled = service.get_scheduled(
            inquiry_id=inquiry_id,
            status_filter=status_filter
        )
        
        if scheduled is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Inquiry with ID {inquiry_id} not found"
            )
        
        logger.info(
            f"Retrieved {len(scheduled)} scheduled follow-ups for inquiry {inquiry_id}"
        )
        
        return scheduled
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error fetching scheduled follow-ups for inquiry {inquiry_id}: {str(e)}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve scheduled follow-ups"
        )


@router.patch(
    "/{inquiry_id}/scheduled/{schedule_id}",
    summary="Update scheduled follow-up",
    description="""
    Update or cancel a scheduled follow-up.
    
    Allows modifying the date, notes, or marking the follow-up as completed/cancelled.
    """,
    response_description="Updated scheduled follow-up",
)
async def update_scheduled_follow_up(
    inquiry_id: str,
    schedule_id: str,
    follow_up_date: Optional[str] = Query(None, description="New follow-up date (ISO format)"),
    notes: Optional[str] = Query(None, description="Updated notes"),
    status: Optional[str] = Query(
        None,
        description="New status: 'pending', 'completed', or 'cancelled'",
        regex="^(pending|completed|cancelled)$"
    ),
    service: InquiryFollowUpService = Depends(get_followup_service),
    current_user: Any = Depends(deps.get_current_user),
) -> dict:
    """
    Update a scheduled follow-up.
    
    Args:
        inquiry_id: Unique identifier of the inquiry
        schedule_id: Unique identifier of the scheduled follow-up
        follow_up_date: Optional new date
        notes: Optional updated notes
        status: Optional new status
        service: Follow-up service instance
        current_user: Authenticated user
        
    Returns:
        Updated scheduled follow-up
        
    Raises:
        HTTPException: If not found or update fails
    """
    try:
        logger.info(
            f"Updating scheduled follow-up {schedule_id} for inquiry {inquiry_id}",
            extra={
                "inquiry_id": inquiry_id,
                "schedule_id": schedule_id,
                "user_id": current_user.id
            }
        )
        
        updated = service.update_scheduled(
            inquiry_id=inquiry_id,
            schedule_id=schedule_id,
            follow_up_date=follow_up_date,
            notes=notes,
            status=status,
            updated_by=current_user.id
        )
        
        if not updated:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Scheduled follow-up {schedule_id} not found"
            )
        
        logger.info(f"Successfully updated scheduled follow-up {schedule_id}")
        return updated
        
    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(f"Validation error updating scheduled follow-up: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(
            f"Error updating scheduled follow-up {schedule_id}: {str(e)}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update scheduled follow-up"
        )