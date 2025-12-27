"""
Mess Menu Feedback API Endpoints

This module handles menu feedback submission, retrieval, and analysis.
"""

from typing import Any, List
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from app.core.dependencies import AuthenticationDependency
from app.services.mess.menu_feedback_service import MenuFeedbackService
from app.schemas.mess import (
    FeedbackResponse,
    FeedbackCreate,
    FeedbackSummary,
    FeedbackAnalysis,
)
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix="/mess/feedback",
    tags=["Mess - Feedback"],
)


async def get_feedback_service() -> MenuFeedbackService:
    """
    Dependency injection for MenuFeedbackService.
    
    Raises:
        NotImplementedError: When DI container is not configured
    """
    raise NotImplementedError(
        "MenuFeedbackService dependency injection not configured. "
        "Please implement this in your DI container."
    )


async def get_current_user(auth: AuthenticationDependency = Depends()) -> Any:
    """
    Get the currently authenticated user.
    
    Args:
        auth: Authentication dependency
        
    Returns:
        Current authenticated user object
    """
    return auth.get_current_user()


@router.post(
    "",
    response_model=FeedbackResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit menu feedback",
    description="Submit feedback and rating for a menu. Students can submit one feedback per menu.",
    responses={
        201: {"description": "Feedback submitted successfully"},
        400: {"description": "Invalid feedback data or duplicate submission"},
        404: {"description": "Menu not found"},
    },
)
async def submit_feedback(
    payload: FeedbackCreate,
    feedback_service: MenuFeedbackService = Depends(get_feedback_service),
    current_user: Any = Depends(get_current_user),
) -> FeedbackResponse:
    """
    Submit feedback for a menu.
    
    Args:
        payload: Feedback data including rating and comments
        feedback_service: Menu feedback service instance
        current_user: Currently authenticated student
        
    Returns:
        FeedbackResponse: Created feedback record
        
    Raises:
        HTTPException: If submission fails or menu not found
    """
    logger.info(
        f"Student {current_user.id} submitting feedback for menu {payload.menu_id}"
    )
    
    result = feedback_service.submit_feedback(
        student_id=current_user.id,
        data=payload,
    )
    
    if result.is_err():
        error = result.unwrap_err()
        logger.error(f"Failed to submit feedback: {error}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        )
    
    feedback = result.unwrap()
    logger.info(f"Feedback {feedback.id} submitted successfully")
    return feedback


@router.get(
    "/menu/{menu_id}",
    response_model=List[FeedbackResponse],
    status_code=status.HTTP_200_OK,
    summary="Get feedback for menu",
    description="Retrieve all feedback entries for a specific menu.",
    responses={
        200: {"description": "Feedback retrieved successfully"},
        404: {"description": "Menu not found"},
    },
)
async def get_menu_feedback(
    menu_id: str = Path(..., description="Unique menu identifier"),
    include_comments: bool = Query(
        True,
        description="Include comment text in response",
    ),
    limit: int = Query(
        100,
        ge=1,
        le=500,
        description="Maximum number of feedback entries to return",
    ),
    offset: int = Query(
        0,
        ge=0,
        description="Number of feedback entries to skip",
    ),
    feedback_service: MenuFeedbackService = Depends(get_feedback_service),
    current_user: Any = Depends(get_current_user),
) -> List[FeedbackResponse]:
    """
    Get all feedback for a specific menu.
    
    Args:
        menu_id: Unique identifier of the menu
        include_comments: Whether to include comment text
        limit: Maximum number of results
        offset: Pagination offset
        feedback_service: Menu feedback service instance
        current_user: Currently authenticated user
        
    Returns:
        List[FeedbackResponse]: List of feedback entries
        
    Raises:
        HTTPException: If menu not found
    """
    logger.debug(
        f"Fetching feedback for menu {menu_id} (limit: {limit}, offset: {offset})"
    )
    
    result = feedback_service.get_feedback_for_menu(
        menu_id=menu_id,
        include_comments=include_comments,
        limit=limit,
        offset=offset,
    )
    
    if result.is_err():
        error = result.unwrap_err()
        logger.error(f"Failed to fetch feedback for menu {menu_id}: {error}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Menu with ID {menu_id} not found",
        )
    
    feedback_list = result.unwrap()
    logger.debug(f"Retrieved {len(feedback_list)} feedback entries for menu {menu_id}")
    return feedback_list


@router.get(
    "/menu/{menu_id}/summary",
    response_model=FeedbackSummary,
    status_code=status.HTTP_200_OK,
    summary="Get feedback summary for menu",
    description="Get aggregated feedback statistics and ratings for a menu.",
    responses={
        200: {"description": "Feedback summary retrieved successfully"},
        404: {"description": "Menu not found"},
    },
)
async def get_feedback_summary(
    menu_id: str = Path(..., description="Unique menu identifier"),
    feedback_service: MenuFeedbackService = Depends(get_feedback_service),
    current_user: Any = Depends(get_current_user),
) -> FeedbackSummary:
    """
    Get feedback summary statistics for a menu.
    
    Args:
        menu_id: Unique identifier of the menu
        feedback_service: Menu feedback service instance
        current_user: Currently authenticated user
        
    Returns:
        FeedbackSummary: Aggregated feedback statistics
        
    Raises:
        HTTPException: If menu not found
    """
    logger.debug(f"Fetching feedback summary for menu {menu_id}")
    
    result = feedback_service.get_ratings_summary(menu_id=menu_id)
    
    if result.is_err():
        error = result.unwrap_err()
        logger.error(f"Failed to fetch feedback summary for menu {menu_id}: {error}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Menu with ID {menu_id} not found",
        )
    
    summary = result.unwrap()
    logger.debug(f"Retrieved feedback summary for menu {menu_id}")
    return summary


@router.get(
    "/analysis",
    response_model=FeedbackAnalysis,
    status_code=status.HTTP_200_OK,
    summary="Get feedback analysis",
    description="Get comprehensive feedback analysis for a hostel within a date range.",
    responses={
        200: {"description": "Feedback analysis retrieved successfully"},
        400: {"description": "Invalid date range or parameters"},
        404: {"description": "Hostel not found"},
    },
)
async def get_feedback_analysis(
    hostel_id: str = Query(..., description="Unique hostel identifier"),
    start_date: str = Query(
        ...,
        regex=r"^\d{4}-\d{2}-\d{2}$",
        description="Start date in YYYY-MM-DD format",
    ),
    end_date: str = Query(
        ...,
        regex=r"^\d{4}-\d{2}-\d{2}$",
        description="End date in YYYY-MM-DD format",
    ),
    feedback_service: MenuFeedbackService = Depends(get_feedback_service),
    current_user: Any = Depends(get_current_user),
) -> FeedbackAnalysis:
    """
    Get detailed feedback analysis for a hostel.
    
    Args:
        hostel_id: Unique identifier of the hostel
        start_date: Analysis period start date (YYYY-MM-DD)
        end_date: Analysis period end date (YYYY-MM-DD)
        feedback_service: Menu feedback service instance
        current_user: Currently authenticated user
        
    Returns:
        FeedbackAnalysis: Comprehensive feedback analysis
        
    Raises:
        HTTPException: If parameters invalid or hostel not found
    """
    # Validate date range
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d").date()
        end = datetime.strptime(end_date, "%Y-%m-%d").date()
        
        if start > end:
            raise ValueError("Start date must be before or equal to end date")
        
        if (end - start).days > 365:
            raise ValueError("Date range cannot exceed 365 days")
            
    except ValueError as e:
        logger.error(f"Invalid date range: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    
    logger.info(
        f"Generating feedback analysis for hostel {hostel_id} "
        f"from {start_date} to {end_date}"
    )
    
    result = feedback_service.get_feedback_analysis(
        hostel_id=hostel_id,
        start_date=start_date,
        end_date=end_date,
    )
    
    if result.is_err():
        error = result.unwrap_err()
        logger.error(f"Failed to generate feedback analysis: {error}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        )
    
    analysis = result.unwrap()
    logger.info(f"Feedback analysis generated successfully for hostel {hostel_id}")
    return analysis


@router.get(
    "/my-feedback",
    response_model=List[FeedbackResponse],
    status_code=status.HTTP_200_OK,
    summary="Get my submitted feedback",
    description="Retrieve all feedback submitted by the current student.",
    responses={
        200: {"description": "Feedback retrieved successfully"},
    },
)
async def get_my_feedback(
    limit: int = Query(50, ge=1, le=200, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    feedback_service: MenuFeedbackService = Depends(get_feedback_service),
    current_user: Any = Depends(get_current_user),
) -> List[FeedbackResponse]:
    """
    Get all feedback submitted by the current student.
    
    Args:
        limit: Maximum number of results
        offset: Pagination offset
        feedback_service: Menu feedback service instance
        current_user: Currently authenticated student
        
    Returns:
        List[FeedbackResponse]: Student's feedback history
    """
    logger.debug(f"Fetching feedback history for student {current_user.id}")
    
    result = feedback_service.get_student_feedback_history(
        student_id=current_user.id,
        limit=limit,
        offset=offset,
    )
    
    if result.is_err():
        logger.error(f"Failed to fetch student feedback: {result.unwrap_err()}")
        return []
    
    feedback_list = result.unwrap()
    logger.debug(f"Retrieved {len(feedback_list)} feedback entries")
    return feedback_list