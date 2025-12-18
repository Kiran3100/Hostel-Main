# app/models/supervisor/supervisor.py
"""
Supervisor core model with comprehensive employment and management features.

Handles supervisor lifecycle, employment details, status management,
and hostel assignments with full audit trail.
"""

from datetime import date as Date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Boolean, Date as SQLDate, Decimal as SQLDecimal, Enum as SQLEnum,
    ForeignKey, Integer, String, Text, UniqueConstraint, Index
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base.base_model import BaseModel, TimestampModel
from app.models.base.mixins import (
    AuditMixin, SoftDeleteMixin, UUIDMixin
)
from app.schemas.common.enums import EmploymentType, SupervisorStatus

if TYPE_CHECKING:
    from app.models.user.user import User
    from app.models.hostel.hostel import Hostel
    from app.models.supervisor.supervisor_permissions import SupervisorPermission
    from app.models.supervisor.supervisor_assignment import SupervisorAssignment
    from app.models.supervisor.supervisor_activity import SupervisorActivity
    from app.models.supervisor.supervisor_performance import SupervisorPerformance

__all__ = [
    "Supervisor",
    "SupervisorEmployment",
    "SupervisorStatusHistory",
    "SupervisorNote",
]


class Supervisor(BaseModel, TimestampModel, UUIDMixin, SoftDeleteMixin, AuditMixin):
    """
    Core supervisor entity with employment and assignment details.
    
    Manages supervisor lifecycle from assignment to termination with
    comprehensive tracking of employment details and status changes.
    """
    
    __tablename__ = "supervisors"
    
    # ============ Relationships - User and Hostel ============
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Associated user account"
    )
    
    assigned_hostel_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("hostels.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        comment="Currently assigned hostel"
    )
    
    # ============ Employment Details ============
    employee_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        unique=True,
        index=True,
        comment="Unique employee/staff ID"
    )
    
    join_date: Mapped[Date] = mapped_column(
        SQLDate,
        nullable=False,
        index=True,
        comment="Joining/start date"
    )
    
    employment_type: Mapped[EmploymentType] = mapped_column(
        SQLEnum(EmploymentType, name="employment_type_enum", create_constraint=True),
        nullable=False,
        default=EmploymentType.FULL_TIME,
        comment="Employment type"
    )
    
    shift_timing: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Shift timing or working hours"
    )
    
    designation: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Job designation/title"
    )
    
    salary: Mapped[Optional[Decimal]] = mapped_column(
        SQLDecimal(10, 2),
        nullable=True,
        comment="Monthly salary (confidential)"
    )
    
    # ============ Status Management ============
    status: Mapped[SupervisorStatus] = mapped_column(
        SQLEnum(SupervisorStatus, name="supervisor_status_enum", create_constraint=True),
        nullable=False,
        default=SupervisorStatus.ACTIVE,
        index=True,
        comment="Current employment status"
    )
    
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
        comment="Active status flag"
    )
    
    # ============ Assignment Details ============
    assigned_by: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=False,
        comment="Admin who assigned supervisor"
    )
    
    assigned_date: Mapped[Date] = mapped_column(
        SQLDate,
        nullable=False,
        default=Date.today,
        comment="Assignment date"
    )
    
    # ============ Contract Details (for contract employees) ============
    contract_start_date: Mapped[Optional[Date]] = mapped_column(
        SQLDate,
        nullable=True,
        comment="Contract start date"
    )
    
    contract_end_date: Mapped[Optional[Date]] = mapped_column(
        SQLDate,
        nullable=True,
        index=True,
        comment="Contract end date"
    )
    
    # ============ Termination Details ============
    termination_date: Mapped[Optional[Date]] = mapped_column(
        SQLDate,
        nullable=True,
        index=True,
        comment="Termination date"
    )
    
    termination_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Detailed termination reason"
    )
    
    termination_type: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Type: voluntary, involuntary, retirement, end_of_contract"
    )
    
    eligible_for_rehire: Mapped[Optional[bool]] = mapped_column(
        Boolean,
        nullable=True,
        comment="Eligible for rehire in future"
    )
    
    # ============ Suspension Details ============
    suspension_start_date: Mapped[Optional[Date]] = mapped_column(
        SQLDate,
        nullable=True,
        comment="Suspension start date"
    )
    
    suspension_end_date: Mapped[Optional[Date]] = mapped_column(
        SQLDate,
        nullable=True,
        comment="Expected suspension end date"
    )
    
    suspension_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Detailed suspension reason"
    )
    
    # ============ Leave Details ============
    leave_start_date: Mapped[Optional[Date]] = mapped_column(
        SQLDate,
        nullable=True,
        comment="Leave start date"
    )
    
    leave_end_date: Mapped[Optional[Date]] = mapped_column(
        SQLDate,
        nullable=True,
        comment="Expected return date from leave"
    )
    
    leave_type: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Type of leave"
    )
    
    # ============ Performance Tracking ============
    last_performance_review: Mapped[Optional[Date]] = mapped_column(
        SQLDate,
        nullable=True,
        comment="Last performance review date"
    )
    
    performance_rating: Mapped[Optional[Decimal]] = mapped_column(
        SQLDecimal(3, 2),
        nullable=True,
        comment="Latest performance rating (0-5 scale)"
    )
    
    total_complaints_resolved: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Total complaints resolved"
    )
    
    average_resolution_time_hours: Mapped[Decimal] = mapped_column(
        SQLDecimal(10, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Average complaint resolution time"
    )
    
    total_attendance_records: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Total attendance records created"
    )
    
    total_maintenance_requests: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Total maintenance requests handled"
    )
    
    # ============ Activity Tracking ============
    last_login: Mapped[Optional[datetime]] = mapped_column(
        nullable=True,
        comment="Last login timestamp"
    )
    
    total_logins: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Total login count"
    )
    
    last_activity: Mapped[Optional[datetime]] = mapped_column(
        nullable=True,
        index=True,
        comment="Last activity timestamp"
    )
    
    # ============ Salary Management ============
    last_salary_revision: Mapped[Optional[Date]] = mapped_column(
        SQLDate,
        nullable=True,
        comment="Last salary revision date"
    )
    
    # ============ Emergency Contact ============
    emergency_contact_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Emergency contact name"
    )
    
    emergency_contact_phone: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="Emergency contact phone"
    )
    
    emergency_contact_relation: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Emergency contact relationship"
    )
    
    # ============ Additional Information ============
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Administrative notes"
    )
    
    # ============ Relationships ============
    user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[user_id],
        back_populates="supervisor_profile",
        lazy="joined"
    )
    
    assigned_hostel: Mapped["Hostel"] = relationship(
        "Hostel",
        foreign_keys=[assigned_hostel_id],
        back_populates="supervisors",
        lazy="joined"
    )
    
    assigned_by_user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[assigned_by],
        lazy="select"
    )
    
    permissions: Mapped[Optional["SupervisorPermission"]] = relationship(
        "SupervisorPermission",
        back_populates="supervisor",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="joined"
    )
    
    assignments: Mapped[list["SupervisorAssignment"]] = relationship(
        "SupervisorAssignment",
        back_populates="supervisor",
        cascade="all, delete-orphan",
        lazy="select"
    )
    
    activities: Mapped[list["SupervisorActivity"]] = relationship(
        "SupervisorActivity",
        back_populates="supervisor",
        cascade="all, delete-orphan",
        lazy="select"
    )
    
    performance_records: Mapped[list["SupervisorPerformance"]] = relationship(
        "SupervisorPerformance",
        back_populates="supervisor",
        cascade="all, delete-orphan",
        lazy="select"
    )
    
    status_history: Mapped[list["SupervisorStatusHistory"]] = relationship(
        "SupervisorStatusHistory",
        back_populates="supervisor",
        cascade="all, delete-orphan",
        order_by="desc(SupervisorStatusHistory.changed_at)",
        lazy="select"
    )
    
    employment_history: Mapped[list["SupervisorEmployment"]] = relationship(
        "SupervisorEmployment",
        back_populates="supervisor",
        cascade="all, delete-orphan",
        order_by="desc(SupervisorEmployment.start_date)",
        lazy="select"
    )
    
    supervisor_notes: Mapped[list["SupervisorNote"]] = relationship(
        "SupervisorNote",
        back_populates="supervisor",
        cascade="all, delete-orphan",
        order_by="desc(SupervisorNote.created_at)",
        lazy="select"
    )
    
    # ============ Indexes ============
    __table_args__ = (
        Index("idx_supervisor_user_hostel", "user_id", "assigned_hostel_id"),
        Index("idx_supervisor_status_active", "status", "is_active"),
        Index("idx_supervisor_join_date", "join_date"),
        Index("idx_supervisor_employee_id", "employee_id"),
        Index("idx_supervisor_contract_end", "contract_end_date"),
        UniqueConstraint("user_id", "assigned_hostel_id", name="uq_supervisor_user_hostel"),
        {
            "comment": "Supervisor core entity with employment and assignment management"
        }
    )
    
    def __repr__(self) -> str:
        return (
            f"<Supervisor(id={self.id}, employee_id={self.employee_id}, "
            f"hostel={self.assigned_hostel_id}, status={self.status.value})>"
        )
    
    @property
    def tenure_days(self) -> int:
        """Calculate total tenure in days since joining."""
        end_date = self.termination_date or Date.today()
        return (end_date - self.join_date).days
    
    @property
    def tenure_months(self) -> int:
        """Calculate approximate tenure in months."""
        return self.tenure_days // 30
    
    @property
    def is_probation(self) -> bool:
        """Check if supervisor is in probation period (first 3 months)."""
        return self.tenure_months < 3
    
    @property
    def can_work(self) -> bool:
        """Check if supervisor is currently allowed to work."""
        return self.is_active and self.status == SupervisorStatus.ACTIVE
    
    @property
    def is_contract_employee(self) -> bool:
        """Check if supervisor is on contract."""
        return self.employment_type == EmploymentType.CONTRACT
    
    @property
    def contract_days_remaining(self) -> Optional[int]:
        """Calculate days remaining in contract."""
        if not self.contract_end_date:
            return None
        
        remaining = (self.contract_end_date - Date.today()).days
        return max(0, remaining)
    
    @property
    def suspension_days_remaining(self) -> Optional[int]:
        """Calculate remaining suspension days."""
        if self.status != SupervisorStatus.SUSPENDED or not self.suspension_end_date:
            return None
        
        remaining = (self.suspension_end_date - Date.today()).days
        return max(0, remaining)


class SupervisorEmployment(BaseModel, TimestampModel, UUIDMixin):
    """
    Employment history tracking for supervisors.
    
    Maintains complete employment history across different hostels
    and positions with performance ratings.
    """
    
    __tablename__ = "supervisor_employment_history"
    
    # ============ Relationships ============
    supervisor_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("supervisors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Supervisor reference"
    )
    
    hostel_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("hostels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Hostel where employed"
    )
    
    # ============ Employment Period ============
    start_date: Mapped[Date] = mapped_column(
        SQLDate,
        nullable=False,
        index=True,
        comment="Assignment start date"
    )
    
    end_date: Mapped[Optional[Date]] = mapped_column(
        SQLDate,
        nullable=True,
        index=True,
        comment="Assignment end date (null if current)"
    )
    
    # ============ Position Details ============
    designation: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Designation during this period"
    )
    
    employment_type: Mapped[EmploymentType] = mapped_column(
        SQLEnum(EmploymentType, name="employment_type_enum", create_constraint=True),
        nullable=False,
        comment="Employment type"
    )
    
    shift_timing: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Shift timing during this period"
    )
    
    # ============ Performance ============
    performance_rating: Mapped[Optional[Decimal]] = mapped_column(
        SQLDecimal(3, 2),
        nullable=True,
        comment="Performance rating for this period"
    )
    
    # ============ Change Details ============
    reason_for_change: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Reason for assignment change/end"
    )
    
    changed_by: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Admin who made the change"
    )
    
    # ============ Relationships ============
    supervisor: Mapped["Supervisor"] = relationship(
        "Supervisor",
        back_populates="employment_history"
    )
    
    hostel: Mapped["Hostel"] = relationship(
        "Hostel",
        lazy="joined"
    )
    
    # ============ Indexes ============
    __table_args__ = (
        Index("idx_employment_supervisor_dates", "supervisor_id", "start_date", "end_date"),
        Index("idx_employment_hostel_dates", "hostel_id", "start_date", "end_date"),
        Index("idx_employment_current", "supervisor_id", "end_date"),
        {
            "comment": "Supervisor employment history across different assignments"
        }
    )
    
    def __repr__(self) -> str:
        return (
            f"<SupervisorEmployment(supervisor={self.supervisor_id}, "
            f"hostel={self.hostel_id}, period={self.start_date} to {self.end_date})>"
        )
    
    @property
    def duration_days(self) -> int:
        """Calculate duration of this assignment in days."""
        end = self.end_date or Date.today()
        return (end - self.start_date).days
    
    @property
    def is_current(self) -> bool:
        """Check if this is the current assignment."""
        return self.end_date is None


class SupervisorStatusHistory(BaseModel, TimestampModel, UUIDMixin):
    """
    Status change history for supervisors.
    
    Tracks all status transitions with detailed reasons and
    approvals for audit and compliance.
    """
    
    __tablename__ = "supervisor_status_history"
    
    # ============ Relationships ============
    supervisor_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("supervisors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Supervisor reference"
    )
    
    # ============ Status Change Details ============
    previous_status: Mapped[SupervisorStatus] = mapped_column(
        SQLEnum(SupervisorStatus, name="supervisor_status_enum", create_constraint=True),
        nullable=False,
        comment="Previous status"
    )
    
    new_status: Mapped[SupervisorStatus] = mapped_column(
        SQLEnum(SupervisorStatus, name="supervisor_status_enum", create_constraint=True),
        nullable=False,
        index=True,
        comment="New status"
    )
    
    effective_date: Mapped[Date] = mapped_column(
        SQLDate,
        nullable=False,
        index=True,
        comment="Status change effective date"
    )
    
    reason: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Reason for status change"
    )
    
    # ============ Change Metadata ============
    changed_by: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=False,
        comment="Admin who made the change"
    )
    
    changed_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=datetime.utcnow,
        comment="Timestamp of change"
    )
    
    # ============ Additional Details ============
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Additional notes"
    )
    
    # ============ Handover Details ============
    handover_to: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("supervisors.id", ondelete="SET NULL"),
        nullable=True,
        comment="Supervisor ID for responsibility handover"
    )
    
    handover_completed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Handover completion status"
    )
    
    # ============ Relationships ============
    supervisor: Mapped["Supervisor"] = relationship(
        "Supervisor",
        foreign_keys=[supervisor_id],
        back_populates="status_history"
    )
    
    changed_by_user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[changed_by],
        lazy="joined"
    )
    
    # ============ Indexes ============
    __table_args__ = (
        Index("idx_status_history_supervisor_date", "supervisor_id", "effective_date"),
        Index("idx_status_history_new_status", "new_status", "effective_date"),
        {
            "comment": "Supervisor status change audit trail"
        }
    )
    
    def __repr__(self) -> str:
        return (
            f"<SupervisorStatusHistory(supervisor={self.supervisor_id}, "
            f"{self.previous_status.value} → {self.new_status.value}, "
            f"date={self.effective_date})>"
        )


class SupervisorNote(BaseModel, TimestampModel, UUIDMixin):
    """
    Administrative notes for supervisors.
    
    Maintains chronological notes and observations about supervisor
    performance, behavior, and administrative actions.
    """
    
    __tablename__ = "supervisor_notes"
    
    # ============ Relationships ============
    supervisor_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("supervisors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Supervisor reference"
    )
    
    # ============ Note Details ============
    note_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Type: performance, disciplinary, commendation, general"
    )
    
    subject: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Note subject/title"
    )
    
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Detailed note content"
    )
    
    # ============ Visibility and Access ============
    is_confidential: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Confidential note (restricted access)"
    )
    
    is_visible_to_supervisor: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Visible to supervisor"
    )
    
    # ============ Authorship ============
    created_by: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=False,
        comment="Admin who created note"
    )
    
    # ============ Follow-up ============
    requires_follow_up: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Requires follow-up action"
    )
    
    follow_up_date: Mapped[Optional[Date]] = mapped_column(
        SQLDate,
        nullable=True,
        index=True,
        comment="Scheduled follow-up date"
    )
    
    follow_up_completed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Follow-up completed"
    )
    
    # ============ Relationships ============
    supervisor: Mapped["Supervisor"] = relationship(
        "Supervisor",
        back_populates="supervisor_notes"
    )
    
    author: Mapped["User"] = relationship(
        "User",
        foreign_keys=[created_by],
        lazy="joined"
    )
    
    # ============ Indexes ============
    __table_args__ = (
        Index("idx_notes_supervisor_type", "supervisor_id", "note_type"),
        Index("idx_notes_follow_up", "requires_follow_up", "follow_up_date"),
        Index("idx_notes_created", "supervisor_id", "created_at"),
        {
            "comment": "Administrative notes and observations for supervisors"
        }
    )
    
    def __repr__(self) -> str:
        return (
            f"<SupervisorNote(supervisor={self.supervisor_id}, "
            f"type={self.note_type}, subject={self.subject[:30]})>"
        )