# app/models/supervisor/supervisor_performance.py
"""
Supervisor performance tracking and evaluation models.

Comprehensive performance management with reviews, goals,
metrics, and comparative analysis for supervisor development.
"""

from datetime import date as Date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Boolean, Date as SQLDate, DateTime, Numeric as SQLDecimal,
    ForeignKey, Integer, String, Text, Index, JSON
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base.base_model import BaseModel, TimestampModel
from app.models.base.mixins import UUIDMixin

if TYPE_CHECKING:
    from app.models.supervisor.supervisor import Supervisor
    from app.models.hostel.hostel import Hostel
    from app.models.user.user import User

__all__ = [
    "SupervisorPerformance",
    "PerformanceReview",
    "PerformanceGoal",
    "PerformanceMetric",
    "PeerComparison",
]


class SupervisorPerformance(BaseModel, TimestampModel, UUIDMixin):
    """
    Comprehensive supervisor performance records.
    
    Tracks performance across all key areas with detailed metrics,
    trends, and comparative analysis for evaluation and development.
    """
    
    __tablename__ = "supervisor_performance_records"
    
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
    
    # ============ Performance Period ============
    period_start: Mapped[Date] = mapped_column(
        SQLDate,
        nullable=False,
        index=True,
        comment="Performance period start"
    )
    
    period_end: Mapped[Date] = mapped_column(
        SQLDate,
        nullable=False,
        index=True,
        comment="Performance period end"
    )
    
    period_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="monthly",
        comment="Period: weekly, monthly, quarterly, annual"
    )
    
    # ============ Complaint Handling Metrics ============
    complaints_handled: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Total complaints handled"
    )
    
    complaints_resolved: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Complaints resolved"
    )
    
    complaint_resolution_rate: Mapped[Decimal] = mapped_column(
        SQLDecimal(5, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Resolution rate %"
    )
    
    average_resolution_time_hours: Mapped[Decimal] = mapped_column(
        SQLDecimal(10, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Average resolution time"
    )
    
    sla_compliance_rate: Mapped[Decimal] = mapped_column(
        SQLDecimal(5, 2),
        nullable=False,
        default=Decimal("100.00"),
        comment="SLA compliance %"
    )
    
    first_response_time_minutes: Mapped[Decimal] = mapped_column(
        SQLDecimal(10, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Average first response time"
    )
    
    # ============ Attendance Management Metrics ============
    attendance_records_created: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Attendance records created"
    )
    
    attendance_accuracy: Mapped[Decimal] = mapped_column(
        SQLDecimal(5, 2),
        nullable=False,
        default=Decimal("100.00"),
        comment="Attendance accuracy %"
    )
    
    leaves_approved: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Leave applications approved"
    )
    
    leaves_rejected: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Leave applications rejected"
    )
    
    attendance_punctuality_rate: Mapped[Decimal] = mapped_column(
        SQLDecimal(5, 2),
        nullable=False,
        default=Decimal("100.00"),
        comment="On-time attendance marking %"
    )
    
    # ============ Maintenance Management Metrics ============
    maintenance_requests_created: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Maintenance requests created"
    )
    
    maintenance_completed: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Maintenance completed"
    )
    
    maintenance_completion_rate: Mapped[Decimal] = mapped_column(
        SQLDecimal(5, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Maintenance completion %"
    )
    
    average_maintenance_time_hours: Mapped[Decimal] = mapped_column(
        SQLDecimal(10, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Average completion time"
    )
    
    maintenance_cost_efficiency: Mapped[Decimal] = mapped_column(
        SQLDecimal(5, 2),
        nullable=False,
        default=Decimal("100.00"),
        comment="Cost efficiency %"
    )
    
    # ============ Communication Metrics ============
    announcements_created: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Announcements created"
    )
    
    announcement_reach: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Total students reached"
    )
    
    student_interactions: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Direct student interactions"
    )
    
    # ============ Responsiveness Metrics ============
    average_first_response_time_minutes: Mapped[Decimal] = mapped_column(
        SQLDecimal(10, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Average first response time"
    )
    
    availability_percentage: Mapped[Decimal] = mapped_column(
        SQLDecimal(5, 2),
        nullable=False,
        default=Decimal("100.00"),
        comment="Availability during working hours %"
    )
    
    response_consistency_score: Mapped[Decimal] = mapped_column(
        SQLDecimal(5, 2),
        nullable=False,
        default=Decimal("100.00"),
        comment="Response consistency score"
    )
    
    # ============ Student Satisfaction ============
    student_feedback_score: Mapped[Optional[Decimal]] = mapped_column(
        SQLDecimal(3, 2),
        nullable=True,
        comment="Average student feedback rating (0-5)"
    )
    
    student_feedback_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of feedback responses"
    )
    
    complaint_escalation_rate: Mapped[Decimal] = mapped_column(
        SQLDecimal(5, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Complaint escalation %"
    )
    
    # ============ Overall Performance ============
    overall_performance_score: Mapped[Decimal] = mapped_column(
        SQLDecimal(5, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Overall performance score (0-100)"
    )
    
    performance_grade: Mapped[str] = mapped_column(
        String(5),
        nullable=False,
        default="C",
        comment="Performance grade: A+, A, B+, B, C, D"
    )
    
    # ============ Trends ============
    performance_trend: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="stable",
        comment="Trend: improving, stable, declining"
    )
    
    # ============ Notes ============
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Performance notes"
    )
    
    # ============ Relationships ============
    supervisor: Mapped["Supervisor"] = relationship(
        "Supervisor",
        back_populates="performance_records",
        lazy="joined"
    )
    
    hostel: Mapped["Hostel"] = relationship(
        "Hostel",
        lazy="joined"
    )
    
    # ============ Indexes ============
    __table_args__ = (
        Index("idx_performance_supervisor_period", "supervisor_id", "period_start", "period_end"),
        Index("idx_performance_hostel_period", "hostel_id", "period_start", "period_end"),
        Index("idx_performance_grade", "performance_grade", "period_end"),
        Index("idx_performance_score", "overall_performance_score", "period_end"),
        {
            "comment": "Comprehensive supervisor performance tracking"
        }
    )
    
    def __repr__(self) -> str:
        return (
            f"<SupervisorPerformance(supervisor={self.supervisor_id}, "
            f"period={self.period_type}, grade={self.performance_grade})>"
        )


class PerformanceReview(BaseModel, TimestampModel, UUIDMixin):
    """
    Formal performance reviews by administrators.
    
    Structured performance reviews with ratings, feedback,
    goals, and development plans for supervisor growth.
    """
    
    __tablename__ = "supervisor_performance_reviews"
    
    # ============ Relationships ============
    supervisor_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("supervisors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Supervisor being reviewed"
    )
    
    # ============ Review Period ============
    review_period_start: Mapped[Date] = mapped_column(
        SQLDate,
        nullable=False,
        comment="Review period start"
    )
    
    review_period_end: Mapped[Date] = mapped_column(
        SQLDate,
        nullable=False,
        comment="Review period end"
    )
    
    review_date: Mapped[Date] = mapped_column(
        SQLDate,
        nullable=False,
        index=True,
        comment="Review date"
    )
    
    # ============ Ratings (1-5 scale) ============
    complaint_handling_rating: Mapped[Decimal] = mapped_column(
        SQLDecimal(3, 2),
        nullable=False,
        comment="Complaint handling rating"
    )
    
    attendance_management_rating: Mapped[Decimal] = mapped_column(
        SQLDecimal(3, 2),
        nullable=False,
        comment="Attendance management rating"
    )
    
    maintenance_management_rating: Mapped[Decimal] = mapped_column(
        SQLDecimal(3, 2),
        nullable=False,
        comment="Maintenance management rating"
    )
    
    communication_rating: Mapped[Decimal] = mapped_column(
        SQLDecimal(3, 2),
        nullable=False,
        comment="Communication skills rating"
    )
    
    professionalism_rating: Mapped[Decimal] = mapped_column(
        SQLDecimal(3, 2),
        nullable=False,
        comment="Professionalism rating"
    )
    
    reliability_rating: Mapped[Decimal] = mapped_column(
        SQLDecimal(3, 2),
        nullable=False,
        comment="Reliability rating"
    )
    
    initiative_rating: Mapped[Decimal] = mapped_column(
        SQLDecimal(3, 2),
        nullable=False,
        comment="Initiative rating"
    )
    
    overall_rating: Mapped[Decimal] = mapped_column(
        SQLDecimal(3, 2),
        nullable=False,
        comment="Overall rating"
    )
    
    # ============ Textual Feedback ============
    strengths: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Supervisor strengths"
    )
    
    areas_for_improvement: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Areas to improve"
    )
    
    goals_for_next_period: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Goals for next review period"
    )
    
    admin_comments: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Additional admin comments"
    )
    
    # ============ Action Items ============
    action_items: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="Specific action items"
    )
    
    training_recommendations: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="Training recommendations"
    )
    
    # ============ Review Metadata ============
    reviewed_by: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=False,
        comment="Admin who conducted review"
    )
    
    # ============ Supervisor Acknowledgment ============
    acknowledged: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Supervisor acknowledged review"
    )
    
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
        comment="Acknowledgment timestamp"
    )
    
    supervisor_comments: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Supervisor's response"
    )
    
    # ============ Relationships ============
    supervisor: Mapped["Supervisor"] = relationship(
        "Supervisor",
        lazy="joined"
    )
    
    reviewer: Mapped["User"] = relationship(
        "User",
        foreign_keys=[reviewed_by],
        lazy="joined"
    )
    
    # ============ Indexes ============
    __table_args__ = (
        Index("idx_review_supervisor_date", "supervisor_id", "review_date"),
        Index("idx_review_period", "review_period_start", "review_period_end"),
        Index("idx_review_acknowledged", "acknowledged", "supervisor_id"),
        {
            "comment": "Formal performance reviews for supervisors"
        }
    )
    
    def __repr__(self) -> str:
        return (
            f"<PerformanceReview(supervisor={self.supervisor_id}, "
            f"date={self.review_date}, rating={self.overall_rating})>"
        )


class PerformanceGoal(BaseModel, TimestampModel, UUIDMixin):
    """
    Performance goals for supervisors.
    
    SMART goals with progress tracking, deadlines,
    and achievement measurement for continuous improvement.
    """
    
    __tablename__ = "supervisor_performance_goals"
    
    # ============ Relationships ============
    supervisor_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("supervisors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Supervisor reference"
    )
    
    # ============ Goal Details ============
    goal_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Goal name"
    )
    
    goal_description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Detailed description"
    )
    
    # ============ Measurable Target ============
    metric_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Metric to measure"
    )
    
    target_value: Mapped[Decimal] = mapped_column(
        SQLDecimal(10, 2),
        nullable=False,
        comment="Target value to achieve"
    )
    
    current_value: Mapped[Optional[Decimal]] = mapped_column(
        SQLDecimal(10, 2),
        nullable=True,
        comment="Current baseline value"
    )
    
    # ============ Timeline ============
    start_date: Mapped[Date] = mapped_column(
        SQLDate,
        nullable=False,
        index=True,
        comment="Goal start date"
    )
    
    end_date: Mapped[Date] = mapped_column(
        SQLDate,
        nullable=False,
        index=True,
        comment="Target completion date"
    )
    
    # ============ Goal Configuration ============
    priority: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="medium",
        comment="Priority: low, medium, high, critical"
    )
    
    category: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Goal category"
    )
    
    measurement_frequency: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="weekly",
        comment="Measurement frequency: daily, weekly, monthly"
    )
    
    # ============ Progress Tracking ============
    progress_percentage: Mapped[Decimal] = mapped_column(
        SQLDecimal(5, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Progress percentage (0-100)"
    )
    
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="on_track",
        index=True,
        comment="Status: on_track, at_risk, behind, completed, failed, paused"
    )
    
    last_updated: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        comment="Last progress update"
    )
    
    # ============ Completion ============
    completed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Goal completed"
    )
    
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
        comment="Completion timestamp"
    )
    
    achievement_percentage: Mapped[Optional[Decimal]] = mapped_column(
        SQLDecimal(5, 2),
        nullable=True,
        comment="Final achievement %"
    )
    
    # ============ Notes ============
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Goal notes and updates"
    )
    
    # ============ Relationships ============
    supervisor: Mapped["Supervisor"] = relationship(
        "Supervisor",
        lazy="joined"
    )
    
    # ============ Indexes ============
    __table_args__ = (
        Index("idx_goal_supervisor_status", "supervisor_id", "status"),
        Index("idx_goal_dates", "start_date", "end_date"),
        Index("idx_goal_priority", "priority", "status"),
        {
            "comment": "Performance goals with progress tracking"
        }
    )
    
    def __repr__(self) -> str:
        return (
            f"<PerformanceGoal(supervisor={self.supervisor_id}, "
            f"goal={self.goal_name[:30]}, status={self.status})>"
        )
    
    @property
    def duration_days(self) -> int:
        """Calculate goal duration in days."""
        return (self.end_date - self.start_date).days
    
    @property
    def days_remaining(self) -> int:
        """Calculate days remaining to achieve goal."""
        if self.completed:
            return 0
        remaining = (self.end_date - Date.today()).days
        return max(0, remaining)


class PerformanceMetric(BaseModel, TimestampModel, UUIDMixin):
    """
    Detailed performance metrics over time.
    
    Time-series performance data for trend analysis,
    forecasting, and continuous monitoring.
    """
    
    __tablename__ = "supervisor_performance_metrics"
    
    # ============ Relationships ============
    supervisor_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("supervisors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Supervisor reference"
    )
    
    # ============ Metric Details ============
    metric_date: Mapped[Date] = mapped_column(
        SQLDate,
        nullable=False,
        index=True,
        comment="Metric date"
    )
    
    metric_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Metric name"
    )
    
    metric_value: Mapped[Decimal] = mapped_column(
        SQLDecimal(10, 2),
        nullable=False,
        comment="Metric value"
    )
    
    metric_unit: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="count",
        comment="Metric unit: count, percentage, hours, etc."
    )
    
    # ============ Context ============
    category: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Metric category"
    )
    
    period_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="daily",
        comment="Period: daily, weekly, monthly"
    )
    
    # ============ Comparison ============
    target_value: Mapped[Optional[Decimal]] = mapped_column(
        SQLDecimal(10, 2),
        nullable=True,
        comment="Target value for this metric"
    )
    
    variance: Mapped[Optional[Decimal]] = mapped_column(
        SQLDecimal(10, 2),
        nullable=True,
        comment="Variance from target"
    )
    
    variance_percentage: Mapped[Optional[Decimal]] = mapped_column(
        SQLDecimal(5, 2),
        nullable=True,
        comment="Variance percentage"
    )
    
    # ============ Trend ============
    trend: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="Trend: improving, stable, declining"
    )
    
    # ============ Metadata ============
    metadata: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="Additional metric metadata"
    )
    
    # ============ Relationships ============
    supervisor: Mapped["Supervisor"] = relationship(
        "Supervisor",
        lazy="joined"
    )
    
    # ============ Indexes ============
    __table_args__ = (
        Index("idx_metric_supervisor_date", "supervisor_id", "metric_date"),
        Index("idx_metric_name_date", "metric_name", "metric_date"),
        Index("idx_metric_category", "category", "metric_date"),
        {
            "comment": "Time-series performance metrics for trend analysis"
        }
    )
    
    def __repr__(self) -> str:
        return (
            f"<PerformanceMetric(supervisor={self.supervisor_id}, "
            f"metric={self.metric_name}, value={self.metric_value})>"
        )


class PeerComparison(BaseModel, TimestampModel, UUIDMixin):
    """
    Peer comparison and benchmarking data.
    
    Comparative analysis with peer supervisors for
    performance benchmarking and improvement insights.
    """
    
    __tablename__ = "supervisor_peer_comparisons"
    
    # ============ Relationships ============
    supervisor_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("supervisors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Supervisor reference"
    )
    
    # ============ Comparison Period ============
    comparison_date: Mapped[Date] = mapped_column(
        SQLDate,
        nullable=False,
        index=True,
        comment="Comparison date"
    )
    
    period_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="monthly",
        comment="Period: weekly, monthly, quarterly"
    )
    
    # ============ Ranking ============
    total_supervisors: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Total supervisors in comparison"
    )
    
    rank: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Supervisor's rank (1 = best)"
    )
    
    percentile: Mapped[Decimal] = mapped_column(
        SQLDecimal(5, 2),
        nullable=False,
        comment="Performance percentile (0-100)"
    )
    
    # ============ Scores ============
    supervisor_score: Mapped[Decimal] = mapped_column(
        SQLDecimal(5, 2),
        nullable=False,
        comment="Supervisor's performance score"
    )
    
    peer_average_score: Mapped[Decimal] = mapped_column(
        SQLDecimal(5, 2),
        nullable=False,
        comment="Peer average score"
    )
    
    peer_median_score: Mapped[Decimal] = mapped_column(
        SQLDecimal(5, 2),
        nullable=False,
        comment="Peer median score"
    )
    
    top_performer_score: Mapped[Decimal] = mapped_column(
        SQLDecimal(5, 2),
        nullable=False,
        comment="Top performer score"
    )
    
    # ============ Gaps ============
    gap_to_average: Mapped[Decimal] = mapped_column(
        SQLDecimal(5, 2),
        nullable=False,
        comment="Gap to peer average"
    )
    
    gap_to_top: Mapped[Decimal] = mapped_column(
        SQLDecimal(5, 2),
        nullable=False,
        comment="Gap to top performer"
    )
    
    # ============ Metric Comparisons ============
    metric_comparisons: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
        comment="Individual metric comparisons"
    )
    
    # ============ Performance Tier ============
    performance_tier: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Tier: top_performer, high_performer, average, below_average"
    )
    
    # ============ Relationships ============
    supervisor: Mapped["Supervisor"] = relationship(
        "Supervisor",
        lazy="joined"
    )
    
    # ============ Indexes ============
    __table_args__ = (
        Index("idx_comparison_supervisor_date", "supervisor_id", "comparison_date"),
        Index("idx_comparison_rank", "rank", "total_supervisors"),
        Index("idx_comparison_tier", "performance_tier", "comparison_date"),
        {
            "comment": "Peer comparison and benchmarking for supervisors"
        }
    )
    
    def __repr__(self) -> str:
        return (
            f"<PeerComparison(supervisor={self.supervisor_id}, "
            f"rank={self.rank}/{self.total_supervisors}, tier={self.performance_tier})>"
        )