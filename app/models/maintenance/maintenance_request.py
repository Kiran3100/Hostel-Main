# app/models/maintenance/maintenance_request.py
"""
Maintenance request models.

Core maintenance request entities with comprehensive tracking,
lifecycle management, and business logic.
"""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import relationship, validates
from sqlalchemy.ext.hybrid import hybrid_property

from app.models.base.base_model import BaseModel, TimestampModel
from app.models.base.mixins import (
    SoftDeleteMixin,
    UUIDMixin,
    LocationMixin,
    MediaMixin,
    AuditMixin,
)
from app.schemas.common.enums import (
    MaintenanceCategory,
    MaintenanceIssueType,
    MaintenanceStatus,
    Priority,
)


class MaintenanceRequest(BaseModel, UUIDMixin, TimestampModel, SoftDeleteMixin, LocationMixin, MediaMixin, AuditMixin):
    """
    Core maintenance request entity.
    
    Tracks all maintenance work orders from creation through completion
    with comprehensive status tracking and audit trail.
    """
    
    __tablename__ = "maintenance_requests"
    
    # Request identification
    request_number = Column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
        comment="Human-readable unique request number (e.g., MNT-2024-001)",
    )
    
    # Hostel and location
    hostel_id = Column(
        UUID(as_uuid=True),
        ForeignKey("hostels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Hostel where maintenance is required",
    )
    
    room_id = Column(
        UUID(as_uuid=True),
        ForeignKey("rooms.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Specific room requiring maintenance",
    )
    
    # Requester information
    requested_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=False,
        index=True,
        comment="User who requested maintenance",
    )
    
    # Request details
    title = Column(
        String(255),
        nullable=False,
        comment="Brief maintenance issue summary",
    )
    
    description = Column(
        Text,
        nullable=False,
        comment="Detailed description of the issue",
    )
    
    # Classification
    category = Column(
        Enum(MaintenanceCategory),
        nullable=False,
        index=True,
        comment="Maintenance category (electrical, plumbing, etc.)",
    )
    
    priority = Column(
        Enum(Priority),
        nullable=False,
        default=Priority.MEDIUM,
        index=True,
        comment="Issue priority level",
    )
    
    issue_type = Column(
        Enum(MaintenanceIssueType),
        nullable=False,
        default=MaintenanceIssueType.ROUTINE,
        index=True,
        comment="Type of maintenance issue",
    )
    
    # Status workflow
    status = Column(
        Enum(MaintenanceStatus),
        nullable=False,
        default=MaintenanceStatus.PENDING,
        index=True,
        comment="Current maintenance status",
    )
    
    status_changed_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Last status change timestamp",
    )
    
    status_changed_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who last changed status",
    )
    
    # Location details (extends LocationMixin)
    floor = Column(
        Integer,
        nullable=True,
        comment="Floor number",
    )
    
    specific_area = Column(
        String(255),
        nullable=True,
        comment="Specific area within location",
    )
    
    # Assignment
    assigned_to = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Staff member assigned to handle maintenance",
    )
    
    assigned_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who made the assignment",
    )
    
    assigned_at = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="Assignment timestamp",
    )
    
    # Cost tracking
    estimated_cost = Column(
        Numeric(10, 2),
        nullable=True,
        comment="Estimated cost of repair",
    )
    
    actual_cost = Column(
        Numeric(10, 2),
        nullable=True,
        comment="Actual cost incurred",
    )
    
    approved_cost = Column(
        Numeric(10, 2),
        nullable=True,
        comment="Approved budget for the work",
    )
    
    # Timeline
    estimated_completion_date = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="Estimated completion date",
    )
    
    actual_start_date = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Actual work start date",
    )
    
    actual_completion_date = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="Actual completion date",
    )
    
    deadline = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Hard deadline for completion",
    )
    
    # Completion details
    completed_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who completed the work",
    )
    
    completed_at = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="Completion timestamp",
    )
    
    work_notes = Column(
        Text,
        nullable=True,
        comment="Notes about work performed",
    )
    
    # Approval workflow
    requires_approval = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether this request requires approval",
    )
    
    approval_pending = Column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="Whether approval is currently pending",
    )
    
    approved_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who approved the request",
    )
    
    approved_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Approval timestamp",
    )
    
    rejected_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who rejected the request",
    )
    
    rejected_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Rejection timestamp",
    )
    
    rejection_reason = Column(
        Text,
        nullable=True,
        comment="Reason for rejection",
    )
    
    # Quality tracking
    quality_checked = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether quality check was performed",
    )
    
    quality_check_passed = Column(
        Boolean,
        nullable=True,
        comment="Quality check result",
    )
    
    quality_checked_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who performed quality check",
    )
    
    quality_checked_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Quality check timestamp",
    )
    
    quality_rating = Column(
        Integer,
        nullable=True,
        comment="Quality rating (1-5 stars)",
    )
    
    # Preventive maintenance
    is_preventive = Column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="Whether this is preventive maintenance",
    )
    
    preventive_schedule_id = Column(
        UUID(as_uuid=True),
        ForeignKey("maintenance_schedules.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Related preventive maintenance schedule",
    )
    
    # Vendor information
    vendor_name = Column(
        String(255),
        nullable=True,
        comment="External vendor company name",
    )
    
    vendor_contact = Column(
        String(20),
        nullable=True,
        comment="Vendor contact number",
    )
    
    # Additional metadata
    metadata = Column(
        JSONB,
        nullable=True,
        default={},
        comment="Additional flexible metadata",
    )
    
    # Warranty
    warranty_applicable = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether warranty applies to this work",
    )
    
    warranty_period_months = Column(
        Integer,
        nullable=True,
        comment="Warranty period in months",
    )
    
    warranty_expiry_date = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Warranty expiration date",
    )
    
    # Relationships
    hostel = relationship("Hostel", back_populates="maintenance_requests")
    room = relationship("Room", back_populates="maintenance_requests")
    requester = relationship(
        "User",
        foreign_keys=[requested_by],
        back_populates="requested_maintenance"
    )
    assignee = relationship(
        "User",
        foreign_keys=[assigned_to],
        back_populates="assigned_maintenance"
    )
    assignments = relationship(
        "MaintenanceAssignment",
        back_populates="maintenance_request",
        cascade="all, delete-orphan"
    )
    approvals = relationship(
        "MaintenanceApproval",
        back_populates="maintenance_request",
        cascade="all, delete-orphan"
    )
    completion_record = relationship(
        "MaintenanceCompletion",
        back_populates="maintenance_request",
        uselist=False,
        cascade="all, delete-orphan"
    )
    cost_records = relationship(
        "MaintenanceCost",
        back_populates="maintenance_request",
        cascade="all, delete-orphan"
    )
    status_history = relationship(
        "MaintenanceStatusHistory",
        back_populates="maintenance_request",
        cascade="all, delete-orphan",
        order_by="MaintenanceStatusHistory.changed_at.desc()"
    )
    preventive_schedule = relationship(
        "MaintenanceSchedule",
        back_populates="maintenance_requests"
    )
    
    # Table constraints
    __table_args__ = (
        CheckConstraint(
            "estimated_cost >= 0",
            name="ck_maintenance_request_estimated_cost_positive"
        ),
        CheckConstraint(
            "actual_cost >= 0",
            name="ck_maintenance_request_actual_cost_positive"
        ),
        CheckConstraint(
            "approved_cost >= 0",
            name="ck_maintenance_request_approved_cost_positive"
        ),
        CheckConstraint(
            "quality_rating >= 1 AND quality_rating <= 5",
            name="ck_maintenance_request_quality_rating_range"
        ),
        CheckConstraint(
            "warranty_period_months >= 0",
            name="ck_maintenance_request_warranty_period_positive"
        ),
        Index("idx_maintenance_hostel_status", "hostel_id", "status"),
        Index("idx_maintenance_category_priority", "category", "priority"),
        Index("idx_maintenance_assigned_status", "assigned_to", "status"),
        Index("idx_maintenance_created_at", "created_at"),
        Index("idx_maintenance_completion_date", "actual_completion_date"),
        {"comment": "Core maintenance request tracking with comprehensive workflow"}
    )
    
    def __repr__(self) -> str:
        return f"<MaintenanceRequest {self.request_number} - {self.status.value}>"
    
    @validates("priority")
    def validate_priority(self, key: str, priority: Priority) -> Priority:
        """Validate priority based on issue type."""
        if self.issue_type == MaintenanceIssueType.EMERGENCY:
            if priority not in [Priority.HIGH, Priority.URGENT, Priority.CRITICAL]:
                raise ValueError(
                    "Emergency issues must have HIGH, URGENT, or CRITICAL priority"
                )
        return priority
    
    @validates("estimated_cost", "actual_cost", "approved_cost")
    def validate_costs(self, key: str, value: Optional[Decimal]) -> Optional[Decimal]:
        """Validate cost values are positive."""
        if value is not None and value < 0:
            raise ValueError(f"{key} must be positive")
        return value
    
    @validates("quality_rating")
    def validate_quality_rating(self, key: str, value: Optional[int]) -> Optional[int]:
        """Validate quality rating is in valid range."""
        if value is not None and (value < 1 or value > 5):
            raise ValueError("Quality rating must be between 1 and 5")
        return value
    
    @hybrid_property
    def is_completed(self) -> bool:
        """Check if maintenance is completed."""
        return self.status == MaintenanceStatus.COMPLETED
    
    @hybrid_property
    def is_overdue(self) -> bool:
        """Check if maintenance is overdue."""
        if self.status == MaintenanceStatus.COMPLETED:
            return False
        if self.deadline:
            return datetime.now(self.deadline.tzinfo) > self.deadline
        if self.estimated_completion_date:
            return datetime.now(self.estimated_completion_date.tzinfo) > self.estimated_completion_date
        return False
    
    @hybrid_property
    def cost_variance(self) -> Optional[Decimal]:
        """Calculate cost variance (actual - estimated)."""
        if self.actual_cost is not None and self.estimated_cost is not None:
            return self.actual_cost - self.estimated_cost
        return None
    
    @hybrid_property
    def days_open(self) -> int:
        """Calculate number of days request has been open."""
        if self.completed_at:
            return (self.completed_at - self.created_at).days
        return (datetime.now(self.created_at.tzinfo) - self.created_at).days
    
    @hybrid_property
    def within_budget(self) -> bool:
        """Check if work was completed within approved budget."""
        if self.actual_cost is None or self.approved_cost is None:
            return True
        return self.actual_cost <= self.approved_cost
    
    def update_status(
        self,
        new_status: MaintenanceStatus,
        changed_by: UUID,
        notes: Optional[str] = None
    ) -> None:
        """
        Update maintenance status with audit trail.
        
        Args:
            new_status: New status to set
            changed_by: User ID making the change
            notes: Optional notes about status change
        """
        old_status = self.status
        self.status = new_status
        self.status_changed_at = datetime.utcnow()
        self.status_changed_by = changed_by
        
        # Create status history record
        history = MaintenanceStatusHistory(
            maintenance_request_id=self.id,
            old_status=old_status,
            new_status=new_status,
            changed_by=changed_by,
            notes=notes
        )
        self.status_history.append(history)
    
    def assign_to_user(
        self,
        user_id: UUID,
        assigned_by: UUID,
        deadline: Optional[datetime] = None
    ) -> None:
        """
        Assign maintenance request to a user.
        
        Args:
            user_id: User to assign to
            assigned_by: User making the assignment
            deadline: Optional deadline for completion
        """
        self.assigned_to = user_id
        self.assigned_by = assigned_by
        self.assigned_at = datetime.utcnow()
        if deadline:
            self.deadline = deadline
        
        # Update status if currently pending
        if self.status == MaintenanceStatus.PENDING:
            self.update_status(
                MaintenanceStatus.ASSIGNED,
                assigned_by,
                f"Assigned to user {user_id}"
            )


class MaintenanceStatusHistory(BaseModel, UUIDMixin, TimestampModel):
    """
    Status change history for maintenance requests.
    
    Tracks all status transitions with timestamps and reasons
    for complete audit trail.
    """
    
    __tablename__ = "maintenance_status_history"
    
    maintenance_request_id = Column(
        UUID(as_uuid=True),
        ForeignKey("maintenance_requests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Related maintenance request",
    )
    
    old_status = Column(
        Enum(MaintenanceStatus),
        nullable=False,
        comment="Previous status",
    )
    
    new_status = Column(
        Enum(MaintenanceStatus),
        nullable=False,
        comment="New status",
    )
    
    changed_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who changed the status",
    )
    
    changed_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        comment="Status change timestamp",
    )
    
    notes = Column(
        Text,
        nullable=True,
        comment="Notes about the status change",
    )
    
    automated = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether change was automated",
    )
    
    # Relationships
    maintenance_request = relationship(
        "MaintenanceRequest",
        back_populates="status_history"
    )
    changer = relationship("User")
    
    # Table constraints
    __table_args__ = (
        Index("idx_status_history_request", "maintenance_request_id", "changed_at"),
        {"comment": "Complete audit trail of status changes"}
    )
    
    def __repr__(self) -> str:
        return (
            f"<MaintenanceStatusHistory {self.old_status.value} → "
            f"{self.new_status.value} at {self.changed_at}>"
        )


class MaintenanceIssueType(BaseModel, UUIDMixin, TimestampModel):
    """
    Maintenance issue type definitions and categorization.
    
    Allows dynamic issue type configuration beyond enum values
    with custom SLA and handling rules.
    """
    
    __tablename__ = "maintenance_issue_types"
    
    name = Column(
        String(100),
        unique=True,
        nullable=False,
        comment="Issue type name",
    )
    
    category = Column(
        Enum(MaintenanceCategory),
        nullable=False,
        index=True,
        comment="Parent category",
    )
    
    description = Column(
        Text,
        nullable=True,
        comment="Detailed description",
    )
    
    default_priority = Column(
        Enum(Priority),
        nullable=False,
        default=Priority.MEDIUM,
        comment="Default priority for this issue type",
    )
    
    sla_hours = Column(
        Integer,
        nullable=True,
        comment="SLA response time in hours",
    )
    
    requires_approval = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether this type requires approval",
    )
    
    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether this issue type is active",
    )
    
    # Table constraints
    __table_args__ = (
        CheckConstraint(
            "sla_hours > 0",
            name="ck_issue_type_sla_positive"
        ),
        {"comment": "Dynamic issue type definitions"}
    )
    
    def __repr__(self) -> str:
        return f"<MaintenanceIssueType {self.name}>"