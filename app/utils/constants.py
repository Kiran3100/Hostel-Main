"""
Application constants for hostel management system
"""

from typing import Dict, List, Tuple, Any
from enum import Enum

# =============================================================================
# SYSTEM CONSTANTS
# =============================================================================

# Application Information
APP_NAME = "Hostel Management System"
APP_VERSION = "1.0.0"
API_VERSION = "v1"
APP_DESCRIPTION = "Comprehensive hostel management platform"

# Environment
DEVELOPMENT = "development"
STAGING = "staging"
PRODUCTION = "production"

ENVIRONMENTS = [DEVELOPMENT, STAGING, PRODUCTION]

# =============================================================================
# DATABASE CONSTANTS
# =============================================================================

# Pagination
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100
MIN_PAGE_SIZE = 1

# String Lengths
MAX_NAME_LENGTH = 100
MAX_EMAIL_LENGTH = 255
MAX_PHONE_LENGTH = 15
MAX_ADDRESS_LENGTH = 500
MAX_DESCRIPTION_LENGTH = 1000
MAX_SLUG_LENGTH = 100
MAX_URL_LENGTH = 2000

# Password Requirements
MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128

# File Upload
MAX_FILE_SIZE_MB = 50
MAX_IMAGE_SIZE_MB = 10
MAX_DOCUMENT_SIZE_MB = 25

# =============================================================================
# USER ROLES AND PERMISSIONS
# =============================================================================

class UserRoles:
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    SUPERVISOR = "supervisor"
    STUDENT = "student"
    VISITOR = "visitor"

USER_ROLE_CHOICES = [
    (UserRoles.SUPER_ADMIN, "Super Admin"),
    (UserRoles.ADMIN, "Admin"),
    (UserRoles.SUPERVISOR, "Supervisor"),
    (UserRoles.STUDENT, "Student"),
    (UserRoles.VISITOR, "Visitor")
]

# Role Hierarchies (higher value = more privileges)
ROLE_HIERARCHY = {
    UserRoles.VISITOR: 1,
    UserRoles.STUDENT: 2,
    UserRoles.SUPERVISOR: 3,
    UserRoles.ADMIN: 4,
    UserRoles.SUPER_ADMIN: 5
}

# =============================================================================
# HOSTEL CONSTANTS
# =============================================================================

class HostelTypes:
    BOYS = "boys"
    GIRLS = "girls"
    COED = "coed"

HOSTEL_TYPE_CHOICES = [
    (HostelTypes.BOYS, "Boys Hostel"),
    (HostelTypes.GIRLS, "Girls Hostel"),
    (HostelTypes.COED, "Co-ed Hostel")
]

class HostelStatus:
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    MAINTENANCE = "maintenance"

HOSTEL_STATUS_CHOICES = [
    (HostelStatus.ACTIVE, "Active"),
    (HostelStatus.INACTIVE, "Inactive"),
    (HostelStatus.SUSPENDED, "Suspended"),
    (HostelStatus.MAINTENANCE, "Under Maintenance")
]

# Room Types
class RoomTypes:
    SINGLE_AC = "single_ac"
    SINGLE_NON_AC = "single_non_ac"
    SHARED_AC = "shared_ac"
    SHARED_NON_AC = "shared_non_ac"
    DORMITORY = "dormitory"

ROOM_TYPE_CHOICES = [
    (RoomTypes.SINGLE_AC, "Single AC"),
    (RoomTypes.SINGLE_NON_AC, "Single Non-AC"),
    (RoomTypes.SHARED_AC, "Shared AC"),
    (RoomTypes.SHARED_NON_AC, "Shared Non-AC"),
    (RoomTypes.DORMITORY, "Dormitory")
]

# Room Status
class RoomStatus:
    AVAILABLE = "available"
    OCCUPIED = "occupied"
    MAINTENANCE = "maintenance"
    OUT_OF_ORDER = "out_of_order"
    RESERVED = "reserved"

ROOM_STATUS_CHOICES = [
    (RoomStatus.AVAILABLE, "Available"),
    (RoomStatus.OCCUPIED, "Occupied"),
    (RoomStatus.MAINTENANCE, "Maintenance"),
    (RoomStatus.OUT_OF_ORDER, "Out of Order"),
    (RoomStatus.RESERVED, "Reserved")
]

# Bed Status
class BedStatus:
    AVAILABLE = "available"
    OCCUPIED = "occupied"
    MAINTENANCE = "maintenance"
    RESERVED = "reserved"

BED_STATUS_CHOICES = [
    (BedStatus.AVAILABLE, "Available"),
    (BedStatus.OCCUPIED, "Occupied"),
    (BedStatus.MAINTENANCE, "Maintenance"),
    (BedStatus.RESERVED, "Reserved")
]

# =============================================================================
# BOOKING CONSTANTS
# =============================================================================

class BookingStatus:
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    NO_SHOW = "no_show"
    EXPIRED = "expired"

BOOKING_STATUS_CHOICES = [
    (BookingStatus.PENDING, "Pending"),
    (BookingStatus.CONFIRMED, "Confirmed"),
    (BookingStatus.CANCELLED, "Cancelled"),
    (BookingStatus.COMPLETED, "Completed"),
    (BookingStatus.NO_SHOW, "No Show"),
    (BookingStatus.EXPIRED, "Expired")
]

class BookingSource:
    WEBSITE = "website"
    MOBILE_APP = "mobile_app"
    WALK_IN = "walk_in"
    PHONE = "phone"
    AGENT = "agent"
    REFERRAL = "referral"

BOOKING_SOURCE_CHOICES = [
    (BookingSource.WEBSITE, "Website"),
    (BookingSource.MOBILE_APP, "Mobile App"),
    (BookingSource.WALK_IN, "Walk-in"),
    (BookingSource.PHONE, "Phone"),
    (BookingSource.AGENT, "Agent"),
    (BookingSource.REFERRAL, "Referral")
]

# Booking Limits
MIN_BOOKING_DAYS = 30
MAX_BOOKING_DAYS = 365
ADVANCE_BOOKING_DAYS = 90

# =============================================================================
# PAYMENT CONSTANTS
# =============================================================================

class PaymentStatus:
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"
    CANCELLED = "cancelled"

PAYMENT_STATUS_CHOICES = [
    (PaymentStatus.PENDING, "Pending"),
    (PaymentStatus.PROCESSING, "Processing"),
    (PaymentStatus.COMPLETED, "Completed"),
    (PaymentStatus.FAILED, "Failed"),
    (PaymentStatus.REFUNDED, "Refunded"),
    (PaymentStatus.CANCELLED, "Cancelled")
]

class PaymentMethod:
    CASH = "cash"
    CARD = "card"
    BANK_TRANSFER = "bank_transfer"
    UPI = "upi"
    CHEQUE = "cheque"
    ONLINE = "online"
    WALLET = "wallet"

PAYMENT_METHOD_CHOICES = [
    (PaymentMethod.CASH, "Cash"),
    (PaymentMethod.CARD, "Card"),
    (PaymentMethod.BANK_TRANSFER, "Bank Transfer"),
    (PaymentMethod.UPI, "UPI"),
    (PaymentMethod.CHEQUE, "Cheque"),
    (PaymentMethod.ONLINE, "Online"),
    (PaymentMethod.WALLET, "Wallet")
]

class PaymentType:
    ADVANCE = "advance"
    MONTHLY_RENT = "monthly_rent"
    SECURITY_DEPOSIT = "security_deposit"
    MESS_FEE = "mess_fee"
    UTILITY_CHARGES = "utility_charges"
    LATE_FEE = "late_fee"
    DAMAGE_CHARGES = "damage_charges"
    OTHER = "other"

PAYMENT_TYPE_CHOICES = [
    (PaymentType.ADVANCE, "Advance Payment"),
    (PaymentType.MONTHLY_RENT, "Monthly Rent"),
    (PaymentType.SECURITY_DEPOSIT, "Security Deposit"),
    (PaymentType.MESS_FEE, "Mess Fee"),
    (PaymentType.UTILITY_CHARGES, "Utility Charges"),
    (PaymentType.LATE_FEE, "Late Fee"),
    (PaymentType.DAMAGE_CHARGES, "Damage Charges"),
    (PaymentType.OTHER, "Other")
]

# Payment Limits
MIN_PAYMENT_AMOUNT = 1.00
MAX_PAYMENT_AMOUNT = 100000.00

# Late Fee Settings
LATE_FEE_GRACE_DAYS = 5
DEFAULT_LATE_FEE_PERCENTAGE = 5.0

# =============================================================================
# STUDENT CONSTANTS
# =============================================================================

class StudentStatus:
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    CHECKED_OUT = "checked_out"
    EXPELLED = "expelled"

STUDENT_STATUS_CHOICES = [
    (StudentStatus.ACTIVE, "Active"),
    (StudentStatus.INACTIVE, "Inactive"),
    (StudentStatus.SUSPENDED, "Suspended"),
    (StudentStatus.CHECKED_OUT, "Checked Out"),
    (StudentStatus.EXPELLED, "Expelled")
]

# Academic Years
ACADEMIC_YEARS = [
    ("1st_year", "1st Year"),
    ("2nd_year", "2nd Year"),
    ("3rd_year", "3rd Year"),
    ("4th_year", "4th Year"),
    ("graduate", "Graduate"),
    ("postgraduate", "Post Graduate")
]

# =============================================================================
# ATTENDANCE CONSTANTS
# =============================================================================

class AttendanceStatus:
    PRESENT = "present"
    ABSENT = "absent"
    LATE = "late"
    ON_LEAVE = "on_leave"
    EXCUSED = "excused"

ATTENDANCE_STATUS_CHOICES = [
    (AttendanceStatus.PRESENT, "Present"),
    (AttendanceStatus.ABSENT, "Absent"),
    (AttendanceStatus.LATE, "Late"),
    (AttendanceStatus.ON_LEAVE, "On Leave"),
    (AttendanceStatus.EXCUSED, "Excused")
]

class AttendanceMode:
    MANUAL = "manual"
    QR_CODE = "qr_code"
    BIOMETRIC = "biometric"
    RFID = "rfid"
    GEOFENCE = "geofence"

ATTENDANCE_MODE_CHOICES = [
    (AttendanceMode.MANUAL, "Manual"),
    (AttendanceMode.QR_CODE, "QR Code"),
    (AttendanceMode.BIOMETRIC, "Biometric"),
    (AttendanceMode.RFID, "RFID"),
    (AttendanceMode.GEOFENCE, "Geofence")
]

# Attendance Policy Defaults
DEFAULT_GRACE_PERIOD_MINUTES = 15
DEFAULT_ATTENDANCE_PERCENTAGE = 75.0
MAX_CONSECUTIVE_ABSENCES = 7

# =============================================================================
# LEAVE CONSTANTS
# =============================================================================

class LeaveStatus:
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    EXPIRED = "expired"

LEAVE_STATUS_CHOICES = [
    (LeaveStatus.PENDING, "Pending"),
    (LeaveStatus.APPROVED, "Approved"),
    (LeaveStatus.REJECTED, "Rejected"),
    (LeaveStatus.CANCELLED, "Cancelled"),
    (LeaveStatus.EXPIRED, "Expired")
]

class LeaveType:
    CASUAL = "casual"
    SICK = "sick"
    EMERGENCY = "emergency"
    VACATION = "vacation"
    MEDICAL = "medical"
    FAMILY = "family"
    OTHER = "other"

LEAVE_TYPE_CHOICES = [
    (LeaveType.CASUAL, "Casual Leave"),
    (LeaveType.SICK, "Sick Leave"),
    (LeaveType.EMERGENCY, "Emergency Leave"),
    (LeaveType.VACATION, "Vacation"),
    (LeaveType.MEDICAL, "Medical Leave"),
    (LeaveType.FAMILY, "Family Leave"),
    (LeaveType.OTHER, "Other")
]

# Leave Limits
MAX_LEAVE_DAYS_PER_REQUEST = 30
MAX_ANNUAL_LEAVE_DAYS = 45
MIN_ADVANCE_NOTICE_DAYS = 1

# =============================================================================
# COMPLAINT CONSTANTS
# =============================================================================

class ComplaintStatus:
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"
    ESCALATED = "escalated"
    REOPENED = "reopened"

COMPLAINT_STATUS_CHOICES = [
    (ComplaintStatus.OPEN, "Open"),
    (ComplaintStatus.IN_PROGRESS, "In Progress"),
    (ComplaintStatus.RESOLVED, "Resolved"),
    (ComplaintStatus.CLOSED, "Closed"),
    (ComplaintStatus.ESCALATED, "Escalated"),
    (ComplaintStatus.REOPENED, "Reopened")
]

class ComplaintCategory:
    MAINTENANCE = "maintenance"
    CLEANLINESS = "cleanliness"
    FOOD = "food"
    NOISE = "noise"
    SECURITY = "security"
    UTILITIES = "utilities"
    STAFF = "staff"
    FACILITIES = "facilities"
    OTHER = "other"

COMPLAINT_CATEGORY_CHOICES = [
    (ComplaintCategory.MAINTENANCE, "Maintenance"),
    (ComplaintCategory.CLEANLINESS, "Cleanliness"),
    (ComplaintCategory.FOOD, "Food"),
    (ComplaintCategory.NOISE, "Noise"),
    (ComplaintCategory.SECURITY, "Security"),
    (ComplaintCategory.UTILITIES, "Utilities"),
    (ComplaintCategory.STAFF, "Staff Behavior"),
    (ComplaintCategory.FACILITIES, "Facilities"),
    (ComplaintCategory.OTHER, "Other")
]

class ComplaintPriority:
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"
    CRITICAL = "critical"

COMPLAINT_PRIORITY_CHOICES = [
    (ComplaintPriority.LOW, "Low"),
    (ComplaintPriority.MEDIUM, "Medium"),
    (ComplaintPriority.HIGH, "High"),
    (ComplaintPriority.URGENT, "Urgent"),
    (ComplaintPriority.CRITICAL, "Critical")
]

# SLA (Service Level Agreement) Times in hours
COMPLAINT_SLA_HOURS = {
    ComplaintPriority.CRITICAL: 1,
    ComplaintPriority.URGENT: 4,
    ComplaintPriority.HIGH: 24,
    ComplaintPriority.MEDIUM: 72,
    ComplaintPriority.LOW: 168  # 1 week
}

# =============================================================================
# MAINTENANCE CONSTANTS
# =============================================================================

class MaintenanceStatus:
    REQUESTED = "requested"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    ON_HOLD = "on_hold"

MAINTENANCE_STATUS_CHOICES = [
    (MaintenanceStatus.REQUESTED, "Requested"),
    (MaintenanceStatus.ASSIGNED, "Assigned"),
    (MaintenanceStatus.IN_PROGRESS, "In Progress"),
    (MaintenanceStatus.COMPLETED, "Completed"),
    (MaintenanceStatus.CANCELLED, "Cancelled"),
    (MaintenanceStatus.ON_HOLD, "On Hold")
]

class MaintenanceCategory:
    ELECTRICAL = "electrical"
    PLUMBING = "plumbing"
    CARPENTRY = "carpentry"
    PAINTING = "painting"
    CLEANING = "cleaning"
    HVAC = "hvac"
    APPLIANCES = "appliances"
    SECURITY = "security"
    NETWORK = "network"
    OTHER = "other"

MAINTENANCE_CATEGORY_CHOICES = [
    (MaintenanceCategory.ELECTRICAL, "Electrical"),
    (MaintenanceCategory.PLUMBING, "Plumbing"),
    (MaintenanceCategory.CARPENTRY, "Carpentry"),
    (MaintenanceCategory.PAINTING, "Painting"),
    (MaintenanceCategory.CLEANING, "Cleaning"),
    (MaintenanceCategory.HVAC, "HVAC"),
    (MaintenanceCategory.APPLIANCES, "Appliances"),
    (MaintenanceCategory.SECURITY, "Security Systems"),
    (MaintenanceCategory.NETWORK, "Network/IT"),
    (MaintenanceCategory.OTHER, "Other")
]

class MaintenancePriority:
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"
    EMERGENCY = "emergency"

MAINTENANCE_PRIORITY_CHOICES = [
    (MaintenancePriority.LOW, "Low"),
    (MaintenancePriority.MEDIUM, "Medium"),
    (MaintenancePriority.HIGH, "High"),
    (MaintenancePriority.URGENT, "Urgent"),
    (MaintenancePriority.EMERGENCY, "Emergency")
]

# Maintenance Cost Thresholds
MAINTENANCE_APPROVAL_THRESHOLDS = {
    "supervisor": 5000.00,
    "admin": 25000.00,
    "super_admin": 100000.00
}

# =============================================================================
# NOTIFICATION CONSTANTS
# =============================================================================

class NotificationStatus:
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    READ = "read"

NOTIFICATION_STATUS_CHOICES = [
    (NotificationStatus.PENDING, "Pending"),
    (NotificationStatus.SENT, "Sent"),
    (NotificationStatus.DELIVERED, "Delivered"),
    (NotificationStatus.FAILED, "Failed"),
    (NotificationStatus.READ, "Read")
]

class NotificationChannel:
    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"
    IN_APP = "in_app"
    WHATSAPP = "whatsapp"

NOTIFICATION_CHANNEL_CHOICES = [
    (NotificationChannel.EMAIL, "Email"),
    (NotificationChannel.SMS, "SMS"),
    (NotificationChannel.PUSH, "Push Notification"),
    (NotificationChannel.IN_APP, "In-App"),
    (NotificationChannel.WHATSAPP, "WhatsApp")
]

class NotificationType:
    ALERT = "alert"
    REMINDER = "reminder"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    SUCCESS = "success"

NOTIFICATION_TYPE_CHOICES = [
    (NotificationType.ALERT, "Alert"),
    (NotificationType.REMINDER, "Reminder"),
    (NotificationType.INFO, "Information"),
    (NotificationType.WARNING, "Warning"),
    (NotificationType.ERROR, "Error"),
    (NotificationType.SUCCESS, "Success")
]

class NotificationPriority:
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"

NOTIFICATION_PRIORITY_CHOICES = [
    (NotificationPriority.LOW, "Low"),
    (NotificationPriority.MEDIUM, "Medium"),
    (NotificationPriority.HIGH, "High"),
    (NotificationPriority.URGENT, "Urgent")
]

# =============================================================================
# ANNOUNCEMENT CONSTANTS
# =============================================================================

class AnnouncementStatus:
    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    PUBLISHED = "published"
    ARCHIVED = "archived"
    REJECTED = "rejected"

ANNOUNCEMENT_STATUS_CHOICES = [
    (AnnouncementStatus.DRAFT, "Draft"),
    (AnnouncementStatus.PENDING_APPROVAL, "Pending Approval"),
    (AnnouncementStatus.APPROVED, "Approved"),
    (AnnouncementStatus.PUBLISHED, "Published"),
    (AnnouncementStatus.ARCHIVED, "Archived"),
    (AnnouncementStatus.REJECTED, "Rejected")
]

class AnnouncementCategory:
    GENERAL = "general"
    EMERGENCY = "emergency"
    EVENT = "event"
    POLICY = "policy"
    MAINTENANCE = "maintenance"
    ACADEMIC = "academic"
    FACILITY = "facility"
    CELEBRATION = "celebration"

ANNOUNCEMENT_CATEGORY_CHOICES = [
    (AnnouncementCategory.GENERAL, "General"),
    (AnnouncementCategory.EMERGENCY, "Emergency"),
    (AnnouncementCategory.EVENT, "Event"),
    (AnnouncementCategory.POLICY, "Policy Update"),
    (AnnouncementCategory.MAINTENANCE, "Maintenance"),
    (AnnouncementCategory.ACADEMIC, "Academic"),
    (AnnouncementCategory.FACILITY, "Facility"),
    (AnnouncementCategory.CELEBRATION, "Celebration")
]

class AnnouncementPriority:
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"

ANNOUNCEMENT_PRIORITY_CHOICES = [
    (AnnouncementPriority.LOW, "Low"),
    (AnnouncementPriority.MEDIUM, "Medium"),
    (AnnouncementPriority.HIGH, "High"),
    (AnnouncementPriority.URGENT, "Urgent")
]

# =============================================================================
# REVIEW CONSTANTS
# =============================================================================

class ReviewStatus:
    DRAFT = "draft"
    SUBMITTED = "submitted"
    MODERATED = "moderated"
    PUBLISHED = "published"
    REJECTED = "rejected"
    FLAGGED = "flagged"

REVIEW_STATUS_CHOICES = [
    (ReviewStatus.DRAFT, "Draft"),
    (ReviewStatus.SUBMITTED, "Submitted"),
    (ReviewStatus.MODERATED, "Moderated"),
    (ReviewStatus.PUBLISHED, "Published"),
    (ReviewStatus.REJECTED, "Rejected"),
    (ReviewStatus.FLAGGED, "Flagged")
]

# Rating Scale
MIN_RATING = 1
MAX_RATING = 5
RATING_CHOICES = [(i, str(i)) for i in range(MIN_RATING, MAX_RATING + 1)]

# Review Aspects
REVIEW_ASPECTS = [
    ("overall", "Overall Experience"),
    ("cleanliness", "Cleanliness"),
    ("food", "Food Quality"),
    ("staff", "Staff Behavior"),
    ("facilities", "Facilities"),
    ("location", "Location"),
    ("value_for_money", "Value for Money"),
    ("security", "Security"),
    ("maintenance", "Maintenance")
]

# =============================================================================
# SUBSCRIPTION CONSTANTS
# =============================================================================

class SubscriptionStatus:
    ACTIVE = "active"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    SUSPENDED = "suspended"
    TRIAL = "trial"

SUBSCRIPTION_STATUS_CHOICES = [
    (SubscriptionStatus.ACTIVE, "Active"),
    (SubscriptionStatus.EXPIRED, "Expired"),
    (SubscriptionStatus.CANCELLED, "Cancelled"),
    (SubscriptionStatus.SUSPENDED, "Suspended"),
    (SubscriptionStatus.TRIAL, "Trial")
]

class SubscriptionType:
    BASIC = "basic"
    STANDARD = "standard"
    PREMIUM = "premium"
    ENTERPRISE = "enterprise"

SUBSCRIPTION_TYPE_CHOICES = [
    (SubscriptionType.BASIC, "Basic"),
    (SubscriptionType.STANDARD, "Standard"),
    (SubscriptionType.PREMIUM, "Premium"),
    (SubscriptionType.ENTERPRISE, "Enterprise")
]

# Commission Rates (in percentage)
DEFAULT_COMMISSION_RATES = {
    SubscriptionType.BASIC: 5.0,
    SubscriptionType.STANDARD: 7.5,
    SubscriptionType.PREMIUM: 10.0,
    SubscriptionType.ENTERPRISE: 12.5
}

# =============================================================================
# FILE UPLOAD CONSTANTS
# =============================================================================

# Allowed file extensions
ALLOWED_IMAGE_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']
ALLOWED_DOCUMENT_EXTENSIONS = ['.pdf', '.doc', '.docx', '.txt', '.csv', '.xls', '.xlsx']
ALLOWED_VIDEO_EXTENSIONS = ['.mp4', '.avi', '.mov', '.wmv', '.flv']
ALLOWED_AUDIO_EXTENSIONS = ['.mp3', '.wav', '.aac', '.flac']

# MIME types
ALLOWED_IMAGE_MIMES = [
    'image/jpeg', 'image/png', 'image/gif', 
    'image/bmp', 'image/webp'
]
ALLOWED_DOCUMENT_MIMES = [
    'application/pdf', 'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'text/plain', 'text/csv',
    'application/vnd.ms-excel',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
]

# File upload paths
UPLOAD_PATHS = {
    'profiles': 'uploads/profiles/',
    'hostels': 'uploads/hostels/',
    'rooms': 'uploads/rooms/',
    'documents': 'uploads/documents/',
    'complaints': 'uploads/complaints/',
    'maintenance': 'uploads/maintenance/',
    'announcements': 'uploads/announcements/',
    'reviews': 'uploads/reviews/',
    'temp': 'uploads/temp/'
}

# =============================================================================
# TIME AND DATE CONSTANTS
# =============================================================================

# Time Formats
TIME_FORMAT_12H = "%I:%M %p"
TIME_FORMAT_24H = "%H:%M"
DATE_FORMAT = "%Y-%m-%d"
DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"
DISPLAY_DATE_FORMAT = "%d %B %Y"
DISPLAY_DATETIME_FORMAT = "%d %B %Y at %I:%M %p"

# Indian Standard Time
DEFAULT_TIMEZONE = "Asia/Kolkata"

# Academic Calendar
ACADEMIC_YEAR_START_MONTH = 7  # July
ACADEMIC_YEAR_END_MONTH = 6   # June

# Business Hours
DEFAULT_BUSINESS_HOURS = {
    'start': '09:00',
    'end': '18:00',
    'days': ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday']
}

# =============================================================================
# CURRENCY AND PRICING CONSTANTS
# =============================================================================

# Currency
DEFAULT_CURRENCY = "INR"
CURRENCY_SYMBOL = "₹"
CURRENCY_CHOICES = [
    ("INR", "Indian Rupee"),
    ("USD", "US Dollar"),
    ("EUR", "Euro")
]

# Pricing Precision
DECIMAL_PLACES = 2
MAX_DIGITS = 10

# GST Rates
GST_RATES = {
    'accommodation': 12.0,
    'food': 5.0,
    'services': 18.0
}

# =============================================================================
# SECURITY CONSTANTS
# =============================================================================

# Password Requirements
PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 128
PASSWORD_REQUIRE_UPPERCASE = True
PASSWORD_REQUIRE_LOWERCASE = True
PASSWORD_REQUIRE_DIGITS = True
PASSWORD_REQUIRE_SPECIAL = True
PASSWORD_SPECIAL_CHARS = "!@#$%^&*()_+-=[]{}|;:,.<>?"

# Session Settings
SESSION_TIMEOUT_MINUTES = 120
MAX_LOGIN_ATTEMPTS = 5
ACCOUNT_LOCKOUT_DURATION = 30  # minutes

# Token Expiry
ACCESS_TOKEN_EXPIRE_MINUTES = 60
REFRESH_TOKEN_EXPIRE_DAYS = 7
OTP_EXPIRE_MINUTES = 10
PASSWORD_RESET_TOKEN_EXPIRE_HOURS = 24

# =============================================================================
# COMMUNICATION CONSTANTS
# =============================================================================

# Email Settings
DEFAULT_FROM_EMAIL = "noreply@hostelmgmt.com"
SUPPORT_EMAIL = "support@hostelmgmt.com"
ADMIN_EMAIL = "admin@hostelmgmt.com"

# SMS Settings
SMS_CHARACTER_LIMIT = 160
SMS_UNICODE_LIMIT = 70

# Push Notification Settings
PUSH_TITLE_MAX_LENGTH = 50
PUSH_BODY_MAX_LENGTH = 150

# =============================================================================
# API CONSTANTS
# =============================================================================

# Rate Limiting
API_RATE_LIMIT_PER_MINUTE = 100
API_RATE_LIMIT_PER_HOUR = 1000
API_RATE_LIMIT_PER_DAY = 10000

# Request/Response
MAX_REQUEST_SIZE = 10 * 1024 * 1024  # 10MB
REQUEST_TIMEOUT_SECONDS = 30

# API Versions
SUPPORTED_API_VERSIONS = ["v1"]
DEFAULT_API_VERSION = "v1"

# =============================================================================
# ANALYTICS CONSTANTS
# =============================================================================

# Metrics Retention
DAILY_METRICS_RETENTION_DAYS = 90
WEEKLY_METRICS_RETENTION_WEEKS = 52
MONTHLY_METRICS_RETENTION_MONTHS = 24

# Performance Thresholds
SLOW_QUERY_THRESHOLD_MS = 1000
HIGH_MEMORY_USAGE_PERCENTAGE = 80.0
HIGH_CPU_USAGE_PERCENTAGE = 80.0

# =============================================================================
# SEARCH AND FILTERING CONSTANTS
# =============================================================================

# Search
MIN_SEARCH_TERM_LENGTH = 2
MAX_SEARCH_TERM_LENGTH = 100
SEARCH_RESULTS_PER_PAGE = 20
MAX_SEARCH_RESULTS = 1000

# Filters
MAX_FILTER_VALUES = 50
MAX_DATE_RANGE_DAYS = 365

# =============================================================================
# CACHE CONSTANTS
# =============================================================================

# Cache Keys
CACHE_KEY_PREFIX = "hostel_mgmt"
CACHE_SEPARATOR = ":"

# Cache Timeouts (in seconds)
CACHE_TIMEOUT_SHORT = 300      # 5 minutes
CACHE_TIMEOUT_MEDIUM = 1800    # 30 minutes
CACHE_TIMEOUT_LONG = 3600      # 1 hour
CACHE_TIMEOUT_VERY_LONG = 86400 # 24 hours

# =============================================================================
# VALIDATION CONSTANTS
# =============================================================================

# Phone Number Patterns
INDIAN_MOBILE_PATTERN = r'^[6-9]\d{9}$'
INTERNATIONAL_PHONE_PATTERN = r'^\+\d{1,3}\d{4,14}$'

# Email Pattern
EMAIL_PATTERN = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'

# Name Patterns
NAME_PATTERN = r'^[a-zA-Z\s\-\.\']+$'

# Postal Code Patterns
INDIAN_PINCODE_PATTERN = r'^\d{6}$'

# =============================================================================
# ERROR MESSAGES
# =============================================================================

ERROR_MESSAGES = {
    'required': 'This field is required.',
    'invalid_email': 'Enter a valid email address.',
    'invalid_phone': 'Enter a valid phone number.',
    'password_too_short': f'Password must be at least {PASSWORD_MIN_LENGTH} characters long.',
    'password_too_weak': 'Password must contain uppercase, lowercase, digit and special character.',
    'invalid_date_range': 'End date must be after start date.',
    'file_too_large': f'File size cannot exceed {MAX_FILE_SIZE_MB}MB.',
    'invalid_file_type': 'File type not allowed.',
    'insufficient_permissions': 'You do not have permission to perform this action.',
    'resource_not_found': 'The requested resource was not found.',
    'duplicate_entry': 'A record with this information already exists.',
    'invalid_credentials': 'Invalid username or password.',
    'account_locked': 'Account is locked due to multiple failed login attempts.',
    'session_expired': 'Your session has expired. Please login again.',
    'rate_limit_exceeded': 'Too many requests. Please try again later.'
}

# =============================================================================
# SUCCESS MESSAGES
# =============================================================================

SUCCESS_MESSAGES = {
    'created': 'Record created successfully.',
    'updated': 'Record updated successfully.',
    'deleted': 'Record deleted successfully.',
    'login_success': 'Login successful.',
    'logout_success': 'Logout successful.',
    'password_changed': 'Password changed successfully.',
    'email_sent': 'Email sent successfully.',
    'sms_sent': 'SMS sent successfully.',
    'file_uploaded': 'File uploaded successfully.',
    'payment_processed': 'Payment processed successfully.',
    'booking_confirmed': 'Booking confirmed successfully.',
    'complaint_submitted': 'Complaint submitted successfully.',
    'maintenance_scheduled': 'Maintenance request scheduled successfully.'
}

# =============================================================================
# FEATURE FLAGS
# =============================================================================

FEATURE_FLAGS = {
    'enable_reviews': True,
    'enable_referrals': True,
    'enable_analytics': True,
    'enable_notifications': True,
    'enable_file_uploads': True,
    'enable_payment_gateway': True,
    'enable_sms': True,
    'enable_email': True,
    'enable_geolocation': True,
    'enable_qr_codes': True,
    'enable_biometric': False,
    'enable_ai_recommendations': False,
    'enable_chatbot': False,
    'maintenance_mode': False
}

# =============================================================================
# SYSTEM LIMITS
# =============================================================================

SYSTEM_LIMITS = {
    'max_hostels_per_admin': 10,
    'max_rooms_per_hostel': 500,
    'max_beds_per_room': 10,
    'max_students_per_hostel': 1000,
    'max_complaints_per_day': 50,
    'max_announcements_per_day': 10,
    'max_file_uploads_per_day': 100,
    'max_bulk_operations': 1000,
    'max_export_records': 10000
}

# =============================================================================
# CONTACT INFORMATION
# =============================================================================

CONTACT_INFO = {
    'company_name': 'Hostel Management Solutions',
    'support_phone': '+91-XXXXXXXXXX',
    'support_email': 'support@hostelmgmt.com',
    'website': 'https://hostelmgmt.com',
    'address': 'India',
    'business_hours': '9:00 AM - 6:00 PM IST'
}