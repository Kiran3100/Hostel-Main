# --- File: C:\Hostel-Main\app\models\base\__init__.py ---
"""
Base models package.

Provides base classes, mixins, custom types, validators,
and enums for all database models.
"""

from app.models.base.base_model import (
    Base,
    BaseModel,
    TimestampModel,
    SoftDeleteModel,
    TenantModel,
)

from app.models.base.mixins import (
    TimestampMixin,
    SoftDeleteMixin,
    UUIDMixin,
    AddressMixin,
    ContactMixin,
    LocationMixin,
    MediaMixin,
    EmergencyContactMixin,
    AuditMixin,
    ApprovalMixin,
    SEOMixin,
    VersionMixin,
    PriorityMixin,
    StatusMixin,
)

from app.models.base.enums import (
    UserRole,
    Gender,
    HostelStatus,
    RoomStatus,
    BedStatus,
    BookingStatus,
    PaymentStatus,
    PaymentType,
    PaymentMethod,
    ComplaintStatus,
    ComplaintCategory,
    ComplaintPriority,
    MaintenanceStatus,
    MaintenanceCategory,
    AttendanceStatus,
    AttendanceMode,
    LeaveStatus,
    LeaveType,
    AnnouncementStatus,
    AnnouncementCategory,
    AnnouncementPriority,
    NotificationStatus,
    NotificationChannel,
    NotificationType,
    ReviewStatus,
    SubscriptionStatus,
    SubscriptionType,
    ReferralStatus,
    InquiryStatus,
    AuditActionCategory,
)

from app.models.base.types import (
    EncryptedType,
    JSONType,
    MoneyType,
    PhoneNumberType,
    EmailType,
    URLType,
    SlugType,
    CoordinateType,
)

from app.models.base import validators

__all__ = [
    # Base models
    "Base",
    "BaseModel",
    "TimestampModel",
    "SoftDeleteModel",
    "TenantModel",
    
    # Mixins
    "TimestampMixin",
    "SoftDeleteMixin",
    "UUIDMixin",
    "AddressMixin",
    "ContactMixin",
    "LocationMixin",
    "MediaMixin",
    "EmergencyContactMixin",
    "AuditMixin",
    "ApprovalMixin",
    "SEOMixin",
    "VersionMixin",
    "PriorityMixin",
    "StatusMixin",
    
    # Enums
    "UserRole",
    "Gender",
    "HostelStatus",
    "RoomStatus",
    "BedStatus",
    "BookingStatus",
    "PaymentStatus",
    "PaymentType",
    "PaymentMethod",
    "ComplaintStatus",
    "ComplaintCategory",
    "ComplaintPriority",
    "MaintenanceStatus",
    "MaintenanceCategory",
    "AttendanceStatus",
    "AttendanceMode",
    "LeaveStatus",
    "LeaveType",
    "AnnouncementStatus",
    "AnnouncementCategory",
    "AnnouncementPriority",
    "NotificationStatus",
    "NotificationChannel",
    "NotificationType",
    "ReviewStatus",
    "SubscriptionStatus",
    "SubscriptionType",
    "ReferralStatus",
    "InquiryStatus",
    "AuditActionCategory",
    
    # Custom types
    "EncryptedType",
    "JSONType",
    "MoneyType",
    "PhoneNumberType",
    "EmailType",
    "URLType",
    "SlugType",
    "CoordinateType",
    
    # Validators
    "validators",
]