"""
Database enums mirroring schema enums.

Provides SQLAlchemy-compatible enum definitions that match
the Pydantic schema enums for consistency.
"""

import enum


class UserRole(str, enum.Enum):
    """User role enumeration."""
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    SUPERVISOR = "supervisor"
    STUDENT = "student"
    VISITOR = "visitor"


class PermissionLevel(str, enum.Enum):
    """Permission level enumeration for access control."""
    READ_ONLY = "read_only"
    READ = "read"
    WRITE = "write"
    ADMIN = "admin"
    FULL_ACCESS = "full_access"
    LIMITED_ACCESS = "limited_access"
    NO_ACCESS = "no_access"


class Gender(str, enum.Enum):
    """Gender enumeration."""
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"
    PREFER_NOT_TO_SAY = "prefer_not_to_say"


class HostelStatus(str, enum.Enum):
    """Hostel operational status."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    UNDER_MAINTENANCE = "under_maintenance"


class HostelType(str, enum.Enum):
    """Hostel type categorization."""
    BOYS = "boys"
    GIRLS = "girls"
    MIXED = "mixed"
    SINGLE_OCCUPANCY = "single_occupancy"
    SHARED_OCCUPANCY = "shared_occupancy"
    PREMIUM = "premium"
    STANDARD = "standard"
    BUDGET = "budget"


class RoomStatus(str, enum.Enum):
    """Room availability status."""
    AVAILABLE = "available"
    OCCUPIED = "occupied"
    MAINTENANCE = "maintenance"
    OUT_OF_ORDER = "out_of_order"


class RoomType(str, enum.Enum):
    """Room type categorization."""
    SINGLE = "single"
    DOUBLE = "double"
    TRIPLE = "triple"
    QUAD = "quad"
    SHARED = "shared"
    DORMITORY = "dormitory"
    SUITE = "suite"
    DELUXE = "deluxe"
    STUDIO = "studio"
    PRIVATE = "private"


class BedStatus(str, enum.Enum):
    """Bed availability status."""
    AVAILABLE = "available"
    OCCUPIED = "occupied"
    RESERVED = "reserved"
    MAINTENANCE = "maintenance"


class BookingStatus(str, enum.Enum):
    """Booking lifecycle status."""
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    NO_SHOW = "no_show"


class PaymentStatus(str, enum.Enum):
    """Payment processing status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"


class PaymentType(str, enum.Enum):
    """Payment type categorization."""
    ADVANCE = "advance"
    MONTHLY_RENT = "monthly_rent"
    MESS_FEE = "mess_fee"
    SECURITY_DEPOSIT = "security_deposit"
    LATE_FEE = "late_fee"
    UTILITY_CHARGE = "utility_charge"
    OTHER = "other"


class PaymentMethod(str, enum.Enum):
    """Payment method types."""
    CASH = "cash"
    CARD = "card"
    BANK_TRANSFER = "bank_transfer"
    UPI = "upi"
    CHEQUE = "cheque"
    ONLINE = "online"


class ComplaintStatus(str, enum.Enum):
    """Complaint resolution status."""
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"
    ESCALATED = "escalated"


class ComplaintCategory(str, enum.Enum):
    """Complaint categorization."""
    MAINTENANCE = "maintenance"
    CLEANLINESS = "cleanliness"
    FOOD = "food"
    NOISE = "noise"
    SECURITY = "security"
    STAFF_BEHAVIOR = "staff_behavior"
    FACILITIES = "facilities"
    OTHER = "other"


class ComplaintPriority(str, enum.Enum):
    """Complaint priority levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class MaintenanceStatus(str, enum.Enum):
    """Maintenance request status."""
    REQUESTED = "requested"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    VERIFIED = "verified"


class MaintenanceCategory(str, enum.Enum):
    """Maintenance work categorization."""
    ELECTRICAL = "electrical"
    PLUMBING = "plumbing"
    CARPENTRY = "carpentry"
    PAINTING = "painting"
    CLEANING = "cleaning"
    HVAC = "hvac"
    APPLIANCE = "appliance"
    OTHER = "other"


class AttendanceStatus(str, enum.Enum):
    """Attendance record status."""
    PRESENT = "present"
    ABSENT = "absent"
    LATE = "late"
    ON_LEAVE = "on_leave"
    HALF_DAY = "half_day"  # ✅ Added this missing value


class AttendanceMode(str, enum.Enum):
    """Attendance recording method."""
    MANUAL = "manual"
    QR_CODE = "qr_code"
    BIOMETRIC = "biometric"
    RFID = "rfid"
    BULK = "bulk"  # ✅ Added this missing value
    MOBILE = "mobile"  # ✅ Added this for mobile app check-ins


class LeaveStatus(str, enum.Enum):
    """Leave application status."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class LeaveType(str, enum.Enum):
    """Leave type categorization."""
    CASUAL = "casual"
    SICK = "sick"
    EMERGENCY = "emergency"
    VACATION = "vacation"
    OTHER = "other"


class AnnouncementStatus(str, enum.Enum):
    """Announcement lifecycle status."""
    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class AnnouncementCategory(str, enum.Enum):
    """Announcement categorization."""
    GENERAL = "general"
    EMERGENCY = "emergency"
    EVENT = "event"
    POLICY = "policy"
    MAINTENANCE = "maintenance"
    ACADEMIC = "academic"


class AnnouncementPriority(str, enum.Enum):
    """Announcement priority levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


# Add alias for backward compatibility
Priority = AnnouncementPriority


class TargetAudience(str, enum.Enum):
    """Target audience for announcements."""
    ALL = "all"
    STUDENTS = "students"
    STAFF = "staff"
    SPECIFIC_ROOMS = "specific_rooms"
    SPECIFIC_FLOORS = "specific_floors"
    SPECIFIC_INDIVIDUALS = "specific_individuals"
    ROOM_BASED = "room_based"
    FLOOR_BASED = "floor_based"


class NotificationStatus(str, enum.Enum):
    """Notification delivery status."""
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    READ = "read"


class NotificationChannel(str, enum.Enum):
    """Notification delivery channels."""
    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"
    IN_APP = "in_app"


class NotificationType(str, enum.Enum):
    """Notification type categorization."""
    ALERT = "alert"
    REMINDER = "reminder"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class ReviewStatus(str, enum.Enum):
    """Review moderation status."""
    DRAFT = "draft"
    SUBMITTED = "submitted"
    MODERATED = "moderated"
    PUBLISHED = "published"
    REJECTED = "rejected"


class SubscriptionStatus(str, enum.Enum):
    """Subscription lifecycle status."""
    ACTIVE = "active"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    SUSPENDED = "suspended"
    TRIAL = "trial"


class SubscriptionType(str, enum.Enum):
    """Subscription tier types."""
    BASIC = "basic"
    STANDARD = "standard"
    PREMIUM = "premium"
    ENTERPRISE = "enterprise"


class ReferralStatus(str, enum.Enum):
    """Referral program status."""
    PENDING = "pending"
    COMPLETED = "completed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class InquiryStatus(str, enum.Enum):
    """Inquiry lifecycle status."""
    NEW = "new"
    CONTACTED = "contacted"
    QUALIFIED = "qualified"
    CONVERTED = "converted"
    LOST = "lost"


class AuditActionCategory(str, enum.Enum):
    """Audit log action categories."""
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    USER_MANAGEMENT = "user_management"
    HOSTEL_MANAGEMENT = "hostel_management"
    BOOKING = "booking"
    PAYMENT = "payment"
    COMPLAINT = "complaint"
    ATTENDANCE = "attendance"
    MAINTENANCE = "maintenance"
    ANNOUNCEMENT = "announcement"
    STUDENT_MANAGEMENT = "student_management"
    SUPERVISOR_MANAGEMENT = "supervisor_management"
    CONFIGURATION = "configuration"
    DATA_EXPORT = "data_export"
    OTHER = "other"


class StudentStatus(str, enum.Enum):
    """Student lifecycle status."""
    PENDING = "pending"
    ACTIVE = "active"
    INACTIVE = "inactive"
    ON_NOTICE = "on_notice"
    CHECKED_OUT = "checked_out"
    SUSPENDED = "suspended"
    EXPELLED = "expelled"


class IDProofType(str, enum.Enum):
    """ID proof document types."""
    AADHAR = "aadhar"
    PASSPORT = "passport"
    DRIVING_LICENSE = "driving_license"
    VOTER_ID = "voter_id"
    PAN_CARD = "pan_card"
    STUDENT_ID = "student_id"
    EMPLOYEE_ID = "employee_id"
    OTHER = "other"


class DietaryPreference(str, enum.Enum):
    """Dietary preference types."""
    VEGETARIAN = "vegetarian"
    NON_VEGETARIAN = "non_vegetarian"
    VEGAN = "vegan"
    JAIN = "jain"
    EGGETARIAN = "eggetarian"
    NO_PREFERENCE = "no_preference"