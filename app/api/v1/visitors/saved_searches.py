"""
Visitor saved searches endpoints.

This module provides endpoints for managing saved searches:
- List saved searches
- Create new saved search
- Update saved search
- Delete saved search
- Execute saved search
- View execution history
- Toggle notifications
"""

from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, Path, Query, Body, status

from app.core.dependencies import get_current_user, get_saved_search_service
from app.schemas.search import (
    SavedSearch,
    SavedSearchCreate,
    SavedSearchUpdate,
    SavedSearchExecution,
    SavedSearchList,
)
from app.services.visitor.saved_search_service import SavedSearchService

# Type aliases for cleaner dependency injection
CurrentUser = Annotated[dict, Depends(get_current_user)]
SavedSearchServiceDep = Annotated[SavedSearchService, Depends(get_saved_search_service)]

router = APIRouter(
    prefix="/visitors/me/saved-searches",
    tags=["Visitors - Saved Searches"],
)


@router.get(
    "",
    response_model=SavedSearchList,
    summary="List saved searches",
    description="Retrieve all saved searches for the current visitor with optional filtering.",
    responses={
        200: {
            "description": "Saved searches retrieved successfully",
            "model": SavedSearchList,
        },
        401: {"description": "Authentication required"},
    },
)
async def list_saved_searches(
    current_user: CurrentUser,
    saved_search_service: SavedSearchServiceDep,
    active_only: bool = Query(
        default=False,
        description="Return only active saved searches"
    ),
    sort_by: Optional[str] = Query(
        default="created_at",
        description="Field to sort by",
        regex="^(created_at|updated_at|name|last_executed)$"
    ),
    order: Optional[str] = Query(
        default="desc",
        description="Sort order",
        regex="^(asc|desc)$"
    ),
) -> SavedSearchList:
    """
    Retrieve all saved searches for the current visitor.

    Features:
    - Filtering by active status
    - Sorting by various fields
    - Includes execution statistics
    - Shows notification status

    Args:
        current_user: Authenticated user from dependency injection
        saved_search_service: Saved search service instance
        active_only: Return only active searches
        sort_by: Field to sort results by
        order: Sort order (asc/desc)

    Returns:
        SavedSearchList: List of saved searches with metadata

    Raises:
        HTTPException: If searches cannot be retrieved
    """
    result = await saved_search_service.list_saved_searches(
        visitor_user_id=current_user.id,
        active_only=active_only,
        sort_by=sort_by,
        order=order
    )
    return result.unwrap()


@router.post(
    "",
    response_model=SavedSearch,
    status_code=status.HTTP_201_CREATED,
    summary="Create saved search",
    description="Save a search query for future use with optional notifications.",
    responses={
        201: {
            "description": "Saved search created successfully",
            "model": SavedSearch,
        },
        400: {"description": "Invalid search data or duplicate name"},
        401: {"description": "Authentication required"},
    },
)
async def create_saved_search(
    current_user: CurrentUser,
    saved_search_service: SavedSearchServiceDep,
    payload: SavedSearchCreate = Body(
        ...,
        description="Saved search details",
        examples=[{
            "name": "Budget hostels in Barcelona",
            "search_params": {
                "location": "Barcelona, Spain",
                "price_max": 25,
                "amenities": ["wifi", "breakfast"]
            },
            "notify_on_new_results": True,
            "notification_frequency": "daily"
        }]
    ),
) -> SavedSearch:
    """
    Create a new saved search.

    Features:
    - Save complex search criteria
    - Optional notifications for new results
    - Customizable notification frequency
    - Name for easy identification

    Args:
        current_user: Authenticated user from dependency injection
        saved_search_service: Saved search service instance
        payload: Search details including criteria and notification settings

    Returns:
        SavedSearch: Newly created saved search

    Raises:
        HTTPException: If creation fails or name is duplicate
    """
    result = await saved_search_service.create_saved_search(
        visitor_user_id=current_user.id,
        data=payload
    )
    return result.unwrap()


@router.get(
    "/{saved_search_id}",
    response_model=SavedSearch,
    summary="Get saved search details",
    description="Retrieve detailed information about a specific saved search.",
    responses={
        200: {
            "description": "Saved search retrieved successfully",
            "model": SavedSearch,
        },
        401: {"description": "Authentication required"},
        404: {"description": "Saved search not found"},
    },
)
async def get_saved_search(
    current_user: CurrentUser,
    saved_search_service: SavedSearchServiceDep,
    saved_search_id: str = Path(
        ...,
        description="Unique identifier of the saved search",
        min_length=1
    ),
) -> SavedSearch:
    """
    Retrieve detailed information about a saved search.

    Includes:
    - Search criteria
    - Notification settings
    - Execution statistics
    - Last execution timestamp
    - Result count trends

    Args:
        current_user: Authenticated user from dependency injection
        saved_search_service: Saved search service instance
        saved_search_id: Unique saved search identifier

    Returns:
        SavedSearch: Complete saved search details

    Raises:
        HTTPException: If saved search not found or access denied
    """
    result = await saved_search_service.get_saved_search(
        visitor_user_id=current_user.id,
        saved_search_id=saved_search_id
    )
    return result.unwrap()


@router.patch(
    "/{saved_search_id}",
    response_model=SavedSearch,
    summary="Update saved search",
    description="Update saved search criteria, name, or notification settings.",
    responses={
        200: {
            "description": "Saved search updated successfully",
            "model": SavedSearch,
        },
        400: {"description": "Invalid update data"},
        401: {"description": "Authentication required"},
        404: {"description": "Saved search not found"},
    },
)
async def update_saved_search(
    current_user: CurrentUser,
    saved_search_service: SavedSearchServiceDep,
    saved_search_id: str = Path(
        ...,
        description="Unique identifier of the saved search",
        min_length=1
    ),
    payload: SavedSearchUpdate = Body(
        ...,
        description="Fields to update",
        examples=[{
            "name": "Budget hostels in Barcelona - Updated",
            "notify_on_new_results": False
        }]
    ),
) -> SavedSearch:
    """
    Update a saved search.

    Updateable fields:
    - Search name
    - Search criteria
    - Notification settings
    - Active/inactive status

    Args:
        current_user: Authenticated user from dependency injection
        saved_search_service: Saved search service instance
        saved_search_id: Unique saved search identifier
        payload: Fields to update

    Returns:
        SavedSearch: Updated saved search

    Raises:
        HTTPException: If saved search not found or update fails
    """
    result = await saved_search_service.update_saved_search(
        visitor_user_id=current_user.id,
        saved_search_id=saved_search_id,
        data=payload
    )
    return result.unwrap()


@router.delete(
    "/{saved_search_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete saved search",
    description="Permanently delete a saved search and its execution history.",
    responses={
        204: {"description": "Saved search deleted successfully"},
        401: {"description": "Authentication required"},
        404: {"description": "Saved search not found"},
    },
)
async def delete_saved_search(
    current_user: CurrentUser,
    saved_search_service: SavedSearchServiceDep,
    saved_search_id: str = Path(
        ...,
        description="Unique identifier of the saved search",
        min_length=1
    ),
) -> None:
    """
    Delete a saved search.

    This action:
    - Permanently removes the saved search
    - Deletes execution history
    - Stops all notifications
    - Cannot be undone

    Args:
        current_user: Authenticated user from dependency injection
        saved_search_service: Saved search service instance
        saved_search_id: Unique saved search identifier

    Raises:
        HTTPException: If saved search not found or deletion fails
    """
    result = await saved_search_service.delete_saved_search(
        visitor_user_id=current_user.id,
        saved_search_id=saved_search_id
    )
    result.unwrap()


@router.post(
    "/{saved_search_id}/execute",
    response_model=SavedSearchExecution,
    summary="Execute saved search",
    description="Execute the saved search and record the execution with results.",
    responses={
        200: {
            "description": "Search executed successfully",
            "model": SavedSearchExecution,
        },
        401: {"description": "Authentication required"},
        404: {"description": "Saved search not found"},
    },
)
async def execute_saved_search(
    current_user: CurrentUser,
    saved_search_service: SavedSearchServiceDep,
    saved_search_id: str = Path(
        ...,
        description="Unique identifier of the saved search",
        min_length=1
    ),
) -> SavedSearchExecution:
    """
    Execute a saved search and get results.

    This endpoint:
    - Runs the saved search query
    - Returns current results
    - Records execution in history
    - Updates last_executed timestamp
    - Tracks result count

    Args:
        current_user: Authenticated user from dependency injection
        saved_search_service: Saved search service instance
        saved_search_id: Unique saved search identifier

    Returns:
        SavedSearchExecution: Execution results with hostel matches

    Raises:
        HTTPException: If search execution fails
    """
    result = await saved_search_service.execute_saved_search(
        visitor_user_id=current_user.id,
        saved_search_id=saved_search_id
    )
    return result.unwrap()


@router.get(
    "/{saved_search_id}/history",
    response_model=List[SavedSearchExecution],
    summary="Get execution history",
    description="Retrieve execution history for a saved search.",
    responses={
        200: {
            "description": "Execution history retrieved successfully",
            "model": List[SavedSearchExecution],
        },
        401: {"description": "Authentication required"},
        404: {"description": "Saved search not found"},
    },
)
async def get_saved_search_history(
    current_user: CurrentUser,
    saved_search_service: SavedSearchServiceDep,
    saved_search_id: str = Path(
        ...,
        description="Unique identifier of the saved search",
        min_length=1
    ),
    limit: int = Query(
        default=50,
        ge=1,
        le=100,
        description="Maximum number of history entries to return"
    ),
) -> List[SavedSearchExecution]:
    """
    Retrieve execution history for a saved search.

    Provides:
    - Execution timestamps
    - Result counts over time
    - Trending information
    - New results notifications

    Useful for:
    - Tracking search result changes
    - Analyzing trends
    - Verifying notifications

    Args:
        current_user: Authenticated user from dependency injection
        saved_search_service: Saved search service instance
        saved_search_id: Unique saved search identifier
        limit: Maximum history entries to return

    Returns:
        List[SavedSearchExecution]: Execution history

    Raises:
        HTTPException: If history cannot be retrieved
    """
    result = await saved_search_service.get_execution_history(
        visitor_user_id=current_user.id,
        saved_search_id=saved_search_id,
        limit=limit
    )
    return result.unwrap()


@router.post(
    "/{saved_search_id}/toggle-notifications",
    response_model=SavedSearch,
    summary="Toggle notifications",
    description="Enable or disable notifications for a saved search.",
    responses={
        200: {
            "description": "Notifications toggled successfully",
            "model": SavedSearch,
        },
        401: {"description": "Authentication required"},
        404: {"description": "Saved search not found"},
    },
)
async def toggle_notifications(
    current_user: CurrentUser,
    saved_search_service: SavedSearchServiceDep,
    saved_search_id: str = Path(
        ...,
        description="Unique identifier of the saved search",
        min_length=1
    ),
    enabled: bool = Body(
        ...,
        description="Enable or disable notifications",
        embed=True
    ),
) -> SavedSearch:
    """
    Toggle notifications for a saved search.

    Quick way to enable/disable notifications without updating
    the entire saved search.

    Args:
        current_user: Authenticated user from dependency injection
        saved_search_service: Saved search service instance
        saved_search_id: Unique saved search identifier
        enabled: True to enable, False to disable

    Returns:
        SavedSearch: Updated saved search

    Raises:
        HTTPException: If toggle fails
    """
    result = await saved_search_service.toggle_notifications(
        visitor_user_id=current_user.id,
        saved_search_id=saved_search_id,
        enabled=enabled
    )
    return result.unwrap()


@router.post(
    "/{saved_search_id}/duplicate",
    response_model=SavedSearch,
    status_code=status.HTTP_201_CREATED,
    summary="Duplicate saved search",
    description="Create a copy of an existing saved search.",
    responses={
        201: {
            "description": "Saved search duplicated successfully",
            "model": SavedSearch,
        },
        401: {"description": "Authentication required"},
        404: {"description": "Saved search not found"},
    },
)
async def duplicate_saved_search(
    current_user: CurrentUser,
    saved_search_service: SavedSearchServiceDep,
    saved_search_id: str = Path(
        ...,
        description="Unique identifier of the saved search to duplicate",
        min_length=1
    ),
    new_name: Optional[str] = Body(
        default=None,
        description="Name for the duplicated search (auto-generated if not provided)",
        embed=True
    ),
) -> SavedSearch:
    """
    Create a duplicate of a saved search.

    Useful for:
    - Creating variations of existing searches
    - Backing up searches before modification
    - Testing different notification settings

    Args:
        current_user: Authenticated user from dependency injection
        saved_search_service: Saved search service instance
        saved_search_id: Unique saved search identifier to duplicate
        new_name: Optional name for the duplicate

    Returns:
        SavedSearch: Newly created duplicate

    Raises:
        HTTPException: If duplication fails
    """
    result = await saved_search_service.duplicate_saved_search(
        visitor_user_id=current_user.id,
        saved_search_id=saved_search_id,
        new_name=new_name
    )
    return result.unwrap()