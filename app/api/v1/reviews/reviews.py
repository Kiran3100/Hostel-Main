"""
Main review endpoints for CRUD operations and summary statistics.
"""
from typing import Optional, List

from fastapi import APIRouter, Depends, Path, Query, status, HTTPException
from fastapi.responses import JSONResponse

from app.core.dependencies import AuthenticationDependency, get_current_user_dependency
from app.core.exceptions import ValidationError, NotFoundError, PermissionError
from app.services.review.review_service import ReviewService
from app.schemas.review import (
    ReviewDetail,
    ReviewListItem,
    ReviewCreate,
    ReviewUpdate,
    ReviewSummary,
    ReviewEligibility,
    PaginatedReviewResponse,
)

router = APIRouter(
    prefix="/reviews",
    tags=["Reviews"],
)


# ========== Dependency Injection ========== #

def get_review_service() -> ReviewService:
    """
    Dependency to provide ReviewService instance.
    Override this in production with actual implementation.
    """
    from app.core.container import get_container
    container = get_container()
    return container.review_service()


# ========== Endpoints ========== #

@router.post(
    "",
    response_model=ReviewDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a review",
    description="Submit a new review for a hostel. User must have a valid booking to review.",
    responses={
        201: {"description": "Review successfully created"},
        400: {"description": "Invalid review data or user not eligible"},
        401: {"description": "Authentication required"},
        404: {"description": "Hostel not found"},
    },
)
async def submit_review(
    payload: ReviewCreate,
    review_service: ReviewService = Depends(get_review_service),
    current_user = Depends(get_current_user_dependency),
) -> ReviewDetail:
    """
    Submit a new review for a hostel.
    
    **Requirements:**
    - User must be authenticated
    - User must have completed a booking at the hostel
    - User can only submit one review per hostel
    - Review must meet minimum content requirements
    
    **Request Body:**
    - rating: Overall rating (1-5) - Required
    - title: Review title (3-100 chars) - Required
    - content: Review content (10-2000 chars) - Required
    - hostel_id: ID of hostel being reviewed - Required
    - Additional ratings and details - Optional
    """
    result = review_service.submit_review(
        data=payload,
        user_id=current_user.id
    )
    
    if result.is_err():
        error = result.err()
        if isinstance(error, ValidationError):
            raise HTTPException(status_code=400, detail=str(error))
        elif isinstance(error, NotFoundError):
            raise HTTPException(status_code=404, detail=str(error))
        else:
            raise HTTPException(status_code=500, detail="Internal server error")
    
    return result.unwrap()


@router.get(
    "",
    response_model=PaginatedReviewResponse,
    summary="List reviews",
    description="Retrieve a paginated list of reviews with optional filtering.",
    responses={
        200: {"description": "Successfully retrieved reviews"},
        400: {"description": "Invalid query parameters"},
    },
)
async def list_reviews(
    hostel_id: Optional[str] = Query(
        None,
        description="Filter by hostel ID",
        example="hostel_123"
    ),
    rating: Optional[int] = Query(
        None,
        ge=1,
        le=5,
        description="Filter by minimum rating"
    ),
    status_filter: Optional[str] = Query(
        None,
        alias="status",
        description="Filter by review status (pending/approved/rejected)"
    ),
    search: Optional[str] = Query(
        None,
        min_length=2,
        max_length=100,
        description="Search in review title and content"
    ),
    sort_by: str = Query(
        "created_at",
        regex="^(created_at|rating|helpful_count|updated_at)$",
        description="Sort field"
    ),
    sort_order: str = Query(
        "desc",
        regex="^(asc|desc)$",
        description="Sort order"
    ),
    page: int = Query(
        1,
        ge=1,
        description="Page number"
    ),
    page_size: int = Query(
        20,
        ge=1,
        le=100,
        description="Items per page"
    ),
    review_service: ReviewService = Depends(get_review_service),
) -> PaginatedReviewResponse:
    """
    List reviews with comprehensive filtering and sorting options.
    
    **Query Parameters:**
    - hostel_id: Filter reviews for a specific hostel
    - rating: Show only reviews with this rating or higher
    - status: Filter by review status
    - search: Full-text search in review content
    - sort_by: Field to sort by
    - sort_order: Ascending or descending order
    - page: Page number for pagination
    - page_size: Number of items per page (max 100)
    """
    filters = {
        "hostel_id": hostel_id,
        "rating": rating,
        "status": status_filter,
        "search": search,
        "sort_by": sort_by,
        "sort_order": sort_order,
        "page": page,
        "page_size": page_size,
    }
    
    # Remove None values
    filters = {k: v for k, v in filters.items() if v is not None}
    
    result = review_service.list_reviews_paginated(filters=filters)
    
    if result.is_err():
        raise HTTPException(status_code=400, detail=str(result.err()))
    
    return result.unwrap()


@router.get(
    "/{review_id}",
    response_model=ReviewDetail,
    summary="Get review details",
    description="Retrieve detailed information about a specific review.",
    responses={
        200: {"description": "Review details retrieved successfully"},
        404: {"description": "Review not found"},
    },
)
async def get_review(
    review_id: str = Path(
        ...,
        description="Unique review identifier",
        example="rev_abc123"
    ),
    review_service: ReviewService = Depends(get_review_service),
) -> ReviewDetail:
    """
    Get comprehensive details for a specific review.
    
    **Returns:**
    - Full review information including ratings, content, and metadata
    - Reviewer information (anonymized if needed)
    - Voting statistics
    - Owner response (if available)
    - Verification status
    """
    result = review_service.get_review(review_id=review_id)
    
    if result.is_err():
        error = result.err()
        if isinstance(error, NotFoundError):
            raise HTTPException(status_code=404, detail=f"Review {review_id} not found")
        raise HTTPException(status_code=500, detail="Internal server error")
    
    return result.unwrap()


@router.patch(
    "/{review_id}",
    response_model=ReviewDetail,
    summary="Update review",
    description="Update an existing review. Only the review author can update their review.",
    responses={
        200: {"description": "Review updated successfully"},
        400: {"description": "Invalid update data"},
        401: {"description": "Authentication required"},
        403: {"description": "Not authorized to update this review"},
        404: {"description": "Review not found"},
    },
)
async def update_review(
    review_id: str = Path(
        ...,
        description="Review ID to update"
    ),
    payload: ReviewUpdate = ...,
    review_service: ReviewService = Depends(get_review_service),
    current_user = Depends(get_current_user_dependency),
) -> ReviewDetail:
    """
    Update an existing review.
    
    **Authorization:**
    - Only the original reviewer can update their review
    - Reviews cannot be updated after a certain time period (configurable)
    - Approved reviews may require re-moderation after update
    
    **Request Body:**
    - All fields are optional
    - Only provided fields will be updated
    - Content updates may trigger re-moderation
    """
    result = review_service.update_review(
        review_id=review_id,
        user_id=current_user.id,
        data=payload,
    )
    
    if result.is_err():
        error = result.err()
        if isinstance(error, NotFoundError):
            raise HTTPException(status_code=404, detail=str(error))
        elif isinstance(error, PermissionError):
            raise HTTPException(status_code=403, detail=str(error))
        elif isinstance(error, ValidationError):
            raise HTTPException(status_code=400, detail=str(error))
        raise HTTPException(status_code=500, detail="Internal server error")
    
    return result.unwrap()


@router.delete(
    "/{review_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete review",
    description="Soft delete a review. Only the review author or admin can delete.",
    responses={
        204: {"description": "Review deleted successfully"},
        401: {"description": "Authentication required"},
        403: {"description": "Not authorized to delete this review"},
        404: {"description": "Review not found"},
    },
)
async def delete_review(
    review_id: str = Path(
        ...,
        description="Review ID to delete"
    ),
    review_service: ReviewService = Depends(get_review_service),
    current_user = Depends(get_current_user_dependency),
) -> None:
    """
    Soft delete a review.
    
    **Authorization:**
    - Review author can delete their own review
    - Admin/moderators can delete any review
    
    **Behavior:**
    - Review is soft-deleted (not permanently removed)
    - Hostel rating statistics are recalculated
    - Deleted reviews can be restored by admin
    """
    result = review_service.delete_review(
        review_id=review_id,
        user_id=current_user.id
    )
    
    if result.is_err():
        error = result.err()
        if isinstance(error, NotFoundError):
            raise HTTPException(status_code=404, detail=str(error))
        elif isinstance(error, PermissionError):
            raise HTTPException(status_code=403, detail=str(error))
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get(
    "/hostels/{hostel_id}/summary",
    response_model=ReviewSummary,
    summary="Get review summary for hostel",
    description="Retrieve aggregated review statistics and insights for a hostel.",
    responses={
        200: {"description": "Summary retrieved successfully"},
        404: {"description": "Hostel not found"},
    },
)
async def get_review_summary(
    hostel_id: str = Path(
        ...,
        description="Hostel ID",
        example="hostel_123"
    ),
    review_service: ReviewService = Depends(get_review_service),
) -> ReviewSummary:
    """
    Get comprehensive review statistics for a hostel.
    
    **Returns:**
    - Average ratings (overall and detailed categories)
    - Rating distribution (1-5 stars)
    - Total review count
    - Verified review count
    - Top tags and common feedback
    - Response rate statistics
    
    **Use Cases:**
    - Display on hostel listing page
    - Analytics dashboard
    - Comparison between hostels
    """
    result = review_service.get_hostel_summary(hostel_id=hostel_id)
    
    if result.is_err():
        error = result.err()
        if isinstance(error, NotFoundError):
            raise HTTPException(status_code=404, detail=f"Hostel {hostel_id} not found")
        raise HTTPException(status_code=500, detail="Internal server error")
    
    return result.unwrap()


@router.get(
    "/eligibility/check",
    response_model=ReviewEligibility,
    summary="Check review eligibility",
    description="Check if the current user is eligible to review a specific hostel.",
    responses={
        200: {"description": "Eligibility check completed"},
        401: {"description": "Authentication required"},
    },
)
async def check_eligibility(
    hostel_id: str = Query(
        ...,
        description="Hostel ID to check eligibility for",
        example="hostel_123"
    ),
    review_service: ReviewService = Depends(get_review_service),
    current_user = Depends(get_current_user_dependency),
) -> ReviewEligibility:
    """
    Check if user can submit a review for the specified hostel.
    
    **Eligibility Criteria:**
    - User must have completed a booking at the hostel
    - Booking must be within eligible timeframe
    - User hasn't already reviewed this hostel
    - User account must be in good standing
    
    **Returns:**
    - is_eligible: Boolean indicating eligibility
    - reason: Explanation if not eligible
    - can_review_after: Date when user becomes eligible (if applicable)
    - existing_review_id: If user already has a review
    """
    result = review_service.check_eligibility(
        user_id=current_user.id,
        hostel_id=hostel_id
    )
    
    if result.is_err():
        raise HTTPException(status_code=400, detail=str(result.err()))
    
    return result.unwrap()


@router.get(
    "/users/{user_id}/reviews",
    response_model=PaginatedReviewResponse,
    summary="Get user's reviews",
    description="Retrieve all reviews submitted by a specific user.",
    responses={
        200: {"description": "User reviews retrieved successfully"},
        404: {"description": "User not found"},
    },
)
async def get_user_reviews(
    user_id: str = Path(
        ...,
        description="User ID"
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    review_service: ReviewService = Depends(get_review_service),
) -> PaginatedReviewResponse:
    """
    Get all reviews submitted by a specific user.
    
    **Use Cases:**
    - User profile page
    - Review history
    - User reputation display
    """
    result = review_service.get_user_reviews(
        user_id=user_id,
        page=page,
        page_size=page_size
    )
    
    if result.is_err():
        error = result.err()
        if isinstance(error, NotFoundError):
            raise HTTPException(status_code=404, detail=str(error))
        raise HTTPException(status_code=500, detail="Internal server error")
    
    return result.unwrap()