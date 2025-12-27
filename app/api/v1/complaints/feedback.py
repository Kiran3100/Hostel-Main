"""
Complaint Feedback API Endpoints
Handles feedback collection and analysis for resolved complaints.
"""
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.complaint import (
    FeedbackRequest,
    FeedbackResponse,
    FeedbackSummary,
    FeedbackAnalysis,
    FeedbackFilterParams,
)
from app.services.complaint.complaint_feedback_service import ComplaintFeedbackService

router = APIRouter(prefix="/complaints/feedback", tags=["complaints:feedback"])


def get_feedback_service(
    db: Session = Depends(deps.get_db),
) -> ComplaintFeedbackService:
    """
    Dependency injection for ComplaintFeedbackService.
    
    Args:
        db: Database session from dependency injection
        
    Returns:
        ComplaintFeedbackService: Initialized service instance
    """
    return ComplaintFeedbackService(db=db)


@router.post(
    "/{complaint_id}",
    response_model=FeedbackResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit feedback for resolved complaint",
    description="Submit satisfaction rating and comments for a resolved complaint. Only complaint creator can provide feedback.",
    responses={
        201: {"description": "Feedback submitted successfully"},
        404: {"description": "Complaint not found"},
        400: {"description": "Complaint not resolved or feedback already submitted"},
        403: {"description": "Not authorized to provide feedback"},
    },
)
def submit_feedback(
    complaint_id: str,
    payload: FeedbackRequest,
    current_user=Depends(deps.get_current_user),
    service: ComplaintFeedbackService = Depends(get_feedback_service),
) -> Any:
    """
    Submit feedback for a resolved complaint.
    
    Args:
        complaint_id: Unique identifier of the complaint
        payload: Feedback details (rating, comments, satisfaction_level)
        current_user: User submitting feedback (must be complaint creator)
        service: Feedback service instance
        
    Returns:
        FeedbackResponse: Submitted feedback with timestamp
        
    Raises:
        HTTPException: If complaint not resolved, feedback exists, or user not authorized
    """
    return service.submit(
        complaint_id=complaint_id,
        payload=payload,
        user_id=current_user.id
    )


@router.put(
    "/{complaint_id}",
    response_model=FeedbackResponse,
    summary="Update feedback",
    description="Update previously submitted feedback. Only complaint creator can update their feedback.",
    responses={
        200: {"description": "Feedback updated successfully"},
        404: {"description": "Complaint or feedback not found"},
        403: {"description": "Not authorized to update feedback"},
    },
)
def update_feedback(
    complaint_id: str,
    payload: FeedbackRequest,
    current_user=Depends(deps.get_current_user),
    service: ComplaintFeedbackService = Depends(get_feedback_service),
) -> Any:
    """
    Update existing feedback.
    
    Args:
        complaint_id: Unique identifier of the complaint
        payload: Updated feedback details
        current_user: User updating feedback
        service: Feedback service instance
        
    Returns:
        FeedbackResponse: Updated feedback
        
    Raises:
        HTTPException: If feedback not found or user not authorized
    """
    return service.update(
        complaint_id=complaint_id,
        payload=payload,
        user_id=current_user.id
    )


@router.get(
    "/{complaint_id}",
    response_model=FeedbackResponse,
    summary="Get feedback for complaint",
    description="Retrieve feedback submitted for a specific complaint.",
    responses={
        200: {"description": "Feedback retrieved successfully"},
        404: {"description": "Complaint or feedback not found"},
    },
)
def get_feedback(
    complaint_id: str,
    current_user=Depends(deps.get_current_user),
    service: ComplaintFeedbackService = Depends(get_feedback_service),
) -> Any:
    """
    Get feedback for a complaint.
    
    Args:
        complaint_id: Unique identifier of the complaint
        current_user: Authenticated user requesting feedback
        service: Feedback service instance
        
    Returns:
        FeedbackResponse: Feedback details
        
    Raises:
        HTTPException: If complaint or feedback not found
    """
    return service.get(complaint_id, user_id=current_user.id)


@router.get(
    "/summary",
    response_model=FeedbackSummary,
    summary="Get feedback summary statistics",
    description="Get aggregated feedback statistics for a hostel including average ratings and satisfaction levels. Admin/Supervisor only.",
    responses={
        200: {"description": "Summary retrieved successfully"},
        400: {"description": "Invalid hostel ID"},
        403: {"description": "Admin/Supervisor access required"},
    },
)
def get_feedback_summary(
    hostel_id: str = Query(..., description="Hostel ID for feedback summary"),
    filters: FeedbackFilterParams = Depends(),
    supervisor=Depends(deps.get_supervisor_user),
    service: ComplaintFeedbackService = Depends(get_feedback_service),
) -> Any:
    """
    Get feedback summary statistics.
    
    Args:
        hostel_id: ID of the hostel
        filters: Optional date range and category filters
        supervisor: Supervisor/Admin user requesting summary
        service: Feedback service instance
        
    Returns:
        FeedbackSummary: Aggregated feedback statistics
    """
    return service.summary(hostel_id=hostel_id, filters=filters)


@router.get(
    "/analysis",
    response_model=FeedbackAnalysis,
    summary="Get detailed feedback analysis",
    description="Get comprehensive feedback analysis including trends, patterns, and insights. Admin only.",
    responses={
        200: {"description": "Analysis retrieved successfully"},
        400: {"description": "Invalid parameters"},
        403: {"description": "Admin access required"},
    },
)
def get_feedback_analysis(
    hostel_id: str = Query(..., description="Hostel ID for analysis"),
    time_period: Optional[str] = Query(None, description="Time period (7d, 30d, 90d, 1y)"),
    admin=Depends(deps.get_admin_user),
    service: ComplaintFeedbackService = Depends(get_feedback_service),
) -> Any:
    """
    Get detailed feedback analysis.
    
    Args:
        hostel_id: ID of the hostel
        time_period: Time period for analysis
        admin: Admin user requesting analysis
        service: Feedback service instance
        
    Returns:
        FeedbackAnalysis: Detailed analytics and insights
    """
    return service.analysis(hostel_id=hostel_id, time_period=time_period)