"""
Attendance service layer.

Provides business logic for:
- Marking attendance (single/bulk/quick)
- Check-in/out handling
- Corrections workflow
- Policy management & violations
- Alerts (generate/acknowledge/list)
- Reporting & summaries

Version: 2.0.0
"""

from app.services.attendance.attendance_service import AttendanceService
from app.services.attendance.check_in_service import CheckInService
from app.services.attendance.attendance_correction_service import AttendanceCorrectionService
from app.services.attendance.attendance_policy_service import AttendancePolicyService
from app.services.attendance.attendance_alert_service import AttendanceAlertService
from app.services.attendance.attendance_report_service import AttendanceReportService

__all__ = [
    "AttendanceService",
    "CheckInService",
    "AttendanceCorrectionService",
    "AttendancePolicyService",
    "AttendanceAlertService",
    "AttendanceReportService",
]

__version__ = "2.0.0"