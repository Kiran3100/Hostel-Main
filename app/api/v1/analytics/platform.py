from datetime import date
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.analytics.platform_analytics import (
    ChurnAnalysis,
    GrowthMetrics,
    MonthlyMetric,
    PlatformMetrics,
    PlatformUsageAnalytics,
    RevenueMetrics,
    SystemHealthMetrics,
    TenantMetrics,
)
from app.services.analytics.platform_analytics_service import PlatformAnalyticsService

router = APIRouter(prefix="/platform", tags=["analytics:platform"])


def get_platform_analytics_service(
    db: Session = Depends(deps.get_db),
) -> PlatformAnalyticsService:
    return PlatformAnalyticsService(db=db)


@router.get(
    "/metrics",
    response_model=PlatformMetrics,
    summary="Get high-level platform metrics",
)
def get_platform_metrics(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    _super_admin=Depends(deps.get_super_admin_user),
    service: PlatformAnalyticsService = Depends(get_platform_analytics_service),
) -> Any:
    return service.get_platform_metrics(
        start_date=start_date,
        end_date=end_date,
    )


@router.get(
    "/growth",
    response_model=GrowthMetrics,
    summary="Get platform growth metrics",
)
def get_growth_metrics(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    _super_admin=Depends(deps.get_super_admin_user),
    service: PlatformAnalyticsService = Depends(get_platform_analytics_service),
) -> Any:
    return service.get_growth(
        start_date=start_date,
        end_date=end_date,
    )


@router.get(
    "/churn",
    response_model=ChurnAnalysis,
    summary="Get churn analysis",
)
def get_churn_analysis(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    _super_admin=Depends(deps.get_super_admin_user),
    service: PlatformAnalyticsService = Depends(get_platform_analytics_service),
) -> Any:
    return service.get_churn(
        start_date=start_date,
        end_date=end_date,
    )


@router.get(
    "/health",
    response_model=SystemHealthMetrics,
    summary="Get system health metrics",
)
def get_system_health(
    _super_admin=Depends(deps.get_super_admin_user),
    service: PlatformAnalyticsService = Depends(get_platform_analytics_service),
) -> Any:
    return service.get_system_health()


@router.get(
    "/revenue",
    response_model=RevenueMetrics,
    summary="Get platform revenue metrics",
)
def get_revenue_metrics(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    _super_admin=Depends(deps.get_super_admin_user),
    service: PlatformAnalyticsService = Depends(get_platform_analytics_service),
) -> Any:
    return service.get_revenue_metrics(
        start_date=start_date,
        end_date=end_date,
    )


@router.get(
    "/usage",
    response_model=PlatformUsageAnalytics,
    summary="Get platform usage analytics",
)
def get_platform_usage(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    _super_admin=Depends(deps.get_super_admin_user),
    service: PlatformAnalyticsService = Depends(get_platform_analytics_service),
) -> Any:
    return service.get_usage_analytics(
        start_date=start_date,
        end_date=end_date,
    )


@router.get(
    "/tenants",
    response_model=List[TenantMetrics],
    summary="Get metrics per tenant (hostel)",
)
def get_tenant_metrics(
    _super_admin=Depends(deps.get_super_admin_user),
    service: PlatformAnalyticsService = Depends(get_platform_analytics_service),
) -> Any:
    return service.get_tenant_metrics()