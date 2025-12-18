# --- File: C:\Hostel-Main\app\models\leave\leave_application.py ---
"""
Leave application database models.

Provides SQLAlchemy models for leave requests, cancellations,
and complete leave lifecycle management.
"""

from datetime import date as Date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date as SQLDate,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
import uuid

from app.models.base.base_model import BaseModel, TimestampModel
from app.models.base.mixins import (
    AuditMixin,
    SoftDeleteMixin,
    UUIDMixin,
)
from app.models.common.enums import LeaveStatus, LeaveType

if TYPE_CHECKING:
    from app.models.student.student import Student
    from app.models.hostel.hostel import Hostel
    from app.models.user.user import User
    from app.models.leave.leave_approval import LeaveApproval

__all__ = [
    "LeaveApplication",
    "LeaveCancellation",
    "LeaveDocument",
    "LeaveEmergencyContact",
    "LeaveStatusHistory",
]


class LeaveApplication(BaseModel, TimestampModel, UUIDMixin, AuditMixin, SoftDeleteMixin):
    """
    Core leave application entity.
    
    Manages complete leave request lifecycle from application
    to approval/rejection/cancellation with comprehensive tracking.
    """
    
    __tablename__ = "leave_applications"
    __table_args__ = (
        # Ensure end date is after or equal to start date
        CheckConstraint(
            "to_date >= from_date",
            name="ck_leave_application_date_order"
        ),
        # Ensure total_days matches date range
        CheckConstraint(
            "total_days > 0",
            name="ck_leave_application_total_days_positive"
        ),
        # Ensure reasonable leave duration based on type
        CheckConstraint(
            """
            (leave_type = 'casual' AND total_days <= 30) OR
            (leave_type = 'sick' AND total_days <= 60) OR
            (leave_type = 'emergency' AND total_days <= 15) OR
            (leave_type = 'vacation' AND total_days <= 90) OR
            (leave_type = 'other' AND total_days <= 30)
            """,
            name="ck_leave_application_duration_limit"
        ),
        # Indexes for common queries
        Index("ix_leave_application_student_id", "student_id"),
        Index("ix_leave_application_hostel_id", "hostel_id"),
        Index("ix_leave_application_status", "status"),
        Index("ix_leave_application_leave_type", "leave_type"),
        Index("ix_leave_application_from_date", "from_date"),
        Index("ix_leave_application_to_date", "to_date"),
        Index("ix_leave_application_applied_at", "applied_at"),
        # Composite indexes for common filter combinations
        Index(
            "ix_leave_application_student_status",
            "student_id",
            "status"
        ),
        Index(
            "ix_leave_application_hostel_status_dates",
            "hostel_id",
            "status",
            "from_date",
            "to_date"
        ),
        Index(
            "ix_leave_application_status_dates",
            "status",
            "from_date",
            "to_date"
        ),
        {"comment": "Leave applications with comprehensive tracking and validation"}
    )

    # Primary identification
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
        comment="Student requesting leave"
    )
    hostel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hostels.id", ondelete="RESTRICT"),
        nullable=False,
        comment="Hostel where student resides"
    )

    # Leave details
    leave_type: Mapped[LeaveType] = mapped_column(
        Enum(LeaveType, name="leave_type_enum", create_type=True),
        nullable=False,
        comment="Type of leave being requested"
    )
    from_date: Mapped[Date] = mapped_column(
        SQLDate,
        nullable=False,
        comment="Leave start date (inclusive)"
    )
    to_date: Mapped[Date] = mapped_column(
        SQLDate,
        nullable=False,
        comment="Leave end date (inclusive)"
    )
    total_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Total number of leave days"
    )
    
    # Reason and documentation
    reason: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Detailed reason for leave request"
    )
    supporting_document_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="URL to supporting document (medical certificate, etc.)"
    )

    # Contact information during leave
    contact_during_leave: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="Contact phone number during leave"
    )
    emergency_contact: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="Emergency contact phone number"
    )
    emergency_contact_relation: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Relation with emergency contact person"
    )
    destination_address: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Destination address during leave"
    )
    expected_return_date: Mapped[Date | None] = mapped_column(
        SQLDate,
        nullable=True,
        comment="Expected return date (may differ from to_date)"
    )

    # Status and workflow
    status: Mapped[LeaveStatus] = mapped_column(
        Enum(LeaveStatus, name="leave_status_enum", create_type=True),
        nullable=False,
        default=LeaveStatus.PENDING,
        comment="Current leave application status"
    )
    applied_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        comment="Application submission timestamp"
    )

    # Approval tracking
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who approved the leave"
    )
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Approval timestamp"
    )
    approval_notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Notes from approver"
    )
    conditions: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Conditions or requirements for approved leave"
    )

    # Rejection tracking
    rejected_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who rejected the leave"
    )
    rejected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Rejection timestamp"
    )
    rejection_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Reason for rejection"
    )

    # Cancellation tracking
    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Cancellation timestamp"
    )
    cancelled_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who cancelled (student or admin)"
    )
    cancellation_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Reason for cancellation"
    )

    # Return tracking
    actual_return_date: Mapped[Date | None] = mapped_column(
        SQLDate,
        nullable=True,
        comment="Actual return date (for early returns)"
    )
    return_confirmed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether return has been confirmed"
    )
    return_confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Return confirmation timestamp"
    )
    return_confirmed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who confirmed return"
    )

    # Administrative fields
    priority: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Priority level for processing (0=normal, higher=urgent)"
    )
    requires_approval: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether this leave requires approval"
    )
    auto_approved: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether leave was automatically approved"
    )
    
    # Metadata
    application_source: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Source of application (web, mobile, admin)"
    )
    ip_address: Mapped[str | None] = mapped_column(
        String(45),
        nullable=True,
        comment="IP address of applicant"
    )
    user_agent: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="User agent string"
    )

    # Last modification tracking
    last_modified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        onupdate=datetime.utcnow,
        comment="Last modification timestamp"
    )
    last_modified_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who last modified the application"
    )

    # Relationships
    student: Mapped["Student"] = relationship(
        "Student",
        back_populates="leave_applications",
        foreign_keys=[student_id],
        lazy="joined"
    )
    
    hostel: Mapped["Hostel"] = relationship(
        "Hostel",
        back_populates="leave_applications",
        lazy="select"
    )
    
    approver: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[approved_by],
        lazy="select"
    )
    
    rejector: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[rejected_by],
        lazy="select"
    )
    
    canceller: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[cancelled_by],
        lazy="select"
    )

    documents: Mapped[list["LeaveDocument"]] = relationship(
        "LeaveDocument",
        back_populates="leave_application",
        cascade="all, delete-orphan",
        lazy="select"
    )

    emergency_contacts: Mapped[list["LeaveEmergencyContact"]] = relationship(
        "LeaveEmergencyContact",
        back_populates="leave_application",
        cascade="all, delete-orphan",
        lazy="select"
    )

    status_history: Mapped[list["LeaveStatusHistory"]] = relationship(
        "LeaveStatusHistory",
        back_populates="leave_application",
        cascade="all, delete-orphan",
        order_by="LeaveStatusHistory.changed_at.desc()",
        lazy="select"
    )

    approvals: Mapped[list["LeaveApproval"]] = relationship(
        "LeaveApproval",
        back_populates="leave_application",
        cascade="all, delete-orphan",
        lazy="select"
    )

    cancellation: Mapped["LeaveCancellation | None"] = relationship(
        "LeaveCancellation",
        back_populates="leave_application",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="select"
    )

    def __repr__(self) -> str:
        return (
            f"<LeaveApplication(id={self.id}, student_id={self.student_id}, "
            f"type={self.leave_type.value}, from={self.from_date}, "
            f"to={self.to_date}, status={self.status.value})>"
        )

    @property
    def is_active(self) -> bool:
        """Check if leave is currently active."""
        if self.status != LeaveStatus.APPROVED:
            return False
        today = Date.today()
        return self.from_date <= today <= self.to_date

    @property
    def is_upcoming(self) -> bool:
        """Check if leave is upcoming."""
        if self.status != LeaveStatus.APPROVED:
            return False
        return self.from_date > Date.today()

    @property
    def is_past(self) -> bool:
        """Check if leave is in the past."""
        return self.to_date < Date.today()

    @property
    def can_be_cancelled(self) -> bool:
        """Check if leave can be cancelled."""
        if self.status not in [LeaveStatus.PENDING, LeaveStatus.APPROVED]:
            return False
        if self.is_past:
            return False
        return True

    @property
    def days_until_start(self) -> int | None:
        """Calculate days until leave starts."""
        if self.is_past or self.is_active:
            return None
        return (self.from_date - Date.today()).days

    @property
    def days_remaining(self) -> int | None:
        """Calculate remaining leave days."""
        if not self.is_active:
            return None
        return (self.to_date - Date.today()).days + 1


class LeaveCancellation(BaseModel, TimestampModel, UUIDMixin):
    """
    Leave cancellation request tracking.
    
    Records cancellation requests with reasons and approval workflow.
    """
    
    __tablename__ = "leave_cancellations"
    __table_args__ = (
        Index("ix_leave_cancellation_leave_id", "leave_id"),
        Index("ix_leave_cancellation_student_id", "student_id"),
        Index("ix_leave_cancellation_requested_at", "requested_at"),
        {"comment": "Leave cancellation requests and processing"}
    )

    # Reference to leave application
    leave_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("leave_applications.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        comment="Leave application being cancelled"
    )
    
    # Student verification
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
        comment="Student requesting cancellation"
    )

    # Cancellation details
    cancellation_reason: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Reason for cancellation"
    )
    
    immediate_return: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether student is returning immediately"
    )
    
    actual_return_date: Mapped[Date | None] = mapped_column(
        SQLDate,
        nullable=True,
        comment="Actual return date for early returns"
    )

    # Request tracking
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        comment="Cancellation request timestamp"
    )
    
    requested_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who requested cancellation"
    )

    # Processing status
    is_processed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether cancellation has been processed"
    )
    
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Processing timestamp"
    )
    
    processed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who processed cancellation"
    )
    
    processing_notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Notes from processing admin"
    )

    # Approval if required
    requires_approval: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether cancellation requires approval"
    )
    
    is_approved: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
        comment="Approval status (NULL=pending, True=approved, False=rejected)"
    )
    
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who approved/rejected cancellation"
    )
    
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Approval/rejection timestamp"
    )

    # Relationships
    leave_application: Mapped["LeaveApplication"] = relationship(
        "LeaveApplication",
        back_populates="cancellation",
        lazy="joined"
    )
    
    student: Mapped["Student"] = relationship(
        "Student",
        lazy="select"
    )

    def __repr__(self) -> str:
        return (
            f"<LeaveCancellation(id={self.id}, leave_id={self.leave_id}, "
            f"student_id={self.student_id}, processed={self.is_processed})>"
        )


class LeaveDocument(BaseModel, TimestampModel, UUIDMixin):
    """
    Supporting documents for leave applications.
    
    Tracks medical certificates, travel documents, and other
    supporting evidence for leave requests.
    """
    
    __tablename__ = "leave_documents"
    __table_args__ = (
        Index("ix_leave_document_leave_id", "leave_id"),
        Index("ix_leave_document_document_type", "document_type"),
        {"comment": "Supporting documents for leave applications"}
    )

    # Reference to leave application
    leave_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("leave_applications.id", ondelete="CASCADE"),
        nullable=False,
        comment="Leave application this document supports"
    )

    # Document details
    document_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Type of document (medical_certificate, travel_document, etc.)"
    )
    
    document_url: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="URL to document file"
    )
    
    document_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Original document filename"
    )
    
    file_size: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="File size in bytes"
    )
    
    mime_type: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="MIME type of document"
    )

    # Verification
    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether document has been verified"
    )
    
    verified_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who verified document"
    )
    
    verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Verification timestamp"
    )
    
    verification_notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Verification notes"
    )

    # Upload tracking
    uploaded_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who uploaded document"
    )

    # Relationships
    leave_application: Mapped["LeaveApplication"] = relationship(
        "LeaveApplication",
        back_populates="documents",
        lazy="select"
    )

    def __repr__(self) -> str:
        return (
            f"<LeaveDocument(id={self.id}, leave_id={self.leave_id}, "
            f"type={self.document_type}, verified={self.is_verified})>"
        )


class LeaveEmergencyContact(BaseModel, TimestampModel, UUIDMixin):
    """
    Emergency contact information for leave periods.
    
    Stores additional emergency contacts specific to leave periods
    beyond the student's primary emergency contact.
    """
    
    __tablename__ = "leave_emergency_contacts"
    __table_args__ = (
        Index("ix_leave_emergency_contact_leave_id", "leave_id"),
        {"comment": "Emergency contacts during leave periods"}
    )

    # Reference to leave application
    leave_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("leave_applications.id", ondelete="CASCADE"),
        nullable=False,
        comment="Leave application this contact is for"
    )

    # Contact details
    contact_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Emergency contact person name"
    )
    
    relationship: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Relationship to student"
    )
    
    phone_number: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Contact phone number"
    )
    
    alternate_phone: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="Alternate phone number"
    )
    
    email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Contact email address"
    )
    
    address: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Contact address"
    )

    # Priority
    priority: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        comment="Contact priority (1=primary, 2=secondary, etc.)"
    )
    
    is_primary: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether this is the primary emergency contact"
    )

    # Verification
    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether contact has been verified"
    )
    
    verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Verification timestamp"
    )

    # Relationships
    leave_application: Mapped["LeaveApplication"] = relationship(
        "LeaveApplication",
        back_populates="emergency_contacts",
        lazy="select"
    )

    def __repr__(self) -> str:
        return (
            f"<LeaveEmergencyContact(id={self.id}, leave_id={self.leave_id}, "
            f"name={self.contact_name}, priority={self.priority})>"
        )


class LeaveStatusHistory(BaseModel, TimestampModel, UUIDMixin):
    """
    Leave application status change history.
    
    Maintains complete audit trail of all status changes
    with timestamps and responsible users.
    """
    
    __tablename__ = "leave_status_history"
    __table_args__ = (
        Index("ix_leave_status_history_leave_id", "leave_id"),
        Index("ix_leave_status_history_changed_at", "changed_at"),
        Index(
            "ix_leave_status_history_leave_status",
            "leave_id",
            "new_status"
        ),
        {"comment": "Leave application status change audit trail"}
    )

    # Reference to leave application
    leave_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("leave_applications.id", ondelete="CASCADE"),
        nullable=False,
        comment="Leave application"
    )

    # Status change details
    old_status: Mapped[LeaveStatus | None] = mapped_column(
        Enum(LeaveStatus, name="leave_status_enum", create_type=False),
        nullable=True,
        comment="Previous status (NULL for initial status)"
    )
    
    new_status: Mapped[LeaveStatus] = mapped_column(
        Enum(LeaveStatus, name="leave_status_enum", create_type=False),
        nullable=False,
        comment="New status"
    )
    
    change_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Reason for status change"
    )
    
    comments: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Additional comments"
    )

    # Change tracking
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        comment="Status change timestamp"
    )
    
    changed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who changed status"
    )
    
    change_source: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Source of change (manual, automatic, system)"
    )

    # IP and device tracking
    ip_address: Mapped[str | None] = mapped_column(
        String(45),
        nullable=True,
        comment="IP address of change initiator"
    )
    
    user_agent: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="User agent string"
    )

    # Relationships
    leave_application: Mapped["LeaveApplication"] = relationship(
        "LeaveApplication",
        back_populates="status_history",
        lazy="select"
    )
    
    changed_by_user: Mapped["User | None"] = relationship(
        "User",
        lazy="select"
    )

    def __repr__(self) -> str:
        return (
            f"<LeaveStatusHistory(id={self.id}, leave_id={self.leave_id}, "
            f"old={self.old_status.value if self.old_status else None}, "
            f"new={self.new_status.value})>"
        )