# models/core/__init__.py
from .user import User
from .hostel import Hostel
from .room import Room
from .bed import Bed
from .student import Student
from .supervisor import Supervisor
from .admin import Admin

__all__ = [
    "User",
    "Hostel",
    "Room",
    "Bed",
    "Student",
    "Supervisor",
    "Admin",
]