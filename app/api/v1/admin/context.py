from typing import Any, Dict, Optional
from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from app.api import deps
from app.core.exceptions import HostelNotFoundError, ContextSwitchError
from app.core.cache import cache_result, invalidate_cache
from app.core.logging import get_logger
from app.schemas.admin import (
    HostelContext,
    HostelSwitchRequest,
    ActiveHostelResponse,
    ContextHistory,
    HostelSelectorResponse,
    RecentHostels,
    FavoriteHostels,
    UpdateFavoriteRequest,
)
from app.services.admin.hostel_context_service import HostelContextService
from app.services.admin.hostel_selector_service import HostelSelectorService

logger = get_logger(__name__)
router = APIRouter(prefix="/context", tags=["admin:context"])


class ContextPreference(BaseModel):
    """Schema for context preferences"""
    auto_switch_enabled: bool = Field(default=False)
    default_hostel_id: Optional[str] = None
    remember_last_context: bool = Field(default=True)
    notification_preferences: Dict[str, bool] = Field(default_factory=dict)


# Enhanced dependency injection
@lru_cache()
def get_context_service(
    db: Session = Depends(deps.get_db),
) -> HostelContextService:
    """Optimized context service dependency with caching."""
    return HostelContextService(db=db)


@lru_cache()
def get_selector_service(
    db: Session = Depends(deps.get_db),
) -> HostelSelectorService:
    """Optimized selector service dependency with caching."""
    return HostelSelectorService(db=db)


@router.get(
    "/active",
    response_model=HostelContext,
    summary="Get active hostel context with extended information",
    description="Retrieve current hostel context with additional metadata",
)
@cache_result(expire_time=180)  # Cache for 3 minutes
async def get_active_context(
    include_permissions: bool = Query(True, description="Include permission summary"),
    include_statistics: bool = Query(False, description="Include basic hostel statistics"),
    current_admin=Depends(deps.get_admin_user),
    service: HostelContextService = Depends(get_context_service),
) -> HostelContext:
    """
    Get active hostel context with enhanced information and caching.
    """
    try:
        context = await service.get_active_context(
            admin_id=current_admin.id,
            include_permissions=include_permissions,
            include_statistics=include_statistics
        )
        
        if not context:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No active context found for admin"
            )
            
        return context
        
    except Exception as e:
        logger.error(f"Failed to get active context for admin {current_admin.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve active context"
        )


@router.post(
    "/switch",
    response_model=ActiveHostelResponse,
    status_code=status.HTTP_200_OK,
    summary="Switch active hostel context with validation",
    description="Switch to different hostel context with permission validation",
)
async def switch_hostel_context(
    payload: HostelSwitchRequest,
    validate_permissions: bool = Query(True, description="Validate admin permissions for target hostel"),
    save_as_favorite: bool = Query(False, description="Add to favorites if not already present"),
    current_admin=Depends(deps.get_admin_user),
    service: HostelContextService = Depends(get_context_service),
) -> ActiveHostelResponse:
    """
    Switch hostel context with comprehensive validation and audit logging.
    """
    try:
        # Validate hostel access if requested
        if validate_permissions:
            has_access = await service.validate_hostel_access(
                admin_id=current_admin.id,
                hostel_id=payload.hostel_id
            )
            if not has_access:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Admin does not have access to the specified hostel"
                )
        
        response = await service.switch_hostel(
            admin_id=current_admin.id,
            payload=payload,
            save_as_favorite=save_as_favorite
        )
        
        # Invalidate related caches
        await invalidate_cache(f"context:active:{current_admin.id}")
        
        logger.info(f"Admin {current_admin.id} switched to hostel {payload.hostel_id}")
        return response
        
    except HTTPException:
        raise
    except ContextSwitchError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Context switch failed: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Failed to switch context for admin {current_admin.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to switch hostel context"
        )


@router.get(
    "/history",
    response_model=ContextHistory,
    summary="Get comprehensive context switch history",
    description="Retrieve context switch history with filtering and pagination",
)
async def get_context_history(
    days: int = Query(30, ge=1, le=365, description="Number of days to retrieve"),
    include_metadata: bool = Query(True, description="Include switch metadata and reasons"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(50, ge=1, le=100, description="Items per page"),
    current_admin=Depends(deps.get_admin_user),
    service: HostelContextService = Depends(get_context_service),
) -> ContextHistory:
    """
    Get context switch history with enhanced filtering and pagination.
    """
    try:
        history = await service.get_context_history(
            admin_id=current_admin.id,
            days=days,
            include_metadata=include_metadata,
            page=page,
            limit=limit
        )
        return history
        
    except Exception as e:
        logger.error(f"Failed to get context history for admin {current_admin.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve context history"
        )


@router.get(
    "/selector",
    response_model=HostelSelectorResponse,
    summary="Get comprehensive hostel selector data",
    description="Retrieve all data needed for hostel selection interface",
)
@cache_result(expire_time=300)  # Cache for 5 minutes
async def get_hostel_selector(
    include_statistics: bool = Query(True, description="Include hostel statistics"),
    include_recent: bool = Query(True, description="Include recent hostels"),
    include_favorites: bool = Query(True, description="Include favorite hostels"),
    filter_by_permission: bool = Query(True, description="Filter by admin permissions"),
    current_admin=Depends(deps.get_admin_user),
    service: HostelSelectorService = Depends(get_selector_service),
) -> HostelSelectorResponse:
    """
    Get comprehensive hostel selector data with customizable inclusions.
    """
    try:
        selector_data = await service.get_selector(
            admin_id=current_admin.id,
            include_statistics=include_statistics,
            include_recent=include_recent,
            include_favorites=include_favorites,
            filter_by_permission=filter_by_permission
        )
        return selector_data
        
    except Exception as e:
        logger.error(f"Failed to get selector data for admin {current_admin.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve hostel selector data"
        )


@router.get(
    "/selector/recent",
    response_model=RecentHostels,
    summary="Get recent hostels with usage statistics",
    description="Retrieve recently accessed hostels with usage metadata",
)
@cache_result(expire_time=180)  # Cache for 3 minutes
async def get_recent_hostels(
    limit: int = Query(10, ge=1, le=50, description="Maximum number of recent hostels"),
    days: int = Query(30, ge=1, le=90, description="Days to look back for recent activity"),
    current_admin=Depends(deps.get_admin_user),
    service: HostelSelectorService = Depends(get_selector_service),
) -> RecentHostels:
    """
    Get recent hostels with enhanced usage statistics and metadata.
    """
    try:
        recent_hostels = await service.get_recent_hostels(
            admin_id=current_admin.id,
            limit=limit,
            days=days
        )
        return recent_hostels
        
    except Exception as e:
        logger.error(f"Failed to get recent hostels for admin {current_admin.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve recent hostels"
        )


@router.get(
    "/selector/favorites",
    response_model=FavoriteHostels,
    summary="Get favorite hostels with metadata",
    description="Retrieve admin's favorite hostels with usage statistics",
)
@cache_result(expire_time=300)  # Cache for 5 minutes
async def get_favorite_hostels(
    include_statistics: bool = Query(True, description="Include usage statistics"),
    sort_by_usage: bool = Query(False, description="Sort by usage frequency"),
    current_admin=Depends(deps.get_admin_user),
    service: HostelSelectorService = Depends(get_selector_service),
) -> FavoriteHostels:
    """
    Get favorite hostels with enhanced metadata and sorting options.
    """
    try:
        favorites = await service.get_favorite_hostels(
            admin_id=current_admin.id,
            include_statistics=include_statistics,
            sort_by_usage=sort_by_usage
        )
        return favorites
        
    except Exception as e:
        logger.error(f"Failed to get favorite hostels for admin {current_admin.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve favorite hostels"
        )


@router.post(
    "/selector/favorites",
    response_model=FavoriteHostels,
    summary="Update favorite hostels with validation",
    description="Add or remove hostels from favorites with access validation",
)
async def update_favorite_hostels(
    payload: UpdateFavoriteRequest,
    validate_access: bool = Query(True, description="Validate admin has access to hostel"),
    current_admin=Depends(deps.get_admin_user),
    service: HostelSelectorService = Depends(get_selector_service),
) -> FavoriteHostels:
    """
    Update favorite hostels with comprehensive validation and audit logging.
    """
    try:
        # Validate hostel access if requested
        if validate_access and payload.action == "add":
            has_access = await service.validate_hostel_access(
                admin_id=current_admin.id,
                hostel_id=payload.hostel_id
            )
            if not has_access:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Admin does not have access to the specified hostel"
                )
        
        favorites = await service.update_favorite(
            admin_id=current_admin.id,
            payload=payload
        )
        
        # Invalidate related caches
        await invalidate_cache(f"favorites:{current_admin.id}")
        
        logger.info(f"Admin {current_admin.id} {payload.action}ed hostel {payload.hostel_id} to/from favorites")
        return favorites
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update favorites for admin {current_admin.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update favorite hostels"
        )


@router.get(
    "/preferences",
    response_model=ContextPreference,
    summary="Get context preferences",
    description="Retrieve admin's context switching preferences",
)
async def get_context_preferences(
    current_admin=Depends(deps.get_admin_user),
    service: HostelContextService = Depends(get_context_service),
) -> ContextPreference:
    """Get admin's context switching preferences."""
    try:
        preferences = await service.get_context_preferences(admin_id=current_admin.id)
        return preferences
        
    except Exception as e:
        logger.error(f"Failed to get context preferences for admin {current_admin.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve context preferences"
        )


@router.put(
    "/preferences",
    response_model=ContextPreference,
    summary="Update context preferences",
    description="Update admin's context switching preferences",
)
async def update_context_preferences(
    preferences: ContextPreference,
    current_admin=Depends(deps.get_admin_user),
    service: HostelContextService = Depends(get_context_service),
) -> ContextPreference:
    """Update admin's context switching preferences."""
    try:
        updated_preferences = await service.update_context_preferences(
            admin_id=current_admin.id,
            preferences=preferences
        )
        
        logger.info(f"Context preferences updated for admin {current_admin.id}")
        return updated_preferences
        
    except Exception as e:
        logger.error(f"Failed to update context preferences for admin {current_admin.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update context preferences"
        )