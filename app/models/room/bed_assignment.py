# app/models/room/bed_assignment.py
"""
Bed assignment models with intelligent assignment and optimization.

Manages current bed assignments, assignment history, conflict resolution,
optimization strategies, and assignment preferences.
"""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import relationship, Mapped, mapped_column

from app.models.base.base_model import BaseModel, TimestampModel
from app.models.base.mixins import (
    SoftDeleteMixin,
    UUIDMixin,
    AuditMixin,
)

__all__ = [
    "BedAssignment",
    "AssignmentRule",
    "AssignmentConflict",
    "AssignmentOptimization",
    "AssignmentHistory",
    "AssignmentPreference",
]


class BedAssignment(BaseModel, UUIDMixin, TimestampModel, SoftDeleteMixin, AuditMixin):
    """
    Current bed assignments with student details.
    
    Tracks active bed assignments with complete lifecycle management.
    """

    __tablename__ = "bed_assignments"

    # Assignment Basics
    bed_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("beds.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    student_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    room_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("rooms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    hostel_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("hostels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Assignment Dates
    occupied_from: Mapped[datetime] = mapped_column(
        Date,
        nullable=False,
        index=True,
    )
    expected_vacate_date: Mapped[Optional[datetime]] = mapped_column(
        Date,
        nullable=True,
        index=True,
    )
    actual_vacate_date: Mapped[Optional[datetime]] = mapped_column(
        Date,
        nullable=True,
    )

    # Assignment Type
    assignment_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="REGULAR",  # REGULAR, TEMPORARY, EMERGENCY, TRANSFER
        index=True,
    )
    assignment_source: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="MANUAL",  # MANUAL, AUTOMATIC, BOOKING, TRANSFER
    )

    # Status
    assignment_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="ACTIVE",  # ACTIVE, COMPLETED, CANCELLED, TRANSFERRED
        index=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
    )
    is_confirmed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    confirmation_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Booking Reference
    booking_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("bookings.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    booking_reference: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )

    # Pricing
    monthly_rent: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )
    security_deposit: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00"),
    )
    total_rent_charged: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
    )
    total_rent_paid: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
    )
    outstanding_balance: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
    )

    # Assignment Method
    assignment_method: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="ADMIN",  # ADMIN, SYSTEM, SELF_SERVICE, PREFERENCE
    )
    assigned_by: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    assignment_algorithm: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,  # Which algorithm was used for automatic assignment
    )
    assignment_score: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,  # Match quality score for preference-based assignment
    )

    # Preferences Met
    preferences_matched: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
    )
    preferences_not_matched: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
    )
    preference_satisfaction_score: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,  # 0-100 scale
    )

    # Check-in/Check-out
    check_in_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    checked_in_by: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    check_out_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    checked_out_by: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Condition Documentation
    check_in_condition: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    check_in_photos: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
    )
    check_out_condition: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    check_out_photos: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
    )

    # Damage Assessment
    damages_reported: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    damage_details: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    damage_cost: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00"),
    )
    damage_deducted_from_deposit: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00"),
    )

    # Duration Tracking
    duration_days: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    duration_months: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(8, 2),
        nullable=True,
    )
    is_extended: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    extension_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    # Roommate Information
    roommate_ids: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
    )
    roommate_compatibility_score: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
    )
    roommate_issues_reported: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    # Transfer Information
    is_transfer: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    previous_bed_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("beds.id", ondelete="SET NULL"),
        nullable=True,
    )
    transfer_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    transfer_date: Mapped[Optional[datetime]] = mapped_column(
        Date,
        nullable=True,
    )
    transfer_approved_by: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Early Checkout
    is_early_checkout: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    early_checkout_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    early_checkout_penalty: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00"),
    )

    # Approval Workflow
    requires_approval: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    is_approved: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    approved_by: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    approved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    approval_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Special Conditions
    has_special_conditions: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    special_conditions: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )
    special_accommodations: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
    )

    # Performance Metrics
    student_satisfaction_rating: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(3, 2),
        nullable=True,  # 1-5 scale
    )
    payment_punctuality_score: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,  # 0-100 scale
    )
    rule_compliance_score: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,  # 0-100 scale
    )

    # Issues and Complaints
    total_complaints: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    total_maintenance_requests: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    has_active_issues: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    # Contract/Agreement
    has_signed_agreement: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    agreement_document_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )
    agreement_signed_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Emergency Contact During Stay
    emergency_contact_updated: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    emergency_contact_verified: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    # Notifications
    notification_preferences: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )
    last_notification_sent: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Notes and Comments
    assignment_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    admin_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    student_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Metadata
    last_status_change: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_modified_by: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    bed = relationship(
        "Bed",
        foreign_keys=[bed_id],
        back_populates="assignments",
    )
    student = relationship(
        "Student",
        back_populates="bed_assignments",
    )
    room = relationship(
        "Room",
        back_populates="bed_assignments",
    )
    hostel = relationship(
        "Hostel",
        back_populates="bed_assignments",
    )
    booking = relationship(
        "Booking",
        back_populates="bed_assignment",
    )
    previous_bed = relationship(
        "Bed",
        foreign_keys=[previous_bed_id],
    )

    __table_args__ = (
        Index("ix_bed_assignment_active", "bed_id", "is_active"),
        Index("ix_bed_assignment_student", "student_id", "is_active"),
        Index("ix_bed_assignment_dates", "occupied_from", "expected_vacate_date"),
        Index("ix_bed_assignment_status", "assignment_status", "is_active"),
    )

    def __repr__(self) -> str:
        return (
            f"<BedAssignment(id={self.id}, bed_id={self.bed_id}, "
            f"student_id={self.student_id}, status={self.assignment_status})>"
        )

    @property
    def days_stayed(self) -> int:
        """Calculate total days stayed."""
        from datetime import date
        end_date = self.actual_vacate_date or date.today()
        return (end_date - self.occupied_from).days

    @property
    def is_overdue(self) -> bool:
        """Check if student has overstayed expected vacate date."""
        from datetime import date
        if not self.expected_vacate_date or self.actual_vacate_date:
            return False
        return date.today() > self.expected_vacate_date

    @property
    def has_outstanding_payment(self) -> bool:
        """Check if there is outstanding balance."""
        return self.outstanding_balance > Decimal("0.00")


class AssignmentRule(BaseModel, UUIDMixin, TimestampModel, SoftDeleteMixin, AuditMixin):
    """
    Automated bed assignment algorithms and rules.
    
    Defines rules for automatic bed assignment based on various criteria.
    """

    __tablename__ = "assignment_rules"

    hostel_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("hostels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Rule Configuration
    rule_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )
    rule_code: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        unique=True,
    )
    rule_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,  # PREFERENCE_BASED, AVAILABILITY_BASED, RANDOM, CUSTOM
    )
    rule_description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Priority and Execution
    priority: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=10,  # Lower number = higher priority
    )
    execution_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=10,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
    )

    # Rule Conditions
    conditions: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
    )
    matching_criteria: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )
    exclusion_criteria: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )

    # Scoring and Weighting
    scoring_algorithm: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="WEIGHTED_SUM",
    )
    scoring_weights: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )
    minimum_match_score: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,  # Minimum score required for assignment
    )

    # Preference Handling
    consider_student_preferences: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    preference_weight: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("50.00"),  # Percentage weight
    )

    # Room Type Preferences
    allowed_room_types: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
    )
    preferred_room_types: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
    )

    # Gender Considerations
    enforce_gender_policy: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    allow_mixed_gender_rooms: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    # Age Considerations
    enforce_age_restrictions: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    age_range_tolerance: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,  # Years
    )

    # Compatibility Matching
    enable_compatibility_matching: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    compatibility_factors: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
    )
    minimum_compatibility_score: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
    )

    # Optimization Goals
    optimization_goal: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="MAXIMIZE_SATISFACTION",  # MAXIMIZE_SATISFACTION, MAXIMIZE_OCCUPANCY, MINIMIZE_VACANCY
    )
    balance_occupancy: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    # Constraints
    max_assignments_per_run: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    allow_overbooking: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    overbooking_percentage: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
    )

    # Fallback Behavior
    fallback_rule_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("assignment_rules.id", ondelete="SET NULL"),
        nullable=True,
    )
    fallback_to_manual: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    # Performance Tracking
    total_assignments: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    successful_assignments: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    failed_assignments: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    average_match_score: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
    )
    success_rate: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,  # Percentage
    )

    # Last Execution
    last_executed: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_execution_duration_ms: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    last_execution_result: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Validity Period
    valid_from: Mapped[Optional[datetime]] = mapped_column(
        Date,
        nullable=True,
    )
    valid_to: Mapped[Optional[datetime]] = mapped_column(
        Date,
        nullable=True,
    )

    # Notes
    rule_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    configuration_json: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )

    # Relationships
    hostel = relationship(
        "Hostel",
        back_populates="assignment_rules",
    )
    fallback_rule = relationship(
        "AssignmentRule",
        remote_side="AssignmentRule.id",
    )

    __table_args__ = (
        Index("ix_assignment_rule_active", "hostel_id", "is_active"),
        Index("ix_assignment_rule_priority", "priority", "execution_order"),
    )

    def __repr__(self) -> str:
        return (
            f"<AssignmentRule(id={self.id}, name={self.rule_name}, "
            f"type={self.rule_type}, priority={self.priority})>"
        )


class AssignmentConflict(BaseModel, UUIDMixin, TimestampModel):
    """
    Conflict resolution for bed assignments.
    
    Tracks and manages conflicts that arise during bed assignment process.
    """

    __tablename__ = "assignment_conflicts"

    # Conflict Basics
    conflict_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,  # DOUBLE_BOOKING, PREFERENCE_MISMATCH, CAPACITY_EXCEEDED, POLICY_VIOLATION
    )
    conflict_severity: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="MEDIUM",  # LOW, MEDIUM, HIGH, CRITICAL
        index=True,
    )
    conflict_description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    # Involved Entities
    bed_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("beds.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    student_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("students.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    conflicting_student_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("students.id", ondelete="SET NULL"),
        nullable=True,
    )
    assignment_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("bed_assignments.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Conflict Details
    conflict_reason: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    affected_dates: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,  # {"start": "2024-01-01", "end": "2024-01-31"}
    )
    policy_violated: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True,
    )

    # Conflict Status
    conflict_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="DETECTED",  # DETECTED, UNDER_REVIEW, RESOLVED, ESCALATED
        index=True,
    )
    is_resolved: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
    )

    # Detection
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    detected_by: Mapped[str] = mapped_column(
        String(50),
        nullable=False,  # SYSTEM, ADMIN, VALIDATION
    )
    detection_algorithm: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )

    # Resolution
    resolution_method: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,  # AUTOMATIC, MANUAL, ESCALATED
    )
    resolution_action: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    resolved_by: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    resolution_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Alternative Solutions
    suggested_solutions: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
    )
    alternative_beds: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
    )

    # Impact Assessment
    impact_level: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="MEDIUM",  # LOW, MEDIUM, HIGH, CRITICAL
    )
    affected_students_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )
    requires_immediate_action: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    # Escalation
    is_escalated: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    escalated_to: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    escalation_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    escalation_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Communication
    notification_sent: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    notification_recipients: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
    )
    last_notification_sent: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Notes and Documentation
    conflict_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    admin_comments: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    documentation_urls: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
    )

    # Relationships
    bed = relationship(
        "Bed",
        foreign_keys=[bed_id],
    )
    student = relationship(
        "Student",
        foreign_keys=[student_id],
    )
    conflicting_student = relationship(
        "Student",
        foreign_keys=[conflicting_student_id],
    )

    __table_args__ = (
        Index("ix_conflict_status", "conflict_status", "is_resolved"),
        Index("ix_conflict_severity", "conflict_severity", "detected_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<AssignmentConflict(id={self.id}, type={self.conflict_type}, "
            f"severity={self.conflict_severity}, status={self.conflict_status})>"
        )


class AssignmentOptimization(BaseModel, UUIDMixin, TimestampModel):
    """
    Optimal bed allocation strategies.
    
    Manages optimization runs and results for bed assignments.
    """

    __tablename__ = "assignment_optimizations"

    hostel_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("hostels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Optimization Run
    optimization_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )
    optimization_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,  # INITIAL_PLACEMENT, REBALANCING, SEASONAL, CUSTOM
    )
    run_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    # Algorithm Configuration
    algorithm_used: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    algorithm_version: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    algorithm_parameters: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )

    # Optimization Goals
    primary_goal: Mapped[str] = mapped_column(
        String(100),
        nullable=False,  # MAXIMIZE_SATISFACTION, MAXIMIZE_REVENUE, MINIMIZE_VACANCY
    )
    secondary_goals: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
    )
    goal_weights: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )

    # Constraints
    constraints_applied: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
    )
    hard_constraints: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
    )
    soft_constraints: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
    )

    # Input Data
    total_beds_considered: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    total_students_considered: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    available_beds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    pending_assignments: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    # Execution Details
    execution_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="RUNNING",  # QUEUED, RUNNING, COMPLETED, FAILED
        index=True,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    execution_duration_ms: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )

    # Results
    assignments_generated: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    assignments_applied: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    conflicts_detected: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    conflicts_resolved: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    # Quality Metrics
    overall_optimization_score: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,  # 0-100 scale
    )
    satisfaction_score: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
    )
    efficiency_score: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
    )
    fairness_score: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
    )

    # Comparison with Current
    improvement_over_current: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(8, 2),
        nullable=True,  # Percentage improvement
    )
    revenue_impact: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 2),
        nullable=True,
    )
    occupancy_improvement: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,  # Percentage points
    )

    # Detailed Results
    optimization_results: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,  # Detailed breakdown of assignments
    )
    assignment_recommendations: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )
    rebalancing_suggestions: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )

    # Application Status
    is_applied: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    applied_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    applied_by: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    application_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Error Handling
    has_errors: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    error_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    error_details: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )
    warnings: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
    )

    # Validation
    is_validated: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    validation_results: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )
    validation_errors: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
    )

    # Notes
    optimization_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    recommendations: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Relationship
    hostel = relationship(
        "Hostel",
        back_populates="assignment_optimizations",
    )

    __table_args__ = (
        Index("ix_optimization_status", "execution_status", "run_date"),
        Index("ix_optimization_applied", "is_applied", "hostel_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<AssignmentOptimization(id={self.id}, name={self.optimization_name}, "
            f"type={self.optimization_type}, status={self.execution_status})>"
        )


class AssignmentHistory(BaseModel, UUIDMixin, TimestampModel):
    """
    Complete assignment history tracking.
    
    Maintains historical record of all bed assignments for audit and analysis.
    """

    __tablename__ = "assignment_history"

    # Reference to Current Assignment
    assignment_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("bed_assignments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Historical Snapshot
    bed_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        index=True,
    )
    student_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        index=True,
    )
    room_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
    )

    # Change Details
    change_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,  # CREATED, UPDATED, TRANSFERRED, EXTENDED, CANCELLED, COMPLETED
    )
    change_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    changed_by: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Previous Values
    previous_values: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )
    new_values: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )
    changed_fields: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
    )

    # Change Reason
    change_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    change_category: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )

    # Duration Information
    occupied_from: Mapped[datetime] = mapped_column(
        Date,
        nullable=False,
    )
    occupied_to: Mapped[Optional[datetime]] = mapped_column(
        Date,
        nullable=True,
    )
    duration_days: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )

    # Financial Summary
    total_rent_paid: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
    )
    total_charges: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
    )
    damages_charged: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00"),
    )

    # Performance Metrics
    satisfaction_rating: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(3, 2),
        nullable=True,
    )
    payment_score: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
    )
    compliance_score: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
    )

    # Issue Summary
    total_complaints: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    total_maintenance_requests: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    # Notes
    historical_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    admin_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Metadata
    snapshot_data: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,  # Complete snapshot of assignment at the time
    )

    __table_args__ = (
        Index("ix_history_assignment", "assignment_id", "change_date"),
        Index("ix_history_bed", "bed_id", "change_date"),
        Index("ix_history_student", "student_id", "change_date"),
        Index("ix_history_change_type", "change_type", "change_date"),
    )

    def __repr__(self) -> str:
        return (
            f"<AssignmentHistory(id={self.id}, assignment_id={self.assignment_id}, "
            f"change_type={self.change_type}, date={self.change_date})>"
        )


class AssignmentPreference(BaseModel, UUIDMixin, TimestampModel):
    """
    Student and admin assignment preferences.
    
    Manages preferences that influence automatic bed assignment decisions.
    """

    __tablename__ = "assignment_preferences"

    hostel_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("hostels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    student_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    # Preference Type
    preference_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,  # STUDENT, ADMIN, SYSTEM, POLICY
    )
    preference_scope: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="INDIVIDUAL",  # INDIVIDUAL, GROUP, HOSTEL_WIDE
    )

    # Room Preferences
    preferred_room_types: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
    )
    preferred_floors: Mapped[Optional[List[int]]] = mapped_column(
        ARRAY(Integer),
        nullable=True,
    )
    preferred_wings: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
    )

    # Bed Position Preferences
    preferred_bed_positions: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
    )
    avoid_upper_bunk: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    avoid_lower_bunk: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    # Environmental Preferences
    natural_light_importance: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="MEDIUM",  # LOW, MEDIUM, HIGH
    )
    noise_sensitivity: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="MEDIUM",
    )
    privacy_requirement: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="MEDIUM",
    )

    # Roommate Preferences
    preferred_roommates: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,  # Student IDs
    )
    avoid_roommates: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
    )
    roommate_matching_criteria: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )

    # Special Requirements
    accessibility_required: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    medical_requirements: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
    )
    special_accommodations: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
    )

    # Lifestyle Preferences
    sleep_schedule: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )
    study_habits: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )
    social_preference: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,  # SOCIAL, MODERATE, QUIET
    )

    # Flexibility
    is_flexible: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    flexibility_score: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("50.00"),  # 0-100 scale
    )
    must_have_criteria: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
    )
    nice_to_have_criteria: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
    )

    # Priority and Weighting
    preference_priority: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=5,  # 1-10 scale
    )
    criteria_weights: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,  # Custom weights for different criteria
    )

    # Validity
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
    )
    valid_from: Mapped[Optional[datetime]] = mapped_column(
        Date,
        nullable=True,
    )
    valid_to: Mapped[Optional[datetime]] = mapped_column(
        Date,
        nullable=True,
    )

    # Satisfaction Tracking
    preferences_met_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    preferences_not_met_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    overall_satisfaction: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(3, 2),
        nullable=True,  # 1-5 scale
    )

    # Notes
    preference_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    admin_override_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Metadata
    preference_source: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="MANUAL",  # MANUAL, SURVEY, ALGORITHM, HISTORICAL
    )
    last_updated_by: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    __table_args__ = (
        Index("ix_pref_student_active", "student_id", "is_active"),
        Index("ix_pref_hostel_type", "hostel_id", "preference_type"),
    )

    def __repr__(self) -> str:
        return (
            f"<AssignmentPreference(id={self.id}, student_id={self.student_id}, "
            f"type={self.preference_type})>"
        )