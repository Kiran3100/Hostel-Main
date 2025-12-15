# app/repositories/services/__init__.py
from .attendance_repository import AttendanceRepository
from .complaint_repository import ComplaintRepository
from .leave_application_repository import LeaveApplicationRepository
from .maintenance_repository import MaintenanceRepository
from .inquiry_repository import InquiryRepository

__all__ = [
    "AttendanceRepository",
    "ComplaintRepository",
    "LeaveApplicationRepository",
    "MaintenanceRepository",
    "InquiryRepository",
]