"""
Maintenance Analytics Service

Provides analytics and performance metrics for maintenance operations.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.maintenance import MaintenanceAnalyticsRepository
from app.schemas.common import DateRangeFilter
from app.schemas.maintenance import (
    MaintenanceAnalytics,
    PerformanceMetrics,
    ProductivityMetrics,
    CategoryBreakdown,
    VendorPerformance,
)
from app.core.exceptions import ValidationException


class MaintenanceAnalyticsService:
    """
    High-level service for maintenance analytics.

    Delegates heavy aggregations to MaintenanceAnalyticsRepository.
    """

    def __init__(self, analytics_repo: MaintenanceAnalyticsRepository) -> None:
        self.analytics_repo = analytics_repo

    def get_hostel_analytics(
        self,
        db: Session,
        hostel_id: UUID,
        period: DateRangeFilter,
    ) -> MaintenanceAnalytics:
        data = self.analytics_repo.get_analytics_for_hostel(
            db=db,
            hostel_id=hostel_id,
            start_date=period.start_date,
            end_date=period.end_date,
        )
        if not data:
            raise ValidationException("No maintenance analytics available")
        return MaintenanceAnalytics.model_validate(data)

    def get_performance_metrics(
        self,
        db: Session,
        hostel_id: UUID,
        period: DateRangeFilter,
    ) -> PerformanceMetrics:
        data = self.analytics_repo.get_performance_metrics(
            db=db,
            hostel_id=hostel_id,
            start_date=period.start_date,
            end_date=period.end_date,
        )
        if not data:
            raise ValidationException("No performance metrics available")
        return PerformanceMetrics.model_validate(data)

    def get_productivity_metrics(
        self,
        db: Session,
        hostel_id: UUID,
        period: DateRangeFilter,
    ) -> ProductivityMetrics:
        data = self.analytics_repo.get_productivity_metrics(
            db=db,
            hostel_id=hostel_id,
            start_date=period.start_date,
            end_date=period.end_date,
        )
        if not data:
            raise ValidationException("No productivity metrics available")
        return ProductivityMetrics.model_validate(data)

    def get_category_breakdown(
        self,
        db: Session,
        hostel_id: UUID,
        period: DateRangeFilter,
    ) -> CategoryBreakdown:
        data = self.analytics_repo.get_category_breakdown(
            db=db,
            hostel_id=hostel_id,
            start_date=period.start_date,
            end_date=period.end_date,
        )
        if not data:
            raise ValidationException("No category breakdown available")
        return CategoryBreakdown.model_validate(data)

    def get_vendor_performance(
        self,
        db: Session,
        hostel_id: UUID,
        period: DateRangeFilter,
    ) -> VendorPerformance:
        data = self.analytics_repo.get_vendor_performance(
            db=db,
            hostel_id=hostel_id,
            start_date=period.start_date,
            end_date=period.end_date,
        )
        if not data:
            raise ValidationException("No vendor performance data available")
        return VendorPerformance.model_validate(data)