"""
Shared dependencies for analytics API endpoints.

Provides reusable query parameter models, service factories,
caching utilities, and common validation logic.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import date, timedelta
from enum import Enum
from functools import lru_cache, wraps
from typing import (
    TYPE_CHECKING,
    Annotated,
    Any,
    Callable,
    Generic,
    Optional,
    TypeVar,
)
from uuid import UUID

from fastapi import Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.api import deps

if TYPE_CHECKING:
    from app.services.analytics.booking_analytics_service import BookingAnalyticsService
    from app.services.analytics.complaint_analytics_service import ComplaintAnalyticsService
    from app.services.analytics.dashboard_analytics_service import DashboardAnalyticsService
    from app.services.analytics.financial_analytics_service import FinancialAnalyticsService
    from app.services.analytics.occupancy_analytics_service import OccupancyAnalyticsService
    from app.services.analytics.platform_analytics_service import PlatformAnalyticsService
    from app.services.analytics.analytics_export_service import AnalyticsExportService

logger = logging.getLogger(__name__)

T = TypeVar("T")


# =============================================================================
# Enums
# =============================================================================


class Granularity(str, Enum):
    """Time granularity options for trend analysis."""

    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class ForecastModel(str, Enum):
    """Available forecasting models."""

    EXPONENTIAL_SMOOTHING = "EXPONENTIAL_SMOOTHING"
    LINEAR_REGRESSION = "LINEAR_REGRESSION"
    MOVING_AVERAGE = "MOVING_AVERAGE"


class ExportFormat(str, Enum):
    """Supported export formats."""

    CSV = "csv"
    EXCEL = "xlsx"
    PDF = "pdf"
    JSON = "json"


# =============================================================================
# Query Parameter Models
# =============================================================================


class DateRangeParams(BaseModel):
    """Base date range query parameters."""

    start_date: Optional[date] = Field(
        default=None,
        description="Start date for the analytics period (inclusive)",
        examples=["2024-01-01"],
    )
    end_date: Optional[date] = Field(
        default=None,
        description="End date for the analytics period (inclusive)",
        examples=["2024-12-31"],
    )

    @field_validator("end_date")
    @classmethod
    def validate_date_range(cls, v: Optional[date], info) -> Optional[date]:
        """Ensure end_date is not before start_date."""
        start = info.data.get("start_date")
        if v and start and v < start:
            raise ValueError("end_date must be greater than or equal to start_date")
        return v

    def get_default_range(self, days_back: int = 30) -> tuple[date, date]:
        """Return date range with defaults if not specified."""
        end = self.end_date or date.today()
        start = self.start_date or (end - timedelta(days=days_back))
        return start, end


class RequiredDateRangeParams(BaseModel):
    """Required date range query parameters."""

    start_date: date = Field(
        ...,
        description="Start date for the analytics period (inclusive)",
        examples=["2024-01-01"],
    )
    end_date: date = Field(
        ...,
        description="End date for the analytics period (inclusive)",
        examples=["2024-12-31"],
    )

    @field_validator("end_date")
    @classmethod
    def validate_date_range(cls, v: date, info) -> date:
        """Ensure end_date is not before start_date."""
        start = info.data.get("start_date")
        if start and v < start:
            raise ValueError("end_date must be greater than or equal to start_date")
        return v


class HostelFilterParams(BaseModel):
    """Hostel filtering parameters."""

    hostel_id: Optional[str] = Field(
        default=None,
        description="Filter by specific hostel UUID",
        examples=["550e8400-e29b-41d4-a716-446655440000"],
    )

    @field_validator("hostel_id")
    @classmethod
    def validate_hostel_id(cls, v: Optional[str]) -> Optional[str]:
        """Validate hostel_id is a valid UUID if provided."""
        if v is not None:
            try:
                UUID(v)
            except ValueError:
                raise ValueError("hostel_id must be a valid UUID")
        return v


class TrendParams(BaseModel):
    """Trend analysis parameters."""

    granularity: Granularity = Field(
        default=Granularity.DAILY,
        description="Time granularity for trend data",
    )


class ForecastParams(BaseModel):
    """Forecast parameters."""

    days_ahead: int = Field(
        default=30,
        ge=1,
        le=365,
        description="Number of days to forecast",
    )
    model: ForecastModel = Field(
        default=ForecastModel.EXPONENTIAL_SMOOTHING,
        description="Forecasting model to use",
    )


class ExportParams(BaseModel):
    """Export parameters."""

    format: ExportFormat = Field(
        default=ExportFormat.CSV,
        description="Export file format",
        alias="format",
    )


# =============================================================================
# Dependency Functions for Query Parameters
# =============================================================================


def get_date_range_params(
    start_date: Annotated[
        Optional[date],
        Query(description="Start date (inclusive)", examples=["2024-01-01"]),
    ] = None,
    end_date: Annotated[
        Optional[date],
        Query(description="End date (inclusive)", examples=["2024-12-31"]),
    ] = None,
) -> DateRangeParams:
    """Dependency for optional date range parameters."""
    return DateRangeParams(start_date=start_date, end_date=end_date)


def get_required_date_range_params(
    start_date: Annotated[
        date,
        Query(..., description="Start date (inclusive)", examples=["2024-01-01"]),
    ],
    end_date: Annotated[
        date,
        Query(..., description="End date (inclusive)", examples=["2024-12-31"]),
    ],
) -> RequiredDateRangeParams:
    """Dependency for required date range parameters."""
    return RequiredDateRangeParams(start_date=start_date, end_date=end_date)


def get_hostel_filter_params(
    hostel_id: Annotated[
        Optional[str],
        Query(
            description="Filter by hostel UUID",
            examples=["550e8400-e29b-41d4-a716-446655440000"],
        ),
    ] = None,
) -> HostelFilterParams:
    """Dependency for hostel filtering parameters."""
    return HostelFilterParams(hostel_id=hostel_id)


def get_trend_params(
    granularity: Annotated[
        Granularity,
        Query(description="Time granularity for trend data"),
    ] = Granularity.DAILY,
) -> TrendParams:
    """Dependency for trend analysis parameters."""
    return TrendParams(granularity=granularity)


def get_forecast_params(
    days_ahead: Annotated[
        int,
        Query(ge=1, le=365, description="Number of days to forecast"),
    ] = 30,
    model: Annotated[
        ForecastModel,
        Query(description="Forecasting model to use"),
    ] = ForecastModel.EXPONENTIAL_SMOOTHING,
) -> ForecastParams:
    """Dependency for forecast parameters."""
    return ForecastParams(days_ahead=days_ahead, model=model)


def get_export_params(
    format: Annotated[
        ExportFormat,
        Query(description="Export file format"),
    ] = ExportFormat.CSV,
) -> ExportParams:
    """Dependency for export parameters."""
    return ExportParams(format=format)


# =============================================================================
# Service Factory Dependencies
# =============================================================================


class ServiceFactory(Generic[T]):
    """Generic service factory for dependency injection."""

    def __init__(self, service_class: type[T]) -> None:
        self._service_class = service_class

    def __call__(self, db: Session = Depends(deps.get_db)) -> T:
        return self._service_class(db=db)


def get_booking_analytics_service(
    db: Session = Depends(deps.get_db),
) -> "BookingAnalyticsService":
    """Factory for BookingAnalyticsService."""
    from app.services.analytics.booking_analytics_service import BookingAnalyticsService
    return BookingAnalyticsService(db=db)


def get_complaint_analytics_service(
    db: Session = Depends(deps.get_db),
) -> "ComplaintAnalyticsService":
    """Factory for ComplaintAnalyticsService."""
    from app.services.analytics.complaint_analytics_service import ComplaintAnalyticsService
    return ComplaintAnalyticsService(db=db)


def get_dashboard_analytics_service(
    db: Session = Depends(deps.get_db),
) -> "DashboardAnalyticsService":
    """Factory for DashboardAnalyticsService."""
    from app.services.analytics.dashboard_analytics_service import DashboardAnalyticsService
    return DashboardAnalyticsService(db=db)


def get_financial_analytics_service(
    db: Session = Depends(deps.get_db),
) -> "FinancialAnalyticsService":
    """Factory for FinancialAnalyticsService."""
    from app.services.analytics.financial_analytics_service import FinancialAnalyticsService
    return FinancialAnalyticsService(db=db)


def get_occupancy_analytics_service(
    db: Session = Depends(deps.get_db),
) -> "OccupancyAnalyticsService":
    """Factory for OccupancyAnalyticsService."""
    from app.services.analytics.occupancy_analytics_service import OccupancyAnalyticsService
    return OccupancyAnalyticsService(db=db)


def get_platform_analytics_service(
    db: Session = Depends(deps.get_db),
) -> "PlatformAnalyticsService":
    """Factory for PlatformAnalyticsService."""
    from app.services.analytics.platform_analytics_service import PlatformAnalyticsService
    return PlatformAnalyticsService(db=db)


def get_analytics_export_service(
    db: Session = Depends(deps.get_db),
) -> "AnalyticsExportService":
    """Factory for AnalyticsExportService."""
    from app.services.analytics.analytics_export_service import AnalyticsExportService
    return AnalyticsExportService(db=db)


# =============================================================================
# Caching Utilities
# =============================================================================


def generate_cache_key(*args: Any, **kwargs: Any) -> str:
    """Generate a cache key from arguments."""
    key_parts = [str(arg) for arg in args]
    key_parts.extend(f"{k}:{v}" for k, v in sorted(kwargs.items()))
    key_string = "|".join(key_parts)
    return hashlib.md5(key_string.encode()).hexdigest()


def cached_response(ttl_seconds: int = 300) -> Callable:
    """
    Decorator for caching endpoint responses.
    
    Note: This is a simple in-memory cache. For production,
    consider using Redis or similar distributed cache.
    """
    cache: dict[str, tuple[Any, float]] = {}

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            import time

            cache_key = generate_cache_key(func.__name__, *args, **kwargs)
            current_time = time.time()

            if cache_key in cache:
                result, cached_at = cache[cache_key]
                if current_time - cached_at < ttl_seconds:
                    logger.debug(f"Cache hit for {func.__name__}")
                    return result

            result = func(*args, **kwargs)
            cache[cache_key] = (result, current_time)
            logger.debug(f"Cache miss for {func.__name__}, caching result")
            return result

        return wrapper

    return decorator


# =============================================================================
# Error Handling
# =============================================================================


class AnalyticsError(Exception):
    """Base exception for analytics errors."""

    def __init__(
        self,
        message: str,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
    ) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class DateRangeError(AnalyticsError):
    """Exception for invalid date range."""

    def __init__(self, message: str = "Invalid date range") -> None:
        super().__init__(message, status.HTTP_400_BAD_REQUEST)


class HostelNotFoundError(AnalyticsError):
    """Exception when hostel is not found."""

    def __init__(self, hostel_id: str) -> None:
        super().__init__(
            f"Hostel with ID '{hostel_id}' not found",
            status.HTTP_404_NOT_FOUND,
        )


def handle_analytics_error(error: Exception) -> HTTPException:
    """Convert analytics errors to HTTP exceptions."""
    if isinstance(error, AnalyticsError):
        return HTTPException(
            status_code=error.status_code,
            detail=error.message,
        )
    logger.exception("Unexpected error in analytics endpoint")
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="An unexpected error occurred while processing analytics",
    )


# =============================================================================
# Type Aliases for Common Dependencies
# =============================================================================

AdminUser = Annotated[Any, Depends(deps.get_admin_user)]
SuperAdminUser = Annotated[Any, Depends(deps.get_super_admin_user)]
CurrentUserWithRoles = Annotated[Any, Depends(deps.get_current_user_with_roles)]

DateRange = Annotated[DateRangeParams, Depends(get_date_range_params)]
RequiredDateRange = Annotated[RequiredDateRangeParams, Depends(get_required_date_range_params)]
HostelFilter = Annotated[HostelFilterParams, Depends(get_hostel_filter_params)]
TrendConfig = Annotated[TrendParams, Depends(get_trend_params)]
ForecastConfig = Annotated[ForecastParams, Depends(get_forecast_params)]
ExportConfig = Annotated[ExportParams, Depends(get_export_params)]