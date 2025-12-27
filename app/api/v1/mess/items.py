"""
Mess Meal Items API Endpoints

This module handles CRUD operations and management for meal items.
"""

from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from app.core.dependencies import AuthenticationDependency
from app.services.mess.meal_item_service import MealItemService
from app.schemas.mess import (
    MealItemResponse,
    MealItemDetail,
    MealItemCreate,
    MealItemUpdate,
    ItemCategory,
)
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix="/mess/items",
    tags=["Mess - Items"],
)


async def get_item_service() -> MealItemService:
    """
    Dependency injection for MealItemService.
    
    Raises:
        NotImplementedError: When DI container is not configured
    """
    raise NotImplementedError(
        "MealItemService dependency injection not configured. "
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
    response_model=MealItemDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Create meal item",
    description="Create a new meal item. Requires admin permissions.",
    responses={
        201: {"description": "Meal item created successfully"},
        400: {"description": "Invalid meal item data"},
        403: {"description": "User not authorized to create meal items"},
        409: {"description": "Meal item with same name already exists"},
    },
)
async def create_item(
    payload: MealItemCreate,
    item_service: MealItemService = Depends(get_item_service),
    current_user: Any = Depends(get_current_user),
) -> MealItemDetail:
    """
    Create a new meal item.
    
    Args:
        payload: Meal item data
        item_service: Meal item service instance
        current_user: Currently authenticated user (must have admin rights)
        
    Returns:
        MealItemDetail: Created meal item with full details
        
    Raises:
        HTTPException: If creation fails or user lacks permission
    """
    logger.info(
        f"User {current_user.id} creating meal item: {payload.name}"
    )
    
    result = item_service.create_item(data=payload)
    
    if result.is_err():
        error = result.unwrap_err()
        logger.error(f"Failed to create meal item: {error}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        )
    
    item = result.unwrap()
    logger.info(f"Meal item {item.id} created successfully")
    return item


@router.get(
    "",
    response_model=List[MealItemResponse],
    status_code=status.HTTP_200_OK,
    summary="List meal items",
    description="List all meal items for a hostel with optional filtering.",
    responses={
        200: {"description": "Meal items retrieved successfully"},
        404: {"description": "Hostel not found"},
    },
)
async def list_items(
    hostel_id: str = Query(..., description="Unique hostel identifier"),
    category: Optional[str] = Query(
        None,
        description="Filter by item category",
    ),
    search: Optional[str] = Query(
        None,
        min_length=2,
        max_length=100,
        description="Search query for item name or description",
    ),
    is_available: Optional[bool] = Query(
        None,
        description="Filter by availability status",
    ),
    dietary_type: Optional[str] = Query(
        None,
        description="Filter by dietary type (veg, non-veg, vegan, etc.)",
    ),
    limit: int = Query(
        100,
        ge=1,
        le=500,
        description="Maximum number of items to return",
    ),
    offset: int = Query(
        0,
        ge=0,
        description="Pagination offset",
    ),
    item_service: MealItemService = Depends(get_item_service),
    current_user: Any = Depends(get_current_user),
) -> List[MealItemResponse]:
    """
    List meal items with filtering and pagination.
    
    Args:
        hostel_id: Unique identifier of the hostel
        category: Optional category filter
        search: Optional search query
        is_available: Optional availability filter
        dietary_type: Optional dietary type filter
        limit: Maximum number of results
        offset: Pagination offset
        item_service: Meal item service instance
        current_user: Currently authenticated user
        
    Returns:
        List[MealItemResponse]: List of meal items matching criteria
        
    Raises:
        HTTPException: If hostel not found
    """
    filters = {
        "category": category,
        "search": search,
        "is_available": is_available,
        "dietary_type": dietary_type,
        "limit": limit,
        "offset": offset,
    }
    
    # Remove None values
    filters = {k: v for k, v in filters.items() if v is not None}
    
    logger.debug(
        f"Listing meal items for hostel {hostel_id} with filters: {filters}"
    )
    
    result = item_service.list_items_for_hostel(
        hostel_id=hostel_id,
        filters=filters,
    )
    
    if result.is_err():
        error = result.unwrap_err()
        logger.error(f"Failed to list meal items: {error}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Hostel with ID {hostel_id} not found",
        )
    
    items = result.unwrap()
    logger.debug(f"Retrieved {len(items)} meal items")
    return items


@router.get(
    "/{item_id}",
    response_model=MealItemDetail,
    status_code=status.HTTP_200_OK,
    summary="Get item detail",
    description="Retrieve detailed information about a specific meal item.",
    responses={
        200: {"description": "Meal item retrieved successfully"},
        404: {"description": "Meal item not found"},
    },
)
async def get_item(
    item_id: str = Path(..., description="Unique meal item identifier"),
    item_service: MealItemService = Depends(get_item_service),
    current_user: Any = Depends(get_current_user),
) -> MealItemDetail:
    """
    Get detailed information about a meal item.
    
    Args:
        item_id: Unique identifier of the meal item
        item_service: Meal item service instance
        current_user: Currently authenticated user
        
    Returns:
        MealItemDetail: Complete meal item details
        
    Raises:
        HTTPException: If meal item not found
    """
    logger.debug(f"Fetching meal item {item_id}")
    
    result = item_service.get_item(item_id=item_id)
    
    if result.is_err():
        error = result.unwrap_err()
        logger.error(f"Failed to fetch meal item {item_id}: {error}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Meal item with ID {item_id} not found",
        )
    
    return result.unwrap()


@router.patch(
    "/{item_id}",
    response_model=MealItemDetail,
    status_code=status.HTTP_200_OK,
    summary="Update meal item",
    description="Update an existing meal item. Requires admin permissions.",
    responses={
        200: {"description": "Meal item updated successfully"},
        400: {"description": "Invalid update data"},
        403: {"description": "User not authorized to update meal items"},
        404: {"description": "Meal item not found"},
    },
)
async def update_item(
    item_id: str = Path(..., description="Unique meal item identifier"),
    payload: MealItemUpdate = ...,
    item_service: MealItemService = Depends(get_item_service),
    current_user: Any = Depends(get_current_user),
) -> MealItemDetail:
    """
    Update a meal item.
    
    Args:
        item_id: Unique identifier of the meal item
        payload: Updated meal item data
        item_service: Meal item service instance
        current_user: Currently authenticated user (must have admin rights)
        
    Returns:
        MealItemDetail: Updated meal item
        
    Raises:
        HTTPException: If update fails or item not found
    """
    logger.info(f"User {current_user.id} updating meal item {item_id}")
    
    result = item_service.update_item(item_id=item_id, data=payload)
    
    if result.is_err():
        error = result.unwrap_err()
        logger.error(f"Failed to update meal item {item_id}: {error}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        )
    
    item = result.unwrap()
    logger.info(f"Meal item {item_id} updated successfully")
    return item


@router.delete(
    "/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete meal item",
    description="Delete a meal item. Requires admin permissions.",
    responses={
        204: {"description": "Meal item deleted successfully"},
        403: {"description": "User not authorized to delete meal items"},
        404: {"description": "Meal item not found"},
        409: {"description": "Cannot delete item - in use by active menus"},
    },
)
async def delete_item(
    item_id: str = Path(..., description="Unique meal item identifier"),
    item_service: MealItemService = Depends(get_item_service),
    current_user: Any = Depends(get_current_user),
) -> None:
    """
    Delete a meal item.
    
    Args:
        item_id: Unique identifier of the meal item
        item_service: Meal item service instance
        current_user: Currently authenticated user (must have admin rights)
        
    Raises:
        HTTPException: If deletion fails or item not found
    """
    logger.info(f"User {current_user.id} deleting meal item {item_id}")
    
    result = item_service.delete_item(item_id=item_id)
    
    if result.is_err():
        error = result.unwrap_err()
        logger.error(f"Failed to delete meal item {item_id}: {error}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        )
    
    logger.info(f"Meal item {item_id} deleted successfully")


@router.get(
    "/categories/list",
    response_model=List[ItemCategory],
    status_code=status.HTTP_200_OK,
    summary="List item categories",
    description="Get all available meal item categories.",
    responses={
        200: {"description": "Categories retrieved successfully"},
    },
)
async def list_categories(
    item_service: MealItemService = Depends(get_item_service),
    current_user: Any = Depends(get_current_user),
) -> List[ItemCategory]:
    """
    List all meal item categories.
    
    Args:
        item_service: Meal item service instance
        current_user: Currently authenticated user
        
    Returns:
        List[ItemCategory]: Available item categories
    """
    logger.debug("Fetching meal item categories")
    
    result = item_service.list_categories()
    
    if result.is_err():
        logger.error(f"Failed to fetch categories: {result.unwrap_err()}")
        return []
    
    categories = result.unwrap()
    logger.debug(f"Retrieved {len(categories)} categories")
    return categories


@router.get(
    "/popular",
    response_model=List[MealItemResponse],
    status_code=status.HTTP_200_OK,
    summary="Get popular items",
    description="Get most popular meal items based on student ratings and frequency.",
    responses={
        200: {"description": "Popular items retrieved successfully"},
        404: {"description": "Hostel not found"},
    },
)
async def get_popular_items(
    hostel_id: str = Query(..., description="Unique hostel identifier"),
    limit: int = Query(
        10,
        ge=1,
        le=50,
        description="Maximum number of popular items to return",
    ),
    time_period: str = Query(
        "month",
        regex="^(week|month|quarter|year)$",
        description="Time period for popularity calculation",
    ),
    item_service: MealItemService = Depends(get_item_service),
    current_user: Any = Depends(get_current_user),
) -> List[MealItemResponse]:
    """
    Get popular meal items for a hostel.
    
    Args:
        hostel_id: Unique identifier of the hostel
        limit: Maximum number of items to return
        time_period: Period for popularity calculation
        item_service: Meal item service instance
        current_user: Currently authenticated user
        
    Returns:
        List[MealItemResponse]: Most popular meal items
        
    Raises:
        HTTPException: If hostel not found
    """
    logger.debug(
        f"Fetching top {limit} popular items for hostel {hostel_id} "
        f"(period: {time_period})"
    )
    
    result = item_service.get_popular_items(
        hostel_id=hostel_id,
        limit=limit,
        time_period=time_period,
    )
    
    if result.is_err():
        error = result.unwrap_err()
        logger.error(f"Failed to fetch popular items: {error}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Hostel with ID {hostel_id} not found",
        )
    
    items = result.unwrap()
    logger.debug(f"Retrieved {len(items)} popular items")
    return items


@router.post(
    "/{item_id}/toggle-availability",
    response_model=MealItemDetail,
    status_code=status.HTTP_200_OK,
    summary="Toggle item availability",
    description="Toggle availability status of a meal item.",
    responses={
        200: {"description": "Availability toggled successfully"},
        404: {"description": "Meal item not found"},
        403: {"description": "User not authorized"},
    },
)
async def toggle_item_availability(
    item_id: str = Path(..., description="Unique meal item identifier"),
    item_service: MealItemService = Depends(get_item_service),
    current_user: Any = Depends(get_current_user),
) -> MealItemDetail:
    """
    Toggle the availability status of a meal item.
    
    Args:
        item_id: Unique identifier of the meal item
        item_service: Meal item service instance
        current_user: Currently authenticated user
        
    Returns:
        MealItemDetail: Updated meal item
        
    Raises:
        HTTPException: If toggle fails or item not found
    """
    logger.info(f"User {current_user.id} toggling availability for item {item_id}")
    
    result = item_service.toggle_availability(item_id=item_id)
    
    if result.is_err():
        error = result.unwrap_err()
        logger.error(f"Failed to toggle availability: {error}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        )
    
    item = result.unwrap()
    logger.info(f"Item {item_id} availability toggled to {item.is_available}")
    return item