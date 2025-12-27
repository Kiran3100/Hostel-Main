from typing import Any

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.attendance import (
    AttendanceReport,
    MonthlyReport,
    StudentMonthlySummary,
    AttendanceComparison,
    AttendanceExportRequest,
)
from app.services.attendance.attendance_report_service import AttendanceReportService

router = APIRouter(prefix="/attendance/reports", tags=["attendance:reports"])


def get_report_service(db: Session = Depends(deps.get_db)) -> AttendanceReportService:
    return AttendanceReportService(db=db)


@router.get(
    "/hostel",
    response_model=AttendanceReport,
    summary="Generate hostel-level attendance report",
)
def generate_hostel_report(
    hostel_id: str = Query(...),
    start_date: str = Query(..., description="YYYY-MM-DD"),
    end_date: str = Query(..., description="YYYY-MM-DD"),
    _admin=Depends(deps.get_admin_user),
    service: AttendanceReportService = Depends(get_report_service),
) -> Any:
    return service.generate_hostel_report(
        hostel_id=hostel_id,
        start_date_str=start_date,
        end_date_str=end_date,
        actor_id=_admin.id,
    )


@router.get(
    "/monthly",
    response_model=MonthlyReport,
    summary="Generate monthly attendance report for hostel",
)
def generate_monthly_report(
    hostel_id: str = Query(...),
    year: int = Query(..., ge=2000),
    month: int = Query(..., ge=1, le=12),
    _admin=Depends(deps.get_admin_user),
    service: AttendanceReportService = Depends(get_report_service),
) -> Any:
    return service.generate_monthly_report(
        hostel_id=hostel_id,
        year=year,
        month=month,
        actor_id=_admin.id,
    )


@router.get(
    "/students/{student_id}",
    response_model=StudentMonthlySummary,
    summary="Generate student attendance report",
)
def generate_student_report(
    student_id: str,
    year: int = Query(..., ge=2000),
    month: int = Query(..., ge=1, le=12),
    _admin=Depends(deps.get_admin_user),
    service: AttendanceReportService = Depends(get_report_service),
) -> Any:
    return service.generate_student_report(
        student_id=student_id,
        year=year,
        month=month,
        actor_id=_admin.id,
    )


@router.post(
    "/compare",
    response_model=AttendanceComparison,
    summary="Compare attendance across multiple entities",
)
def compare_attendance(
    payload: AttendanceComparison,
    _admin=Depends(deps.get_admin_user),
    service: AttendanceReportService = Depends(get_report_service),
) -> Any:
    """
    Payload already contains comparison items (students/rooms/hostels) and period.
    """
    return service.compare_attendance(payload=payload, actor_id=_admin.id)


@router.get(
    "/weekly-summary",
    summary="Get weekly attendance summary",
)
def get_weekly_summary(
    hostel_id: str = Query(...),
    week_start: str = Query(..., description="Week start date YYYY-MM-DD"),
    _admin=Depends(deps.get_admin_user),
    service: AttendanceReportService = Depends(get_report_service),
) -> Any:
    return service.get_weekly_summary(
        hostel_id=hostel_id,
        week_start_str=week_start,
        actor_id=_admin.id,
    )


@router.get(
    "/trend",
    summary="Get attendance trend analysis",
)
def get_trend_analysis(
    hostel_id: str = Query(...),
    start_date: str = Query(...),
    end_date: str = Query(...),
    _admin=Depends(deps.get_admin_user),
    service: AttendanceReportService = Depends(get_report_service),
) -> Any:
    return service.get_trend_analysis(
        hostel_id=hostel_id,
        start_date_str=start_date,
        end_date_str=end_date,
        actor_id=_admin.id,
    )


@router.post(
    "/export",
    summary="Export attendance data",
)
def export_attendance_report(
    payload: AttendanceExportRequest,
    _admin=Depends(deps.get_admin_user),
    service: AttendanceReportService = Depends(get_report_service),
) -> Any:
    """
    Exports attendance data to CSV/Excel/PDF as per AttendanceExportRequest.

    Return type should be an export result schema (e.g., containing file URL).
    """
    return service.export_report(payload=payload, actor_id=_admin.id)