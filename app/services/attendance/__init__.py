# --- File: app/services/attendance/__init__.py ---
"""
Attendance services package.

Comprehensive business logic layer for attendance management
with policy enforcement, alerting, reporting, and check-in operations.
"""

from app.services.attendance.attendance_service import AttendanceService
from app.services.attendance.attendance_policy_service import AttendancePolicyService
from app.services.attendance.attendance_alert_service import AttendanceAlertService
from app.services.attendance.attendance_correction_service import (
    AttendanceCorrectionService,
)
from app.services.attendance.attendance_report_service import AttendanceReportService
from app.services.attendance.check_in_service import CheckInService

__all__ = [
    "AttendanceService",
    "AttendancePolicyService",
    "AttendanceAlertService",
    "AttendanceCorrectionService",
    "AttendanceReportService",
    "CheckInService",
]