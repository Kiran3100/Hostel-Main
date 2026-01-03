"""
Student schemas package.

Re-exports commonly used student-related schemas for convenient imports.

Example:
    from app.schemas.student import (
        StudentCreate,
        StudentDetail,
        StudentDashboard,
        RoomTransferRequest,
        StudentDocument,
        GuardianContact,
        OnboardingRequest,
        StudentStatus,
    )
"""

from typing import Union

# Base student schemas
from app.schemas.student.student_base import (
    StudentBase,
    StudentCheckInRequest,
    StudentCheckOutRequest,
    StudentCreate,
    StudentRoomAssignment,
    StudentStatusUpdate,
    StudentUpdate,
)

# Dashboard schemas
from app.schemas.student.student_dashboard import (
    AttendanceSummary,
    DashboardPeriod,
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

# Filter schemas
from app.schemas.student.student_filters import (
    AdvancedStudentFilters,
    StudentBulkActionRequest,
    StudentExportRequest,
    StudentFilterParams,
    StudentSearchRequest,
    StudentSortOptions,
)

# Profile schemas
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

# Response schemas
from app.schemas.student.student_response import (
    StudentContactInfo,
    StudentDetail,
    StudentDocumentInfo,
    StudentFinancialInfo,
    StudentListItem,
    StudentProfile,
    StudentResponse,
)

# Room history schemas
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

# Document schemas (API compatibility)
from app.schemas.student.student_document import (
    DocumentType,
    DocumentVerificationStatus,
    StudentDocument,
    StudentDocumentCreate,
    StudentDocumentUpdate,
    DocumentVerificationRequest as DocumentVerificationRequestAPI,
    DocumentListResponse,
)

# Guardian schemas (API compatibility)
from app.schemas.student.guardian_contact import (
    GuardianRelationType,
    GuardianContact,
    GuardianContactCreate,
    GuardianContactUpdate,
    GuardianContactList,
)

# Lifecycle schemas (API compatibility)
from app.schemas.student.student_lifecycle import (
    OnboardingRequest,
    CheckoutRequest,
    BulkStatusUpdate,
    StatusUpdateRequest,
    OnboardingResponse,
    CheckoutResponse,
)

# Common enums used across student schemas
from app.schemas.common.enums import (
    StudentStatus,
    DietaryPreference,
    IDProofType,
)

__all__ = [
    # Base schemas
    "StudentBase",
    "StudentCreate",
    "StudentUpdate",
    "StudentCheckInRequest",
    "StudentCheckOutRequest",
    "StudentRoomAssignment",
    "StudentStatusUpdate",
    
    # Response schemas
    "StudentResponse",
    "StudentDetail",
    "StudentProfile",
    "StudentListItem",
    "StudentFinancialInfo",
    "StudentContactInfo",
    "StudentDocumentInfo",
    
    # Profile schemas
    "StudentProfileCreate",
    "StudentProfileUpdate",
    "StudentDocuments",
    "DocumentInfo",
    "DocumentUploadRequest",
    "DocumentVerificationRequest",
    "StudentPreferences",
    "StudentPrivacySettings",
    "StudentBulkImport",
    
    # Room history schemas
    "RoomHistoryResponse",
    "RoomHistoryItem",
    "RoomTransferRequest",
    "RoomTransferApproval",
    "RoomTransferStatus",
    "BulkRoomTransfer",
    "SingleTransfer",
    "RoomSwapRequest",
    
    # Dashboard schemas
    "StudentDashboard",
    "StudentStats",
    "StudentFinancialSummary",
    "AttendanceSummary",
    "DashboardPeriod",
    "RecentPayment",
    "RecentComplaint",
    "PendingLeave",
    "RecentAnnouncement",
    "TodayMessMenu",
    "UpcomingEvent",
    
    # Filter schemas
    "StudentFilterParams",
    "StudentSearchRequest",
    "StudentSortOptions",
    "StudentExportRequest",
    "StudentBulkActionRequest",
    "AdvancedStudentFilters",
    
    # Document schemas (API compatibility)
    "DocumentType",
    "DocumentVerificationStatus",
    "StudentDocument",
    "StudentDocumentCreate",
    "StudentDocumentUpdate",
    "DocumentVerificationRequestAPI",
    "DocumentListResponse",
    
    # Guardian schemas (API compatibility)
    "GuardianRelationType",
    "GuardianContact",
    "GuardianContactCreate",
    "GuardianContactUpdate",
    "GuardianContactList",
    
    # Lifecycle schemas (API compatibility)
    "OnboardingRequest",
    "CheckoutRequest",
    "BulkStatusUpdate",
    "StatusUpdateRequest",
    "OnboardingResponse",
    "CheckoutResponse",
    
    # Common enums
    "StudentStatus",
    "DietaryPreference",
    "IDProofType",
]