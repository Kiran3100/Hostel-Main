# models/associations/__init__.py
from .admin_hostel import AdminHostel
from .supervisor_hostel import SupervisorHostel
from .student_room import StudentRoomAssignment
from .user_hostel import UserHostel

__all__ = [
    "AdminHostel",
    "SupervisorHostel",
    "StudentRoomAssignment",
    "UserHostel",
]