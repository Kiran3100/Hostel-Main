# app/services/student/__init__.py
"""
Student-related services.

- StudentService:
    Core CRUD, listing, and detail for students.

- StudentProfileService:
    Profile & document management on top of Student/User.

- StudentDashboardService:
    Student dashboard aggregation (financial, attendance, activity).

- StudentSearchService:
    Advanced search & sorting over students.

- StudentRoomHistoryService:
    Room/bed history and transfer-oriented views.

- StudentFinanceService:
    Student-level financial summaries & details.
"""

from .student_service import StudentService
from .student_profile_service import StudentProfileService, StudentDocumentStore
from .student_dashboard_service import StudentDashboardService
from .student_search_service import StudentSearchService
from .student_room_history_service import StudentRoomHistoryService
from .student_finance_service import StudentFinanceService

__all__ = [
    "StudentService",
    "StudentProfileService",
    "StudentDocumentStore",
    "StudentDashboardService",
    "StudentSearchService",
    "StudentRoomHistoryService",
    "StudentFinanceService",
]