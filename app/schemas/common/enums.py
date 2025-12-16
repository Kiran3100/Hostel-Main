# --- File: app/schemas/common/enums.py ---
"""
All enumeration types used across the application.

These enums represent the core domain concepts for the hostel management
system (users, hostels, rooms, bookings, payments, complaints, etc.).
"""

from enum import Enum

__all__ = [
    "UserRole",
    "Gender",
    "HostelType",
    "HostelStatus",
    "RoomType",
    "RoomStatus",
    "BedStatus",
    "BookingStatus",
    "BookingSource",
    "PaymentStatus",
    "PaymentMethod",
    "PaymentType",
    "FeeType",
    "ComplaintCategory",
    "ComplaintStatus",
    "Priority",
    "AttendanceStatus",
    "AttendanceMode",
    "LeaveType",
    "LeaveStatus",
    "MaintenanceCategory",
    "MaintenanceStatus",
    "MaintenanceIssueType",
    "MaintenanceRecurrence",
    "NotificationType",
    "NotificationStatus",
    "SubscriptionPlan",
    "SubscriptionStatus",
    "BillingCycle",
    "StudentStatus",
    "SupervisorStatus",
    "EmploymentType",
    "AnnouncementCategory",
    "TargetAudience",
    "MealType",
    "DietaryPreference",
    "IDProofType",
    "PermissionLevel",
    "ReferralStatus",
    "RewardStatus",
    "ReviewStatus",
    "VoteType",
    "DeviceType",
    "SearchSource",
    "InquiryStatus",
    "InquirySource",
    "WaitlistStatus",
    "OTPType",
    "AuditActionCategory",
    "ChargeType",
]


class UserRole(str, Enum):
    """User role enumeration."""

    SUPER_ADMIN = "super_admin"
    HOSTEL_ADMIN = "hostel_admin"
    SUPERVISOR = "supervisor"
    STUDENT = "student"
    VISITOR = "visitor"


class Gender(str, Enum):
    """Gender enumeration."""

    MALE = "male"
    FEMALE = "female"
    OTHER = "other"


class HostelType(str, Enum):
    """Hostel type enumeration."""

    BOYS = "boys"
    GIRLS = "girls"
    CO_ED = "co_ed"


class HostelStatus(str, Enum):
    """Hostel operational status."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    UNDER_MAINTENANCE = "under_maintenance"
    CLOSED = "closed"


class RoomType(str, Enum):
    """Room type enumeration."""

    SINGLE = "single"
    DOUBLE = "double"
    TRIPLE = "triple"
    FOUR_SHARING = "four_sharing"
    DORMITORY = "dormitory"


class RoomStatus(str, Enum):
    """Room status enumeration."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    MAINTENANCE = "maintenance"
    RESERVED = "reserved"


class BedStatus(str, Enum):
    """Bed status enumeration."""

    AVAILABLE = "available"
    OCCUPIED = "occupied"
    RESERVED = "reserved"
    MAINTENANCE = "maintenance"


class BookingStatus(str, Enum):
    """Booking status enumeration."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    CONFIRMED = "confirmed"
    CHECKED_IN = "checked_in"
    COMPLETED = "completed"


class BookingSource(str, Enum):
    """Booking source enumeration."""

    WEBSITE = "website"
    MOBILE_APP = "mobile_app"
    REFERRAL = "referral"
    WALK_IN = "walk_in"
    AGENT = "agent"
    OTHER = "other"


class PaymentStatus(str, Enum):
    """Payment status enumeration."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"
    PARTIALLY_REFUNDED = "partially_refunded"


class PaymentMethod(str, Enum):
    """Payment method enumeration."""

    CASH = "cash"
    UPI = "upi"
    CARD = "card"
    NET_BANKING = "net_banking"
    CHEQUE = "cheque"
    BANK_TRANSFER = "bank_transfer"
    PAYMENT_GATEWAY = "payment_gateway"


class PaymentType(str, Enum):
    """Payment type enumeration."""

    RENT = "rent"
    SECURITY_DEPOSIT = "security_deposit"
    MESS_CHARGES = "mess_charges"
    ELECTRICITY = "electricity"
    WATER = "water"
    MAINTENANCE = "maintenance"
    BOOKING_ADVANCE = "booking_advance"
    OTHER = "other"


class FeeType(str, Enum):
    """Fee type enumeration."""

    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    HALF_YEARLY = "half_yearly"
    YEARLY = "yearly"


class ComplaintCategory(str, Enum):
    """Complaint category enumeration."""

    ROOM_MAINTENANCE = "room_maintenance"
    PLUMBING = "plumbing"
    ELECTRICAL = "electrical"
    CLEANLINESS = "cleanliness"
    MESS_FOOD_QUALITY = "mess_food_quality"
    SECURITY = "security"
    NOISE = "noise"
    INTERNET = "internet"
    STAFF_BEHAVIOR = "staff_behavior"
    OTHER = "other"


class ComplaintStatus(str, Enum):
    """Complaint status enumeration."""

    OPEN = "open"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    ON_HOLD = "on_hold"
    RESOLVED = "resolved"
    CLOSED = "closed"
    REOPENED = "reopened"
    REJECTED = "rejected"


class Priority(str, Enum):
    """Priority level enumeration."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"
    CRITICAL = "critical"


class AttendanceStatus(str, Enum):
    """Attendance status enumeration."""

    PRESENT = "present"
    ABSENT = "absent"
    LATE = "late"
    ON_LEAVE = "on_leave"
    HALF_DAY = "half_day"


class AttendanceMode(str, Enum):
    """Attendance recording mode."""

    MANUAL = "manual"
    BIOMETRIC = "biometric"
    QR_CODE = "qr_code"
    MOBILE_APP = "mobile_app"


class LeaveType(str, Enum):
    """Leave type enumeration."""

    CASUAL = "casual"
    SICK = "sick"
    EMERGENCY = "emergency"
    VACATION = "vacation"
    OTHER = "other"


class LeaveStatus(str, Enum):
    """Leave application status."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class MaintenanceCategory(str, Enum):
    """Maintenance category enumeration."""

    ELECTRICAL = "electrical"
    PLUMBING = "plumbing"
    CARPENTRY = "carpentry"
    CLEANING = "cleaning"
    APPLIANCE_REPAIR = "appliance_repair"
    STRUCTURAL = "structural"
    PAINTING = "painting"
    OTHER = "other"


class MaintenanceStatus(str, Enum):
    """Maintenance request status."""

    PENDING = "pending"
    APPROVED = "approved"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    ON_HOLD = "on_hold"
    COMPLETED = "completed"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class MaintenanceIssueType(str, Enum):
    """Maintenance issue type."""

    ROUTINE = "routine"
    PREVENTIVE = "preventive"
    EMERGENCY = "emergency"
    BREAKDOWN = "breakdown"


class MaintenanceRecurrence(str, Enum):
    """Preventive maintenance recurrence."""

    NONE = "none"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    HALF_YEARLY = "half_yearly"
    YEARLY = "yearly"


class NotificationType(str, Enum):
    """Notification type enumeration."""

    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"


class NotificationStatus(str, Enum):
    """Notification delivery status."""

    QUEUED = "queued"
    PROCESSING = "processing"
    SENT = "sent"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SubscriptionPlan(str, Enum):
    """Subscription plan types."""

    FREE = "free"
    BASIC = "basic"
    STANDARD = "standard"
    PREMIUM = "premium"
    ENTERPRISE = "enterprise"


class SubscriptionStatus(str, Enum):
    """Subscription status."""

    TRIAL = "trial"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class BillingCycle(str, Enum):
    """Billing cycle."""

    MONTHLY = "monthly"
    YEARLY = "yearly"


class StudentStatus(str, Enum):
    """Student status enumeration."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    NOTICE_PERIOD = "notice_period"
    ALUMNI = "alumni"
    SUSPENDED = "suspended"


class SupervisorStatus(str, Enum):
    """Supervisor status enumeration."""

    ACTIVE = "active"
    ON_LEAVE = "on_leave"
    SUSPENDED = "suspended"
    TERMINATED = "terminated"


class EmploymentType(str, Enum):
    """Employment type."""

    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACT = "contract"


class AnnouncementCategory(str, Enum):
    """Announcement category."""

    GENERAL = "general"
    URGENT = "urgent"
    MAINTENANCE = "maintenance"
    EVENT = "event"
    RULE_CHANGE = "rule_change"
    FEE_RELATED = "fee_related"
    SECURITY = "security"
    OTHER = "other"


class TargetAudience(str, Enum):
    """Target audience for announcements."""

    ALL = "all"
    STUDENTS_ONLY = "students_only"
    SPECIFIC_ROOMS = "specific_rooms"
    SPECIFIC_FLOORS = "specific_floors"
    INDIVIDUAL = "individual"


class MealType(str, Enum):
    """Meal type enumeration."""

    BREAKFAST = "breakfast"
    LUNCH = "lunch"
    SNACKS = "snacks"
    DINNER = "dinner"


class DietaryPreference(str, Enum):
    """Dietary preference."""

    VEGETARIAN = "vegetarian"
    NON_VEGETARIAN = "non_vegetarian"
    VEGAN = "vegan"
    JAIN = "jain"


class IDProofType(str, Enum):
    """ID proof type."""

    AADHAAR = "aadhaar"
    PASSPORT = "passport"
    DRIVING_LICENSE = "driving_license"
    VOTER_ID = "voter_id"
    PAN_CARD = "pan_card"


class PermissionLevel(str, Enum):
    """Permission level for admin-hostel assignments."""

    FULL_ACCESS = "full_access"
    LIMITED_ACCESS = "limited_access"
    VIEW_ONLY = "view_only"


class ReferralStatus(str, Enum):
    """Referral status."""

    PENDING = "pending"
    REGISTERED = "registered"
    BOOKING_MADE = "booking_made"
    COMPLETED = "completed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class RewardStatus(str, Enum):
    """Reward payment status."""

    PENDING = "pending"
    APPROVED = "approved"
    PAID = "paid"
    CANCELLED = "cancelled"


class ReviewStatus(str, Enum):
    """Review moderation status."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    FLAGGED = "flagged"


class VoteType(str, Enum):
    """Review vote type."""

    HELPFUL = "helpful"
    NOT_HELPFUL = "not_helpful"


class DeviceType(str, Enum):
    """Device type for push notifications."""

    IOS = "ios"
    ANDROID = "android"
    WEB = "web"


class SearchSource(str, Enum):
    """Search result source."""

    SEARCH_RESULTS = "search_results"
    DIRECT_LINK = "direct_link"
    FEATURED = "featured"
    COMPARISON = "comparison"
    REFERRAL = "referral"


class InquiryStatus(str, Enum):
    """Inquiry status."""

    NEW = "new"
    CONTACTED = "contacted"
    INTERESTED = "interested"
    NOT_INTERESTED = "not_interested"
    CONVERTED = "converted"


class InquirySource(str, Enum):
    """Inquiry source."""

    WEBSITE = "website"
    MOBILE_APP = "mobile_app"
    REFERRAL = "referral"
    SOCIAL_MEDIA = "social_media"
    OTHER = "other"


class WaitlistStatus(str, Enum):
    """Waitlist status."""

    WAITING = "waiting"
    NOTIFIED = "notified"
    CONVERTED = "converted"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class OTPType(str, Enum):
    """OTP type."""

    EMAIL_VERIFICATION = "email_verification"
    PHONE_VERIFICATION = "phone_verification"
    LOGIN = "login"
    PASSWORD_RESET = "password_reset"


class AuditActionCategory(str, Enum):
    """Audit action category."""

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
    OTHER = "other"


class ChargeType(str, Enum):
    """Utility charge type."""

    INCLUDED = "included"
    ACTUAL = "actual"
    FIXED_MONTHLY = "fixed_monthly"