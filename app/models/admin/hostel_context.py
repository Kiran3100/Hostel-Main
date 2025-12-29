"""
Hostel Context Model

Manages hostel context switching and session tracking for multi-hostel admins.
Provides comprehensive session management, context history, and user experience
optimization for seamless multi-hostel administration.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional
from uuid import UUID

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Integer,
    String,
    ForeignKey,
    Text,
    Numeric,
    Index,
    CheckConstraint,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.ext.hybrid import hybrid_property

from app.models.base.base_model import TimestampModel
from app.models.base.mixins import UUIDMixin

if TYPE_CHECKING:
    from app.models.admin.admin_user import AdminUser
    from app.models.hostel.hostel import Hostel

__all__ = [
    "HostelContext",
    "ContextSwitch",
    "ContextPreference",
    "ContextSnapshot",
]


class HostelContext(TimestampModel, UUIDMixin):
    """
    Current hostel context for multi-hostel admin.
    
    Maintains the active hostel session for admins managing multiple hostels,
    with comprehensive session tracking, quick stats, and context metadata.
    
    Features:
        - Active hostel tracking
        - Session duration monitoring
        - Quick stats caching
        - Context preferences
        - Auto-expiration
    """
    
    __tablename__ = "hostel_contexts"
    __table_args__ = (
        UniqueConstraint("admin_id", "is_active", name="uq_admin_active_context"),
        Index("idx_context_admin_id", "admin_id"),
        Index("idx_context_hostel_id", "active_hostel_id"),
        Index("idx_context_active", "is_active"),
        Index("idx_context_started", "context_started_at"),
        Index("idx_context_expires", "expires_at"),
    )
    
    # Foreign Keys
    admin_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("admin_users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Admin user ID"
    )
    
    active_hostel_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("hostels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Currently active hostel"
    )
    
    # Session Tracking
    context_started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        index=True,
        comment="When context session started"
    )
    
    last_accessed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        index=True,
        comment="Last activity in this context"
    )
    
    session_duration_minutes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Total session duration (minutes)"
    )
    
    # Context Status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
        comment="Context is currently active"
    )
    
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="Context expiration timestamp"
    )
    
    # Previous Context
    previous_hostel_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("hostels.id", ondelete="SET NULL"),
        nullable=True,
        comment="Previously active hostel"
    )
    
    switch_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of context switches in this session"
    )
    
    # Quick Statistics (Cached)
    total_students: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Total students in active hostel"
    )
    
    active_students: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Active students in hostel"
    )
    
    occupancy_percentage: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Current occupancy rate"
    )
    
    pending_tasks: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Pending tasks count"
    )
    
    urgent_alerts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Urgent alerts count"
    )
    
    unread_notifications: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Unread notifications count"
    )
    
    # Financial Snapshot
    revenue_this_month: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Revenue for current month"
    )
    
    outstanding_payments: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Outstanding payments"
    )
    
    # Activity Metrics
    actions_performed: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Actions performed in this context session"
    )
    
    decisions_made: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Decisions made in this session"
    )
    
    # Context Metadata
    context_data: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        default=dict,
        comment="Additional context data and state"
    )
    
    ui_state: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        default=dict,
        comment="UI state for session restoration"
    )
    
    # Device and Location
    device_type: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Device type (desktop, mobile, tablet)"
    )
    
    device_info: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Detailed device information"
    )
    
    ip_address: Mapped[Optional[str]] = mapped_column(
        String(45),
        nullable=True,
        comment="IP address of session"
    )
    
    # Stats Update
    stats_last_updated: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When cached stats were last updated"
    )
    
    # Relationships
    admin: Mapped["AdminUser"] = relationship(
        "AdminUser",
        back_populates="contexts",
        lazy="select",
        foreign_keys=[admin_id]
    )
    
    active_hostel: Mapped["Hostel"] = relationship(
        "Hostel",
        lazy="select",
        foreign_keys=[active_hostel_id]
    )
    
    previous_hostel: Mapped[Optional["Hostel"]] = relationship(
        "Hostel",
        lazy="select",
        foreign_keys=[previous_hostel_id]
    )
    

    context_switches: Mapped[List["ContextSwitch"]] = relationship(
        "ContextSwitch",
        back_populates="context",
        lazy="select",
        cascade="all, delete-orphan",
        order_by="ContextSwitch.switched_at.desc()"
    )
    
    preferences: Mapped[Optional["ContextPreference"]] = relationship(
        "ContextPreference",
        back_populates="context",
        lazy="select",
        uselist=False,
        cascade="all, delete-orphan"
    )
    
    # Hybrid Properties
    @hybrid_property
    def is_expired(self) -> bool:
        """Check if context has expired."""
        if not self.expires_at:
            return False
        return datetime.utcnow() > self.expires_at
    
    @hybrid_property
    def is_stale(self) -> bool:
        """Check if context is stale (no activity for 30+ minutes)."""
        inactive_duration = datetime.utcnow() - self.last_accessed_at
        return inactive_duration > timedelta(minutes=30)
    
    @hybrid_property
    def session_duration_hours(self) -> Decimal:
        """Calculate session duration in hours."""
        return Decimal(self.session_duration_minutes) / Decimal("60")
    
    @hybrid_property
    def requires_attention(self) -> bool:
        """Check if hostel requires immediate attention."""
        return (
            self.urgent_alerts > 0 or
            self.pending_tasks > 20 or
            self.occupancy_percentage < Decimal("50.00") or
            self.outstanding_payments > self.revenue_this_month
        )
    
    @hybrid_property
    def stats_are_fresh(self) -> bool:
        """Check if cached stats are fresh (< 5 minutes old)."""
        if not self.stats_last_updated:
            return False
        age = datetime.utcnow() - self.stats_last_updated
        return age < timedelta(minutes=5)
    
 
    def update_activity(self) -> None:
        """Update last accessed timestamp and session duration."""
        now = datetime.utcnow()
        duration_delta = now - self.last_accessed_at
        self.session_duration_minutes += int(duration_delta.total_seconds() / 60)
        self.last_accessed_at = now
    

    def refresh_stats(self, stats_dict: dict) -> None:
        """Refresh cached statistics from provided dictionary."""
        self.total_students = stats_dict.get("total_students", 0)
        self.active_students = stats_dict.get("active_students", 0)
        self.occupancy_percentage = Decimal(str(stats_dict.get("occupancy_percentage", 0)))
        self.pending_tasks = stats_dict.get("pending_tasks", 0)
        self.urgent_alerts = stats_dict.get("urgent_alerts", 0)
        self.unread_notifications = stats_dict.get("unread_notifications", 0)
        self.revenue_this_month = Decimal(str(stats_dict.get("revenue_this_month", 0)))
        self.outstanding_payments = Decimal(str(stats_dict.get("outstanding_payments", 0)))
        self.stats_last_updated = datetime.utcnow()
    
    def __repr__(self) -> str:
        return (
            f"<HostelContext(id={self.id}, admin_id={self.admin_id}, "
            f"hostel_id={self.active_hostel_id}, active={self.is_active})>"
        )


class ContextSwitch(TimestampModel, UUIDMixin):
    """
    Individual context switch record with comprehensive tracking.
    
    Records each hostel context switch with timing, reason, session metrics,
    and navigation context for analytics and audit purposes.
    """
    
    __tablename__ = "context_switches"
    __table_args__ = (
        Index("idx_switch_context_id", "context_id"),
        Index("idx_switch_admin_id", "admin_id"),
        Index("idx_switch_timestamp", "switched_at"),
        Index("idx_switch_from_hostel", "from_hostel_id"),
        Index("idx_switch_to_hostel", "to_hostel_id"),
    )
    
    # Foreign Keys
    context_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("hostel_contexts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Parent context ID"
    )
    
    admin_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("admin_users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Admin who performed the switch"
    )
    
    # Switch Details
    from_hostel_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("hostels.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Source hostel (NULL for initial context)"
    )
    
    to_hostel_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("hostels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Destination hostel"
    )
    
    # Timing
    switched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        index=True,
        comment="Switch timestamp"
    )
    
    session_duration_minutes: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Duration in previous hostel (minutes)"
    )
    
    # Switch Context
    switch_reason: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True,
        comment="Reason for switch"
    )
    
    triggered_by: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="manual",
        index=True,
        comment="Trigger type (manual, automatic, notification, alert)"
    )
    
    # Activity Metrics
    actions_performed: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Actions in previous session"
    )
    
    decisions_made: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Decisions in previous session"
    )
    
    # Navigation Context
    source_page: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="Page where switch was initiated"
    )
    
    destination_page: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="Landing page after switch"
    )
    
    # Device and Location
    device_type: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Device type"
    )
    
    ip_address: Mapped[Optional[str]] = mapped_column(
        String(45),
        nullable=True,
        comment="IP address"
    )
    
    # Metadata
    context_metadata: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Additional switch metadata"
    )
    
    # Relationships
    context: Mapped["HostelContext"] = relationship(
        "HostelContext",
        back_populates="context_switches",
        lazy="select"
    )
    
    admin: Mapped["AdminUser"] = relationship(
        "AdminUser",
        lazy="select",
        foreign_keys=[admin_id]
    )
    
    from_hostel: Mapped[Optional["Hostel"]] = relationship(
        "Hostel",
        lazy="select",
        foreign_keys=[from_hostel_id]
    )
    
    to_hostel: Mapped["Hostel"] = relationship(
        "Hostel",
        lazy="select",
        foreign_keys=[to_hostel_id]
    )
    
    snapshot: Mapped[Optional["ContextSnapshot"]] = relationship(
        "ContextSnapshot",
        back_populates="switch",
        lazy="select",
        uselist=False,
        cascade="all, delete-orphan"
    )
    
    # Hybrid Properties
    @hybrid_property
    def was_productive(self) -> bool:
        """Check if session was productive."""
        if not self.session_duration_minutes:
            return False
        return (
            self.session_duration_minutes >= 5 and 
            (self.actions_performed > 0 or self.decisions_made > 0)
        )
    
    @hybrid_property
    def productivity_score(self) -> Decimal:
        """Calculate productivity score for the session."""
        if not self.session_duration_minutes or self.session_duration_minutes == 0:
            return Decimal("0.00")
        
        actions_per_minute = Decimal(self.actions_performed) / Decimal(self.session_duration_minutes)
        score = min((actions_per_minute / Decimal("0.5")) * 100, 100)
        return score.quantize(Decimal("0.01"))
    
    def __repr__(self) -> str:
        return (
            f"<ContextSwitch(id={self.id}, admin_id={self.admin_id}, "
            f"to_hostel={self.to_hostel_id}, at={self.switched_at})>"
        )


class ContextPreference(TimestampModel, UUIDMixin):
    """
    User preferences for each hostel context.
    
    Stores user-specific preferences and settings for individual
    hostel contexts to provide personalized experience.
    """
    
    __tablename__ = "context_preferences"
    __table_args__ = (
        Index("idx_context_pref_context_id", "context_id"),
    )
    
    # Foreign Keys
    context_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("hostel_contexts.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
        comment="Context ID"
    )
    
    # Display Preferences
    dashboard_layout: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Preferred dashboard layout"
    )
    
    default_view: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Default landing view"
    )
    
    widgets_config: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Dashboard widgets configuration"
    )
    
    # Notification Preferences
    notification_settings: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Context-specific notification settings"
    )
    
    alert_thresholds: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Custom alert thresholds for this hostel"
    )
    
    # Data Preferences
    default_filters: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Default data filters"
    )
    
    sort_preferences: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Default sort preferences"
    )
    
    records_per_page: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=25,
        comment="Records per page preference"
    )
    
    # Quick Access
    pinned_sections: Mapped[Optional[List[str]]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Pinned sections for quick access"
    )
    
    favorite_reports: Mapped[Optional[List[str]]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Favorite report IDs"
    )
    
    bookmarks: Mapped[Optional[List[dict]]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Bookmarked pages and filters"
    )
    
    # Automation Preferences
    auto_refresh_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Enable auto-refresh of data"
    )
    
    auto_refresh_interval_seconds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=300,
        comment="Auto-refresh interval (seconds)"
    )
    
    # Custom Settings
    custom_settings: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Additional custom settings"
    )
    
    # Relationships
    context: Mapped["HostelContext"] = relationship(
        "HostelContext",
        back_populates="preferences",
        lazy="select"
    )
    
    def __repr__(self) -> str:
        return f"<ContextPreference(id={self.id}, context_id={self.context_id})>"


class ContextSnapshot(TimestampModel, UUIDMixin):
    """
    Snapshot of context state at time of switch.
    
    Captures complete state of hostel context at the moment of switching,
    useful for session restoration and historical analysis.
    """
    
    __tablename__ = "context_snapshots"
    __table_args__ = (
        Index("idx_snapshot_switch_id", "switch_id"),
        Index("idx_snapshot_timestamp", "snapshot_timestamp"),
    )
    
    # Foreign Keys
    switch_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("context_switches.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
        comment="Context switch ID"
    )
    
    # Snapshot Details
    snapshot_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        index=True,
        comment="When snapshot was taken"
    )
    
    # State Data
    hostel_state: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        comment="Complete hostel state data"
    )
    
    ui_state: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="UI state at time of switch"
    )
    
    pending_actions: Mapped[Optional[List[dict]]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Actions that were pending"
    )
    
    # Statistics at Time of Switch
    stats_snapshot: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        comment="Statistics at time of switch"
    )
    
    # Alerts and Notifications
    active_alerts: Mapped[Optional[List[dict]]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Active alerts at time of switch"
    )
    
    unread_notifications: Mapped[Optional[List[dict]]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Unread notifications"
    )
    
    # Metadata
    snapshot_version: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="1.0",
        comment="Snapshot format version"
    )
    
    compression_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Snapshot data is compressed"
    )
    
    # Relationships
    switch: Mapped["ContextSwitch"] = relationship(
        "ContextSwitch",
        back_populates="snapshot",
        lazy="select"
    )
    
    def __repr__(self) -> str:
        return (
            f"<ContextSnapshot(id={self.id}, switch_id={self.switch_id}, "
            f"timestamp={self.snapshot_timestamp})>"
        )