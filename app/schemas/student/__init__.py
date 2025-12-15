# --- File: app/schemas/student/__init__.py ---
"""
Student schemas package.

Re-exports commonly used student-related schemas for convenient imports.

Example:
    from app.schemas.student import (
        StudentCreate,
        StudentDetail,
        StudentDashboard,
        RoomTransferRequest,
    )
"""

from __future__ import annotations

from app.schemas.student.student_base import (
    StudentBase,
    StudentCheckInRequest,
    StudentCheckOutRequest,
    StudentCreate,
    StudentRoomAssignment,
    StudentStatusUpdate,
    StudentUpdate,
)
from app.schemas.student.student_dashboard import (
    AttendanceSummary,
    PendingLeave,
    RecentAnnouncement,
    RecentComplaint,
    RecentPayment,
    StudentDashboard,
    StudentFinancialSummary,
    StudentStats,
    TodayMessMenu,
    UpcomingEvent,
)
from app.schemas.student.student_filters import (
    AdvancedStudentFilters,
    StudentBulkActionRequest,
    StudentExportRequest,
    StudentFilterParams,
    StudentSearchRequest,
    StudentSortOptions,
)
from app.schemas.student.student_profile import (
    DocumentInfo,
    DocumentUploadRequest,
    DocumentVerificationRequest,
    StudentBulkImport,
    StudentDocuments,
    StudentPreferences,
    StudentPrivacySettings,
    StudentProfileCreate,
    StudentProfileUpdate,
)
from app.schemas.student.student_response import (
    StudentContactInfo,
    StudentDetail,
    StudentDocumentInfo,
    StudentFinancialInfo,
    StudentListItem,
    StudentProfile,
    StudentResponse,
)
from app.schemas.student.student_room_history import (
    BulkRoomTransfer,
    RoomHistoryItem,
    RoomHistoryResponse,
    RoomSwapRequest,
    RoomTransferApproval,
    RoomTransferRequest,
    RoomTransferStatus,
    SingleTransfer,
)

__all__ = [
    # Base
    "StudentBase",
    "StudentCreate",
    "StudentUpdate",
    "StudentCheckInRequest",
    "StudentCheckOutRequest",
    "StudentRoomAssignment",
    "StudentStatusUpdate",
    # Response
    "StudentResponse",
    "StudentDetail",
    "StudentProfile",
    "StudentListItem",
    "StudentFinancialInfo",
    "StudentContactInfo",
    "StudentDocumentInfo",
    # Profile
    "StudentProfileCreate",
    "StudentProfileUpdate",
    "StudentDocuments",
    "DocumentInfo",
    "DocumentUploadRequest",
    "DocumentVerificationRequest",
    "StudentPreferences",
    "StudentPrivacySettings",
    "StudentBulkImport",
    # Room history
    "RoomHistoryResponse",
    "RoomHistoryItem",
    "RoomTransferRequest",
    "RoomTransferApproval",
    "RoomTransferStatus",
    "BulkRoomTransfer",
    "SingleTransfer",
    "RoomSwapRequest",
    # Dashboard
    "StudentDashboard",
    "StudentStats",
    "StudentFinancialSummary",
    "AttendanceSummary",
    "RecentPayment",
    "RecentComplaint",
    "PendingLeave",
    "RecentAnnouncement",
    "TodayMessMenu",
    "UpcomingEvent",
    # Filters
    "StudentFilterParams",
    "StudentSearchRequest",
    "StudentSortOptions",
    "StudentExportRequest",
    "StudentBulkActionRequest",
    "AdvancedStudentFilters",
]