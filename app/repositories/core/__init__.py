# app/repositories/core/__init__.py
from .user_repository import UserRepository
from .hostel_repository import HostelRepository
from .room_repository import RoomRepository
from .bed_repository import BedRepository
from .student_repository import StudentRepository
from .supervisor_repository import SupervisorRepository
from .admin_repository import AdminRepository

__all__ = [
    "UserRepository",
    "HostelRepository",
    "RoomRepository",
    "BedRepository",
    "StudentRepository",
    "SupervisorRepository",
    "AdminRepository",
]