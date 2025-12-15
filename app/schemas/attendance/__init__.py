# --- File: app/schemas/attendance/__init__.py ---
"""
Attendance schemas package.

Comprehensive attendance tracking, reporting, and alerting schemas
for hostel management system with enhanced validation and type safety.
"""

from __future__ import annotations

from app.schemas.attendance.attendance_alert import (
    AlertAcknowledgment,
    AlertConfig,
    AlertList,
    AlertSummary,
    AlertTrigger,
    AttendanceAlert,
)
from app.schemas.attendance.attendance_base import (
    AttendanceBase,
    AttendanceCreate,
    AttendanceUpdate,
    BulkAttendanceCreate,
    SingleAttendanceRecord,
)
from app.schemas.attendance.attendance_filters import (
    AttendanceExportRequest,
    AttendanceFilterParams,
    DateRangeRequest,
)
from app.schemas.attendance.attendance_policy import (
    AttendancePolicy,
    PolicyConfig,
    PolicyUpdate,
    PolicyViolation,
)
from app.schemas.attendance.attendance_record import (
    AttendanceCorrection,
    AttendanceRecordRequest,
    BulkAttendanceRequest,
    QuickAttendanceMarkAll,
    StudentAttendanceRecord,
)
from app.schemas.attendance.attendance_report import (
    AttendanceComparison,
    AttendanceReport,
    AttendanceSummary,
    ComparisonItem,
    DailyAttendanceRecord,
    MonthlyComparison,
    MonthlyReport,
    StudentMonthlySummary,
    TrendAnalysis,
    WeeklyAttendance,
)
from app.schemas.attendance.attendance_response import (
    AttendanceDetail,
    AttendanceListItem,
    AttendanceResponse,
    DailyAttendanceSummary,
)

__all__ = [
    # Base schemas
    "AttendanceBase",
    "AttendanceCreate",
    "AttendanceUpdate",
    "BulkAttendanceCreate",
    "SingleAttendanceRecord",
    # Response schemas
    "AttendanceResponse",
    "AttendanceDetail",
    "AttendanceListItem",
    "DailyAttendanceSummary",
    # Recording schemas
    "AttendanceRecordRequest",
    "BulkAttendanceRequest",
    "StudentAttendanceRecord",
    "AttendanceCorrection",
    "QuickAttendanceMarkAll",
    # Report schemas
    "AttendanceReport",
    "AttendanceSummary",
    "DailyAttendanceRecord",
    "TrendAnalysis",
    "WeeklyAttendance",
    "MonthlyComparison",
    "MonthlyReport",
    "StudentMonthlySummary",
    "AttendanceComparison",
    "ComparisonItem",
    # Policy schemas
    "AttendancePolicy",
    "PolicyConfig",
    "PolicyUpdate",
    "PolicyViolation",
    # Alert schemas
    "AttendanceAlert",
    "AlertConfig",
    "AlertTrigger",
    "AlertAcknowledgment",
    "AlertList",
    "AlertSummary",
    # Filter schemas
    "AttendanceFilterParams",
    "DateRangeRequest",
    "AttendanceExportRequest",
]