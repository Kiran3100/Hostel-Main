"""
Common enums for the hostel management system.
"""

from enum import Enum


class LeaveStatus(str, Enum):
    """Leave application status enumeration."""
    
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    WITHDRAWN = "withdrawn"
    EXPIRED = "expired"
    PROCESSING = "processing"
    ESCALATED = "escalated"
    
    def __str__(self) -> str:
        return self.value
    
    @classmethod
    def active_statuses(cls) -> list["LeaveStatus"]:
        """Return statuses that represent active/ongoing leaves."""
        return [cls.APPROVED, cls.PROCESSING]
    
    @classmethod
    def final_statuses(cls) -> list["LeaveStatus"]:
        """Return statuses that represent finalized decisions."""
        return [cls.APPROVED, cls.REJECTED, cls.CANCELLED, cls.WITHDRAWN, cls.EXPIRED]
    
    @classmethod
    def pending_statuses(cls) -> list["LeaveStatus"]:
        """Return statuses that require action."""
        return [cls.PENDING, cls.PROCESSING, cls.ESCALATED]


class LeaveType(str, Enum):
    """Leave type enumeration."""
    
    CASUAL = "casual"
    SICK = "sick"
    EMERGENCY = "emergency"
    VACATION = "vacation"
    MEDICAL = "medical"
    FAMILY = "family"
    PERSONAL = "personal"
    STUDY = "study"
    OFFICIAL = "official"
    OTHER = "other"
    
    def __str__(self) -> str:
        return self.value
    
    @classmethod
    def requires_document_types(cls) -> list["LeaveType"]:
        """Return leave types that typically require documentation."""
        return [cls.SICK, cls.MEDICAL, cls.EMERGENCY, cls.FAMILY]
    
    @classmethod
    def short_term_types(cls) -> list["LeaveType"]:
        """Return leave types that are typically short-term."""
        return [cls.CASUAL, cls.SICK, cls.EMERGENCY, cls.PERSONAL]
    
    @classmethod
    def long_term_types(cls) -> list["LeaveType"]:
        """Return leave types that can be long-term."""
        return [cls.VACATION, cls.MEDICAL, cls.STUDY, cls.FAMILY]


class UserRole(str, Enum):
    """User role enumeration."""
    
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    WARDEN = "warden"
    ASSISTANT_WARDEN = "assistant_warden"
    SECURITY = "security"
    STAFF = "staff"
    STUDENT = "student"
    PARENT = "parent"
    GUARDIAN = "guardian"
    
    def __str__(self) -> str:
        return self.value
    
    @classmethod
    def admin_roles(cls) -> list["UserRole"]:
        """Return roles with administrative privileges."""
        return [cls.SUPER_ADMIN, cls.ADMIN, cls.WARDEN, cls.ASSISTANT_WARDEN]
    
    @classmethod
    def staff_roles(cls) -> list["UserRole"]:
        """Return staff-level roles."""
        return [cls.WARDEN, cls.ASSISTANT_WARDEN, cls.SECURITY, cls.STAFF]
    
    @classmethod
    def can_approve_leaves(cls) -> list["UserRole"]:
        """Return roles that can approve leave applications."""
        return [cls.SUPER_ADMIN, cls.ADMIN, cls.WARDEN, cls.ASSISTANT_WARDEN]


class UserStatus(str, Enum):
    """User account status enumeration."""
    
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    BLOCKED = "blocked"
    PENDING_VERIFICATION = "pending_verification"
    PENDING_APPROVAL = "pending_approval"
    
    def __str__(self) -> str:
        return self.value
    
    @classmethod
    def active_statuses(cls) -> list["UserStatus"]:
        """Return statuses that allow system access."""
        return [cls.ACTIVE]
    
    @classmethod
    def restricted_statuses(cls) -> list["UserStatus"]:
        """Return statuses with restricted access."""
        return [cls.SUSPENDED, cls.BLOCKED, cls.INACTIVE]


class ReviewStatus(str, Enum):
    """Review status enumeration."""
    
    DRAFT = "draft"
    PENDING = "pending"
    PUBLISHED = "published"
    REJECTED = "rejected"
    FLAGGED = "flagged"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    ARCHIVED = "archived"
    WITHDRAWN = "withdrawn"
    SUSPENDED = "suspended"
    
    def __str__(self) -> str:
        return self.value
    
    @classmethod
    def active_statuses(cls) -> list["ReviewStatus"]:
        """Return statuses for active reviews."""
        return [cls.PUBLISHED, cls.APPROVED]
    
    @classmethod
    def pending_statuses(cls) -> list["ReviewStatus"]:
        """Return statuses requiring action."""
        return [cls.PENDING, cls.UNDER_REVIEW, cls.FLAGGED]
    
    @classmethod
    def final_statuses(cls) -> list["ReviewStatus"]:
        """Return final statuses."""
        return [cls.PUBLISHED, cls.REJECTED, cls.ARCHIVED, cls.WITHDRAWN]
    
    @classmethod
    def moderation_statuses(cls) -> list["ReviewStatus"]:
        """Return statuses in moderation workflow."""
        return [cls.PENDING, cls.UNDER_REVIEW, cls.FLAGGED, cls.REJECTED]


class VoteType(str, Enum):
    """Vote type enumeration for review helpfulness."""
    
    HELPFUL = "helpful"
    NOT_HELPFUL = "not_helpful"
    
    def __str__(self) -> str:
        return self.value
    
    @classmethod
    def positive_vote(cls) -> "VoteType":
        """Return positive vote type."""
        return cls.HELPFUL
    
    @classmethod
    def negative_vote(cls) -> "VoteType":
        """Return negative vote type."""
        return cls.NOT_HELPFUL


class MealType(str, Enum):
    """Meal type enumeration."""
    
    BREAKFAST = "breakfast"
    LUNCH = "lunch"
    SNACKS = "snacks"
    DINNER = "dinner"
    
    def __str__(self) -> str:
        return self.value
    
    @classmethod
    def main_meals(cls) -> list["MealType"]:
        """Return main meal types."""
        return [cls.BREAKFAST, cls.LUNCH, cls.DINNER]
    
    @classmethod
    def all_meals(cls) -> list["MealType"]:
        """Return all meal types."""
        return [cls.BREAKFAST, cls.LUNCH, cls.SNACKS, cls.DINNER]


class NotificationType(str, Enum):
    """Notification type enumeration."""
    
    LEAVE_APPLICATION_SUBMITTED = "leave_application_submitted"
    LEAVE_APPLICATION_APPROVED = "leave_application_approved"
    LEAVE_APPLICATION_REJECTED = "leave_application_rejected"
    LEAVE_APPLICATION_CANCELLED = "leave_application_cancelled"
    LEAVE_REMINDER = "leave_reminder"
    LEAVE_OVERDUE = "leave_overdue"
    LEAVE_RETURN_REMINDER = "leave_return_reminder"
    SYSTEM_MAINTENANCE = "system_maintenance"
    ACCOUNT_CREATED = "account_created"
    PASSWORD_RESET = "password_reset"
    PROFILE_UPDATED = "profile_updated"
    
    def __str__(self) -> str:
        return self.value
    
    @classmethod
    def leave_related(cls) -> list["NotificationType"]:
        """Return leave-related notification types."""
        return [
            cls.LEAVE_APPLICATION_SUBMITTED,
            cls.LEAVE_APPLICATION_APPROVED,
            cls.LEAVE_APPLICATION_REJECTED,
            cls.LEAVE_APPLICATION_CANCELLED,
            cls.LEAVE_REMINDER,
            cls.LEAVE_OVERDUE,
            cls.LEAVE_RETURN_REMINDER,
        ]


class Priority(str, Enum):
    """Priority level enumeration."""
    
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"
    CRITICAL = "critical"
    
    def __str__(self) -> str:
        return self.value
    
    @classmethod
    def escalation_priorities(cls) -> list["Priority"]:
        """Return priorities that trigger escalation."""
        return [cls.URGENT, cls.CRITICAL]


class DocumentType(str, Enum):
    """Document type enumeration."""
    
    MEDICAL_CERTIFICATE = "medical_certificate"
    TRAVEL_DOCUMENT = "travel_document"
    FAMILY_EMERGENCY_PROOF = "family_emergency_proof"
    ACADEMIC_DOCUMENT = "academic_document"
    OFFICIAL_LETTER = "official_letter"
    IDENTITY_PROOF = "identity_proof"
    PARENT_CONSENT = "parent_consent"
    OTHER = "other"
    
    def __str__(self) -> str:
        return self.value
    
    @classmethod
    def medical_types(cls) -> list["DocumentType"]:
        """Return medical-related document types."""
        return [cls.MEDICAL_CERTIFICATE]
    
    @classmethod
    def verification_types(cls) -> list["DocumentType"]:
        """Return document types used for verification."""
        return [cls.IDENTITY_PROOF, cls.OFFICIAL_LETTER, cls.PARENT_CONSENT]


class RecurrencePattern(str, Enum):
    """Recurrence pattern enumeration."""
    
    NONE = "none"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUALLY = "annually"
    
    def __str__(self) -> str:
        return self.value


class AuditAction(str, Enum):
    """Audit action enumeration."""
    
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    VIEW = "view"
    APPROVE = "approve"
    REJECT = "reject"
    CANCEL = "cancel"
    RESTORE = "restore"
    LOGIN = "login"
    LOGOUT = "logout"
    EXPORT = "export"
    IMPORT = "import"
    
    def __str__(self) -> str:
        return self.value
    
    @classmethod
    def modification_actions(cls) -> list["AuditAction"]:
        """Return actions that modify data."""
        return [cls.CREATE, cls.UPDATE, cls.DELETE, cls.APPROVE, cls.REJECT, cls.CANCEL]


class Gender(str, Enum):
    """Gender enumeration."""
    
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"
    PREFER_NOT_TO_SAY = "prefer_not_to_say"
    
    def __str__(self) -> str:
        return self.value


class BloodGroup(str, Enum):
    """Blood group enumeration."""
    
    A_POSITIVE = "A+"
    A_NEGATIVE = "A-"
    B_POSITIVE = "B+"
    B_NEGATIVE = "B-"
    AB_POSITIVE = "AB+"
    AB_NEGATIVE = "AB-"
    O_POSITIVE = "O+"
    O_NEGATIVE = "O-"
    
    def __str__(self) -> str:
        return self.value


class ContactType(str, Enum):
    """Contact type enumeration."""
    
    PRIMARY = "primary"
    SECONDARY = "secondary"
    EMERGENCY = "emergency"
    WORK = "work"
    HOME = "home"
    MOBILE = "mobile"
    EMAIL = "email"
    
    def __str__(self) -> str:
        return self.value


class AddressType(str, Enum):
    """Address type enumeration."""
    
    PERMANENT = "permanent"
    TEMPORARY = "temporary"
    CURRENT = "current"
    CORRESPONDENCE = "correspondence"
    EMERGENCY = "emergency"
    
    def __str__(self) -> str:
        return self.value