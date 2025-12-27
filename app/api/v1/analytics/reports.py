from datetime import date
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api import deps
from app.services.analytics.analytics_export_service import (
    AnalyticsExportService,
    ExportFormat,
)

router = APIRouter(prefix="/reports", tags=["analytics:reports"])


def get_analytics_export_service(
    db: Session = Depends(deps.get_db),
) -> AnalyticsExportService:
    return AnalyticsExportService(db=db)


@router.get(
    "/bookings/export",
    summary="Export booking analytics report",
)
def export_bookings_report(
    hostel_id: Optional[str] = Query(None),
    start_date: date = Query(...),
    end_date: date = Query(...),
    format: ExportFormat = Query(ExportFormat.CSV),
    _admin=Depends(deps.get_admin_user),
    service: AnalyticsExportService = Depends(get_analytics_export_service),
) -> Any:
    """
    Returns metadata about the generated export (e.g., download URL, file id).
    Adjust return type to your actual export result schema.
    """
    return service.export_booking_summary(
        hostel_id=hostel_id,
        start_date=start_date,
        end_date=end_date,
        export_format=format,
    )


@router.get(
    "/complaints/export",
    summary="Export complaint analytics report",
)
def export_complaints_report(
    hostel_id: Optional[str] = Query(None),
    start_date: date = Query(...),
    end_date: date = Query(...),
    format: ExportFormat = Query(ExportFormat.CSV),
    _admin=Depends(deps.get_admin_user),
    service: AnalyticsExportService = Depends(get_analytics_export_service),
) -> Any:
    return service.export_complaint_dashboard(
        hostel_id=hostel_id,
        start_date=start_date,
        end_date=end_date,
        export_format=format,
    )


@router.get(
    "/financial/export",
    summary="Export financial analytics report",
)
def export_financial_report(
    hostel_id: Optional[str] = Query(None),
    start_date: date = Query(...),
    end_date: date = Query(...),
    format: ExportFormat = Query(ExportFormat.CSV),
    _admin=Depends(deps.get_admin_user),
    service: AnalyticsExportService = Depends(get_analytics_export_service),
) -> Any:
    return service.export_financial_report(
        hostel_id=hostel_id,
        start_date=start_date,
        end_date=end_date,
        export_format=format,
    )


@router.get(
    "/occupancy/export",
    summary="Export occupancy analytics report",
)
def export_occupancy_report(
    hostel_id: Optional[str] = Query(None),
    start_date: date = Query(...),
    end_date: date = Query(...),
    format: ExportFormat = Query(ExportFormat.CSV),
    _admin=Depends(deps.get_admin_user),
    service: AnalyticsExportService = Depends(get_analytics_export_service),
) -> Any:
    return service.export_occupancy_report(
        hostel_id=hostel_id,
        start_date=start_date,
        end_date=end_date,
        export_format=format,
    )


@router.get(
    "/platform/export",
    summary="Export platform overview report",
)
def export_platform_overview(
    start_date: date = Query(...),
    end_date: date = Query(...),
    format: ExportFormat = Query(ExportFormat.CSV),
    _super_admin=Depends(deps.get_super_admin_user),
    service: AnalyticsExportService = Depends(get_analytics_export_service),
) -> Any:
    return service.export_platform_overview(
        start_date=start_date,
        end_date=end_date,
        export_format=format,
    )


@router.get(
    "/exports/history",
    summary="Get analytics export history",
)
def get_export_history(
    _admin=Depends(deps.get_admin_user),
    service: AnalyticsExportService = Depends(get_analytics_export_service),
) -> Any:
    return service.get_export_history()