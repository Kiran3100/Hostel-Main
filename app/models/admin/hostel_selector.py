"""
Hostel Selector Model

UI-focused models for hostel selection dropdown/sidebar with quick stats,
favorites management, and recent access tracking for improved UX.
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
from app.models.base.mixins import UUIDMixin, SoftDeleteMixin

if TYPE_CHECKING:
    from app.models.admin.admin_user import AdminUser
    from app.models.hostel.hostel import Hostel

__all__ = [
    "RecentHostel",
    "FavoriteHostel",
    "HostelQuickStats",
    "HostelSelectorCache",
]


class RecentHostel(TimestampModel, UUIDMixin):
    """
    Recently accessed hostels tracking with access patterns.
    
    Tracks recent hostel access with frequency and recency metrics
    for intelligent sorting and quick access recommendations.
    """
    
    __tablename__ = "recent_hostels"
    __table_args__ = (
        UniqueConstraint("admin_id", "hostel_id", name="uq_admin_recent_hostel"),
        Index("idx_recent_hostel_admin_id", "admin_id"),
        Index("idx_recent_hostel_hostel_id", "hostel_id"),
        Index("idx_recent_hostel_last_accessed", "last_accessed"),
        Index("idx_recent_hostel_frequency", "access_count_last_7_days"),
    )
    
    # Foreign Keys
    admin_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("admin_users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Admin user ID"
    )
    
    hostel_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("hostels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Hostel ID"
    )
    
    # Access Tracking
    last_accessed: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        index=True,
        comment="Last access timestamp"
    )
    
    first_accessed: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        comment="First access timestamp"
    )
    
    access_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        comment="Total access count"
    )
    
    access_count_last_7_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        index=True,
        comment="Access count in last 7 days"
    )
    
    access_count_last_30_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        comment="Access count in last 30 days"
    )
    
    # Session Metrics
    total_session_time_minutes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Total session time (minutes)"
    )
    
    avg_session_duration_minutes: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Average session duration"
    )
    
    # Last Visit Stats
    last_occupancy: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Occupancy at last visit"
    )
    
    pending_tasks_on_last_visit: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Pending tasks at last visit"
    )
    
    # Frequency Score (for ranking)
    frequency_score: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Calculated frequency score for ranking"
    )
    
    # Metadata
    last_action_performed: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True,
        comment="Last action performed in this hostel"
    )
    
    access_pattern: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Access pattern analytics"
    )
    
    # Relationships
    admin: Mapped["AdminUser"] = relationship(
        "AdminUser",
        lazy="select",
        foreign_keys=[admin_id]
    )
    
    hostel: Mapped["Hostel"] = relationship(
        "Hostel",
        lazy="select",
        foreign_keys=[hostel_id]
    )
    
    # Hybrid Properties
    @hybrid_property
    def hours_since_access(self) -> int:
        """Calculate hours since last access."""
        delta = datetime.utcnow() - self.last_accessed
        return int(delta.total_seconds() // 3600)
    
    @hybrid_property
    def days_since_first_access(self) -> int:
        """Calculate days since first access."""
        delta = datetime.utcnow() - self.first_accessed
        return max(1, delta.days)
    
    @hybrid_property
    def is_frequent(self) -> bool:
        """Check if this is a frequently accessed hostel."""
        return self.access_count_last_7_days >= 5
    
    @hybrid_property
    def is_recent(self) -> bool:
        """Check if accessed within last 24 hours."""
        return self.hours_since_access <= 24
    
    def update_access(self, session_duration_minutes: int = 0) -> None:
        """Update access metrics when hostel is accessed."""
        now = datetime.utcnow()
        
        # Update access count
        self.access_count += 1
        self.last_accessed = now
        
        # Update session time
        if session_duration_minutes > 0:
            self.total_session_time_minutes += session_duration_minutes
            self.avg_session_duration_minutes = Decimal(
                self.total_session_time_minutes
            ) / Decimal(self.access_count)
        
        # Recalculate frequency score
        self.calculate_frequency_score()
    
    def calculate_frequency_score(self) -> None:
        """Calculate frequency score for ranking."""
        # Recent access gets higher score
        recency_score = max(0, 100 - self.hours_since_access)
        
        # Frequency score based on 7-day access
        frequency_score = min(self.access_count_last_7_days * 10, 100)
        
        # Combined score (60% frequency, 40% recency)
        total_score = (frequency_score * 0.6) + (recency_score * 0.4)
        
        self.frequency_score = Decimal(str(total_score)).quantize(Decimal("0.01"))
    
    def __repr__(self) -> str:
        return (
            f"<RecentHostel(id={self.id}, admin_id={self.admin_id}, "
            f"hostel_id={self.hostel_id}, count={self.access_count})>"
        )


class FavoriteHostel(TimestampModel, UUIDMixin, SoftDeleteMixin):
    """
    Favorite hostel with customization options.
    
    Supports hostel favorites with custom labels, notes,
    and priority ordering for personalized quick access.
    """
    
    __tablename__ = "favorite_hostels"
    __table_args__ = (
        UniqueConstraint("admin_id", "hostel_id", "is_deleted", name="uq_admin_favorite_hostel"),
        Index("idx_favorite_hostel_admin_id", "admin_id"),
        Index("idx_favorite_hostel_hostel_id", "hostel_id"),
        Index("idx_favorite_hostel_order", "display_order"),
    )
    
    # Foreign Keys
    admin_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("admin_users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Admin user ID"
    )
    
    hostel_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("hostels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Hostel ID"
    )
    
    # Customization
    custom_label: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Custom label/nickname for hostel"
    )
    
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Personal notes about this hostel"
    )
    
    display_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        index=True,
        comment="Display order (0 = highest priority)"
    )
    
    # Visual Customization
    color_code: Mapped[Optional[str]] = mapped_column(
        String(7),
        nullable=True,
        comment="Custom color code (hex)"
    )
    
    icon: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Custom icon identifier"
    )
    
    # Favorite Metadata
    added_to_favorites: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        comment="When added to favorites"
    )
    
    # Quick Stats (Cached)
    current_occupancy: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Current occupancy percentage"
    )
    
    pending_items: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Total pending items (tasks, alerts)"
    )
    
    # Access Tracking for Favorites
    last_accessed: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Last access timestamp"
    )
    
    access_count_since_favorited: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Access count since favorited"
    )
    
    # Quick Actions
    quick_actions: Mapped[Optional[List[str]]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Pinned quick actions for this hostel"
    )
    
    # Metadata
    tags: Mapped[Optional[List[str]]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Custom tags for organization"
    )
    
    custom_data: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Additional custom data"
    )
    
    # Relationships
    admin: Mapped["AdminUser"] = relationship(
        "AdminUser",
        lazy="select",
        foreign_keys=[admin_id]
    )
    
    hostel: Mapped["Hostel"] = relationship(
        "Hostel",
        lazy="select",
        foreign_keys=[hostel_id]
    )
    
    # Hybrid Properties
    @hybrid_property
    def days_in_favorites(self) -> int:
        """Calculate days since added to favorites."""
        delta = datetime.utcnow() - self.added_to_favorites
        return delta.days
    
    @hybrid_property
    def is_recently_accessed(self) -> bool:
        """Check if accessed in last 24 hours."""
        if not self.last_accessed:
            return False
        hours_since = (datetime.utcnow() - self.last_accessed).total_seconds() / 3600
        return hours_since <= 24
    
    @hybrid_property
    def display_name(self) -> Optional[str]:
        """Get display name (custom label if set, otherwise None)."""
        return self.custom_label
    
    def __repr__(self) -> str:
        return (
            f"<FavoriteHostel(id={self.id}, admin_id={self.admin_id}, "
            f"hostel_id={self.hostel_id}, order={self.display_order})>"
        )


class HostelQuickStats(TimestampModel, UUIDMixin):
    """
    Cached quick statistics for hostel selector.
    
    Provides pre-computed statistics for fast hostel selector
    rendering without expensive real-time calculations.
    """
    
    __tablename__ = "hostel_quick_stats"
    __table_args__ = (
        UniqueConstraint("hostel_id", name="uq_hostel_quick_stats"),
        Index("idx_quick_stats_hostel_id", "hostel_id"),
        Index("idx_quick_stats_updated", "last_updated"),
    )
    
    # Foreign Keys
    hostel_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("hostels.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
        comment="Hostel ID"
    )
    
    # Basic Stats
    total_students: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Total students"
    )
    
    active_students: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Active students"
    )
    
    total_capacity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Total bed capacity"
    )
    
    available_beds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Available beds"
    )
    
    occupancy_percentage: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Current occupancy percentage"
    )
    
    # Workload Stats
    pending_tasks: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Pending tasks"
    )
    
    urgent_alerts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Urgent alerts"
    )
    
    pending_bookings: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Pending booking requests"
    )
    
    open_complaints: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Open complaints"
    )
    
    maintenance_requests: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Active maintenance requests"
    )
    
    # Financial Stats
    revenue_this_month: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Revenue this month"
    )
    
    outstanding_payments: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Outstanding payments"
    )
    
    collection_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Payment collection rate (%)"
    )
    
    # Satisfaction Metrics
    avg_student_rating: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(3, 2),
        nullable=True,
        comment="Average student rating (0-5)"
    )
    
    student_satisfaction_score: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
        comment="Overall student satisfaction (0-100)"
    )
    
    # Health Indicators
    health_score: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Overall hostel health score (0-100)"
    )
    
    status_indicator: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="normal",
        comment="Status indicator (critical, warning, normal, excellent)"
    )
    
    requires_attention: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Hostel requires immediate attention"
    )
    
    # Trend Indicators
    occupancy_trend: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="Occupancy trend (increasing, decreasing, stable)"
    )
    
    revenue_trend: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="Revenue trend (increasing, decreasing, stable)"
    )
    
    # Cache Management
    last_updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        index=True,
        comment="Last stats update timestamp"
    )
    
    cache_ttl_seconds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=300,
        comment="Cache TTL in seconds (default 5 minutes)"
    )
    
    # Detailed Stats (JSON for flexibility)
    detailed_stats: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Additional detailed statistics"
    )
    
    # Relationships
    hostel: Mapped["Hostel"] = relationship(
        "Hostel",
        lazy="select",
        foreign_keys=[hostel_id]
    )
    
    # Hybrid Properties
    @hybrid_property
    def is_stale(self) -> bool:
        """Check if cache is stale and needs refresh."""
        age_seconds = (datetime.utcnow() - self.last_updated).total_seconds()
        return age_seconds > self.cache_ttl_seconds
    
    @hybrid_property
    def cache_age_minutes(self) -> int:
        """Calculate cache age in minutes."""
        age_seconds = (datetime.utcnow() - self.last_updated).total_seconds()
        return int(age_seconds // 60)
    
    @hybrid_property
    def notification_badge_count(self) -> int:
        """Calculate total notification badge count."""
        return self.pending_bookings + self.urgent_alerts + self.open_complaints
    
    @hybrid_property
    def is_critical(self) -> bool:
        """Check if hostel is in critical status."""
        return self.status_indicator == "critical" or self.urgent_alerts > 5
    
    def refresh_stats(self, stats_dict: dict) -> None:
        """Refresh cached statistics from provided dictionary."""
        # Basic stats
        self.total_students = stats_dict.get("total_students", 0)
        self.active_students = stats_dict.get("active_students", 0)
        self.total_capacity = stats_dict.get("total_capacity", 0)
        self.available_beds = stats_dict.get("available_beds", 0)
        self.occupancy_percentage = Decimal(str(stats_dict.get("occupancy_percentage", 0)))
        
        # Workload stats
        self.pending_tasks = stats_dict.get("pending_tasks", 0)
        self.urgent_alerts = stats_dict.get("urgent_alerts", 0)
        self.pending_bookings = stats_dict.get("pending_bookings", 0)
        self.open_complaints = stats_dict.get("open_complaints", 0)
        self.maintenance_requests = stats_dict.get("maintenance_requests", 0)
        
        # Financial stats
        self.revenue_this_month = Decimal(str(stats_dict.get("revenue_this_month", 0)))
        self.outstanding_payments = Decimal(str(stats_dict.get("outstanding_payments", 0)))
        self.collection_rate = Decimal(str(stats_dict.get("collection_rate", 0)))
        
        # Satisfaction metrics
        self.avg_student_rating = (
            Decimal(str(stats_dict["avg_student_rating"])) 
            if stats_dict.get("avg_student_rating") 
            else None
        )
        self.student_satisfaction_score = (
            Decimal(str(stats_dict["student_satisfaction_score"])) 
            if stats_dict.get("student_satisfaction_score") 
            else None
        )
        
        # Health and status
        self.health_score = Decimal(str(stats_dict.get("health_score", 0)))
        self.status_indicator = stats_dict.get("status_indicator", "normal")
        self.requires_attention = stats_dict.get("requires_attention", False)
        
        # Trends
        self.occupancy_trend = stats_dict.get("occupancy_trend")
        self.revenue_trend = stats_dict.get("revenue_trend")
        
        # Update timestamp
        self.last_updated = datetime.utcnow()
        
        # Store detailed stats if provided
        if "detailed_stats" in stats_dict:
            self.detailed_stats = stats_dict["detailed_stats"]
    
    def __repr__(self) -> str:
        return (
            f"<HostelQuickStats(id={self.id}, hostel_id={self.hostel_id}, "
            f"occupancy={self.occupancy_percentage}%)>"
        )


class HostelSelectorCache(TimestampModel, UUIDMixin):
    """
    Cached hostel selector response for fast rendering.
    
    Pre-computes complete hostel selector data for admins
    to enable instant dropdown/sidebar rendering.
    """
    
    __tablename__ = "hostel_selector_cache"
    __table_args__ = (
        UniqueConstraint("admin_id", name="uq_admin_selector_cache"),
        Index("idx_selector_cache_admin_id", "admin_id"),
        Index("idx_selector_cache_updated", "last_updated"),
    )
    
    # Foreign Keys
    admin_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("admin_users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
        comment="Admin user ID"
    )
    
    # Summary Stats
    total_hostels: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Total hostels managed"
    )
    
    active_hostels: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Active hostel assignments"
    )
    
    # Active Context
    active_hostel_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("hostels.id", ondelete="SET NULL"),
        nullable=True,
        comment="Currently active hostel"
    )
    
    # Quick Lists (IDs only for efficiency)
    recent_hostel_ids: Mapped[List[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        comment="Recent hostel IDs (ordered)"
    )
    
    favorite_hostel_ids: Mapped[List[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        comment="Favorite hostel IDs"
    )
    
    attention_required_ids: Mapped[List[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        comment="Hostels requiring attention"
    )
    
    # Aggregate Stats
    total_pending_tasks: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Total pending tasks across hostels"
    )
    
    total_urgent_alerts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Total urgent alerts across hostels"
    )
    
    avg_occupancy_percentage: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Average occupancy across hostels"
    )
    
    # Cached Hostel Data
    hostels_data: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="Complete hostel selector data"
    )
    
    # Cache Management
    last_updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        index=True,
        comment="Last cache update"
    )
    
    cache_version: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="1.0",
        comment="Cache data format version"
    )
    
    cache_ttl_seconds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=300,
        comment="Cache TTL (default 5 minutes)"
    )
    
    # Metadata
    build_duration_ms: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Time taken to build cache (milliseconds)"
    )
    
    # Relationships
    admin: Mapped["AdminUser"] = relationship(
        "AdminUser",
        lazy="select",
        foreign_keys=[admin_id]
    )
    
    active_hostel: Mapped[Optional["Hostel"]] = relationship(
        "Hostel",
        lazy="select",
        foreign_keys=[active_hostel_id]
    )
    
    # Hybrid Properties
    @hybrid_property
    def is_stale(self) -> bool:
        """Check if cache is stale."""
        age_seconds = (datetime.utcnow() - self.last_updated).total_seconds()
        return age_seconds > self.cache_ttl_seconds
    
    @hybrid_property
    def has_critical_alerts(self) -> bool:
        """Check if any hostel has critical alerts."""
        return len(self.attention_required_ids) > 0
    
    @hybrid_property
    def cache_age_minutes(self) -> int:
        """Cache age in minutes."""
        age_seconds = (datetime.utcnow() - self.last_updated).total_seconds()
        return int(age_seconds // 60)
    
    def invalidate(self) -> None:
        """Invalidate cache by setting last_updated to past."""
        self.last_updated = datetime.utcnow() - timedelta(seconds=self.cache_ttl_seconds + 1)
    
    def __repr__(self) -> str:
        return (
            f"<HostelSelectorCache(id={self.id}, admin_id={self.admin_id}, "
            f"hostels={self.total_hostels}, stale={self.is_stale})>"
        )