# app/services/attendance/__init__.py
"""
Attendance-related services.

- AttendanceService: core attendance CRUD, listing, daily summary.
- AttendanceAlertService: alert configuration and alert lifecycle.
- AttendancePolicyService: attendance policy configuration and violation checks.
- AttendanceReportService: higher-level reports (student, monthly hostel).
"""

from .attendance_service import AttendanceService
from .attendance_alert_service import AttendanceAlertService, AlertStore
from .attendance_policy_service import AttendancePolicyService, PolicyStore
from .attendance_report_service import AttendanceReportService

__all__ = [
    "AttendanceService",
    "AttendanceAlertService",
    "AlertStore",
    "AttendancePolicyService",
    "PolicyStore",
    "AttendanceReportService",
]