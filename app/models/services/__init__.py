# models/services/__init__.py
from .complaint import Complaint
from .maintenance import Maintenance
from .attendance import Attendance
from .leave_application import LeaveApplication
from .inquiry import Inquiry

__all__ = [
    "Complaint",
    "Maintenance",
    "Attendance",
    "LeaveApplication",
    "Inquiry",
]