# app/models/supervisor/supervisor_activity.py
"""
Supervisor activity tracking and audit log models.

Comprehensive activity logging with performance metrics,
session tracking, and analytics for supervisor monitoring.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Boolean, DateTime, ForeignKey, Integer,
    String, Text, Index, JSON
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base.base_model import BaseModel, TimestampModel
from app.models.base.mixins import UUIDMixin

if TYPE_CHECKING:
    from app.models.supervisor.supervisor import Supervisor
    from app.models.hostel.hostel import Hostel
    from app.models.user.user import User

__all__ = [
    "SupervisorActivity",
    "SupervisorSession",
    "ActivitySummary",
    "ActivityMetric",
]


class SupervisorActivity(BaseModel, TimestampModel, UUIDMixin):
    """
    Detailed supervisor activity logging.
    
    Tracks all supervisor actions with context, performance data,
    and comprehensive metadata for audit and analytics.
    """
    
    __tablename__ = "supervisor_activities"
    
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
    
    # ============ Activity Details ============
    action_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Specific action performed"
    )
    
    action_category: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Action category for grouping"
    )
    
    action_description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Human-readable description"
    )
    
    # ============ Entity Affected ============
    entity_type: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        index=True,
        comment="Type of entity affected"
    )
    
    entity_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        nullable=True,
        index=True,
        comment="ID of affected entity"
    )
    
    entity_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Name/title of affected entity"
    )
    
    # ============ Context and Metadata ============
    metadata: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="Additional action details and context"
    )
    
    # ============ Technical Details ============
    ip_address: Mapped[Optional[str]] = mapped_column(
        String(45),
        nullable=True,
        comment="IP address of action origin"
    )
    
    user_agent: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="User agent string"
    )
    
    device_type: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="Device type: mobile, desktop, tablet"
    )
    
    device_info: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="Detailed device information"
    )
    
    # ============ Performance Tracking ============
    response_time_ms: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Action response time in milliseconds"
    )
    
    success: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
        comment="Whether action completed successfully"
    )
    
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Error message if action failed"
    )
    
    error_code: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Error code if action failed"
    )
    
    # ============ Impact Assessment ============
    impact_level: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="Impact level: low, medium, high, critical"
    )
    
    affected_users_count: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Number of users affected by action"
    )
    
    # ============ Session Tracking ============
    session_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        index=True,
        comment="User session identifier"
    )
    
    # ============ Relationships ============
    supervisor: Mapped["Supervisor"] = relationship(
        "Supervisor",
        back_populates="activities",
        lazy="joined"
    )
    
    hostel: Mapped["Hostel"] = relationship(
        "Hostel",
        lazy="joined"
    )
    
    # ============ Indexes ============
    __table_args__ = (
        Index("idx_activity_supervisor_created", "supervisor_id", "created_at"),
        Index("idx_activity_action_type", "action_type", "created_at"),
        Index("idx_activity_category", "action_category", "created_at"),
        Index("idx_activity_entity", "entity_type", "entity_id"),
        Index("idx_activity_success", "success", "created_at"),
        Index("idx_activity_session", "session_id", "created_at"),
        Index("idx_activity_hostel_created", "hostel_id", "created_at"),
        {
            "comment": "Comprehensive supervisor activity tracking and audit log"
        }
    )
    
    def __repr__(self) -> str:
        return (
            f"<SupervisorActivity(supervisor={self.supervisor_id}, "
            f"action={self.action_type}, success={self.success})>"
        )


class SupervisorSession(BaseModel, TimestampModel, UUIDMixin):
    """
    Supervisor login session tracking.
    
    Manages active sessions with security monitoring,
    device fingerprinting, and activity correlation.
    """
    
    __tablename__ = "supervisor_sessions"
    
    # ============ Relationships ============
    supervisor_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("supervisors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Supervisor reference"
    )
    
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="User reference"
    )
    
    # ============ Session Details ============
    session_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
        comment="Unique session identifier"
    )
    
    session_token: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Session token (hashed)"
    )
    
    # ============ Login Details ============
    login_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        index=True,
        comment="Login timestamp"
    )
    
    logout_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
        comment="Logout timestamp"
    )
    
    last_activity: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        index=True,
        comment="Last activity timestamp"
    )
    
    # ============ Device Information ============
    ip_address: Mapped[str] = mapped_column(
        String(45),
        nullable=False,
        comment="Login IP address"
    )
    
    user_agent: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="User agent string"
    )
    
    device_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="desktop",
        comment="Device type: mobile, desktop, tablet"
    )
    
    device_info: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="Detailed device information"
    )
    
    device_fingerprint: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Device fingerprint hash"
    )
    
    # ============ Location Information ============
    location: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Geographic location"
    )
    
    country: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Country"
    )
    
    city: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="City"
    )
    
    # ============ Session Status ============
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
        comment="Session is currently active"
    )
    
    logout_reason: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Logout reason: manual, timeout, forced, expired"
    )
    
    # ============ Activity Metrics ============
    actions_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of actions in session"
    )
    
    pages_visited: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of pages visited"
    )
    
    # ============ Security Flags ============
    is_suspicious: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Suspicious activity detected"
    )
    
    security_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Security-related notes"
    )
    
    # ============ Relationships ============
    supervisor: Mapped["Supervisor"] = relationship(
        "Supervisor",
        lazy="joined"
    )
    
    user: Mapped["User"] = relationship(
        "User",
        lazy="joined"
    )
    
    # ============ Indexes ============
    __table_args__ = (
        Index("idx_session_supervisor_login", "supervisor_id", "login_at"),
        Index("idx_session_active", "is_active", "last_activity"),
        Index("idx_session_token", "session_token"),
        Index("idx_session_suspicious", "is_suspicious", "supervisor_id"),
        {
            "comment": "Supervisor session tracking and security monitoring"
        }
    )
    
    def __repr__(self) -> str:
        return (
            f"<SupervisorSession(supervisor={self.supervisor_id}, "
            f"active={self.is_active}, login={self.login_at})>"
        )
    
    @property
    def session_duration_minutes(self) -> Optional[int]:
        """Calculate session duration in minutes."""
        if not self.logout_at:
            # Session still active
            duration = (datetime.utcnow() - self.login_at).total_seconds()
        else:
            duration = (self.logout_at - self.login_at).total_seconds()
        
        return int(duration / 60)


class ActivitySummary(BaseModel, TimestampModel, UUIDMixin):
    """
    Aggregated activity summary for supervisors.
    
    Pre-calculated activity summaries for efficient dashboard
    and reporting with periodic aggregation.
    """
    
    __tablename__ = "supervisor_activity_summaries"
    
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
    
    # ============ Summary Period ============
    period_start: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        index=True,
        comment="Period start timestamp"
    )
    
    period_end: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        index=True,
        comment="Period end timestamp"
    )
    
    period_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="daily",
        comment="Period type: hourly, daily, weekly, monthly"
    )
    
    # ============ Activity Counts ============
    total_actions: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Total actions performed"
    )
    
    successful_actions: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Successful actions"
    )
    
    failed_actions: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Failed actions"
    )
    
    unique_action_types: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of unique action types"
    )
    
    # ============ Category Breakdown ============
    actions_by_category: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
        comment="Action count by category"
    )
    
    actions_by_type: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
        comment="Action count by specific type"
    )
    
    # ============ Performance Metrics ============
    average_response_time_ms: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Average response time"
    )
    
    success_rate: Mapped[float] = mapped_column(
        nullable=False,
        default=100.0,
        comment="Success rate percentage"
    )
    
    # ============ Activity Patterns ============
    peak_hour: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Hour with most activity (0-23)"
    )
    
    most_common_action: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Most frequently performed action"
    )
    
    # ============ Session Info ============
    sessions_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of sessions"
    )
    
    total_session_time_minutes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Total session time in minutes"
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
        Index("idx_summary_supervisor_period", "supervisor_id", "period_start", "period_end"),
        Index("idx_summary_hostel_period", "hostel_id", "period_start", "period_end"),
        Index("idx_summary_period_type", "period_type", "period_start"),
        {
            "comment": "Aggregated supervisor activity summaries for reporting"
        }
    )
    
    def __repr__(self) -> str:
        return (
            f"<ActivitySummary(supervisor={self.supervisor_id}, "
            f"period={self.period_type}, actions={self.total_actions})>"
        )


class ActivityMetric(BaseModel, TimestampModel, UUIDMixin):
    """
    Detailed activity performance metrics.
    
    Tracks KPIs and performance indicators for supervisor
    activity analysis and optimization.
    """
    
    __tablename__ = "supervisor_activity_metrics"
    
    # ============ Relationships ============
    supervisor_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("supervisors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Supervisor reference"
    )
    
    # ============ Metric Period ============
    metric_date: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        index=True,
        comment="Metric calculation date"
    )
    
    period_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="daily",
        comment="Period: daily, weekly, monthly"
    )
    
    # ============ Volume Metrics ============
    total_actions: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Total actions in period"
    )
    
    unique_action_types: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Unique action types"
    )
    
    active_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Days with activity"
    )
    
    # ============ Performance Metrics ============
    overall_success_rate: Mapped[float] = mapped_column(
        nullable=False,
        default=100.0,
        comment="Overall success rate %"
    )
    
    average_response_time_ms: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Average response time"
    )
    
    response_time_trend: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="Trend: improving, stable, declining"
    )
    
    # ============ Efficiency Metrics ============
    actions_per_day: Mapped[float] = mapped_column(
        nullable=False,
        default=0.0,
        comment="Average actions per active day"
    )
    
    actions_per_session: Mapped[float] = mapped_column(
        nullable=False,
        default=0.0,
        comment="Average actions per session"
    )
    
    # ============ Peak Activity Analysis ============
    peak_hour: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Hour with most activity (0-23)"
    )
    
    peak_day_of_week: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Day with most activity (0=Monday)"
    )
    
    # ============ Category Distribution ============
    actions_by_category: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
        comment="Action count by category"
    )
    
    # ============ Activity Score ============
    activity_score: Mapped[float] = mapped_column(
        nullable=False,
        default=0.0,
        comment="Calculated activity score (0-100)"
    )
    
    productivity_level: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="average",
        comment="Productivity: excellent, good, average, poor"
    )
    
    # ============ Relationships ============
    supervisor: Mapped["Supervisor"] = relationship(
        "Supervisor",
        lazy="joined"
    )
    
    # ============ Indexes ============
    __table_args__ = (
        Index("idx_metric_supervisor_date", "supervisor_id", "metric_date"),
        Index("idx_metric_period_type", "period_type", "metric_date"),
        Index("idx_metric_productivity", "productivity_level", "metric_date"),
        {
            "comment": "Supervisor activity performance metrics and KPIs"
        }
    )
    
    def __repr__(self) -> str:
        return (
            f"<ActivityMetric(supervisor={self.supervisor_id}, "
            f"date={self.metric_date}, score={self.activity_score})>"
        )