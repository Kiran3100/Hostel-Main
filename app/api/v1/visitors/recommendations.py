"""
Visitor recommendations endpoints.

This module provides endpoints for personalized hostel recommendations:
- Get recommendations based on behavior and preferences
- Refresh recommendations
- Provide feedback on recommendations
- Get recommendation explanations
"""

from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, Query, Body, Path

from app.core.dependencies import get_current_user, get_visitor_recommendation_service
from app.schemas.visitor import (
    RecommendedHostel,
    RecommendationFeedback,
    RecommendationExplanation,
)
from app.services.visitor.visitor_recommendation_service import VisitorRecommendationService

# Type aliases for cleaner dependency injection
CurrentUser = Annotated[dict, Depends(get_current_user)]
RecommendationServiceDep = Annotated[
    VisitorRecommendationService,
    Depends(get_visitor_recommendation_service)
]

router = APIRouter(
    prefix="/visitors/me/recommendations",
    tags=["Visitors - Recommendations"],
)


@router.get(
    "",
    response_model=List[RecommendedHostel],
    summary="Get personalized recommendations",
    description="Retrieve personalized hostel recommendations based on visitor behavior and preferences.",
    responses={
        200: {
            "description": "Recommendations retrieved successfully",
            "model": List[RecommendedHostel],
        },
        401: {"description": "Authentication required"},
    },
)
async def get_recommendations(
    current_user: CurrentUser,
    recommendation_service: RecommendationServiceDep,
    limit: int = Query(
        default=10,
        ge=1,
        le=100,
        description="Maximum number of recommendations to return"
    ),
    include_visited: bool = Query(
        default=False,
        description="Include previously visited hostels"
    ),
    context: Optional[str] = Query(
        default=None,
        description="Context for recommendations (e.g., 'homepage', 'search-results')",
        regex="^(homepage|search-results|dashboard|favorites|similar)$"
    ),
) -> List[RecommendedHostel]:
    """
    Retrieve personalized hostel recommendations.

    Recommendations are based on:
    - Viewing history
    - Search patterns
    - Favorite hostels
    - Booking history
    - Similar user preferences
    - Trending hostels
    - Seasonal factors

    Args:
        current_user: Authenticated user from dependency injection
        recommendation_service: Recommendation service instance
        limit: Maximum recommendations to return (1-100)
        include_visited: Whether to include previously visited hostels
        context: Context for generating recommendations

    Returns:
        List[RecommendedHostel]: List of recommended hostels with scores

    Raises:
        HTTPException: If recommendations cannot be generated
    """
    result = await recommendation_service.get_recommendations(
        user_id=current_user.id,
        limit=limit,
        include_visited=include_visited,
        context=context
    )
    return result.unwrap()


@router.post(
    "/refresh",
    response_model=List[RecommendedHostel],
    summary="Refresh recommendations",
    description="Force regeneration of recommendations and return updated list.",
    responses={
        200: {
            "description": "Recommendations refreshed successfully",
            "model": List[RecommendedHostel],
        },
        401: {"description": "Authentication required"},
    },
)
async def refresh_recommendations(
    current_user: CurrentUser,
    recommendation_service: RecommendationServiceDep,
    limit: int = Query(
        default=10,
        ge=1,
        le=100,
        description="Maximum number of recommendations to return"
    ),
) -> List[RecommendedHostel]:
    """
    Force regeneration of recommendations.

    Useful for:
    - Getting fresh recommendations
    - After preference updates
    - Manual refresh requests
    - Cache invalidation

    Args:
        current_user: Authenticated user from dependency injection
        recommendation_service: Recommendation service instance
        limit: Maximum recommendations to return (1-100)

    Returns:
        List[RecommendedHostel]: Newly generated recommendations

    Raises:
        HTTPException: If refresh fails
    """
    result = await recommendation_service.refresh_recommendations(
        user_id=current_user.id,
        limit=limit
    )
    return result.unwrap()


@router.post(
    "/{hostel_id}/feedback",
    status_code=201,
    summary="Provide recommendation feedback",
    description="Submit feedback on a recommended hostel to improve future recommendations.",
    responses={
        201: {"description": "Feedback recorded successfully"},
        400: {"description": "Invalid feedback data"},
        401: {"description": "Authentication required"},
    },
)
async def submit_recommendation_feedback(
    current_user: CurrentUser,
    recommendation_service: RecommendationServiceDep,
    hostel_id: str = Path(..., description="Hostel ID that was recommended"),
    feedback: RecommendationFeedback = Body(
        ...,
        description="Feedback on the recommendation",
        examples=[{
            "action": "clicked",
            "relevant": True,
            "reason": "Great match for my preferences"
        }]
    ),
) -> dict:
    """
    Submit feedback on a recommendation.

    Feedback types:
    - clicked: User clicked on the recommendation
    - viewed: User viewed hostel details
    - favorited: User added to favorites
    - booked: User made a booking
    - dismissed: User dismissed the recommendation
    - not_relevant: User marked as not relevant

    This feedback improves future recommendations.

    Args:
        current_user: Authenticated user from dependency injection
        recommendation_service: Recommendation service instance
        hostel_id: ID of the recommended hostel
        feedback: Feedback details

    Returns:
        dict: Confirmation of feedback submission

    Raises:
        HTTPException: If feedback submission fails
    """
    result = await recommendation_service.submit_feedback(
        user_id=current_user.id,
        hostel_id=hostel_id,
        feedback=feedback
    )
    return result.unwrap()


@router.get(
    "/{hostel_id}/explanation",
    response_model=RecommendationExplanation,
    summary="Get recommendation explanation",
    description="Get explanation of why a hostel was recommended.",
    responses={
        200: {
            "description": "Explanation retrieved successfully",
            "model": RecommendationExplanation,
        },
        401: {"description": "Authentication required"},
        404: {"description": "Recommendation not found"},
    },
)
async def get_recommendation_explanation(
    current_user: CurrentUser,
    recommendation_service: RecommendationServiceDep,
    hostel_id: str = Path(..., description="Hostel ID to explain"),
) -> RecommendationExplanation:
    """
    Get explanation for why a hostel was recommended.

    Provides transparency by explaining:
    - Matching criteria
    - Similarity to favorites
    - Based on search history
    - Popular with similar users
    - Trending in your area

    Args:
        current_user: Authenticated user from dependency injection
        recommendation_service: Recommendation service instance
        hostel_id: ID of the recommended hostel

    Returns:
        RecommendationExplanation: Detailed explanation with reasoning

    Raises:
        HTTPException: If explanation cannot be generated
    """
    result = await recommendation_service.get_explanation(
        user_id=current_user.id,
        hostel_id=hostel_id
    )
    return result.unwrap()


@router.get(
    "/similar/{hostel_id}",
    response_model=List[RecommendedHostel],
    summary="Get similar hostels",
    description="Get hostels similar to a specific hostel.",
    responses={
        200: {
            "description": "Similar hostels retrieved successfully",
            "model": List[RecommendedHostel],
        },
        401: {"description": "Authentication required"},
        404: {"description": "Hostel not found"},
    },
)
async def get_similar_hostels(
    current_user: CurrentUser,
    recommendation_service: RecommendationServiceDep,
    hostel_id: str = Path(..., description="Reference hostel ID"),
    limit: int = Query(
        default=10,
        ge=1,
        le=50,
        description="Maximum number of similar hostels"
    ),
) -> List[RecommendedHostel]:
    """
    Get hostels similar to a reference hostel.

    Similarity based on:
    - Location proximity
    - Price range
    - Amenities
    - Style and atmosphere
    - Guest ratings
    - Property type

    Args:
        current_user: Authenticated user from dependency injection
        recommendation_service: Recommendation service instance
        hostel_id: Reference hostel ID
        limit: Maximum similar hostels to return

    Returns:
        List[RecommendedHostel]: List of similar hostels

    Raises:
        HTTPException: If hostel not found or similar hostels cannot be found
    """
    result = await recommendation_service.get_similar_hostels(
        user_id=current_user.id,
        hostel_id=hostel_id,
        limit=limit
    )
    return result.unwrap()


@router.delete(
    "/history",
    status_code=204,
    summary="Clear recommendation history",
    description="Clear all recommendation history and start fresh.",
    responses={
        204: {"description": "Recommendation history cleared successfully"},
        401: {"description": "Authentication required"},
    },
)
async def clear_recommendation_history(
    current_user: CurrentUser,
    recommendation_service: RecommendationServiceDep,
) -> None:
    """
    Clear all recommendation history.

    This action:
    - Removes all recommendation records
    - Resets recommendation algorithm
    - Starts with fresh recommendations
    - Cannot be undone

    Args:
        current_user: Authenticated user from dependency injection
        recommendation_service: Recommendation service instance

    Raises:
        HTTPException: If clearing fails
    """
    result = await recommendation_service.clear_history(user_id=current_user.id)
    result.unwrap()