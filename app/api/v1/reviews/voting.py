"""
Review voting endpoints for marking reviews as helpful or unhelpful.
"""
from typing import Optional

from fastapi import APIRouter, Depends, Path, Query, status, HTTPException

from app.core.dependencies import get_current_user_dependency
from app.core.exceptions import NotFoundError, ValidationError
from app.services.review.review_voting_service import ReviewVotingService
from app.schemas.review import (
    VoteType,
    VoteResponse,
    HostelVotingStats,
)

router = APIRouter(
    prefix="/reviews/votes",
    tags=["Reviews - Voting"],
)


# ========== Dependency Injection ========== #

def get_voting_service() -> ReviewVotingService:
    """Provide ReviewVotingService instance."""
    from app.core.container import get_container
    container = get_container()
    return container.review_voting_service()


# ========== Endpoints ========== #

@router.post(
    "/{review_id}",
    response_model=VoteResponse,
    summary="Cast vote on review",
    description="Mark a review as helpful or unhelpful.",
    responses={
        200: {"description": "Vote cast successfully"},
        400: {"description": "Invalid vote request"},
        401: {"description": "Authentication required"},
        404: {"description": "Review not found"},
        409: {"description": "Cannot vote on own review"},
    },
)
async def cast_vote(
    review_id: str = Path(
        ...,
        description="Review ID to vote on"
    ),
    vote_type: VoteType = Query(
        ...,
        description="Type of vote: helpful or unhelpful"
    ),
    voting_service: ReviewVotingService = Depends(get_voting_service),
    current_user = Depends(get_current_user_dependency),
) -> VoteResponse:
    """
    Cast or update a vote on a review.
    
    **Voting Rules:**
    - Users can vote on any review except their own
    - One vote per user per review
    - Changing vote updates the counts
    - Vote affects review helpfulness score
    
    **Query Parameters:**
    - vote_type: "helpful" or "unhelpful"
    
    **Returns:**
    - Updated vote counts
    - New helpfulness score
    - User's current vote status
    
    **Use Cases:**
    - Users can indicate which reviews are most useful
    - Helps surface high-quality reviews
    - Filters spam or unhelpful content
    """
    result = voting_service.cast_vote(
        review_id=review_id,
        user_id=current_user.id,
        vote_type=vote_type,
    )
    
    if result.is_err():
        error = result.err()
        if isinstance(error, NotFoundError):
            raise HTTPException(status_code=404, detail=str(error))
        elif isinstance(error, ValidationError):
            raise HTTPException(status_code=400, detail=str(error))
        elif "own review" in str(error).lower():
            raise HTTPException(status_code=409, detail=str(error))
        raise HTTPException(status_code=500, detail="Internal server error")
    
    return result.unwrap()


@router.delete(
    "/{review_id}",
    response_model=VoteResponse,
    summary="Remove vote",
    description="Remove a previously cast vote from a review.",
    responses={
        200: {"description": "Vote removed successfully"},
        401: {"description": "Authentication required"},
        404: {"description": "Review or vote not found"},
    },
)
async def remove_vote(
    review_id: str = Path(
        ...,
        description="Review ID"
    ),
    voting_service: ReviewVotingService = Depends(get_voting_service),
    current_user = Depends(get_current_user_dependency),
) -> VoteResponse:
    """
    Remove a vote from a review.
    
    **Behavior:**
    - Removes user's vote if exists
    - Updates vote counts
    - Recalculates helpfulness score
    
    **Returns:**
    - Updated vote counts after removal
    - Updated helpfulness score
    
    **Use Case:**
    - User changes mind about vote
    - Accidentally voted
    """
    result = voting_service.remove_vote(
        review_id=review_id,
        user_id=current_user.id,
    )
    
    if result.is_err():
        error = result.err()
        if isinstance(error, NotFoundError):
            raise HTTPException(status_code=404, detail=str(error))
        raise HTTPException(status_code=500, detail="Internal server error")
    
    return result.unwrap()


@router.get(
    "/{review_id}",
    response_model=VoteResponse,
    summary="Get vote status",
    description="Get current vote status and counts for a review.",
    responses={
        200: {"description": "Vote status retrieved successfully"},
        404: {"description": "Review not found"},
    },
)
async def get_vote_status(
    review_id: str = Path(
        ...,
        description="Review ID"
    ),
    voting_service: ReviewVotingService = Depends(get_voting_service),
    current_user = Depends(get_current_user_dependency),
) -> VoteResponse:
    """
    Get voting information for a review.
    
    **Returns:**
    - Total helpful votes
    - Total unhelpful votes
    - Helpfulness score (0-1)
    - Current user's vote (if any)
    
    **Use Case:**
    - Display vote counts on review
    - Show user's previous vote
    - Calculate review quality score
    """
    result = voting_service.get_vote_status(
        review_id=review_id,
        user_id=current_user.id,
    )
    
    if result.is_err():
        error = result.err()
        if isinstance(error, NotFoundError):
            raise HTTPException(status_code=404, detail=str(error))
        raise HTTPException(status_code=500, detail="Internal server error")
    
    return result.unwrap()


@router.get(
    "/stats/{hostel_id}",
    response_model=HostelVotingStats,
    summary="Get voting stats for hostel",
    description="Retrieve aggregated voting statistics for a hostel's reviews.",
    responses={
        200: {"description": "Statistics retrieved successfully"},
        404: {"description": "Hostel not found"},
    },
)
async def get_voting_stats(
    hostel_id: str = Path(
        ...,
        description="Hostel ID"
    ),
    limit: int = Query(
        5,
        ge=1,
        le=20,
        description="Number of top reviews to return"
    ),
    voting_service: ReviewVotingService = Depends(get_voting_service),
) -> HostelVotingStats:
    """
    Get aggregated voting statistics for a hostel.
    
    **Returns:**
    - Total votes across all reviews
    - Total helpful votes
    - Total unhelpful votes
    - Average helpfulness score
    - Most helpful reviews (top N)
    
    **Query Parameters:**
    - limit: Number of most helpful reviews to include (1-20)
    
    **Use Cases:**
    - Display most helpful reviews prominently
    - Analyze review quality for hostel
    - Identify valuable reviewers
    """
    result = voting_service.get_voting_stats_for_hostel(
        hostel_id=hostel_id,
        limit=limit
    )
    
    if result.is_err():
        error = result.err()
        if isinstance(error, NotFoundError):
            raise HTTPException(status_code=404, detail=f"Hostel {hostel_id} not found")
        raise HTTPException(status_code=500, detail="Internal server error")
    
    return result.unwrap()


@router.get(
    "/user/history",
    summary="Get user voting history",
    description="Retrieve the current user's voting history.",
    responses={
        200: {"description": "Voting history retrieved successfully"},
        401: {"description": "Authentication required"},
    },
)
async def get_user_voting_history(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    voting_service: ReviewVotingService = Depends(get_voting_service),
    current_user = Depends(get_current_user_dependency),
) -> dict:
    """
    Get the current user's voting history.
    
    **Returns:**
    - Paginated list of votes
    - Review information for each vote
    - Vote type (helpful/unhelpful)
    - Timestamp of vote
    
    **Use Case:**
    - User profile page
    - Review voting history
    """
    result = voting_service.get_user_voting_history(
        user_id=current_user.id,
        page=page,
        page_size=page_size
    )
    
    if result.is_err():
        raise HTTPException(status_code=500, detail="Internal server error")
    
    return result.unwrap()