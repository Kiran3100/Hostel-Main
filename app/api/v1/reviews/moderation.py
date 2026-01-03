"""
Review moderation endpoints for admin and moderator actions.
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, Path, Query, status, HTTPException
from fastapi.security import HTTPBearer

from app.core.dependencies import get_current_user_dependency, require_role
from app.core.exceptions import NotFoundError, PermissionError, ValidationError
from app.services.review.review_moderation_service import ReviewModerationService
from app.schemas.review import (
    PendingReview,
    ModerationRequest,
    FlagReview,
    ModerationStats,
    ReviewDetail,
)

router = APIRouter(
    prefix="/reviews/moderation",
    tags=["Reviews - Moderation"],
)

security = HTTPBearer()


# ========== Dependency Injection ========== #

def get_moderation_service() -> ReviewModerationService:
    """Provide ReviewModerationService instance."""
    from app.core.container import get_container
    container = get_container()
    return container.review_moderation_service()


# ========== Endpoints ========== #

@router.get(
    "/queue",
    response_model=List[PendingReview],
    summary="Get moderation queue",
    description="Retrieve reviews pending moderation. Admin/Moderator only.",
    dependencies=[Depends(require_role(["admin", "moderator"]))],
    responses={
        200: {"description": "Moderation queue retrieved successfully"},
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
    },
)
async def get_moderation_queue(
    status_filter: Optional[str] = Query(
        "pending",
        alias="status",
        regex="^(pending|flagged|all)$",
        description="Filter by status"
    ),
    priority: Optional[str] = Query(
        None,
        regex="^(high|medium|low)$",
        description="Filter by priority level"
    ),
    hostel_id: Optional[str] = Query(
        None,
        description="Filter by hostel"
    ),
    sort_by: str = Query(
        "created_at",
        regex="^(created_at|flag_count|rating)$",
        description="Sort field"
    ),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    moderation_service: ReviewModerationService = Depends(get_moderation_service),
    current_user = Depends(get_current_user_dependency),
) -> dict:
    """
    Retrieve the moderation queue with filtering and sorting.
    
    **Access:** Admin and Moderator roles only
    
    **Query Parameters:**
    - status: Filter by review status (pending/flagged/all)
    - priority: Filter by priority (high/medium/low)
    - hostel_id: Filter by specific hostel
    - sort_by: Sort field
    - page: Page number
    - page_size: Items per page
    
    **Returns:**
    - Paginated list of reviews requiring moderation
    - Includes flag information and priority indicators
    """
    filters = {
        "status": status_filter,
        "priority": priority,
        "hostel_id": hostel_id,
        "sort_by": sort_by,
        "page": page,
        "page_size": page_size,
    }
    
    result = moderation_service.get_moderation_queue(filters=filters)
    
    if result.is_err():
        raise HTTPException(status_code=400, detail=str(result.err()))
    
    return result.unwrap()


@router.post(
    "/{review_id}/moderate",
    response_model=ReviewDetail,
    summary="Moderate a review",
    description="Approve or reject a review. Admin/Moderator only.",
    dependencies=[Depends(require_role(["admin", "moderator"]))],
    responses={
        200: {"description": "Review moderated successfully"},
        400: {"description": "Invalid moderation request"},
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
        404: {"description": "Review not found"},
    },
)
async def moderate_review(
    review_id: str = Path(
        ...,
        description="Review ID to moderate"
    ),
    payload: ModerationRequest = ...,
    moderation_service: ReviewModerationService = Depends(get_moderation_service),
    current_user = Depends(get_current_user_dependency),
) -> ReviewDetail:
    """
    Approve or reject a review with optional reason.
    
    **Access:** Admin and Moderator roles only
    
    **Actions:**
    - approve: Make review publicly visible
    - reject: Hide review from public view
    
    **Request Body:**
    - action: "approve" or "reject" (required)
    - reason: Explanation for action (optional but recommended for rejections)
    
    **Side Effects:**
    - Updates hostel rating statistics (for approvals)
    - Sends notification to reviewer
    - Records moderation action in audit log
    """
    result = moderation_service.moderate_review(
        review_id=review_id,
        moderator_id=current_user.id,
        action=payload.action,
        reason=payload.reason,
    )
    
    if result.is_err():
        error = result.err()
        if isinstance(error, NotFoundError):
            raise HTTPException(status_code=404, detail=str(error))
        elif isinstance(error, ValidationError):
            raise HTTPException(status_code=400, detail=str(error))
        raise HTTPException(status_code=500, detail="Internal server error")
    
    return result.unwrap()


@router.post(
    "/{review_id}/flag",
    status_code=status.HTTP_201_CREATED,
    summary="Flag a review",
    description="Flag a review as inappropriate or problematic.",
    responses={
        201: {"description": "Review flagged successfully"},
        400: {"description": "Invalid flag request"},
        401: {"description": "Authentication required"},
        404: {"description": "Review not found"},
        409: {"description": "User has already flagged this review"},
    },
)
async def flag_review(
    review_id: str = Path(
        ...,
        description="Review ID to flag"
    ),
    payload: FlagReview = ...,
    moderation_service: ReviewModerationService = Depends(get_moderation_service),
    current_user = Depends(get_current_user_dependency),
) -> dict:
    """
    Flag a review for moderator attention.
    
    **Anyone can flag a review** - Authentication required
    
    **Flag Reasons:**
    - spam: Promotional or irrelevant content
    - inappropriate: Offensive or unsuitable content
    - offensive: Hate speech or harassment
    - fake: Suspected fake or fraudulent review
    - other: Other issues (provide details)
    
    **Request Body:**
    - reason: Flag reason (required)
    - details: Additional context (optional but recommended)
    
    **Limitations:**
    - Users can only flag a review once
    - Multiple flags increase priority for moderation
    """
    result = moderation_service.flag_review(
        review_id=review_id,
        user_id=current_user.id,
        flag_reason=payload.flag_reason,
        details=payload.description,
    )
    
    if result.is_err():
        error = result.err()
        if isinstance(error, NotFoundError):
            raise HTTPException(status_code=404, detail=str(error))
        elif isinstance(error, ValidationError):
            raise HTTPException(status_code=400, detail=str(error))
        elif "already flagged" in str(error).lower():
            raise HTTPException(status_code=409, detail=str(error))
        raise HTTPException(status_code=500, detail="Internal server error")
    
    return result.unwrap()


@router.delete(
    "/{review_id}/flag",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove flag from review",
    description="Remove user's flag from a review.",
    responses={
        204: {"description": "Flag removed successfully"},
        401: {"description": "Authentication required"},
        404: {"description": "Review or flag not found"},
    },
)
async def remove_flag(
    review_id: str = Path(
        ...,
        description="Review ID"
    ),
    moderation_service: ReviewModerationService = Depends(get_moderation_service),
    current_user = Depends(get_current_user_dependency),
) -> None:
    """
    Remove a flag that the current user placed on a review.
    
    **Use Case:**
    - User flagged review by mistake
    - Issue has been resolved
    """
    result = moderation_service.remove_flag(
        review_id=review_id,
        user_id=current_user.id
    )
    
    if result.is_err():
        error = result.err()
        if isinstance(error, NotFoundError):
            raise HTTPException(status_code=404, detail=str(error))
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get(
    "/stats",
    response_model=ModerationStats,
    summary="Get moderation statistics",
    description="Retrieve overall moderation statistics. Admin/Moderator only.",
    dependencies=[Depends(require_role(["admin", "moderator"]))],
    responses={
        200: {"description": "Statistics retrieved successfully"},
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
    },
)
async def get_moderation_stats(
    time_range: str = Query(
        "all",
        regex="^(24h|7d|30d|all)$",
        description="Time range for statistics"
    ),
    moderation_service: ReviewModerationService = Depends(get_moderation_service),
    current_user = Depends(get_current_user_dependency),
) -> ModerationStats:
    """
    Get comprehensive moderation statistics.
    
    **Access:** Admin and Moderator roles only
    
    **Returns:**
    - Count of reviews by status (pending/approved/rejected/flagged)
    - Average moderation time
    - Moderation rate trends
    - Top moderators
    
    **Query Parameters:**
    - time_range: Filter statistics by time period
      - 24h: Last 24 hours
      - 7d: Last 7 days
      - 30d: Last 30 days
      - all: All time
    """
    result = moderation_service.get_moderation_stats(time_range=time_range)
    
    if result.is_err():
        raise HTTPException(status_code=500, detail="Internal server error")
    
    return result.unwrap()


@router.post(
    "/bulk-moderate",
    summary="Bulk moderate reviews",
    description="Moderate multiple reviews at once. Admin only.",
    dependencies=[Depends(require_role(["admin"]))],
    responses={
        200: {"description": "Bulk moderation completed"},
        400: {"description": "Invalid request"},
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
    },
)
async def bulk_moderate(
    review_ids: List[str] = Query(
        ...,
        description="List of review IDs to moderate",
        max_items=50
    ),
    action: str = Query(
        ...,
        regex="^(approve|reject)$",
        description="Action to apply"
    ),
    reason: Optional[str] = Query(
        None,
        max_length=500,
        description="Reason for bulk action"
    ),
    moderation_service: ReviewModerationService = Depends(get_moderation_service),
    current_user = Depends(get_current_user_dependency),
) -> dict:
    """
    Moderate multiple reviews with a single action.
    
    **Access:** Admin only
    
    **Limitations:**
    - Maximum 50 reviews per request
    - All reviews must exist
    
    **Returns:**
    - success_count: Number of successfully moderated reviews
    - failed_count: Number of failed moderations
    - errors: List of errors for failed items
    """
    result = moderation_service.bulk_moderate(
        review_ids=review_ids,
        moderator_id=current_user.id,
        action=action,
        reason=reason
    )
    
    if result.is_err():
        raise HTTPException(status_code=400, detail=str(result.err()))
    
    return result.unwrap()