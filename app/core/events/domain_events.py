import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Any, Optional, Union, TypeVar, Generic
from enum import Enum
from datetime import datetime
import json
import logging

logger = logging.getLogger(__name__)

class EventCategory(Enum):
    """Event category for domain events"""
    USER = "user"
    BOOKING = "booking"
    PAYMENT = "payment"
    STUDENT = "student"
    HOSTEL = "hostel"
    ROOM = "room"
    COMPLAINT = "complaint"
    MAINTENANCE = "maintenance"
    ANNOUNCEMENT = "announcement"
    ATTENDANCE = "attendance"
    SECURITY = "security"
    SYSTEM = "system"

class EventSeverity(Enum):
    """Severity level for events"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

T = TypeVar('T')

@dataclass
class BaseDomainEvent(Generic[T]):
    """Base domain event class"""
    
    # Metadata fields
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = field(default_factory=lambda: None)
    event_category: EventCategory = EventCategory.SYSTEM
    event_severity: EventSeverity = EventSeverity.INFO
    timestamp: float = field(default_factory=time.time)
    version: str = "1.0"
    source: str = "api"
    correlation_id: Optional[str] = None
    causation_id: Optional[str] = None
    
    # Data fields
    entity_id: Optional[str] = None
    entity_type: Optional[str] = None
    actor_id: Optional[str] = None
    actor_type: Optional[str] = None
    tenant_id: Optional[str] = None
    hostel_id: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Post initialization to set event_type"""
        if self.event_type is None:
            self.event_type = self.__class__.__name__
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary"""
        event_dict = asdict(self)
        
        # Convert enum values to strings
        event_dict['event_category'] = self.event_category.value
        event_dict['event_severity'] = self.event_severity.value
        
        return event_dict
    
    def to_json(self) -> str:
        """Convert event to JSON string"""
        return json.dumps(self.to_dict())
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BaseDomainEvent':
        """Create event from dictionary"""
        # Convert string values back to enums
        if 'event_category' in data and isinstance(data['event_category'], str):
            data['event_category'] = EventCategory(data['event_category'])
        
        if 'event_severity' in data and isinstance(data['event_severity'], str):
            data['event_severity'] = EventSeverity(data['event_severity'])
        
        return cls(**data)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'BaseDomainEvent':
        """Create event from JSON string"""
        data = json.loads(json_str)
        return cls.from_dict(data)

# User events
@dataclass
class UserRegisteredEvent(BaseDomainEvent):
    """Event when a new user is registered"""
    
    event_category: EventCategory = EventCategory.USER
    
    # Additional fields
    email: Optional[str] = None
    role: Optional[str] = None
    source: Optional[str] = None
    is_verified: bool = False

@dataclass
class UserVerifiedEvent(BaseDomainEvent):
    """Event when a user is verified"""
    
    event_category: EventCategory = EventCategory.USER
    
    # Additional fields
    verification_type: str = "email"  # email, phone, document
    verification_time: float = field(default_factory=time.time)

@dataclass
class UserRoleChangedEvent(BaseDomainEvent):
    """Event when a user's role is changed"""
    
    event_category: EventCategory = EventCategory.USER
    
    # Additional fields
    previous_role: Optional[str] = None
    new_role: Optional[str] = None
    reason: Optional[str] = None
    changed_by: Optional[str] = None

@dataclass
class UserPasswordChangedEvent(BaseDomainEvent):
    """Event when a user changes password"""
    
    event_category: EventCategory = EventCategory.USER
    event_severity: EventSeverity = EventSeverity.INFO
    
    # Additional fields
    change_type: str = "user_initiated"  # user_initiated, reset, admin, system
    change_timestamp: float = field(default_factory=time.time)
    requester_ip: Optional[str] = None

# Booking events
@dataclass
class BookingCreatedEvent(BaseDomainEvent):
    """Event when a booking is created"""
    
    event_category: EventCategory = EventCategory.BOOKING
    
    # Additional fields
    booking_id: Optional[str] = None
    hostel_id: Optional[str] = None
    room_type: Optional[str] = None
    check_in_date: Optional[str] = None
    check_out_date: Optional[str] = None
    amount: Optional[float] = None
    currency: Optional[str] = "USD"

@dataclass
class BookingConfirmedEvent(BaseDomainEvent):
    """Event when a booking is confirmed"""
    
    event_category: EventCategory = EventCategory.BOOKING
    
    # Additional fields
    booking_id: Optional[str] = None
    hostel_id: Optional[str] = None
    room_id: Optional[str] = None
    bed_id: Optional[str] = None
    confirmation_code: Optional[str] = None
    confirmed_by: Optional[str] = None

@dataclass
class BookingCancelledEvent(BaseDomainEvent):
    """Event when a booking is cancelled"""
    
    event_category: EventCategory = EventCategory.BOOKING
    
    # Additional fields
    booking_id: Optional[str] = None
    hostel_id: Optional[str] = None
    cancellation_reason: Optional[str] = None
    refund_amount: Optional[float] = None
    cancellation_fee: Optional[float] = None
    cancelled_by: Optional[str] = None
    cancellation_policy: Optional[str] = None

@dataclass
class BookingModifiedEvent(BaseDomainEvent):
    """Event when a booking is modified"""
    
    event_category: EventCategory = EventCategory.BOOKING
    
    # Additional fields
    booking_id: Optional[str] = None
    hostel_id: Optional[str] = None
    modification_type: Optional[str] = None  # date_change, room_change, guest_change
    previous_state: Dict[str, Any] = field(default_factory=dict)
    new_state: Dict[str, Any] = field(default_factory=dict)
    price_difference: Optional[float] = None
    modified_by: Optional[str] = None

# Payment events
@dataclass
class PaymentProcessedEvent(BaseDomainEvent):
    """Event when a payment is processed"""
    
    event_category: EventCategory = EventCategory.PAYMENT
    
    # Additional fields
    payment_id: Optional[str] = None
    booking_id: Optional[str] = None
    student_id: Optional[str] = None
    amount: Optional[float] = None
    currency: Optional[str] = "USD"
    payment_method: Optional[str] = None
    payment_status: Optional[str] = None
    transaction_id: Optional[str] = None
    gateway: Optional[str] = None
    payment_type: Optional[str] = None  # booking, rent, deposit, fee

@dataclass
class PaymentFailedEvent(BaseDomainEvent):
    """Event when a payment fails"""
    
    event_category: EventCategory = EventCategory.PAYMENT
    event_severity: EventSeverity = EventSeverity.WARNING
    
    # Additional fields
    payment_id: Optional[str] = None
    booking_id: Optional[str] = None
    student_id: Optional[str] = None
    amount: Optional[float] = None
    currency: Optional[str] = "USD"
    payment_method: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    gateway: Optional[str] = None
    retry_count: int = 0

@dataclass
class PaymentRefundedEvent(BaseDomainEvent):
    """Event when a payment is refunded"""
    
    event_category: EventCategory = EventCategory.PAYMENT
    
    # Additional fields
    payment_id: Optional[str] = None
    refund_id: Optional[str] = None
    booking_id: Optional[str] = None
    student_id: Optional[str] = None
    amount: Optional[float] = None
    currency: Optional[str] = "USD"
    refund_reason: Optional[str] = None
    refund_method: Optional[str] = None
    refund_status: Optional[str] = None
    refund_transaction_id: Optional[str] = None
    processed_by: Optional[str] = None

# Complaint events
@dataclass
class ComplaintCreatedEvent(BaseDomainEvent):
    """Event when a complaint is created"""
    
    event_category: EventCategory = EventCategory.COMPLAINT
    
    # Additional fields
    complaint_id: Optional[str] = None
    hostel_id: Optional[str] = None
    student_id: Optional[str] = None
    complaint_type: Optional[str] = None
    priority: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None

@dataclass
class ComplaintAssignedEvent(BaseDomainEvent):
    """Event when a complaint is assigned"""
    
    event_category: EventCategory = EventCategory.COMPLAINT
    
    # Additional fields
    complaint_id: Optional[str] = None
    hostel_id: Optional[str] = None
    assigned_to: Optional[str] = None
    assigned_by: Optional[str] = None
    expected_resolution_time: Optional[float] = None
    priority: Optional[str] = None
    notes: Optional[str] = None

@dataclass
class ComplaintResolvedEvent(BaseDomainEvent):
    """Event when a complaint is resolved"""
    
    event_category: EventCategory = EventCategory.COMPLAINT
    
    # Additional fields
    complaint_id: Optional[str] = None
    hostel_id: Optional[str] = None
    resolution_time: Optional[float] = None
    resolution_details: Optional[str] = None
    resolved_by: Optional[str] = None
    resolution_feedback: Optional[str] = None
    resolution_rating: Optional[int] = None
    sla_breach: bool = False

@dataclass
class ComplaintEscalatedEvent(BaseDomainEvent):
    """Event when a complaint is escalated"""
    
    event_category: EventCategory = EventCategory.COMPLAINT
    event_severity: EventSeverity = EventCategory.WARNING
    
    # Additional fields
    complaint_id: Optional[str] = None
    hostel_id: Optional[str] = None
    escalated_from: Optional[str] = None
    escalated_to: Optional[str] = None
    escalation_reason: Optional[str] = None
    escalation_level: int = 1
    escalation_time: float = field(default_factory=time.time)

# Maintenance events
@dataclass
class MaintenanceRequestedEvent(BaseDomainEvent):
    """Event when maintenance is requested"""
    
    event_category: EventCategory = EventCategory.MAINTENANCE
    
    # Additional fields
    maintenance_id: Optional[str] = None
    hostel_id: Optional[str] = None
    requested_by: Optional[str] = None
    maintenance_type: Optional[str] = None
    priority: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None
    scheduled_time: Optional[float] = None
    is_emergency: bool = False

@dataclass
class MaintenanceAssignedEvent(BaseDomainEvent):
    """Event when maintenance is assigned"""
    
    event_category: EventCategory = EventCategory.MAINTENANCE
    
    # Additional fields
    maintenance_id: Optional[str] = None
    hostel_id: Optional[str] = None
    assigned_to: Optional[str] = None
    assigned_by: Optional[str] = None
    assignment_time: float = field(default_factory=time.time)
    expected_completion_time: Optional[float] = None
    assignment_notes: Optional[str] = None
    is_vendor: bool = False
    vendor_id: Optional[str] = None

@dataclass
class MaintenanceCompletedEvent(BaseDomainEvent):
    """Event when maintenance is completed"""
    
    event_category: EventCategory = EventCategory.MAINTENANCE
    
    # Additional fields
    maintenance_id: Optional[str] = None
    hostel_id: Optional[str] = None
    completed_by: Optional[str] = None
    completion_time: float = field(default_factory=time.time)
    completion_notes: Optional[str] = None
    materials_used: List[Dict[str, Any]] = field(default_factory=list)
    cost: Optional[float] = None
    quality_check_passed: Optional[bool] = None
    followup_required: bool = False
    completion_photos: List[str] = field(default_factory=list)

# Student events
@dataclass
class StudentCheckedInEvent(BaseDomainEvent):
    """Event when a student checks in"""
    
    event_category: EventCategory = EventCategory.STUDENT
    
    # Additional fields
    student_id: Optional[str] = None
    hostel_id: Optional[str] = None
    room_id: Optional[str] = None
    bed_id: Optional[str] = None
    check_in_time: float = field(default_factory=time.time)
    checked_in_by: Optional[str] = None
    booking_id: Optional[str] = None
    check_in_notes: Optional[str] = None
    documents_verified: bool = False

@dataclass
class StudentCheckedOutEvent(BaseDomainEvent):
    """Event when a student checks out"""
    
    event_category: EventCategory = EventCategory.STUDENT
    
    # Additional fields
    student_id: Optional[str] = None
    hostel_id: Optional[str] = None
    room_id: Optional[str] = None
    bed_id: Optional[str] = None
    check_out_time: float = field(default_factory=time.time)
    checked_out_by: Optional[str] = None
    refund_amount: Optional[float] = None
    check_out_reason: Optional[str] = None
    check_out_notes: Optional[str] = None
    room_condition: Optional[str] = None

@dataclass
class StudentTransferredEvent(BaseDomainEvent):
    """Event when a student is transferred to another room/bed"""
    
    event_category: EventCategory = EventCategory.STUDENT
    
    # Additional fields
    student_id: Optional[str] = None
    hostel_id: Optional[str] = None
    previous_room_id: Optional[str] = None
    previous_bed_id: Optional[str] = None
    new_room_id: Optional[str] = None
    new_bed_id: Optional[str] = None
    transfer_time: float = field(default_factory=time.time)
    transfer_reason: Optional[str] = None
    transferred_by: Optional[str] = None
    price_difference: Optional[float] = None
    is_upgrade: Optional[bool] = None

# Room events
@dataclass
class RoomAssignedEvent(BaseDomainEvent):
    """Event when a room is assigned"""
    
    event_category: EventCategory = EventCategory.ROOM
    
    # Additional fields
    room_id: Optional[str] = None
    hostel_id: Optional[str] = None
    student_id: Optional[str] = None
    bed_id: Optional[str] = None
    booking_id: Optional[str] = None
    assigned_by: Optional[str] = None
    assignment_time: float = field(default_factory=time.time)
    room_type: Optional[str] = None
    rental_amount: Optional[float] = None
    is_reserved: bool = False

@dataclass
class RoomStatusChangedEvent(BaseDomainEvent):
    """Event when room status changes"""
    
    event_category: EventCategory = EventCategory.ROOM
    
    # Additional fields
    room_id: Optional[str] = None
    hostel_id: Optional[str] = None
    previous_status: Optional[str] = None
    new_status: Optional[str] = None
    changed_by: Optional[str] = None
    change_reason: Optional[str] = None
    maintenance_id: Optional[str] = None
    expected_availability_date: Optional[float] = None

# Attendance events
@dataclass
class AttendanceRecordedEvent(BaseDomainEvent):
    """Event when attendance is recorded"""
    
    event_category: EventCategory = EventCategory.ATTENDANCE
    
    # Additional fields
    student_id: Optional[str] = None
    hostel_id: Optional[str] = None
    attendance_date: Optional[str] = None
    status: Optional[str] = None  # present, absent, late, leave
    check_in_time: Optional[float] = None
    check_out_time: Optional[float] = None
    recorded_by: Optional[str] = None
    attendance_mode: Optional[str] = None  # manual, qr, biometric
    location: Optional[Dict[str, Any]] = None
    device_info: Optional[Dict[str, Any]] = None

@dataclass
class AttendanceViolationEvent(BaseDomainEvent):
    """Event when attendance policy is violated"""
    
    event_category: EventCategory = EventCategory.ATTENDANCE
    event_severity: EventSeverity = EventSeverity.WARNING
    
    # Additional fields
    student_id: Optional[str] = None
    hostel_id: Optional[str] = None
    violation_type: Optional[str] = None  # consecutive_absence, frequent_lateness
    violation_details: Optional[str] = None
    violation_period: Dict[str, Any] = field(default_factory=dict)
    violation_count: int = 1
    policy_reference: Optional[str] = None
    recommended_action: Optional[str] = None

# Announcement events
@dataclass
class AnnouncementPublishedEvent(BaseDomainEvent):
    """Event when an announcement is published"""
    
    event_category: EventCategory = EventCategory.ANNOUNCEMENT
    
    # Additional fields
    announcement_id: Optional[str] = None
    hostel_id: Optional[str] = None
    title: Optional[str] = None
    category: Optional[str] = None
    priority: Optional[str] = None
    published_by: Optional[str] = None
    target_audience: Dict[str, Any] = field(default_factory=dict)
    expiry_time: Optional[float] = None
    is_emergency: bool = False
    requires_acknowledgment: bool = False

@dataclass
class AnnouncementAcknowledgedEvent(BaseDomainEvent):
    """Event when an announcement is acknowledged"""
    
    event_category: EventCategory = EventCategory.ANNOUNCEMENT
    
    # Additional fields
    announcement_id: Optional[str] = None
    hostel_id: Optional[str] = None
    acknowledged_by: Optional[str] = None
    acknowledgment_time: float = field(default_factory=time.time)
    acknowledgment_method: Optional[str] = None  # web, mobile, email
    device_info: Optional[Dict[str, Any]] = None

# Notification events
@dataclass
class NotificationSentEvent(BaseDomainEvent):
    """Event when a notification is sent"""
    
    event_category: EventCategory = EventCategory.SYSTEM
    
    # Additional fields
    notification_id: Optional[str] = None
    recipient_id: Optional[str] = None
    notification_type: Optional[str] = None
    channel: Optional[str] = None  # email, sms, push, in-app
    template_id: Optional[str] = None
    content_summary: Optional[str] = None
    delivery_status: Optional[str] = None
    send_time: float = field(default_factory=time.time)
    retry_count: int = 0

@dataclass
class NotificationReadEvent(BaseDomainEvent):
    """Event when a notification is read"""
    
    event_category: EventCategory = EventCategory.SYSTEM
    
    # Additional fields
    notification_id: Optional[str] = None
    recipient_id: Optional[str] = None
    read_time: float = field(default_factory=time.time)
    device_type: Optional[str] = None
    time_to_read: Optional[float] = None  # seconds from delivery to reading
    interaction: Optional[str] = None  # clicked, dismissed, etc.

# File upload events
@dataclass
class FileUploadedEvent(BaseDomainEvent):
    """Event when a file is uploaded"""
    
    event_category: EventCategory = EventCategory.SYSTEM
    
    # Additional fields
    file_id: Optional[str] = None
    uploader_id: Optional[str] = None
    file_type: Optional[str] = None  # image, document, video
    file_size: Optional[int] = None  # bytes
    file_name: Optional[str] = None
    content_type: Optional[str] = None
    storage_location: Optional[str] = None
    entity_type: Optional[str] = None  # student_document, complaint_attachment, etc.
    entity_id: Optional[str] = None
    is_public: bool = False

# Security events
@dataclass
class SecurityAlertEvent(BaseDomainEvent):
    """Event for security alerts"""
    
    event_category: EventCategory = EventCategory.SECURITY
    event_severity: EventSeverity = EventSeverity.WARNING
    
    # Additional fields
    alert_type: Optional[str] = None
    user_id: Optional[str] = None
    ip_address: Optional[str] = None
    device_info: Optional[Dict[str, Any]] = None
    location_info: Optional[Dict[str, Any]] = None
    alert_details: Optional[str] = None
    threat_level: Optional[str] = None
    recommended_action: Optional[str] = None

@dataclass
class UserLoginEvent(BaseDomainEvent):
    """Event for user login"""
    
    event_category: EventCategory = EventCategory.SECURITY
    
    # Additional fields
    user_id: Optional[str] = None
    login_time: float = field(default_factory=time.time)
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    device_id: Optional[str] = None
    location: Optional[Dict[str, Any]] = None
    login_method: Optional[str] = None  # password, social, mfa
    session_id: Optional[str] = None
    login_status: Optional[str] = "success"

# System health events
@dataclass
class SystemHealthEvent(BaseDomainEvent):
    """Event for system health monitoring"""
    
    event_category: EventCategory = EventCategory.SYSTEM
    
    # Additional fields
    component: Optional[str] = None  # api, database, cache, etc.
    status: Optional[str] = None  # healthy, degraded, down
    metrics: Dict[str, Any] = field(default_factory=dict)
    error_details: Optional[str] = None
    response_time: Optional[float] = None  # milliseconds
    resource_utilization: Dict[str, Any] = field(default_factory=dict)
    alert_threshold_breached: bool = False
    region: Optional[str] = None