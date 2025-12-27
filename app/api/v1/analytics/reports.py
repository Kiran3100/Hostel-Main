"""
Analytics Export API Endpoints.

Provides export functionality for all analytics modules:
- Multiple export formats (CSV, Excel, PDF, JSON)
- Export history tracking
- Scheduled export management
"""

from __future__ import annotations

import logging
from typing import Annotated, Any, Dict, List

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.services.analytics.analytics_export_service import (
    AnalyticsExportService,
    ExportFormat as ServiceExportFormat,
)

from .dependencies import (
    AdminUser,
    ExportConfig,
    ExportFormat,
    HostelFilter,
    RequiredDateRange,
    SuperAdminUser,
    get_analytics_export_service,
    handle_analytics_error,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reports", tags=["analytics:reports"])

# Type alias for service dependency
ExportService = Annotated[
    AnalyticsExportService,
    Depends(get_analytics_export_service),
]


# =============================================================================
# Response Models
# =============================================================================


class ExportResult(BaseModel):
    """Response model for export operations."""

    export_id: str = Field(..., description="Unique identifier for the export")
    status: str = Field(..., description="Export status (pending, completed, failed)")
    file_name: str = Field(..., description="Generated file name")
    download_url: str | None = Field(None, description="URL to download the file")
    expires_at: str | None = Field(None, description="URL expiration timestamp")
    file_size_bytes: int | None = Field(None, description="File size in bytes")


class ExportHistoryItem(BaseModel):
    """Model for export history entry."""

    export_id: str
    report_type: str
    format: str
    created_at: str
    status: str
    file_name: str | None
    download_url: str | None


# =============================================================================
# Helper Functions
# =============================================================================


def convert_export_format(format: ExportFormat) -> ServiceExportFormat:
    """Convert API export format to service export format."""
    format_mapping = {
        ExportFormat.CSV: ServiceExportFormat.CSV,
        ExportFormat.EXCEL: ServiceExportFormat.EXCEL
        if hasattr(ServiceExportFormat, "EXCEL")
        else ServiceExportFormat.CSV,
        ExportFormat.PDF: ServiceExportFormat.PDF
        if hasattr(ServiceExportFormat, "PDF")
        else ServiceExportFormat.CSV,
        ExportFormat.JSON: ServiceExportFormat.JSON
        if hasattr(ServiceExportFormat, "JSON")
        else ServiceExportFormat.CSV,
    }
    return format_mapping.get(format, ServiceExportFormat.CSV)


# =============================================================================
# Endpoints
# =============================================================================


@router.get(
    "/bookings/export",
    response_model=ExportResult,
    summary="Export booking analytics report",
    description="""
    Exports booking analytics data in the specified format:
    - Booking summary and KPIs
    - Trend data
    - Source performance
    - Cancellation analytics
    
    Supported formats: CSV, Excel, PDF, JSON
    """,
    responses={
        200: {"description": "Export initiated successfully"},
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
    },
)
def export_bookings_report(
    hostel_filter: HostelFilter,
    date_range: RequiredDateRange,
    export_config: ExportConfig,
    _admin: AdminUser,
    service: ExportService,
) -> ExportResult:
    """
    Export booking analytics report.
    
    Generates a downloadable report containing
    booking analytics for the specified period.
    """
    try:
        result = service.export_booking_summary(
            hostel_id=hostel_filter.hostel_id,
            start_date=date_range.start_date,
            end_date=date_range.end_date,
            export_format=convert_export_format(export_config.format),
        )
        return _build_export_result(result)
    except Exception as e:
        logger.error(f"Error exporting bookings report: {e}")
        raise handle_analytics_error(e)


@router.get(
    "/complaints/export",
    response_model=ExportResult,
    summary="Export complaint analytics report",
    description="""
    Exports complaint analytics data in the specified format:
    - Complaint dashboard summary
    - Category breakdown
    - SLA metrics
    - Trend analysis
    """,
    responses={
        200: {"description": "Export initiated successfully"},
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
    },
)
def export_complaints_report(
    hostel_filter: HostelFilter,
    date_range: RequiredDateRange,
    export_config: ExportConfig,
    _admin: AdminUser,
    service: ExportService,
) -> ExportResult:
    """
    Export complaint analytics report.
    
    Generates a downloadable report containing
    complaint analytics for the specified period.
    """
    try:
        result = service.export_complaint_dashboard(
            hostel_id=hostel_filter.hostel_id,
            start_date=date_range.start_date,
            end_date=date_range.end_date,
            export_format=convert_export_format(export_config.format),
        )
        return _build_export_result(result)
    except Exception as e:
        logger.error(f"Error exporting complaints report: {e}")
        raise handle_analytics_error(e)


@router.get(
    "/financial/export",
    response_model=ExportResult,
    summary="Export financial analytics report",
    description="""
    Exports financial analytics data in the specified format:
    - Profit & Loss statement
    - Revenue breakdown
    - Expense breakdown
    - Cashflow summary
    - Financial ratios
    """,
    responses={
        200: {"description": "Export initiated successfully"},
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
    },
)
def export_financial_report(
    hostel_filter: HostelFilter,
    date_range: RequiredDateRange,
    export_config: ExportConfig,
    _admin: AdminUser,
    service: ExportService,
) -> ExportResult:
    """
    Export financial analytics report.
    
    Generates a downloadable financial report
    for the specified period.
    """
    try:
        result = service.export_financial_report(
            hostel_id=hostel_filter.hostel_id,
            start_date=date_range.start_date,
            end_date=date_range.end_date,
            export_format=convert_export_format(export_config.format),
        )
        return _build_export_result(result)
    except Exception as e:
        logger.error(f"Error exporting financial report: {e}")
        raise handle_analytics_error(e)


@router.get(
    "/occupancy/export",
    response_model=ExportResult,
    summary="Export occupancy analytics report",
    description="""
    Exports occupancy analytics data in the specified format:
    - Occupancy rates and trends
    - Room type breakdown
    - Seasonal patterns
    - Forecast data
    """,
    responses={
        200: {"description": "Export initiated successfully"},
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
    },
)
def export_occupancy_report(
    hostel_filter: HostelFilter,
    date_range: RequiredDateRange,
    export_config: ExportConfig,
    _admin: AdminUser,
    service: ExportService,
) -> ExportResult:
    """
    Export occupancy analytics report.
    
    Generates a downloadable occupancy report
    for the specified period.
    """
    try:
        result = service.export_occupancy_report(
            hostel_id=hostel_filter.hostel_id,
            start_date=date_range.start_date,
            end_date=date_range.end_date,
            export_format=convert_export_format(export_config.format),
        )
        return _build_export_result(result)
    except Exception as e:
        logger.error(f"Error exporting occupancy report: {e}")
        raise handle_analytics_error(e)


@router.get(
    "/platform/export",
    response_model=ExportResult,
    summary="Export platform overview report",
    description="""
    Exports platform-wide analytics data (super admin only):
    - Platform metrics summary
    - Growth and churn analysis
    - Tenant performance
    - System health overview
    """,
    responses={
        200: {"description": "Export initiated successfully"},
        401: {"description": "Authentication required"},
        403: {"description": "Super admin access required"},
    },
)
def export_platform_overview(
    date_range: RequiredDateRange,
    export_config: ExportConfig,
    _super_admin: SuperAdminUser,
    service: ExportService,
) -> ExportResult:
    """
    Export platform overview report.
    
    Generates a comprehensive platform report
    for executive review.
    """
    try:
        result = service.export_platform_overview(
            start_date=date_range.start_date,
            end_date=date_range.end_date,
            export_format=convert_export_format(export_config.format),
        )
        return _build_export_result(result)
    except Exception as e:
        logger.error(f"Error exporting platform overview: {e}")
        raise handle_analytics_error(e)


@router.get(
    "/exports/history",
    response_model=List[ExportHistoryItem],
    summary="Get analytics export history",
    description="""
    Retrieves history of analytics exports:
    - Recent exports
    - Export status
    - Download links (if still valid)
    - Export metadata
    """,
    responses={
        200: {"description": "Export history retrieved successfully"},
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
    },
)
def get_export_history(
    _admin: AdminUser,
    service: ExportService,
) -> List[ExportHistoryItem]:
    """
    Get analytics export history.
    
    Returns a list of previous exports with their
    status and download information.
    """
    try:
        history = service.get_export_history()
        return [_build_export_history_item(item) for item in history]
    except Exception as e:
        logger.error(f"Error fetching export history: {e}")
        raise handle_analytics_error(e)


# =============================================================================
# Helper Functions
# =============================================================================


def _build_export_result(result: Any) -> ExportResult:
    """Build ExportResult from service response."""
    if isinstance(result, dict):
        return ExportResult(
            export_id=result.get("export_id", ""),
            status=result.get("status", "pending"),
            file_name=result.get("file_name", ""),
            download_url=result.get("download_url"),
            expires_at=result.get("expires_at"),
            file_size_bytes=result.get("file_size_bytes"),
        )
    # Handle case where result is already a model or has attributes
    return ExportResult(
        export_id=getattr(result, "export_id", str(result)),
        status=getattr(result, "status", "completed"),
        file_name=getattr(result, "file_name", "export"),
        download_url=getattr(result, "download_url", None),
        expires_at=getattr(result, "expires_at", None),
        file_size_bytes=getattr(result, "file_size_bytes", None),
    )


def _build_export_history_item(item: Any) -> ExportHistoryItem:
    """Build ExportHistoryItem from service response."""
    if isinstance(item, dict):
        return ExportHistoryItem(
            export_id=item.get("export_id", ""),
            report_type=item.get("report_type", ""),
            format=item.get("format", ""),
            created_at=item.get("created_at", ""),
            status=item.get("status", ""),
            file_name=item.get("file_name"),
            download_url=item.get("download_url"),
        )
    return ExportHistoryItem(
        export_id=getattr(item, "export_id", ""),
        report_type=getattr(item, "report_type", ""),
        format=getattr(item, "format", ""),
        created_at=str(getattr(item, "created_at", "")),
        status=getattr(item, "status", ""),
        file_name=getattr(item, "file_name", None),
        download_url=getattr(item, "download_url", None),
    )