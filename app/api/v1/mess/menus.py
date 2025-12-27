"""
Mess Menus API Endpoints

This module handles CRUD operations and management for daily mess menus.
"""

from typing import Any, List, Optional
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from app.core.dependencies import AuthenticationDependency
from app.services.mess.mess_menu_service import MessMenuService
from app.schemas.mess import (
    MenuResponse,
    MenuDetail,
    MenuCreate,
    MenuUpdate,
    DailyMenuSummary,
    MenuStats,
)
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix="/mess/menus",
    tags=["Mess - Menus"],
)


async def get_menu_service() -> MessMenuService:
    """
    Dependency injection for MessMenuService.
    
    Raises:
        NotImplementedError: When DI container is not configured
    """
    raise NotImplementedError(
        "MessMenuService dependency injection not configured. "
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
    response_model=MenuDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Create daily menu",
    description="Create a new daily menu for a hostel. Requires admin permissions.",
    responses={
        201: {"description": "Menu created successfully"},
        400: {"description": "Invalid menu data or duplicate menu for date"},
        403: {"description": "User not authorized to create menus"},
    },
)
async def create_menu(
    payload: MenuCreate,
    menu_service: MessMenuService = Depends(get_menu_service),
    current_user: Any = Depends(get_current_user),
) -> MenuDetail:
    """
    Create a new daily menu.
    
    Args:
        payload: Menu creation data
        menu_service: Menu service instance
        current_user: Currently authenticated user (must have admin rights)
        
    Returns:
        MenuDetail: Created menu with full details
        
    Raises:
        HTTPException: If creation fails or user lacks permission
    """
    logger.info(
        f"User {current_user.id} creating menu for date {payload.date} "
        f"in hostel {payload.hostel_id}"
    )
    
    result = menu_service.create_menu(data=payload)
    
    if result.is_err():
        error = result.unwrap_err()
        logger.error(f"Failed to create menu: {error}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        )
    
    menu = result.unwrap()
    logger.info(f"Menu {menu.id} created successfully")
    return menu


@router.get(
    "/{menu_id}",
    response_model=MenuDetail,
    status_code=status.HTTP_200_OK,
    summary="Get menu detail",
    description="Retrieve detailed information about a specific menu.",
    responses={
        200: {"description": "Menu retrieved successfully"},
        404: {"description": "Menu not found"},
    },
)
async def get_menu(
    menu_id: str = Path(..., description="Unique menu identifier"),
    menu_service: MessMenuService = Depends(get_menu_service),
    current_user: Any = Depends(get_current_user),
) -> MenuDetail:
    """
    Get detailed information about a menu.
    
    Args:
        menu_id: Unique identifier of the menu
        menu_service: Menu service instance
        current_user: Currently authenticated user
        
    Returns:
        MenuDetail: Complete menu details
        
    Raises:
        HTTPException: If menu not found
    """
    logger.debug(f"Fetching menu {menu_id}")
    
    result = menu_service.get_menu(menu_id=menu_id)
    
    if result.is_err():
        error = result.unwrap_err()
        logger.error(f"Failed to fetch menu {menu_id}: {error}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Menu with ID {menu_id} not found",
        )
    
    return result.unwrap()


@router.patch(
    "/{menu_id}",
    response_model=MenuDetail,
    status_code=status.HTTP_200_OK,
    summary="Update menu",
    description="Update an existing menu. Requires admin permissions.",
    responses={
        200: {"description": "Menu updated successfully"},
        400: {"description": "Invalid update data or menu in invalid state"},
        403: {"description": "User not authorized to update menus"},
        404: {"description": "Menu not found"},
    },
)
async def update_menu(
    menu_id: str = Path(..., description="Unique menu identifier"),
    payload: MenuUpdate = ...,
    menu_service: MessMenuService = Depends(get_menu_service),
    current_user: Any = Depends(get_current_user),
) -> MenuDetail:
    """
    Update a menu.
    
    Args:
        menu_id: Unique identifier of the menu
        payload: Updated menu data
        menu_service: Menu service instance
        current_user: Currently authenticated user (must have admin rights)
        
    Returns:
        MenuDetail: Updated menu
        
    Raises:
        HTTPException: If update fails or menu not found
    """
    logger.info(f"User {current_user.id} updating menu {menu_id}")
    
    result = menu_service.update_menu(menu_id=menu_id, data=payload)
    
    if result.is_err():
        error = result.unwrap_err()
        logger.error(f"Failed to update menu {menu_id}: {error}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        )
    
    menu = result.unwrap()
    logger.info(f"Menu {menu_id} updated successfully")
    return menu


@router.delete(
    "/{menu_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete menu",
    description="Delete a menu. Requires admin permissions.",
    responses={
        204: {"description": "Menu deleted successfully"},
        403: {"description": "User not authorized to delete menus"},
        404: {"description": "Menu not found"},
        409: {"description": "Cannot delete published or approved menu"},
    },
)
async def delete_menu(
    menu_id: str = Path(..., description="Unique menu identifier"),
    menu_service: MessMenuService = Depends(get_menu_service),
    current_user: Any = Depends(get_current_user),
) -> None:
    """
    Delete a menu.
    
    Args:
        menu_id: Unique identifier of the menu
        menu_service: Menu service instance
        current_user: Currently authenticated user (must have admin rights)
        
    Raises:
        HTTPException: If deletion fails or menu not found
    """
    logger.info(f"User {current_user.id} deleting menu {menu_id}")
    
    result = menu_service.delete_menu(menu_id=menu_id)
    
    if result.is_err():
        error = result.unwrap_err()
        logger.error(f"Failed to delete menu {menu_id}: {error}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        )
    
    logger.info(f"Menu {menu_id} deleted successfully")


@router.get(
    "/by-date",
    response_model=MenuDetail,
    status_code=status.HTTP_200_OK,
    summary="Get menu by date",
    description="Retrieve menu for a specific date and hostel.",
    responses={
        200: {"description": "Menu retrieved successfully"},
        404: {"description": "No menu found for specified date"},
    },
)
async def get_menu_by_date(
    date: str = Query(
        ...,
        regex=r"^\d{4}-\d{2}-\d{2}$",
        description="Date in YYYY-MM-DD format",
    ),
    hostel_id: str = Query(..., description="Unique hostel identifier"),
    menu_service: MessMenuService = Depends(get_menu_service),
    current_user: Any = Depends(get_current_user),
) -> MenuDetail:
    """
    Get menu for a specific date.
    
    Args:
        date: Menu date in YYYY-MM-DD format
        hostel_id: Unique identifier of the hostel
        menu_service: Menu service instance
        current_user: Currently authenticated user
        
    Returns:
        MenuDetail: Menu for the specified date
        
    Raises:
        HTTPException: If no menu found for date
    """
    logger.debug(f"Fetching menu for hostel {hostel_id} on {date}")
    
    result = menu_service.get_menu_by_date(hostel_id=hostel_id, date=date)
    
    if result.is_err():
        error = result.unwrap_err()
        logger.error(f"Failed to fetch menu for date {date}: {error}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No menu found for hostel {hostel_id} on {date}",
        )
    
    return result.unwrap()


@router.get(
    "/today",
    response_model=MenuDetail,
    status_code=status.HTTP_200_OK,
    summary="Get today's menu",
    description="Retrieve today's menu for a specific hostel.",
    responses={
        200: {"description": "Today's menu retrieved successfully"},
        404: {"description": "No menu found for today"},
    },
)
async def get_today_menu(
    hostel_id: str = Query(..., description="Unique hostel identifier"),
    menu_service: MessMenuService = Depends(get_menu_service),
    current_user: Any = Depends(get_current_user),
) -> MenuDetail:
    """
    Get today's menu for a hostel.
    
    Args:
        hostel_id: Unique identifier of the hostel
        menu_service: Menu service instance
        current_user: Currently authenticated user
        
    Returns:
        MenuDetail: Today's menu
        
    Raises:
        HTTPException: If no menu found for today
    """
    logger.debug(f"Fetching today's menu for hostel {hostel_id}")
    
    result = menu_service.get_today_menu_for_hostel(hostel_id=hostel_id)
    
    if result.is_err():
        error = result.unwrap_err()
        logger.error(f"Failed to fetch today's menu: {error}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No menu found for hostel {hostel_id} today",
        )
    
    return result.unwrap()


@router.get(
    "/weekly",
    response_model=List[MenuResponse],
    status_code=status.HTTP_200_OK,
    summary="Get current week menus",
    description="Retrieve all menus for the current week (Monday-Sunday).",
    responses={
        200: {"description": "Weekly menus retrieved successfully"},
        404: {"description": "Hostel not found"},
    },
)
async def get_weekly_menu(
    hostel_id: str = Query(..., description="Unique hostel identifier"),
    start_date: Optional[str] = Query(
        None,
        regex=r"^\d{4}-\d{2}-\d{2}$",
        description="Week start date (defaults to current week Monday)",
    ),
    menu_service: MessMenuService = Depends(get_menu_service),
    current_user: Any = Depends(get_current_user),
) -> List[MenuResponse]:
    """
    Get weekly menus for a hostel.
    
    Args:
        hostel_id: Unique identifier of the hostel
        start_date: Optional week start date (defaults to current week)
        menu_service: Menu service instance
        current_user: Currently authenticated user
        
    Returns:
        List[MenuResponse]: Menus for the week
        
    Raises:
        HTTPException: If hostel not found
    """
    logger.debug(
        f"Fetching weekly menu for hostel {hostel_id}, start_date: {start_date}"
    )
    
    result = menu_service.get_weekly_menu_for_hostel(
        hostel_id=hostel_id,
        start_date=start_date,
    )
    
    if result.is_err():
        error = result.unwrap_err()
        logger.error(f"Failed to fetch weekly menu: {error}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Hostel with ID {hostel_id} not found",
        )
    
    menus = result.unwrap()
    logger.debug(f"Retrieved {len(menus)} weekly menus")
    return menus


@router.get(
    "/monthly-summary",
    response_model=List[DailyMenuSummary],
    status_code=status.HTTP_200_OK,
    summary="Get monthly menu summaries",
    description="Retrieve daily menu summaries for a specific month.",
    responses={
        200: {"description": "Monthly summaries retrieved successfully"},
        400: {"description": "Invalid month format"},
        404: {"description": "Hostel not found"},
    },
)
async def get_monthly_summaries(
    hostel_id: str = Query(..., description="Unique hostel identifier"),
    month: str = Query(
        ...,
        regex=r"^\d{4}-\d{2}$",
        description="Month in YYYY-MM format",
    ),
    menu_service: MessMenuService = Depends(get_menu_service),
    current_user: Any = Depends(get_current_user),
) -> List[DailyMenuSummary]:
    """
    Get monthly menu summaries.
    
    Args:
        hostel_id: Unique identifier of the hostel
        month: Month in YYYY-MM format
        menu_service: Menu service instance
        current_user: Currently authenticated user
        
    Returns:
        List[DailyMenuSummary]: Daily summaries for the month
        
    Raises:
        HTTPException: If invalid month format or hostel not found
    """
    logger.debug(f"Fetching monthly summaries for hostel {hostel_id}, month: {month}")
    
    result = menu_service.list_daily_summaries_for_month(
        hostel_id=hostel_id,
        month=month,
    )
    
    if result.is_err():
        error = result.unwrap_err()
        logger.error(f"Failed to fetch monthly summaries: {error}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        )
    
    summaries = result.unwrap()
    logger.debug(f"Retrieved {len(summaries)} daily summaries")
    return summaries


@router.post(
    "/{menu_id}/publish",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Publish menu",
    description="Publish an approved menu to make it visible to students.",
    responses={
        200: {"description": "Menu published successfully"},
        400: {"description": "Menu not in publishable state"},
        403: {"description": "User not authorized to publish menus"},
        404: {"description": "Menu not found"},
    },
)
async def publish_menu(
    menu_id: str = Path(..., description="Unique menu identifier"),
    menu_service: MessMenuService = Depends(get_menu_service),
    current_user: Any = Depends(get_current_user),
) -> dict:
    """
    Publish a menu.
    
    Args:
        menu_id: Unique identifier of the menu
        menu_service: Menu service instance
        current_user: Currently authenticated user (must have admin rights)
        
    Returns:
        dict: Publication confirmation
        
    Raises:
        HTTPException: If publication fails
    """
    logger.info(f"User {current_user.id} publishing menu {menu_id}")
    
    result = menu_service.publish_menu(menu_id=menu_id)
    
    if result.is_err():
        error = result.unwrap_err()
        logger.error(f"Failed to publish menu {menu_id}: {error}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        )
    
    logger.info(f"Menu {menu_id} published successfully")
    return result.unwrap()


@router.post(
    "/{menu_id}/unpublish",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Unpublish menu",
    description="Unpublish a menu to hide it from students.",
    responses={
        200: {"description": "Menu unpublished successfully"},
        400: {"description": "Menu cannot be unpublished"},
        403: {"description": "User not authorized to unpublish menus"},
        404: {"description": "Menu not found"},
    },
)
async def unpublish_menu(
    menu_id: str = Path(..., description="Unique menu identifier"),
    menu_service: MessMenuService = Depends(get_menu_service),
    current_user: Any = Depends(get_current_user),
) -> dict:
    """
    Unpublish a menu.
    
    Args:
        menu_id: Unique identifier of the menu
        menu_service: Menu service instance
        current_user: Currently authenticated user (must have admin rights)
        
    Returns:
        dict: Unpublication confirmation
        
    Raises:
        HTTPException: If unpublication fails
    """
    logger.info(f"User {current_user.id} unpublishing menu {menu_id}")
    
    result = menu_service.unpublish_menu(menu_id=menu_id)
    
    if result.is_err():
        error = result.unwrap_err()
        logger.error(f"Failed to unpublish menu {menu_id}: {error}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        )
    
    logger.info(f"Menu {menu_id} unpublished successfully")
    return result.unwrap()


@router.post(
    "/{menu_id}/duplicate",
    response_model=MenuDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Duplicate menu to date",
    description="Create a copy of an existing menu for a different date.",
    responses={
        201: {"description": "Menu duplicated successfully"},
        400: {"description": "Invalid target date or duplicate menu exists"},
        403: {"description": "User not authorized to duplicate menus"},
        404: {"description": "Source menu not found"},
    },
)
async def duplicate_menu(
    menu_id: str = Path(..., description="Source menu identifier"),
    target_date: str = Query(
        ...,
        regex=r"^\d{4}-\d{2}-\d{2}$",
        description="Target date for duplicated menu (YYYY-MM-DD)",
    ),
    menu_service: MessMenuService = Depends(get_menu_service),
    current_user: Any = Depends(get_current_user),
) -> MenuDetail:
    """
    Duplicate a menu to a different date.
    
    Args:
        menu_id: Unique identifier of the source menu
        target_date: Date for the duplicated menu (YYYY-MM-DD)
        menu_service: Menu service instance
        current_user: Currently authenticated user (must have admin rights)
        
    Returns:
        MenuDetail: Newly created duplicate menu
        
    Raises:
        HTTPException: If duplication fails
    """
    logger.info(
        f"User {current_user.id} duplicating menu {menu_id} to {target_date}"
    )
    
    result = menu_service.duplicate_menu(menu_id=menu_id, target_date=target_date)
    
    if result.is_err():
        error = result.unwrap_err()
        logger.error(f"Failed to duplicate menu: {error}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        )
    
    duplicate = result.unwrap()
    logger.info(f"Menu duplicated successfully, new menu ID: {duplicate.id}")
    return duplicate


@router.get(
    "/stats",
    response_model=MenuStats,
    status_code=status.HTTP_200_OK,
    summary="Get menu statistics",
    description="Get comprehensive statistics for menus in a hostel.",
    responses={
        200: {"description": "Statistics retrieved successfully"},
        404: {"description": "Hostel not found"},
    },
)
async def get_menu_stats(
    hostel_id: str = Query(..., description="Unique hostel identifier"),
    time_period: str = Query(
        "month",
        regex="^(week|month|quarter|year)$",
        description="Time period for statistics",
    ),
    menu_service: MessMenuService = Depends(get_menu_service),
    current_user: Any = Depends(get_current_user),
) -> MenuStats:
    """
    Get menu statistics for a hostel.
    
    Args:
        hostel_id: Unique identifier of the hostel
        time_period: Period for statistics calculation
        menu_service: Menu service instance
        current_user: Currently authenticated user
        
    Returns:
        MenuStats: Comprehensive menu statistics
        
    Raises:
        HTTPException: If hostel not found
    """
    logger.debug(
        f"Fetching menu statistics for hostel {hostel_id}, period: {time_period}"
    )
    
    result = menu_service.get_menu_statistics(
        hostel_id=hostel_id,
        time_period=time_period,
    )
    
    if result.is_err():
        error = result.unwrap_err()
        logger.error(f"Failed to fetch menu statistics: {error}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Hostel with ID {hostel_id} not found",
        )
    
    stats = result.unwrap()
    logger.debug(f"Retrieved menu statistics for hostel {hostel_id}")
    return stats


@router.get(
    "/search",
    response_model=List[MenuResponse],
    status_code=status.HTTP_200_OK,
    summary="Search menus",
    description="Search menus by various criteria.",
    responses={
        200: {"description": "Search results retrieved successfully"},
    },
)
async def search_menus(
    hostel_id: str = Query(..., description="Unique hostel identifier"),
    query: Optional[str] = Query(
        None,
        min_length=2,
        max_length=100,
        description="Search query for menu items",
    ),
    date_from: Optional[str] = Query(
        None,
        regex=r"^\d{4}-\d{2}-\d{2}$",
        description="Start date filter",
    ),
    date_to: Optional[str] = Query(
        None,
        regex=r"^\d{4}-\d{2}-\d{2}$",
        description="End date filter",
    ),
    status: Optional[str] = Query(
        None,
        description="Menu status filter",
    ),
    limit: int = Query(50, ge=1, le=200, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    menu_service: MessMenuService = Depends(get_menu_service),
    current_user: Any = Depends(get_current_user),
) -> List[MenuResponse]:
    """
    Search menus with various filters.
    
    Args:
        hostel_id: Unique identifier of the hostel
        query: Optional search query
        date_from: Optional start date filter
        date_to: Optional end date filter
        status: Optional status filter
        limit: Maximum number of results
        offset: Pagination offset
        menu_service: Menu service instance
        current_user: Currently authenticated user
        
    Returns:
        List[MenuResponse]: Matching menus
    """
    filters = {
        "query": query,
        "date_from": date_from,
        "date_to": date_to,
        "status": status,
        "limit": limit,
        "offset": offset,
    }
    
    # Remove None values
    filters = {k: v for k, v in filters.items() if v is not None}
    
    logger.debug(f"Searching menus with filters: {filters}")
    
    result = menu_service.search_menus(hostel_id=hostel_id, filters=filters)
    
    if result.is_err():
        logger.error(f"Menu search failed: {result.unwrap_err()}")
        return []
    
    menus = result.unwrap()
    logger.debug(f"Found {len(menus)} menus matching criteria")
    return menus