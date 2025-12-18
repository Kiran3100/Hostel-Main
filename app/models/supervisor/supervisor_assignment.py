# app/models/supervisor/supervisor_assignment.py
"""
Supervisor assignment and transfer management models.

Handles supervisor-hostel assignments, transfers, and workload
distribution with comprehensive tracking and approval workflows.
"""

from datetime import date as Date, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Boolean, Date as SQLDate, DateTime, ForeignKey,
    Integer, String, Text, Index, JSON
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base.base_model import BaseModel, TimestampModel
from app.models.base.mixins import UUIDMixin

if TYPE_CHECKING:
    from app.models.supervisor.supervisor import Supervisor
    from app.models.hostel.hostel import Hostel
    from app.models.user.user import User

__all__ = [
    "SupervisorAssignment",
    "AssignmentTransfer",
    "AssignmentCoverage",
    "WorkloadMetric",
]


class SupervisorAssignment(BaseModel, TimestampModel, UUIDMixin):
    """
    Supervisor-hostel assignment records.
    
    Tracks assignment lifecycle with permissions, workload,
    and performance metrics per assignment.
    """
    
    __tablename__ = "supervisor_assignments"
    
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
        comment="Assigned hostel"
    )
    
    # ============ Assignment Period ============
    assigned_date: Mapped[Date] = mapped_column(
        SQLDate,
        nullable=False,
        index=True,
        comment="Assignment start date"
    )
    
    effective_from: Mapped[Date] = mapped_column(
        SQLDate,
        nullable=False,
        default=Date.today,
        comment="Effective start date"
    )
    
    effective_to: Mapped[Optional[Date]] = mapped_column(
        SQLDate,
        nullable=True,
        index=True,
        comment="Effective end date (null if current)"
    )
    
    # ============ Assignment Details ============
    is_primary: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Primary hostel assignment"
    )
    
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
        comment="Assignment is currently active"
    )
    
    assignment_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="permanent",
        comment="Type: permanent, temporary, backup, relief"
    )
    
    # ============ Assignment Authority ============
    assigned_by: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=False,
        comment="Admin who assigned"
    )
    
    assignment_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Reason for assignment"
    )
    
    # ============ Workload Configuration ============
    assigned_rooms: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Number of rooms assigned"
    )
    
    assigned_floors: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Assigned floors (e.g., '1,2,3')"
    )
    
    assigned_areas: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="Specific areas/zones assigned"
    )
    
    # ============ Responsibilities ============
    responsibilities: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="Specific responsibilities and duties"
    )
    
    shift_timing: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Shift timing for this assignment"
    )
    
    # ============ Performance Tracking ============
    complaints_handled: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Complaints handled in this assignment"
    )
    
    complaints_resolved: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Complaints resolved"
    )
    
    maintenance_requests: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Maintenance requests created"
    )
    
    attendance_records: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Attendance records created"
    )
    
    # ============ Revocation Details ============
    revoked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
        comment="Revocation timestamp"
    )
    
    revoked_by: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Admin who revoked"
    )
    
    revocation_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Reason for revocation"
    )
    
    # ============ Handover Details ============
    handover_to_supervisor_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("supervisors.id", ondelete="SET NULL"),
        nullable=True,
        comment="Supervisor taking over responsibilities"
    )
    
    handover_completed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Handover completion status"
    )
    
    handover_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Handover instructions and notes"
    )
    
    # ============ Notes ============
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Additional assignment notes"
    )
    
    # ============ Relationships ============
    supervisor: Mapped["Supervisor"] = relationship(
        "Supervisor",
        foreign_keys=[supervisor_id],
        back_populates="assignments",
        lazy="joined"
    )
    
    hostel: Mapped["Hostel"] = relationship(
        "Hostel",
        back_populates="supervisor_assignments",
        lazy="joined"
    )
    
    assigned_by_user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[assigned_by],
        lazy="joined"
    )
    
    revoked_by_user: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[revoked_by],
        lazy="select"
    )
    
    handover_to_supervisor: Mapped[Optional["Supervisor"]] = relationship(
        "Supervisor",
        foreign_keys=[handover_to_supervisor_id],
        lazy="select"
    )
    
    # ============ Indexes ============
    __table_args__ = (
        Index("idx_assignment_supervisor_hostel", "supervisor_id", "hostel_id"),
        Index("idx_assignment_active", "is_active", "is_primary"),
        Index("idx_assignment_dates", "effective_from", "effective_to"),
        Index("idx_assignment_hostel_active", "hostel_id", "is_active"),
        {
            "comment": "Supervisor-hostel assignment tracking"
        }
    )
    
    def __repr__(self) -> str:
        return (
            f"<SupervisorAssignment(supervisor={self.supervisor_id}, "
            f"hostel={self.hostel_id}, active={self.is_active})>"
        )
    
    @property
    def assignment_duration_days(self) -> int:
        """Calculate assignment duration in days."""
        end_date = self.effective_to or Date.today()
        return (end_date - self.effective_from).days
    
    @property
    def is_current(self) -> bool:
        """Check if this is the current active assignment."""
        return self.is_active and self.effective_to is None


class AssignmentTransfer(BaseModel, TimestampModel, UUIDMixin):
    """
    Supervisor transfer records between hostels.
    
    Tracks transfer requests, approvals, and execution with
    handover management and impact assessment.
    """
    
    __tablename__ = "supervisor_assignment_transfers"
    
    # ============ Relationships ============
    supervisor_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("supervisors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Supervisor being transferred"
    )
    
    from_hostel_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("hostels.id", ondelete="CASCADE"),
        nullable=False,
        comment="Current hostel"
    )
    
    to_hostel_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("hostels.id", ondelete="CASCADE"),
        nullable=False,
        comment="New hostel"
    )
    
    # ============ Transfer Details ============
    transfer_date: Mapped[Date] = mapped_column(
        SQLDate,
        nullable=False,
        index=True,
        comment="Transfer effective date"
    )
    
    transfer_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="permanent",
        comment="Type: permanent, temporary, emergency"
    )
    
    reason: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Transfer reason"
    )
    
    # ============ Request Details ============
    requested_by: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=False,
        comment="Who requested transfer"
    )
    
    requested_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        comment="Request timestamp"
    )
    
    # ============ Approval Workflow ============
    approval_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="pending",
        index=True,
        comment="Status: pending, approved, rejected, cancelled"
    )
    
    approved_by: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Admin who approved"
    )
    
    approved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
        comment="Approval timestamp"
    )
    
    rejection_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Rejection reason if rejected"
    )
    
    # ============ Permission Handling ============
    retain_permissions: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Retain same permissions at new hostel"
    )
    
    new_permissions_config: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="New permission configuration if not retaining"
    )
    
    # ============ Handover Management ============
    handover_period_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=7,
        comment="Handover period in days"
    )
    
    handover_to_supervisor_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("supervisors.id", ondelete="SET NULL"),
        nullable=True,
        comment="Supervisor taking over at current hostel"
    )
    
    handover_completed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Handover completion status"
    )
    
    handover_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Handover notes and instructions"
    )
    
    # ============ Execution Details ============
    transfer_completed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Transfer execution completed"
    )
    
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
        comment="Completion timestamp"
    )
    
    completed_by: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Admin who completed transfer"
    )
    
    # ============ Notes ============
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Additional transfer notes"
    )
    
    # ============ Relationships ============
    supervisor: Mapped["Supervisor"] = relationship(
        "Supervisor",
        foreign_keys=[supervisor_id],
        lazy="joined"
    )
    
    from_hostel: Mapped["Hostel"] = relationship(
        "Hostel",
        foreign_keys=[from_hostel_id],
        lazy="joined"
    )
    
    to_hostel: Mapped["Hostel"] = relationship(
        "Hostel",
        foreign_keys=[to_hostel_id],
        lazy="joined"
    )
    
    requested_by_user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[requested_by],
        lazy="joined"
    )
    
    approved_by_user: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[approved_by],
        lazy="select"
    )
    
    # ============ Indexes ============
    __table_args__ = (
        Index("idx_transfer_supervisor", "supervisor_id", "transfer_date"),
        Index("idx_transfer_status", "approval_status", "transfer_date"),
        Index("idx_transfer_hostels", "from_hostel_id", "to_hostel_id"),
        {
            "comment": "Supervisor transfer management and tracking"
        }
    )
    
    def __repr__(self) -> str:
        return (
            f"<AssignmentTransfer(supervisor={self.supervisor_id}, "
            f"{self.from_hostel_id} → {self.to_hostel_id}, "
            f"status={self.approval_status})>"
        )


class AssignmentCoverage(BaseModel, TimestampModel, UUIDMixin):
    """
    Assignment coverage analysis and optimization.
    
    Tracks hostel coverage by supervisors with shift analysis
    and gap identification for optimal staffing.
    """
    
    __tablename__ = "supervisor_assignment_coverage"
    
    # ============ Relationships ============
    hostel_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("hostels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Hostel reference"
    )
    
    # ============ Coverage Period ============
    coverage_date: Mapped[Date] = mapped_column(
        SQLDate,
        nullable=False,
        index=True,
        comment="Coverage date"
    )
    
    shift: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Shift: morning, afternoon, evening, night, 24x7"
    )
    
    # ============ Coverage Metrics ============
    total_supervisors_assigned: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Total supervisors assigned"
    )
    
    supervisors_present: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Supervisors actually present"
    )
    
    supervisors_on_leave: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Supervisors on leave"
    )
    
    coverage_percentage: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=100,
        comment="Coverage percentage"
    )
    
    # ============ Gap Analysis ============
    has_coverage_gap: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Coverage gap identified"
    )
    
    gap_severity: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="Severity: low, medium, high, critical"
    )
    
    gap_details: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Coverage gap details"
    )
    
    # ============ Mitigation ============
    backup_supervisor_assigned: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("supervisors.id", ondelete="SET NULL"),
        nullable=True,
        comment="Backup supervisor if assigned"
    )
    
    mitigation_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Gap mitigation notes"
    )
    
    # ============ Alert Status ============
    alert_sent: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Alert sent for coverage gap"
    )
    
    alert_sent_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
        comment="Alert timestamp"
    )
    
    # ============ Relationships ============
    hostel: Mapped["Hostel"] = relationship(
        "Hostel",
        lazy="joined"
    )
    
    backup_supervisor: Mapped[Optional["Supervisor"]] = relationship(
        "Supervisor",
        lazy="select"
    )
    
    # ============ Indexes ============
    __table_args__ = (
        Index("idx_coverage_hostel_date", "hostel_id", "coverage_date"),
        Index("idx_coverage_gap", "has_coverage_gap", "gap_severity"),
        Index("idx_coverage_shift", "hostel_id", "shift", "coverage_date"),
        {
            "comment": "Supervisor coverage analysis for optimal staffing"
        }
    )
    
    def __repr__(self) -> str:
        return (
            f"<AssignmentCoverage(hostel={self.hostel_id}, "
            f"date={self.coverage_date}, coverage={self.coverage_percentage}%)>"
        )


class WorkloadMetric(BaseModel, TimestampModel, UUIDMixin):
    """
    Supervisor workload tracking and analysis.
    
    Monitors workload distribution and balance across supervisors
    for fair assignment and performance optimization.
    """
    
    __tablename__ = "supervisor_workload_metrics"
    
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
        comment="Hostel reference"
    )
    
    # ============ Measurement Period ============
    measurement_date: Mapped[Date] = mapped_column(
        SQLDate,
        nullable=False,
        index=True,
        comment="Measurement date"
    )
    
    period_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="daily",
        comment="Period: daily, weekly, monthly"
    )
    
    # ============ Task Counts ============
    total_tasks: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Total tasks assigned"
    )
    
    pending_tasks: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Pending tasks"
    )
    
    completed_tasks: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Completed tasks"
    )
    
    overdue_tasks: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Overdue tasks"
    )
    
    # ============ Workload by Category ============
    complaints_assigned: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Complaints assigned"
    )
    
    maintenance_assigned: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Maintenance requests assigned"
    )
    
    leave_approvals_pending: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Leave approvals pending"
    )
    
    attendance_records_due: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Attendance records due"
    )
    
    # ============ Workload Score ============
    workload_score: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Calculated workload score (0-100)"
    )
    
    workload_level: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="normal",
        comment="Level: light, normal, heavy, overloaded"
    )
    
    # ============ Capacity Analysis ============
    estimated_capacity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=100,
        comment="Estimated capacity percentage"
    )
    
    utilization_percentage: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Actual utilization percentage"
    )
    
    # ============ Balance Indicators ============
    is_balanced: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Workload is balanced"
    )
    
    requires_rebalancing: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Requires workload rebalancing"
    )
    
    # ============ Relationships ============
    supervisor: Mapped["Supervisor"] = relationship(
        "Supervisor",
        lazy="joined"
    )
    
    hostel: Mapped["Hostel"] = relationship(
        "Hostel",
        lazy="joined"
    )
    
    # ============ Indexes ============
    __table_args__ = (
        Index("idx_workload_supervisor_date", "supervisor_id", "measurement_date"),
        Index("idx_workload_hostel_date", "hostel_id", "measurement_date"),
        Index("idx_workload_level", "workload_level", "measurement_date"),
        Index("idx_workload_rebalance", "requires_rebalancing", "hostel_id"),
        {
            "comment": "Supervisor workload tracking and balance optimization"
        }
    )
    
    def __repr__(self) -> str:
        return (
            f"<WorkloadMetric(supervisor={self.supervisor_id}, "
            f"date={self.measurement_date}, level={self.workload_level})>"
        )
    
    @property
    def completion_rate(self) -> float:
        """Calculate task completion rate."""
        if self.total_tasks == 0:
            return 100.0
        return (self.completed_tasks / self.total_tasks) * 100