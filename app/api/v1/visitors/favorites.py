"""
Visitor favorites management endpoints.

This module provides endpoints for managing favorite hostels:
- List all favorites
- Add hostel to favorites
- Get favorite details
- Update favorite notes/tags
- Remove from favorites
- Bulk operations
"""

from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, Path, Query, Body, status

from app.core.dependencies import get_current_user, get_visitor_favorite_service
from app.schemas.visitor import (
    FavoritesList,
    FavoriteHostelItem,
    FavoriteRequest,
    FavoriteUpdate,
    FavoriteBulkOperation,
)
from app.services.visitor.visitor_favorite_service import VisitorFavoriteService

# Type aliases for cleaner dependency injection
CurrentUser = Annotated[dict, Depends(get_current_user)]
FavoriteServiceDep = Annotated[VisitorFavoriteService, Depends(get_visitor_favorite_service)]

router = APIRouter(
    prefix="/visitors/me/favorites",
    tags=["Visitors - Favorites"],
)


@router.get(
    "",
    response_model=FavoritesList,
    summary="List favorite hostels",
    description="Retrieve all favorite hostels for the current visitor with optional filtering and sorting.",
    responses={
        200: {
            "description": "Favorites retrieved successfully",
            "model": FavoritesList,
        },
        401: {"description": "Authentication required"},
    },
)
async def list_favorites(
    current_user: CurrentUser,
    favorite_service: FavoriteServiceDep,
    sort_by: Optional[str] = Query(
        default="created_at",
        description="Field to sort by: created_at, updated_at, hostel_name",
        regex="^(created_at|updated_at|hostel_name)$"
    ),
    order: Optional[str] = Query(
        default="desc",
        description="Sort order: asc or desc",
        regex="^(asc|desc)$"
    ),
    tags: Optional[List[str]] = Query(
        default=None,
        description="Filter by tags"
    ),
) -> FavoritesList:
    """
    Retrieve all favorite hostels for the current visitor.

    Features:
    - Sorting by date or name
    - Filtering by tags
    - Pagination support
    - Count of total favorites

    Args:
        current_user: Authenticated user from dependency injection
        favorite_service: Favorite service instance
        sort_by: Field to sort results by
        order: Sort order (ascending or descending)
        tags: Optional tag filters

    Returns:
        FavoritesList: List of favorite hostels with metadata

    Raises:
        HTTPException: If favorites cannot be retrieved
    """
    result = await favorite_service.list_favorites(
        user_id=current_user.id,
        sort_by=sort_by,
        order=order,
        tags=tags
    )
    return result.unwrap()


@router.post(
    "",
    response_model=FavoriteHostelItem,
    status_code=status.HTTP_201_CREATED,
    summary="Add hostel to favorites",
    description="Add a hostel to favorites with optional notes and tags.",
    responses={
        201: {
            "description": "Hostel added to favorites successfully",
            "model": FavoriteHostelItem,
        },
        400: {"description": "Hostel already in favorites or invalid data"},
        401: {"description": "Authentication required"},
        404: {"description": "Hostel not found"},
    },
)
async def add_favorite(
    current_user: CurrentUser,
    favorite_service: FavoriteServiceDep,
    payload: FavoriteRequest = Body(
        ...,
        description="Favorite hostel details",
        examples=[{
            "hostel_id": "hostel_123",
            "notes": "Great location near city center",
            "tags": ["budget-friendly", "central-location"]
        }]
    ),
) -> FavoriteHostelItem:
    """
    Add a hostel to the visitor's favorites.

    Features:
    - Optional personal notes
    - Custom tags for organization
    - Duplicate prevention
    - Timestamp tracking

    Args:
        current_user: Authenticated user from dependency injection
        favorite_service: Favorite service instance
        payload: Favorite details including hostel ID, notes, and tags

    Returns:
        FavoriteHostelItem: Newly created favorite with complete hostel details

    Raises:
        HTTPException: If hostel not found or already favorited
    """
    result = await favorite_service.add_favorite(
        user_id=current_user.id,
        data=payload
    )
    return result.unwrap()


@router.get(
    "/{favorite_id}",
    response_model=FavoriteHostelItem,
    summary="Get favorite hostel details",
    description="Retrieve detailed information about a specific favorite hostel.",
    responses={
        200: {
            "description": "Favorite retrieved successfully",
            "model": FavoriteHostelItem,
        },
        401: {"description": "Authentication required"},
        404: {"description": "Favorite not found"},
    },
)
async def get_favorite(
    current_user: CurrentUser,
    favorite_service: FavoriteServiceDep,
    favorite_id: str = Path(
        ...,
        description="Unique identifier of the favorite",
        min_length=1
    ),
) -> FavoriteHostelItem:
    """
    Retrieve detailed information about a specific favorite.

    Includes:
    - Complete hostel information
    - Personal notes and tags
    - Date added
    - Last updated timestamp

    Args:
        current_user: Authenticated user from dependency injection
        favorite_service: Favorite service instance
        favorite_id: Unique favorite identifier

    Returns:
        FavoriteHostelItem: Complete favorite details

    Raises:
        HTTPException: If favorite not found or access denied
    """
    result = await favorite_service.get_favorite(
        user_id=current_user.id,
        favorite_id=favorite_id
    )
    return result.unwrap()


@router.patch(
    "/{favorite_id}",
    response_model=FavoriteHostelItem,
    summary="Update favorite notes/tags",
    description="Update personal notes and tags for a favorite hostel.",
    responses={
        200: {
            "description": "Favorite updated successfully",
            "model": FavoriteHostelItem,
        },
        400: {"description": "Invalid update data"},
        401: {"description": "Authentication required"},
        404: {"description": "Favorite not found"},
    },
)
async def update_favorite(
    current_user: CurrentUser,
    favorite_service: FavoriteServiceDep,
    favorite_id: str = Path(
        ...,
        description="Unique identifier of the favorite",
        min_length=1
    ),
    payload: FavoriteUpdate = Body(
        ...,
        description="Fields to update",
        examples=[{
            "notes": "Updated: Booked for summer trip",
            "tags": ["budget-friendly", "booked", "summer-2024"]
        }]
    ),
) -> FavoriteHostelItem:
    """
    Update notes and tags for a favorite hostel.

    Updateable fields:
    - Personal notes
    - Tags (replaces existing tags)
    - Custom metadata

    Args:
        current_user: Authenticated user from dependency injection
        favorite_service: Favorite service instance
        favorite_id: Unique favorite identifier
        payload: Fields to update

    Returns:
        FavoriteHostelItem: Updated favorite details

    Raises:
        HTTPException: If favorite not found or update fails
    """
    result = await favorite_service.update_favorite(
        user_id=current_user.id,
        favorite_id=favorite_id,
        data=payload
    )
    return result.unwrap()


@router.delete(
    "/{favorite_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove favorite hostel",
    description="Remove a hostel from favorites.",
    responses={
        204: {"description": "Favorite removed successfully"},
        401: {"description": "Authentication required"},
        404: {"description": "Favorite not found"},
    },
)
async def remove_favorite(
    current_user: CurrentUser,
    favorite_service: FavoriteServiceDep,
    favorite_id: str = Path(
        ...,
        description="Unique identifier of the favorite",
        min_length=1
    ),
) -> None:
    """
    Remove a hostel from the visitor's favorites.

    This action:
    - Permanently removes the favorite
    - Preserves hostel data
    - Cannot be undone

    Args:
        current_user: Authenticated user from dependency injection
        favorite_service: Favorite service instance
        favorite_id: Unique favorite identifier

    Raises:
        HTTPException: If favorite not found or deletion fails
    """
    result = await favorite_service.remove_favorite(
        user_id=current_user.id,
        favorite_id=favorite_id
    )
    result.unwrap()


@router.post(
    "/bulk",
    response_model=dict,
    summary="Bulk operations on favorites",
    description="Perform bulk operations (add, remove, tag) on multiple favorites.",
    responses={
        200: {"description": "Bulk operation completed successfully"},
        400: {"description": "Invalid operation or data"},
        401: {"description": "Authentication required"},
    },
)
async def bulk_favorite_operations(
    current_user: CurrentUser,
    favorite_service: FavoriteServiceDep,
    operation: FavoriteBulkOperation = Body(
        ...,
        description="Bulk operation details",
        examples=[{
            "action": "add_tag",
            "favorite_ids": ["fav_1", "fav_2", "fav_3"],
            "tag": "summer-trip"
        }]
    ),
) -> dict:
    """
    Perform bulk operations on multiple favorites.

    Supported operations:
    - add_tag: Add a tag to multiple favorites
    - remove_tag: Remove a tag from multiple favorites
    - delete: Remove multiple favorites

    Args:
        current_user: Authenticated user from dependency injection
        favorite_service: Favorite service instance
        operation: Bulk operation details

    Returns:
        dict: Operation results with success/failure counts

    Raises:
        HTTPException: If operation fails
    """
    result = await favorite_service.bulk_operations(
        user_id=current_user.id,
        operation=operation
    )
    return result.unwrap()


@router.get(
    "/check/{hostel_id}",
    response_model=dict,
    summary="Check if hostel is favorited",
    description="Check if a specific hostel is in the visitor's favorites.",
    responses={
        200: {"description": "Check completed successfully"},
        401: {"description": "Authentication required"},
    },
)
async def check_favorite_status(
    current_user: CurrentUser,
    favorite_service: FavoriteServiceDep,
    hostel_id: str = Path(
        ...,
        description="Hostel ID to check",
        min_length=1
    ),
) -> dict:
    """
    Check if a hostel is in favorites.

    Useful for:
    - UI state management
    - Preventing duplicates
    - Quick status checks

    Args:
        current_user: Authenticated user from dependency injection
        favorite_service: Favorite service instance
        hostel_id: Hostel ID to check

    Returns:
        dict: Contains 'is_favorite' boolean and favorite_id if exists

    Raises:
        HTTPException: If check fails
    """
    result = await favorite_service.check_favorite_status(
        user_id=current_user.id,
        hostel_id=hostel_id
    )
    return result.unwrap()