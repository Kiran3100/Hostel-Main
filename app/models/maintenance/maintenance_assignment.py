# app/models/maintenance/maintenance_assignment.py
"""
Maintenance assignment models.

Task assignment tracking for staff and vendor assignments
with workload management and performance metrics.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional

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
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import relationship, validates
from sqlalchemy.ext.hybrid import hybrid_property

from app.models.base.base_model import BaseModel, TimestampModel
from app.models.base.mixins import SoftDeleteMixin, UUIDMixin, AuditMixin

from app.schemas.common.enums import MaintenanceStatus


class MaintenanceAssignment(UUIDMixin, TimestampModel, SoftDeleteMixin, AuditMixin, BaseModel):
    """
    Task assignment tracking for maintenance requests.
    
    Manages assignment of maintenance tasks to internal staff
    with deadline tracking and reassignment history.
    """
    
    __tablename__ = "maintenance_assignments"
    
    maintenance_request_id = Column(
        UUID(as_uuid=True),
        ForeignKey("maintenance_requests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Related maintenance request",
    )
    
    # Assignment details
    assigned_to = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=False,
        index=True,
        comment="Staff member assigned",
    )
    
    assigned_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=False,
        comment="User who made the assignment",
    )
    
    assigned_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        index=True,
        comment="Assignment timestamp",
    )
    
    # Timeline
    deadline = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="Task completion deadline",
    )
    
    started_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Work start timestamp",
    )
    
    completed_at = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="Task completion timestamp",
    )
    
    # Instructions and notes
    instructions = Column(
        Text,
        nullable=True,
        comment="Specific instructions for assigned staff",
    )
    
    completion_notes = Column(
        Text,
        nullable=True,
        comment="Notes upon task completion",
    )
    
    # Priority and estimates
    priority_level = Column(
        String(20),
        nullable=True,
        comment="Assignment priority level",
    )
    
    estimated_hours = Column(
        Numeric(5, 2),
        nullable=True,
        comment="Estimated hours to complete",
    )
    
    actual_hours = Column(
        Numeric(5, 2),
        nullable=True,
        comment="Actual hours spent",
    )
    
    # Status tracking
    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
        comment="Whether assignment is currently active",
    )
    
    is_completed = Column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="Whether task is completed",
    )
    
    is_reassigned = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether task was reassigned to someone else",
    )
    
    reassigned_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Reassignment timestamp",
    )
    
    reassignment_reason = Column(
        Text,
        nullable=True,
        comment="Reason for reassignment",
    )
    
    # Performance tracking
    met_deadline = Column(
        Boolean,
        nullable=True,
        comment="Whether deadline was met",
    )
    
    quality_rating = Column(
        Integer,
        nullable=True,
        comment="Quality rating for completed work (1-5)",
    )
    
    # Required skills and tools
    required_skills = Column(
        ARRAY(String),
        nullable=True,
        default=[],
        comment="Skills required for the task",
    )
    
    tools_required = Column(
        ARRAY(String),
        nullable=True,
        default=[],
        comment="Tools/equipment required",
    )
    
    # Metadata - renamed from 'metadata' to avoid conflict with SQLAlchemy
    additional_data = Column(
        JSONB,
        nullable=True,
        default={},
        comment="Additional flexible metadata",
    )
    
    # Relationships
    maintenance_request = relationship(
        "MaintenanceRequest",
        back_populates="assignments"
    )
    assignee = relationship(
        "User",
        foreign_keys=[assigned_to],
        back_populates="maintenance_assignments"
    )
    assigner = relationship(
        "User",
        foreign_keys=[assigned_by]
    )
    
    # Table constraints
    __table_args__ = (
        CheckConstraint(
            "estimated_hours >= 0",
            name="ck_assignment_estimated_hours_positive"
        ),
        CheckConstraint(
            "actual_hours >= 0",
            name="ck_assignment_actual_hours_positive"
        ),
        CheckConstraint(
            "quality_rating >= 1 AND quality_rating <= 5",
            name="ck_assignment_quality_rating_range"
        ),
        Index("idx_assignment_assignee_active", "assigned_to", "is_active"),
        Index("idx_assignment_deadline", "deadline"),
        {"comment": "Task assignment tracking for maintenance requests"}
    )
    
    def __repr__(self) -> str:
        return (
            f"<MaintenanceAssignment request={self.maintenance_request_id} "
            f"assignee={self.assigned_to}>"
        )
    
    @validates("quality_rating")
    def validate_quality_rating(self, key: str, value: Optional[int]) -> Optional[int]:
        """Validate quality rating is in valid range."""
        if value is not None and (value < 1 or value > 5):
            raise ValueError("Quality rating must be between 1 and 5")
        return value
    
    @hybrid_property
    def is_overdue(self) -> bool:
        """Check if assignment is overdue."""
        if self.is_completed:
            return False
        if self.deadline:
            return datetime.now(self.deadline.tzinfo) > self.deadline
        return False
    
    @hybrid_property
    def hours_variance(self) -> Optional[Decimal]:
        """Calculate variance between estimated and actual hours."""
        if self.actual_hours is not None and self.estimated_hours is not None:
            return self.actual_hours - self.estimated_hours
        return None
    
    def mark_completed(
        self,
        completion_notes: Optional[str] = None,
        actual_hours: Optional[Decimal] = None,
        quality_rating: Optional[int] = None
    ) -> None:
        """
        Mark assignment as completed.
        
        Args:
            completion_notes: Notes about completion
            actual_hours: Actual hours spent
            quality_rating: Quality rating (1-5)
        """
        self.is_completed = True
        self.completed_at = datetime.utcnow()
        self.is_active = False
        
        if completion_notes:
            self.completion_notes = completion_notes
        if actual_hours is not None:
            self.actual_hours = actual_hours
        if quality_rating is not None:
            self.quality_rating = quality_rating
        
        # Check if deadline was met
        if self.deadline:
            self.met_deadline = self.completed_at <= self.deadline
    
    def reassign(
        self,
        new_assignee: UUID,
        reason: str,
        reassigned_by: UUID
    ) -> "MaintenanceAssignment":
        """
        Reassign task to a different user.
        
        Args:
            new_assignee: New user to assign to
            reason: Reason for reassignment
            reassigned_by: User making the reassignment
            
        Returns:
            New assignment record
        """
        # Mark current assignment as reassigned
        self.is_reassigned = True
        self.reassigned_at = datetime.utcnow()
        self.reassignment_reason = reason
        self.is_active = False
        
        # Create new assignment
        new_assignment = MaintenanceAssignment(
            maintenance_request_id=self.maintenance_request_id,
            assigned_to=new_assignee,
            assigned_by=reassigned_by,
            deadline=self.deadline,
            instructions=self.instructions,
            priority_level=self.priority_level,
            estimated_hours=self.estimated_hours,
            required_skills=self.required_skills,
            tools_required=self.tools_required
        )
        
        return new_assignment


class VendorAssignment(UUIDMixin, TimestampModel, SoftDeleteMixin, AuditMixin, BaseModel):
    """
    Vendor/contractor assignment for maintenance work.
    
    Manages outsourced maintenance work with vendor details,
    contracts, and payment tracking.
    """
    
    __tablename__ = "vendor_assignments"
    
    maintenance_request_id = Column(
        UUID(as_uuid=True),
        ForeignKey("maintenance_requests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Related maintenance request",
    )
    
    vendor_id = Column(
        UUID(as_uuid=True),
        ForeignKey("maintenance_vendors.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Vendor from master vendor list",
    )
    
    # Vendor details (denormalized for historical accuracy)
    vendor_name = Column(
        String(255),
        nullable=False,
        comment="Vendor company name",
    )
    
    vendor_contact_person = Column(
        String(255),
        nullable=True,
        comment="Contact person name",
    )
    
    vendor_contact = Column(
        String(20),
        nullable=False,
        comment="Primary contact number",
    )
    
    vendor_email = Column(
        String(255),
        nullable=True,
        comment="Vendor email address",
    )
    
    vendor_address = Column(
        Text,
        nullable=True,
        comment="Vendor business address",
    )
    
    # Quote and contract
    quoted_amount = Column(
        Numeric(10, 2),
        nullable=False,
        comment="Vendor quoted amount",
    )
    
    quote_reference = Column(
        String(100),
        nullable=True,
        comment="Quote reference number",
    )
    
    quote_valid_until = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Quote validity date",
    )
    
    payment_terms = Column(
        Text,
        nullable=True,
        comment="Payment terms and conditions",
    )
    
    advance_payment_percentage = Column(
        Numeric(5, 2),
        nullable=True,
        comment="Advance payment percentage",
    )
    
    advance_payment_amount = Column(
        Numeric(10, 2),
        nullable=True,
        comment="Advance payment amount",
    )
    
    # Timeline
    estimated_start_date = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Estimated work start date",
    )
    
    estimated_completion_date = Column(
        DateTime(timezone=True),
        nullable=False,
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
        comment="Actual completion date",
    )
    
    # Contract details
    work_order_number = Column(
        String(100),
        nullable=True,
        unique=True,
        comment="Work order reference number",
    )
    
    contract_details = Column(
        Text,
        nullable=True,
        comment="Contract terms and scope of work",
    )
    
    warranty_period_months = Column(
        Integer,
        nullable=True,
        comment="Warranty period in months",
    )
    
    warranty_terms = Column(
        Text,
        nullable=True,
        comment="Warranty terms and conditions",
    )
    
    # Insurance and compliance
    vendor_insured = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether vendor has liability insurance",
    )
    
    insurance_details = Column(
        Text,
        nullable=True,
        comment="Insurance policy details",
    )
    
    compliance_certificates = Column(
        ARRAY(String),
        nullable=True,
        default=[],
        comment="Required compliance certificates",
    )
    
    # Status tracking
    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
        comment="Whether assignment is active",
    )
    
    is_completed = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether work is completed",
    )
    
    # Payment tracking
    payment_made = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether payment has been made",
    )
    
    payment_amount = Column(
        Numeric(10, 2),
        nullable=True,
        comment="Total payment amount",
    )
    
    payment_date = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Payment date",
    )
    
    # Performance tracking
    vendor_rating = Column(
        Integer,
        nullable=True,
        comment="Vendor performance rating (1-5)",
    )
    
    would_recommend = Column(
        Boolean,
        nullable=True,
        comment="Whether to recommend vendor for future work",
    )
    
    performance_notes = Column(
        Text,
        nullable=True,
        comment="Vendor performance notes",
    )
    
    # Metadata - renamed from 'metadata' to avoid conflict with SQLAlchemy
    additional_data = Column(
        JSONB,
        nullable=True,
        default={},
        comment="Additional flexible metadata",
    )
    
    # Relationships
    maintenance_request = relationship(
        "MaintenanceRequest",
        back_populates="vendor_assignments"
    )
    vendor = relationship(
        "MaintenanceVendor",
        back_populates="assignments"
    )
    
    # Table constraints
    __table_args__ = (
        CheckConstraint(
            "quoted_amount >= 0",
            name="ck_vendor_assignment_quoted_amount_positive"
        ),
        CheckConstraint(
            "advance_payment_percentage >= 0 AND advance_payment_percentage <= 100",
            name="ck_vendor_assignment_advance_percentage_range"
        ),
        CheckConstraint(
            "advance_payment_amount >= 0",
            name="ck_vendor_assignment_advance_amount_positive"
        ),
        CheckConstraint(
            "payment_amount >= 0",
            name="ck_vendor_assignment_payment_amount_positive"
        ),
        CheckConstraint(
            "vendor_rating >= 1 AND vendor_rating <= 5",
            name="ck_vendor_assignment_rating_range"
        ),
        Index("idx_vendor_assignment_vendor", "vendor_id", "is_active"),
        Index("idx_vendor_assignment_completion", "estimated_completion_date"),
        {"comment": "Vendor assignment tracking for outsourced maintenance"}
    )
    
    def __repr__(self) -> str:
        return f"<VendorAssignment {self.vendor_name} - {self.work_order_number}>"
    
    @validates("vendor_rating")
    def validate_vendor_rating(self, key: str, value: Optional[int]) -> Optional[int]:
        """Validate vendor rating is in valid range."""
        if value is not None and (value < 1 or value > 5):
            raise ValueError("Vendor rating must be between 1 and 5")
        return value
    
    @hybrid_property
    def is_overdue(self) -> bool:
        """Check if work is overdue."""
        if self.is_completed:
            return False
        if self.estimated_completion_date:
            return datetime.now(self.estimated_completion_date.tzinfo) > self.estimated_completion_date
        return False
    
    @hybrid_property
    def days_delayed(self) -> int:
        """Calculate days delayed from estimated completion."""
        if self.actual_completion_date and self.estimated_completion_date:
            delta = self.actual_completion_date - self.estimated_completion_date
            return max(0, delta.days)
        return 0