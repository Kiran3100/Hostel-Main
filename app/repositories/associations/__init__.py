# app/repositories/associations/__init__.py
from .admin_hostel_repository import AdminHostelRepository
from .supervisor_hostel_repository import SupervisorHostelRepository
from .student_room_assignment_repository import StudentRoomAssignmentRepository
from .user_hostel_repository import UserHostelRepository

__all__ = [
    "AdminHostelRepository",
    "SupervisorHostelRepository",
    "StudentRoomAssignmentRepository",
    "UserHostelRepository",
]