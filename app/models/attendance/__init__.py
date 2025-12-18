# --- File: app/models/attendance/__init__.py ---
"""
Attendance models package.

Comprehensive attendance tracking, reporting, and alerting models
for hostel management system with enhanced validation and analytics.
"""

from app.models.attendance.attendance_alert import (
    AlertConfiguration,
    AlertNotification,
    AttendanceAlert,
)
from app.models.attendance.attendance_policy import (
    AttendancePolicy,
    PolicyException,
    PolicyViolation,
)
from app.models.attendance.attendance_record import (
    AttendanceCorrection,
    AttendanceRecord,
    BulkAttendanceLog,
)
from app.models.attendance.attendance_report import (
    AttendanceReport,
    AttendanceSummary,
    AttendanceTrend,
)

__all__ = [
    # Record models
    "AttendanceRecord",
    "AttendanceCorrection",
    "BulkAttendanceLog",
    # Policy models
    "AttendancePolicy",
    "PolicyViolation",
    "PolicyException",
    # Alert models
    "AttendanceAlert",
    "AlertConfiguration",
    "AlertNotification",
    # Report models
    "AttendanceReport",
    "AttendanceSummary",
    "AttendanceTrend",
]