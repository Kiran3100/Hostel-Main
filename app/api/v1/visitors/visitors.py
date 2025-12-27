"""
Visitor profile management endpoints.

This module provides endpoints for managing visitor profiles including:
- Profile creation
- Profile retrieval
- Profile updates
- Statistics and engagement metrics
"""

from typing import Annotated

from fastapi import APIRouter, Depends, status, Body

from app.core.dependencies import get_current_user, get_visitor_service
from app.schemas.visitor import (
    VisitorDetail,
    VisitorStats,
    VisitorUpdate,
)
from app.services.visitor.visitor_service import VisitorService

# Type aliases for cleaner dependency injection
CurrentUser = Annotated[dict, Depends(get_current_user)]
VisitorServiceDep = Annotated[VisitorService, Depends(get_visitor_service)]

router = APIRouter(
    prefix="/visitors",
    tags=["Visitors"],
)


@router.post(
    "",
    response_model=VisitorDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Create visitor profile",
    description="Create a new visitor profile for the authenticated user. "
                "Typically called once after registration or first login.",
    responses={
        201: {
            "description": "Visitor profile created successfully",
            "model": VisitorDetail,
        },
        400: {"description": "Visitor profile already exists or invalid data"},
        401: {"description": "Authentication required"},
    },
)
async def create_visitor_profile(
    current_user: CurrentUser,
    visitor_service: VisitorServiceDep,
) -> VisitorDetail:
    """
    Create a new visitor profile for the authenticated user.

    Args:
        current_user: Authenticated user from dependency injection
        visitor_service: Visitor service instance

    Returns:
        VisitorDetail: Newly created visitor profile

    Raises:
        HTTPException: If profile already exists or creation fails
    """
    result = await visitor_service.create_visitor(user_id=current_user.id)
    return result.unwrap()


@router.get(
    "/me",
    response_model=VisitorDetail,
    summary="Get current visitor profile",
    description="Retrieve the current visitor's profile, including preferences and engagement summary.",
    responses={
        200: {
            "description": "Visitor profile retrieved successfully",
            "model": VisitorDetail,
        },
        401: {"description": "Authentication required"},
        404: {"description": "Visitor profile not found"},
    },
)
async def get_my_visitor_profile(
    current_user: CurrentUser,
    visitor_service: VisitorServiceDep,
) -> VisitorDetail:
    """
    Retrieve the current visitor's complete profile.

    Args:
        current_user: Authenticated user from dependency injection
        visitor_service: Visitor service instance

    Returns:
        VisitorDetail: Complete visitor profile with preferences and engagement data

    Raises:
        HTTPException: If profile not found
    """
    result = await visitor_service.get_visitor_by_user_id(current_user.id)
    return result.unwrap()


@router.patch(
    "/me",
    response_model=VisitorDetail,
    summary="Update current visitor profile",
    description="Partially update current visitor profile fields such as name, phone, and other basic information.",
    responses={
        200: {
            "description": "Visitor profile updated successfully",
            "model": VisitorDetail,
        },
        400: {"description": "Invalid update data"},
        401: {"description": "Authentication required"},
        404: {"description": "Visitor profile not found"},
    },
)
async def update_my_visitor_profile(
    current_user: CurrentUser,
    visitor_service: VisitorServiceDep,
    payload: VisitorUpdate = Body(
        ...,
        description="Fields to update in the visitor profile",
        examples=[{
            "name": "John Doe",
            "phone": "+1234567890",
            "bio": "Travel enthusiast looking for unique hostel experiences"
        }]
    ),
) -> VisitorDetail:
    """
    Partially update the current visitor's profile.

    Args:
        current_user: Authenticated user from dependency injection
        visitor_service: Visitor service instance
        payload: Fields to update

    Returns:
        VisitorDetail: Updated visitor profile

    Raises:
        HTTPException: If profile not found or update fails
    """
    result = await visitor_service.update_visitor(
        user_id=current_user.id,
        data=payload
    )
    return result.unwrap()


@router.get(
    "/me/stats",
    response_model=VisitorStats,
    summary="Get visitor statistics",
    description="Retrieve engagement and conversion statistics for the current visitor.",
    responses={
        200: {
            "description": "Visitor statistics retrieved successfully",
            "model": VisitorStats,
        },
        401: {"description": "Authentication required"},
        404: {"description": "Visitor profile not found"},
    },
)
async def get_my_visitor_stats(
    current_user: CurrentUser,
    visitor_service: VisitorServiceDep,
) -> VisitorStats:
    """
    Get comprehensive statistics for the current visitor.

    Includes metrics such as:
    - Total searches performed
    - Hostels viewed
    - Inquiries made
    - Bookings completed
    - Favorite hostels count
    - Engagement score

    Args:
        current_user: Authenticated user from dependency injection
        visitor_service: Visitor service instance

    Returns:
        VisitorStats: Comprehensive visitor statistics

    Raises:
        HTTPException: If profile not found
    """
    result = await visitor_service.get_visitor_stats(user_id=current_user.id)
    return result.unwrap()


@router.delete(
    "/me",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete visitor profile",
    description="Permanently delete the current visitor's profile and all associated data.",
    responses={
        204: {"description": "Visitor profile deleted successfully"},
        401: {"description": "Authentication required"},
        404: {"description": "Visitor profile not found"},
    },
)
async def delete_my_visitor_profile(
    current_user: CurrentUser,
    visitor_service: VisitorServiceDep,
) -> None:
    """
    Permanently delete the current visitor's profile.

    This action will remove:
    - Visitor profile data
    - Preferences
    - Favorites
    - Saved searches
    - Activity history

    Args:
        current_user: Authenticated user from dependency injection
        visitor_service: Visitor service instance

    Raises:
        HTTPException: If profile not found or deletion fails
    """
    result = await visitor_service.delete_visitor(user_id=current_user.id)
    result.unwrap()