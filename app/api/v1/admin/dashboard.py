from typing import Any, Dict, List, Optional
from functools import lru_cache
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from app.api import deps
from app.core.cache import cache_result, invalidate_cache
from app.core.logging import get_logger
from app.core.background_tasks import enqueue_task
from app.schemas.admin import (
    MultiHostelDashboard,
    AggregatedStats,
    HostelQuickStats,
    CrossHostelComparison,
)
from app.services.admin.multi_hostel_dashboard_service import MultiHostelDashboardService

logger = get_logger(__name__)
router = APIRouter(prefix="/dashboard", tags=["admin:dashboard"])


class DashboardPreferences(BaseModel):
    """Schema for dashboard preferences"""
    refresh_interval: int = Field(default=300, ge=60, le=3600)  # 1 minute to 1 hour
    default_period: str = Field(default="7d", pattern="^(1d|7d|30d|90d)$")
    enabled_widgets: List[str] = Field(default_factory=list)
    chart_preferences: Dict[str, Any] = Field(default_factory=dict)


class DashboardFilter(BaseModel):
    """Schema for dashboard filtering"""
    hostel_ids: Optional[List[str]] = None
    date_range: Optional[str] = Field(None, pattern="^(1d|7d|30d|90d|custom)$")
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    include_inactive: bool = Field(default=False)


# Enhanced dependency injection
@lru_cache()
def get_dashboard_service(
    db: Session = Depends(deps.get_db),
) -> MultiHostelDashboardService:
    """Optimized dashboard service dependency with caching."""
    return MultiHostelDashboardService(db=db)


@router.get(
    "",
    response_model=MultiHostelDashboard,
    summary="Get comprehensive multi-hostel dashboard",
    description="Retrieve complete dashboard data with customizable filters and caching",
)
@cache_result(expire_time=300)  # Cache for 5 minutes
async def get_dashboard(
    period: str = Query("7d", pattern="^(1d|7d|30d|90d)$", description="Dashboard period"),
    hostel_ids: Optional[str] = Query(None, description="Comma-separated hostel IDs to include"),
    include_trends: bool = Query(True, description="Include trend analysis"),
    include_comparisons: bool = Query(True, description="Include cross-hostel comparisons"),
    refresh_cache: bool = Query(False, description="Force refresh cached data"),
    current_admin=Depends(deps.get_admin_user),
    service: MultiHostelDashboardService = Depends(get_dashboard_service),
) -> MultiHostelDashboard:
    """
    Get comprehensive multi-hostel dashboard with advanced filtering and caching.
    """
    try:
        # Parse hostel IDs if provided
        hostel_id_list = None
        if hostel_ids:
            hostel_id_list = [hid.strip() for hid in hostel_ids.split(",") if hid.strip()]
        
        # Force cache refresh if requested
        if refresh_cache:
            await invalidate_cache(f"dashboard:main:{current_admin.id}")
        
        dashboard = await service.generate_dashboard(
            admin_id=current_admin.id,
            period=period,
            hostel_ids=hostel_id_list,
            include_trends=include_trends,
            include_comparisons=include_comparisons
        )
        
        return dashboard
        
    except Exception as e:
        logger.error(f"Failed to generate dashboard for admin {current_admin.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate dashboard"
        )


@router.post(
    "/refresh",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger comprehensive dashboard refresh",
    description="Asynchronously refresh dashboard data with progress tracking",
)
async def refresh_dashboard(
    background_tasks: BackgroundTasks,
    refresh_type: str = Query("full", pattern="^(quick|full|deep)$", description="Refresh type"),
    notify_on_complete: bool = Query(True, description="Send notification when refresh completes"),
    current_admin=Depends(deps.get_admin_user),
    service: MultiHostelDashboardService = Depends(get_dashboard_service),
) -> Dict[str, Any]:
    """
    Trigger dashboard refresh with background processing and progress tracking.
    """
    try:
        # Enqueue refresh task
        task_id = await enqueue_task(
            "dashboard_refresh",
            admin_id=current_admin.id,
            refresh_type=refresh_type,
            notify_on_complete=notify_on_complete
        )
        
        # Start immediate quick refresh if requested
        if refresh_type == "quick":
            await service.quick_refresh_dashboard(admin_id=current_admin.id)
        
        logger.info(f"Dashboard refresh ({refresh_type}) triggered for admin {current_admin.id}")
        
        return {
            "detail": "Dashboard refresh triggered successfully",
            "task_id": task_id,
            "refresh_type": refresh_type,
            "estimated_completion": (datetime.utcnow() + timedelta(minutes=2)).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to trigger dashboard refresh for admin {current_admin.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to trigger dashboard refresh"
        )


@router.get(
    "/refresh/{task_id}/status",
    summary="Get dashboard refresh status",
    description="Check status of ongoing dashboard refresh operation",
)
async def get_refresh_status(
    task_id: str,
    current_admin=Depends(deps.get_admin_user),
    service: MultiHostelDashboardService = Depends(get_dashboard_service),
) -> Dict[str, Any]:
    """Get status of dashboard refresh operation."""
    try:
        status_info = await service.get_refresh_status(
            task_id=task_id,
            admin_id=current_admin.id
        )
        return status_info
        
    except Exception as e:
        logger.error(f"Failed to get refresh status for task {task_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve refresh status"
        )


@router.get(
    "/stats",
    response_model=AggregatedStats,
    summary="Get aggregated portfolio statistics",
    description="Retrieve comprehensive aggregated statistics across admin's hostel portfolio",
)
@cache_result(expire_time=600)  # Cache for 10 minutes
async def get_aggregated_stats(
    period: str = Query("30d", pattern="^(1d|7d|30d|90d)$", description="Statistics period"),
    include_forecasts: bool = Query(False, description="Include forecast data"),
    breakdown_by: str = Query("hostel", pattern="^(hostel|region|type)$", description="Breakdown dimension"),
    current_admin=Depends(deps.get_admin_user),
    service: MultiHostelDashboardService = Depends(get_dashboard_service),
) -> AggregatedStats:
    """
    Get aggregated portfolio statistics with advanced analytics and forecasting.
    """
    try:
        stats = await service.get_aggregated_stats(
            admin_id=current_admin.id,
            period=period,
            include_forecasts=include_forecasts,
            breakdown_by=breakdown_by
        )
        return stats
        
    except Exception as e:
        logger.error(f"Failed to get aggregated stats for admin {current_admin.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve aggregated statistics"
        )


@router.get(
    "/hostels/{hostel_id}/quick-stats",
    response_model=HostelQuickStats,
    summary="Get optimized quick stats for specific hostel",
    description="Retrieve essential statistics for a hostel with minimal latency",
)
@cache_result(expire_time=180)  # Cache for 3 minutes
async def get_hostel_quick_stats(
    hostel_id: str,
    include_alerts: bool = Query(True, description="Include active alerts and warnings"),
    include_trends: bool = Query(True, description="Include short-term trends"),
    current_admin=Depends(deps.get_admin_user),
    service: MultiHostelDashboardService = Depends(get_dashboard_service),
) -> HostelQuickStats:
    """
    Get optimized quick statistics for a specific hostel with enhanced information.
    """
    try:
        # Verify admin has access to this hostel
        has_access = await service.verify_hostel_access(
            admin_id=current_admin.id,
            hostel_id=hostel_id
        )
        if not has_access:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin does not have access to this hostel"
            )
        
        quick_stats = await service.get_hostel_quick_stats(
            admin_id=current_admin.id,
            hostel_id=hostel_id,
            include_alerts=include_alerts,
            include_trends=include_trends
        )
        return quick_stats
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get quick stats for hostel {hostel_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve hostel quick statistics"
        )


@router.get(
    "/comparison",
    response_model=CrossHostelComparison,
    summary="Get comprehensive cross-hostel comparison",
    description="Compare performance metrics across hostels in admin's portfolio",
)
@cache_result(expire_time=900)  # Cache for 15 minutes
async def get_cross_hostel_comparison(
    metrics: str = Query("occupancy,revenue,satisfaction", description="Comma-separated metrics to compare"),
    period: str = Query("30d", pattern="^(7d|30d|90d)$", description="Comparison period"),
    normalize_by: Optional[str] = Query(None, pattern="^(capacity|rooms|size)$", description="Normalization factor"),
    include_benchmarks: bool = Query(True, description="Include industry benchmarks"),
    current_admin=Depends(deps.get_admin_user),
    service: MultiHostelDashboardService = Depends(get_dashboard_service),
) -> CrossHostelComparison:
    """
    Get comprehensive cross-hostel comparison with advanced analytics and benchmarking.
    """
    try:
        # Parse metrics
        metric_list = [metric.strip() for metric in metrics.split(",") if metric.strip()]
        
        comparison = await service.get_cross_hostel_comparison(
            admin_id=current_admin.id,
            metrics=metric_list,
            period=period,
            normalize_by=normalize_by,
            include_benchmarks=include_benchmarks
        )
        return comparison
        
    except Exception as e:
        logger.error(f"Failed to get cross-hostel comparison for admin {current_admin.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate cross-hostel comparison"
        )


@router.get(
    "/preferences",
    response_model=DashboardPreferences,
    summary="Get dashboard preferences",
    description="Retrieve admin's dashboard preferences and customizations",
)
async def get_dashboard_preferences(
    current_admin=Depends(deps.get_admin_user),
    service: MultiHostelDashboardService = Depends(get_dashboard_service),
) -> DashboardPreferences:
    """Get admin's dashboard preferences."""
    try:
        preferences = await service.get_dashboard_preferences(admin_id=current_admin.id)
        return preferences
        
    except Exception as e:
        logger.error(f"Failed to get dashboard preferences for admin {current_admin.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve dashboard preferences"
        )


@router.put(
    "/preferences",
    response_model=DashboardPreferences,
    summary="Update dashboard preferences",
    description="Update admin's dashboard preferences and customizations",
)
async def update_dashboard_preferences(
    preferences: DashboardPreferences,
    current_admin=Depends(deps.get_admin_user),
    service: MultiHostelDashboardService = Depends(get_dashboard_service),
) -> DashboardPreferences:
    """Update admin's dashboard preferences."""
    try:
        updated_preferences = await service.update_dashboard_preferences(
            admin_id=current_admin.id,
            preferences=preferences
        )
        
        # Invalidate dashboard caches to apply new preferences
        await invalidate_cache(f"dashboard:*:{current_admin.id}")
        
        logger.info(f"Dashboard preferences updated for admin {current_admin.id}")
        return updated_preferences
        
    except Exception as e:
        logger.error(f"Failed to update dashboard preferences for admin {current_admin.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update dashboard preferences"
        )