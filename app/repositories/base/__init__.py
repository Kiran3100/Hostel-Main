"""
Base repositories package.

Provides base repository infrastructure, query builders,
specifications, pagination, filtering, and caching.
"""

from app.repositories.base.base_repository import (
    BaseRepository,
    AuditContext,
)

from app.repositories.base.query_builder import (
    QueryBuilder,
    JoinType,
    OrderDirection,
)

from app.repositories.base.specifications import (
    Specification,
    AndSpecification,
    OrSpecification,
    NotSpecification,
    FieldEqualsSpecification,
    FieldInSpecification,
    FieldBetweenSpecification,
    FieldLikeSpecification,
    DateRangeSpecification,
    # Student specs
    ActiveStudentsSpecification,
    StudentsEnrolledInPeriodSpecification,
    StudentsWithOverdueDocumentsSpecification,
    # Booking specs
    PendingBookingsSpecification,
    ConfirmedBookingsSpecification,
    BookingsForDateRangeSpecification,
    ExpiredBookingsSpecification,
    # Room & Bed specs
    AvailableRoomsSpecification,
    AvailableBedsSpecification,
    RoomsRequiringMaintenanceSpecification,
    # Payment specs
    OverduePaymentsSpecification,
    PendingPaymentsSpecification,
    PaymentsInDateRangeSpecification,
    FailedPaymentsSpecification,
    # Complaint specs
    OpenComplaintsSpecification,
    HighPriorityComplaintsSpecification,
    EscalatedComplaintsSpecification,
    OverdueComplaintsSpecification,
    ComplaintsByCategorySpecification,
    # Maintenance specs
    PendingMaintenanceSpecification,
    InProgressMaintenanceSpecification,
    OverdueMaintenanceSpecification,
    MaintenanceRequiringVerificationSpecification,
    PreventiveMaintenanceSpecification,
    # Attendance specs
    PresentTodaySpecification,
    AbsentTodaySpecification,
    LowAttendanceSpecification,
    # Leave specs
    PendingLeaveRequestsSpecification,
    ApprovedLeaveSpecification,
    ActiveLeaveSpecification,
    # Document specs
    ExpiredDocumentsSpecification,
    ExpiringDocumentsSpecification,
    UnverifiedDocumentsSpecification,
    # Announcement specs
    PublishedAnnouncementsSpecification,
    UrgentAnnouncementsSpecification,
    TargetedAnnouncementsSpecification,
    # Hostel specs
    ActiveHostelsSpecification,
    HostelsWithAvailabilitySpecification,
    HostelsByLocationSpecification,
    # Utility specs
    SoftDeletedSpecification,
    NotDeletedSpecification,
    CreatedInLastDaysSpecification,
    UpdatedInLastDaysSpecification,
    ByHostelSpecification,
    ByUserSpecification,
)

from app.repositories.base.repository_factory import (
    RepositoryFactory,
    RepositoryRegistry,
    RepositoryDecorator,
    PerformanceProfilingDecorator,
    TransactionDecorator,
    get_repository_factory,
    reset_factory,
)

from app.repositories.base.pagination import (
    PaginationManager,
    PaginationStrategy,
    PaginationParams,  # Added this line
    PageInfo,
    PaginatedResult,
    Cursor,
    PageSizeOptimizer,
    PaginationCache,
)

from app.repositories.base.filtering import (
    FilterEngine,
    Filter,
    FilterGroup,
    FilterOperator,
    FilterType,
    SearchQueryBuilder,
)

from app.repositories.base.caching_repository import (
    CachingRepository,
    CacheStrategy,
    CacheLevel,
    LRUCache,
    CacheKeyGenerator,
    CacheInvalidator,
    cached_method,
)

__all__ = [
    # Base repository
    "BaseRepository",
    "AuditContext",
    
    # Query builder
    "QueryBuilder",
    "JoinType",
    "OrderDirection",
    
    # Specifications
    "Specification",
    "AndSpecification",
    "OrSpecification",
    "NotSpecification",
    "FieldEqualsSpecification",
    "FieldInSpecification",
    "FieldBetweenSpecification",
    "FieldLikeSpecification",
    "DateRangeSpecification",
    # Student
    "ActiveStudentsSpecification",
    "StudentsEnrolledInPeriodSpecification",
    "StudentsWithOverdueDocumentsSpecification",
    # Booking
    "PendingBookingsSpecification",
    "ConfirmedBookingsSpecification",
    "BookingsForDateRangeSpecification",
    "ExpiredBookingsSpecification",
    # Room & Bed
    "AvailableRoomsSpecification",
    "AvailableBedsSpecification",
    "RoomsRequiringMaintenanceSpecification",
    # Payment
    "OverduePaymentsSpecification",
    "PendingPaymentsSpecification",
    "PaymentsInDateRangeSpecification",
    "FailedPaymentsSpecification",
    # Complaint
    "OpenComplaintsSpecification",
    "HighPriorityComplaintsSpecification",
    "EscalatedComplaintsSpecification",
    "OverdueComplaintsSpecification",
    "ComplaintsByCategorySpecification",
    # Maintenance
    "PendingMaintenanceSpecification",
    "InProgressMaintenanceSpecification",
    "OverdueMaintenanceSpecification",
    "MaintenanceRequiringVerificationSpecification",
    "PreventiveMaintenanceSpecification",
    # Attendance
    "PresentTodaySpecification",
    "AbsentTodaySpecification",
    "LowAttendanceSpecification",
    # Leave
    "PendingLeaveRequestsSpecification",
    "ApprovedLeaveSpecification",
    "ActiveLeaveSpecification",
    # Document
    "ExpiredDocumentsSpecification",
    "ExpiringDocumentsSpecification",
    "UnverifiedDocumentsSpecification",
    # Announcement
    "PublishedAnnouncementsSpecification",
    "UrgentAnnouncementsSpecification",
    "TargetedAnnouncementsSpecification",
    # Hostel
    "ActiveHostelsSpecification",
    "HostelsWithAvailabilitySpecification",
    "HostelsByLocationSpecification",
    # Utility
    "SoftDeletedSpecification",
    "NotDeletedSpecification",
    "CreatedInLastDaysSpecification",
    "UpdatedInLastDaysSpecification",
    "ByHostelSpecification",
    "ByUserSpecification",
    
    # Repository factory
    "RepositoryFactory",
    "RepositoryRegistry",
    "RepositoryDecorator",
    "PerformanceProfilingDecorator",
    "TransactionDecorator",
    "get_repository_factory",
    "reset_factory",
    
    # Pagination
    "PaginationManager",
    "PaginationStrategy",
    "PaginationParams",  # Added this line
    "PageInfo",
    "PaginatedResult",
    "Cursor",
    "PageSizeOptimizer",
    "PaginationCache",
    
    # Filtering
    "FilterEngine",
    "Filter",
    "FilterGroup",
    "FilterOperator",
    "FilterType",
    "SearchQueryBuilder",
    
    # Caching
    "CachingRepository",
    "CacheStrategy",
    "CacheLevel",
    "LRUCache",
    "CacheKeyGenerator",
    "CacheInvalidator",
    "cached_method",
]


# Version
__version__ = "1.0.0"

# Package metadata
__author__ = "Hostel Management System Team"
__description__ = "Base repository infrastructure with advanced features"