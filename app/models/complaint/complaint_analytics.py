"""
Complaint analytics and aggregation model.

Handles pre-computed analytics, metrics, and insights for complaint
management performance monitoring and reporting.
"""

from datetime import date as Date
from datetime import datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    CheckConstraint,
    Date as SQLDate,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base.base_model import BaseModel
from app.models.base.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.hostel.hostel import Hostel
    from app.models.user.user import User

__all__ = [
    "ComplaintAnalyticSnapshot",
    "ComplaintCategoryMetric",
    "ComplaintStaffPerformance",
]


class ComplaintAnalyticSnapshot(BaseModel, TimestampMixin):
    """
    Pre-computed complaint analytics snapshot.
    
    Stores aggregated metrics for specific time periods to optimize
    dashboard and reporting performance.
    
    Attributes:
        hostel_id: Hostel identifier (NULL for system-wide)
        period_start: Analytics period start date
        period_end: Analytics period end date
        snapshot_type: Snapshot type (DAILY, WEEKLY, MONTHLY, QUARTERLY)
        
        total_complaints: Total complaint count
        open_complaints: Open complaints count
        in_progress_complaints: In-progress complaints count
        resolved_complaints: Resolved complaints count
        closed_complaints: Closed complaints count
        
        avg_resolution_time_hours: Average resolution time
        median_resolution_time_hours: Median resolution time
        min_resolution_time_hours: Minimum resolution time
        max_resolution_time_hours: Maximum resolution time
        
        sla_compliant_count: SLA compliant complaints
        sla_breached_count: SLA breached complaints
        sla_compliance_rate: SLA compliance percentage
        
        escalated_count: Escalated complaints
        reopened_count: Reopened complaints
        
        avg_rating: Average student rating
        total_feedback_count: Total feedback received
        
        category_breakdown: Complaints by category (JSONB)
        priority_breakdown: Complaints by priority (JSONB)
        status_breakdown: Complaints by status (JSONB)
        
        analytics_metadata: Additional analytics analytics_metadata
    """

    __tablename__ = "complaint_analytic_snapshots"
    __table_args__ = (
        # Indexes
        Index("ix_complaint_analytics_hostel_period", "hostel_id", "period_start", "period_end"),
        Index("ix_complaint_analytics_snapshot_type", "snapshot_type"),
        Index("ix_complaint_analytics_period_start", "period_start"),
        
        # Unique constraint for snapshot
        Index(
            "ix_complaint_analytics_unique_snapshot",
            "hostel_id",
            "period_start",
            "period_end",
            "snapshot_type",
            unique=True,
        ),
        
        # Check constraints
        CheckConstraint(
            "period_end >= period_start",
            name="check_period_valid",
        ),
        CheckConstraint(
            "total_complaints >= 0",
            name="check_total_complaints_positive",
        ),
        CheckConstraint(
            "avg_resolution_time_hours IS NULL OR avg_resolution_time_hours >= 0",
            name="check_avg_resolution_time_positive",
        ),
        CheckConstraint(
            "sla_compliance_rate IS NULL OR (sla_compliance_rate >= 0 AND sla_compliance_rate <= 100)",
            name="check_sla_compliance_rate_range",
        ),
        CheckConstraint(
            "avg_rating IS NULL OR (avg_rating >= 0 AND avg_rating <= 5)",
            name="check_avg_rating_range",
        ),
        
        {"comment": "Pre-computed complaint analytics snapshots"},
    )

    # Scope
    hostel_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("hostels.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment="Hostel identifier (NULL for system-wide analytics)",
    )

    # Period
    period_start: Mapped[Date] = mapped_column(
        SQLDate,
        nullable=False,
        index=True,
        comment="Analytics period start date",
    )
    
    period_end: Mapped[Date] = mapped_column(
        SQLDate,
        nullable=False,
        comment="Analytics period end date",
    )
    
    snapshot_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
        comment="Snapshot type: DAILY, WEEKLY, MONTHLY, QUARTERLY, YEARLY",
    )

    # Summary Counts
    total_complaints: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Total complaint count in period",
    )
    
    open_complaints: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Open complaints count",
    )
    
    in_progress_complaints: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="In-progress complaints count",
    )
    
    resolved_complaints: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Resolved complaints count",
    )
    
    closed_complaints: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Closed complaints count",
    )

    # Resolution Time Metrics
    avg_resolution_time_hours: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="Average resolution time in hours",
    )
    
    median_resolution_time_hours: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="Median resolution time in hours",
    )
    
    min_resolution_time_hours: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="Minimum resolution time in hours",
    )
    
    max_resolution_time_hours: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="Maximum resolution time in hours",
    )

    # SLA Metrics
    sla_compliant_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="SLA compliant complaints count",
    )
    
    sla_breached_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="SLA breached complaints count",
    )
    
    sla_compliance_rate: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
        comment="SLA compliance rate percentage (0-100)",
    )

    # Additional Metrics
    escalated_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Escalated complaints count",
    )
    
    reopened_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Reopened complaints count",
    )

    # Feedback Metrics
    avg_rating: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(3, 2),
        nullable=True,
        comment="Average student rating (1-5)",
    )
    
    total_feedback_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Total feedback received count",
    )

    # Breakdown Data (JSONB)
    category_breakdown: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
        comment="Complaints count by category",
    )
    
    priority_breakdown: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
        comment="Complaints count by priority",
    )
    
    status_breakdown: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
        comment="Complaints count by status",
    )

    # analytics_metadata
    analytics_metadata: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
        comment="Additional analytics analytics_metadata and trend data",
    )

    # Snapshot Generation
    generated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        comment="Snapshot generation timestamp",
    )

    # Relationships
    hostel: Mapped[Optional["Hostel"]] = relationship(
        "Hostel",
        lazy="joined",
    )

    def __repr__(self) -> str:
        """String representation of ComplaintAnalyticSnapshot."""
        return (
            f"<ComplaintAnalyticSnapshot(id={self.id}, "
            f"hostel_id={self.hostel_id}, "
            f"type={self.snapshot_type}, "
            f"period={self.period_start} to {self.period_end})>"
        )

    @property
    def resolution_rate(self) -> Optional[Decimal]:
        """Calculate resolution rate percentage."""
        if self.total_complaints == 0:
            return None
        return Decimal(self.resolved_complaints / self.total_complaints * 100).quantize(Decimal("0.01"))


class ComplaintCategoryMetric(BaseModel, TimestampMixin):
    """
    Category-wise complaint metrics.
    
    Tracks detailed performance metrics for each complaint category.
    
    Attributes:
        hostel_id: Hostel identifier
        category: Complaint category
        period_start: Metrics period start
        period_end: Metrics period end
        
        total_complaints: Total complaints in category
        open_complaints: Open complaints
        resolved_complaints: Resolved complaints
        
        avg_resolution_time_hours: Average resolution time
        resolution_rate: Resolution rate percentage
        
        avg_rating: Average rating for category
        
        most_common_sub_category: Most frequent sub-category
        
        analytics_metadata: Additional category-specific metrics
    """

    __tablename__ = "complaint_category_metrics"
    __table_args__ = (
        # Indexes
        Index("ix_complaint_category_metrics_hostel_category", "hostel_id", "category"),
        Index("ix_complaint_category_metrics_period", "period_start", "period_end"),
        
        # Unique constraint
        Index(
            "ix_complaint_category_metrics_unique",
            "hostel_id",
            "category",
            "period_start",
            "period_end",
            unique=True,
        ),
        
        # Check constraints
        CheckConstraint(
            "period_end >= period_start",
            name="check_period_valid",
        ),
        CheckConstraint(
            "total_complaints >= 0",
            name="check_total_complaints_positive",
        ),
        CheckConstraint(
            "resolution_rate IS NULL OR (resolution_rate >= 0 AND resolution_rate <= 100)",
            name="check_resolution_rate_range",
        ),
        
        {"comment": "Category-wise complaint performance metrics"},
    )

    # Scope
    hostel_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("hostels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Hostel identifier",
    )
    
    category: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Complaint category",
    )

    # Period
    period_start: Mapped[Date] = mapped_column(
        SQLDate,
        nullable=False,
        comment="Metrics period start date",
    )
    
    period_end: Mapped[Date] = mapped_column(
        SQLDate,
        nullable=False,
        comment="Metrics period end date",
    )

    # Metrics
    total_complaints: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Total complaints in category",
    )
    
    open_complaints: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Open complaints count",
    )
    
    resolved_complaints: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Resolved complaints count",
    )
    
    avg_resolution_time_hours: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="Average resolution time in hours",
    )
    
    resolution_rate: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
        comment="Resolution rate percentage",
    )
    
    avg_rating: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(3, 2),
        nullable=True,
        comment="Average rating for category",
    )
    
    most_common_sub_category: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Most frequent sub-category",
    )

    # analytics_metadata
    analytics_metadata: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
        comment="Additional category-specific metrics",
    )

    # Relationships
    hostel: Mapped["Hostel"] = relationship(
        "Hostel",
        lazy="joined",
    )

    def __repr__(self) -> str:
        """String representation of ComplaintCategoryMetric."""
        return (
            f"<ComplaintCategoryMetric(id={self.id}, "
            f"category={self.category}, "
            f"total={self.total_complaints})>"
        )


class ComplaintStaffPerformance(BaseModel, TimestampMixin):
    """
    Staff performance metrics for complaint handling.
    
    Tracks individual staff member performance in complaint resolution.
    
    Attributes:
        staff_id: Staff member user ID
        hostel_id: Hostel identifier
        period_start: Performance period start
        period_end: Performance period end
        
        complaints_assigned: Total complaints assigned
        complaints_resolved: Total complaints resolved
        complaints_pending: Currently pending complaints
        
        avg_resolution_time_hours: Average resolution time
        resolution_rate: Resolution rate percentage
        
        avg_rating: Average feedback rating
        total_feedback_count: Total feedback received
        
        escalation_count: Number of escalations
        reopened_count: Number of reopened complaints
        
        workload_score: Current workload score
        performance_score: Overall performance score
        
        analytics_metadata: Additional performance metrics
    """

    __tablename__ = "complaint_staff_performance"
    __table_args__ = (
        # Indexes
        Index("ix_complaint_staff_performance_staff_hostel", "staff_id", "hostel_id"),
        Index("ix_complaint_staff_performance_period", "period_start", "period_end"),
        Index("ix_complaint_staff_performance_score", "performance_score"),
        
        # Unique constraint
        Index(
            "ix_complaint_staff_performance_unique",
            "staff_id",
            "hostel_id",
            "period_start",
            "period_end",
            unique=True,
        ),
        
        # Check constraints
        CheckConstraint(
            "period_end >= period_start",
            name="check_period_valid",
        ),
        CheckConstraint(
            "complaints_assigned >= 0",
            name="check_complaints_assigned_positive",
        ),
        CheckConstraint(
            "resolution_rate IS NULL OR (resolution_rate >= 0 AND resolution_rate <= 100)",
            name="check_resolution_rate_range",
        ),
        CheckConstraint(
            "performance_score IS NULL OR (performance_score >= 0 AND performance_score <= 100)",
            name="check_performance_score_range",
        ),
        
        {"comment": "Staff performance metrics for complaint handling"},
    )

    # Scope
    staff_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Staff member user ID",
    )
    
    hostel_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("hostels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Hostel identifier",
    )

    # Period
    period_start: Mapped[Date] = mapped_column(
        SQLDate,
        nullable=False,
        comment="Performance period start date",
    )
    
    period_end: Mapped[Date] = mapped_column(
        SQLDate,
        nullable=False,
        comment="Performance period end date",
    )

    # Assignment Metrics
    complaints_assigned: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Total complaints assigned",
    )
    
    complaints_resolved: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Total complaints resolved",
    )
    
    complaints_pending: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Currently pending complaints",
    )

    # Performance Metrics
    avg_resolution_time_hours: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="Average resolution time in hours",
    )
    
    resolution_rate: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
        comment="Resolution rate percentage",
    )

    # Feedback Metrics
    avg_rating: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(3, 2),
        nullable=True,
        comment="Average feedback rating (1-5)",
    )
    
    total_feedback_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Total feedback received",
    )

    # Quality Metrics
    escalation_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of escalations from assigned complaints",
    )
    
    reopened_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of reopened complaints",
    )

    # Overall Scores
    workload_score: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Current workload score",
    )
    
    performance_score: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
        index=True,
        comment="Overall performance score (0-100)",
    )

    # analytics_metadata
    analytics_metadata: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
        comment="Additional performance metrics and insights",
    )

    # Relationships
    staff_member: Mapped["User"] = relationship(
        "User",
        foreign_keys=[staff_id],
        lazy="joined",
    )
    
    hostel: Mapped["Hostel"] = relationship(
        "Hostel",
        lazy="joined",
    )

    def __repr__(self) -> str:
        """String representation of ComplaintStaffPerformance."""
        return (
            f"<ComplaintStaffPerformance(id={self.id}, "
            f"staff_id={self.staff_id}, "
            f"performance_score={self.performance_score})>"
        )

    @property
    def efficiency_rating(self) -> Optional[str]:
        """Calculate efficiency rating based on resolution time."""
        if not self.avg_resolution_time_hours:
            return None
        
        hours = float(self.avg_resolution_time_hours)
        
        if hours <= 6:
            return "EXCELLENT"
        elif hours <= 12:
            return "GOOD"
        elif hours <= 24:
            return "AVERAGE"
        else:
            return "NEEDS_IMPROVEMENT"