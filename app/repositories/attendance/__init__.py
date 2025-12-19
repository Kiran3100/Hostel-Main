# --- File: app/repositories/attendance/__init__.py ---
"""
Attendance repositories package.

Comprehensive repository implementations for attendance management
with advanced querying, analytics, and reporting capabilities.
"""

from app.repositories.attendance.attendance_record_repository import (
    AttendanceRecordRepository,
)
from app.repositories.attendance.attendance_policy_repository import (
    AttendancePolicyRepository,
)
from app.repositories.attendance.attendance_alert_repository import (
    AttendanceAlertRepository,
)
from app.repositories.attendance.attendance_report_repository import (
    AttendanceReportRepository,
)
from app.repositories.attendance.attendance_aggregate_repository import (
    AttendanceAggregateRepository,
)

__all__ = [
    "AttendanceRecordRepository",
    "AttendancePolicyRepository",
    "AttendanceAlertRepository",
    "AttendanceReportRepository",
    "AttendanceAggregateRepository",
]