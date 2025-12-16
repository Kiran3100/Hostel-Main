"""
Enhanced hostel context management for multi-hostel admin operations.

Provides robust context switching, session tracking, and history management
for seamless multi-hostel administration with comprehensive audit trails.

Fully migrated to Pydantic v2.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Union
from uuid import UUID

from pydantic import Field, computed_field, field_validator, model_validator, ConfigDict

from app.schemas.common.base import BaseCreateSchema, BaseSchema

__all__ = [
    "HostelContext",
    "HostelSwitchRequest",
    "ActiveHostelResponse",
    "ContextHistory",
    "ContextSwitch",
]


# Constants
STALE_SESSION_MINUTES = 30
RECENT_ACCESS_HOURS = 24
MAX_RETURN_URL_LENGTH = 500
MAX_SWITCH_REASON_LENGTH = 200
MIN_PRODUCTIVE_SESSION_MINUTES = 5
EXCELLENT_ACTIONS_PER_MINUTE = 0.5

HEALTH_SCORE_WEIGHTS = {
    "occupancy": 0.4,
    "tasks": 0.3,
    "alerts": 0.3,
}

ACTIVITY_TRIGGERS = {
    "manual",
    "automatic",
    "notification",
    "alert",
    "scheduled",
}


class HostelContext(BaseSchema):
    """
    Enhanced current hostel context for multi-hostel admin with real-time metrics.

    Maintains active hostel state with comprehensive permission information,
    session tracking, and quick access to relevant statistics.
    """
    
    model_config = ConfigDict()

    # Admin and context identifiers
    admin_id: UUID = Field(..., description="Admin user ID")
    context_id: UUID = Field(..., description="Unique context session ID")

    # Active hostel information
    active_hostel_id: UUID = Field(..., description="Currently active hostel ID")
    hostel_name: str = Field(..., min_length=1, description="Active hostel name")
    hostel_city: str = Field(..., min_length=1, description="Hostel city location")
    hostel_type: str = Field(..., description="Hostel type classification")

    # Permission information for active hostel
    permission_level: str = Field(..., description="Permission level for active hostel")
    permissions: dict = Field(
        default_factory=dict, description="Detailed permissions for active hostel"
    )

    # Context session tracking
    context_started_at: datetime = Field(..., description="Context session start time")
    last_accessed_at: datetime = Field(..., description="Last activity timestamp")
    session_duration_minutes: int = Field(0, ge=0, description="Current session duration")

    # Quick statistics for active hostel
    total_students: int = Field(0, ge=0, description="Total students in active hostel")
    active_students: int = Field(0, ge=0, description="Currently active students")
    
    # Pydantic v2: Decimal with ge/le constraints
    occupancy_percentage: Decimal = Field(
        Decimal("0.00"), ge=Decimal("0"), le=Decimal("100"), description="Current occupancy rate"
    )

    # Pending tasks and alerts
    pending_tasks: int = Field(0, ge=0, description="Pending tasks count")
    urgent_alerts: int = Field(0, ge=0, description="Urgent alerts count")
    unread_notifications: int = Field(0, ge=0, description="Unread notifications count")

    # Revenue snapshot - Pydantic v2: Decimal with ge constraint
    revenue_this_month: Decimal = Field(
        Decimal("0.00"), ge=Decimal("0"), description="Revenue for current month"
    )
    outstanding_payments: Decimal = Field(
        Decimal("0.00"), ge=Decimal("0"), description="Outstanding payment amount"
    )

    # Context metadata
    previous_hostel_id: Union[UUID, None] = Field(None, description="Previously active hostel")
    switch_count: int = Field(0, ge=0, description="Number of context switches in session")

    @computed_field
    @property
    def session_active_duration(self) -> str:
        """Calculate and format active session duration."""
        duration = datetime.utcnow() - self.context_started_at

        total_seconds = int(duration.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60

        if hours > 0:
            return f"{hours}h {minutes}m"
        else:
            return f"{minutes}m"

    @computed_field
    @property
    def context_health_score(self) -> Decimal:
        """Calculate context health score based on hostel metrics."""
        score = Decimal("0.00")

        # Occupancy contribution (40 points)
        occupancy_score = self.occupancy_percentage * Decimal(str(HEALTH_SCORE_WEIGHTS["occupancy"]))
        score += occupancy_score

        # Task management (30 points)
        task_weight = Decimal(str(HEALTH_SCORE_WEIGHTS["tasks"] * 100))
        if self.pending_tasks == 0:
            score += task_weight
        elif self.pending_tasks <= 5:
            score += task_weight * Decimal("0.67")
        elif self.pending_tasks <= 10:
            score += task_weight * Decimal("0.33")

        # Alert status (30 points)
        alert_weight = Decimal(str(HEALTH_SCORE_WEIGHTS["alerts"] * 100))
        if self.urgent_alerts == 0:
            score += alert_weight
        elif self.urgent_alerts <= 2:
            score += alert_weight * Decimal("0.5")

        return score.quantize(Decimal("0.01"))

    @computed_field
    @property
    def requires_attention(self) -> bool:
        """Determine if active hostel requires immediate attention."""
        return (
            self.urgent_alerts > 0
            or self.pending_tasks > 10
            or self.occupancy_percentage < Decimal("50.00")
            or self.outstanding_payments > self.revenue_this_month
        )

    @computed_field
    @property
    def is_stale_session(self) -> bool:
        """Check if context session is stale (no activity for 30+ minutes)."""
        inactive_duration = datetime.utcnow() - self.last_accessed_at
        return inactive_duration > timedelta(minutes=STALE_SESSION_MINUTES)

    @computed_field
    @property
    def attention_priority(self) -> str:
        """Determine attention priority level."""
        if self.urgent_alerts > 5:
            return "Critical"
        elif self.urgent_alerts > 0 or self.pending_tasks > 20:
            return "High"
        elif self.pending_tasks > 10 or self.occupancy_percentage < Decimal("60.00"):
            return "Medium"
        else:
            return "Low"

    @field_validator("hostel_type")
    @classmethod
    def validate_hostel_type(cls, v: str) -> str:
        """Validate hostel type."""
        valid_types = {"boys", "girls", "co-ed", "coed", "mixed"}
        normalized = v.strip().lower()
        if normalized not in valid_types:
            raise ValueError(f"Invalid hostel type: {v}")
        return "co-ed" if normalized in {"coed", "mixed"} else normalized

    @model_validator(mode="after")
    def validate_session_consistency(self) -> "HostelContext":
        """Validate session timing consistency."""
        if self.last_accessed_at < self.context_started_at:
            raise ValueError("last_accessed_at cannot be before context_started_at")

        # Calculate expected duration
        expected_duration = int(
            (self.last_accessed_at - self.context_started_at).total_seconds() / 60
        )

        # Allow some tolerance for concurrent updates
        # Pydantic v2: Cannot log warnings from validators
        # Application code should handle logging if needed
        if abs(expected_duration - self.session_duration_minutes) > 5:
            pass

        return self


class HostelSwitchRequest(BaseCreateSchema):
    """
    Enhanced hostel context switch request with validation and options.

    Supports seamless context switching with proper validation,
    session management, and optional data refresh preferences.
    """
    
    model_config = ConfigDict(validate_assignment=True)

    hostel_id: UUID = Field(..., description="Target hostel ID to switch to")

    # Switch preferences
    save_current_session: bool = Field(
        True, description="Save current session state before switching"
    )
    refresh_dashboard: bool = Field(
        True, description="Refresh dashboard data after switch"
    )
    load_pending_tasks: bool = Field(
        True, description="Load pending tasks for new context"
    )

    # Navigation context
    return_url: Union[str, None] = Field(
        None, max_length=MAX_RETURN_URL_LENGTH, description="URL to navigate to after switch"
    )
    switch_reason: Union[str, None] = Field(
        None, max_length=MAX_SWITCH_REASON_LENGTH, description="Reason for context switch (for analytics)"
    )

    @field_validator("return_url")
    @classmethod
    def validate_return_url(cls, v: Union[str, None]) -> Union[str, None]:
        """Validate return URL format."""
        if v is not None:
            v = v.strip()
            if not v:
                return None

            # Basic URL validation
            if not v.startswith(("/", "http://", "https://")):
                raise ValueError(
                    "Invalid return URL format. Must start with /, http://, or https://"
                )

            # Prevent potential XSS
            dangerous_patterns = ["javascript:", "data:", "vbscript:"]
            if any(pattern in v.lower() for pattern in dangerous_patterns):
                raise ValueError("Return URL contains potentially dangerous content")

        return v

    @field_validator("switch_reason")
    @classmethod
    def validate_switch_reason(cls, v: Union[str, None]) -> Union[str, None]:
        """Validate and normalize switch reason."""
        if v is not None:
            v = v.strip()
            if not v:
                return None
            v = " ".join(v.split())  # Normalize whitespace
        return v


class ActiveHostelResponse(BaseSchema):
    """
    Enhanced response after successful hostel context switch.

    Provides comprehensive information about the newly active hostel
    with permissions, statistics, and navigation guidance.
    """
    
    model_config = ConfigDict()

    # Context identifiers
    admin_id: UUID = Field(..., description="Admin user ID")
    context_id: UUID = Field(..., description="New context session ID")

    # Previous and current hostel information
    previous_hostel_id: Union[UUID, None] = Field(None, description="Previous active hostel ID")
    previous_hostel_name: Union[str, None] = Field(None, description="Previous hostel name")

    active_hostel_id: UUID = Field(..., description="Newly active hostel ID")
    hostel_name: str = Field(..., min_length=1, description="Active hostel name")
    hostel_city: str = Field(..., min_length=1, description="Hostel city")
    hostel_type: str = Field(..., description="Hostel type")

    # Permission configuration for new context
    permission_level: str = Field(..., description="Permission level for new hostel")
    permissions: dict = Field(default_factory=dict, description="Detailed permissions")

    # Context timing
    switched_at: datetime = Field(..., description="Context switch timestamp")
    previous_session_duration_minutes: Union[int, None] = Field(
        None, ge=0, description="Duration of previous session"
    )

    # Quick statistics for new hostel - Pydantic v2: Decimal with constraints
    total_students: int = Field(0, ge=0, description="Total students")
    occupancy_percentage: Decimal = Field(
        Decimal("0.00"), ge=Decimal("0"), le=Decimal("100")
    )
    pending_tasks: int = Field(0, ge=0, description="Pending tasks")
    urgent_alerts: int = Field(0, ge=0, description="Urgent alerts")

    # Response metadata
    message: str = Field(..., min_length=1, description="Success message")
    dashboard_url: Union[str, None] = Field(None, description="Dashboard URL for new context")

    # Navigation suggestions
    suggested_actions: List[str] = Field(
        default_factory=list, description="Suggested next actions based on hostel state"
    )

    @computed_field
    @property
    def switch_summary(self) -> str:
        """Generate human-readable switch summary."""
        if self.previous_hostel_name:
            return f"Switched from {self.previous_hostel_name} to {self.hostel_name}"
        else:
            return f"Activated context for {self.hostel_name}"

    @computed_field
    @property
    def requires_immediate_action(self) -> bool:
        """Check if new context requires immediate action."""
        return self.urgent_alerts > 0 or self.pending_tasks > 5

    @computed_field
    @property
    def hostel_health_indicator(self) -> str:
        """Generate health indicator for newly active hostel."""
        if self.urgent_alerts > 0:
            return "critical"
        elif self.pending_tasks > 10:
            return "warning"
        elif self.occupancy_percentage < Decimal("60.00"):
            return "attention"
        else:
            return "healthy"

    @computed_field
    @property
    def priority_level(self) -> int:
        """Calculate priority level (1-5, where 5 is highest)."""
        if self.urgent_alerts > 5:
            return 5
        elif self.urgent_alerts > 0:
            return 4
        elif self.pending_tasks > 10:
            return 3
        elif self.pending_tasks > 5:
            return 2
        else:
            return 1

    @model_validator(mode="after")
    def populate_suggested_actions(self) -> "ActiveHostelResponse":
        """Populate suggested actions based on hostel state."""
        if not self.suggested_actions:
            actions = []

            if self.urgent_alerts > 0:
                actions.append(f"Review {self.urgent_alerts} urgent alerts")

            if self.pending_tasks > 10:
                actions.append(f"Process {self.pending_tasks} pending tasks")

            if self.occupancy_percentage < Decimal("50.00"):
                actions.append("Review low occupancy and marketing strategy")

            if self.occupancy_percentage > Decimal("95.00"):
                actions.append("Check waitlist for high occupancy")

            if not actions:
                actions.append("Dashboard is up to date")

            self.suggested_actions = actions

        return self


class ContextSwitch(BaseSchema):
    """
    Enhanced individual context switch record with comprehensive tracking.

    Represents a single hostel context switch with timing, reason,
    and session metrics for analytics and audit purposes.
    """
    
    model_config = ConfigDict()

    # Switch identification
    switch_id: UUID = Field(..., description="Unique switch record ID")
    admin_id: UUID = Field(..., description="Admin user ID")

    # Source and destination hostels
    from_hostel_id: Union[UUID, None] = Field(None, description="Source hostel ID")
    from_hostel_name: Union[str, None] = Field(None, description="Source hostel name")
    to_hostel_id: UUID = Field(..., description="Destination hostel ID")
    to_hostel_name: str = Field(..., min_length=1, description="Destination hostel name")

    # Switch timing
    switched_at: datetime = Field(..., description="Switch timestamp")
    session_duration_minutes: Union[int, None] = Field(
        None, ge=0, description="Duration spent in previous hostel (if applicable)"
    )

    # Switch context
    switch_reason: Union[str, None] = Field(None, description="Reason for switch")
    triggered_by: str = Field(
        "manual",
        description="What triggered the switch (manual, automatic, notification, alert, scheduled)",
    )

    # Activity metrics during session
    actions_performed: int = Field(0, ge=0, description="Actions performed in session")
    decisions_made: int = Field(0, ge=0, description="Decisions made in session")

    # Navigation context
    source_page: Union[str, None] = Field(None, description="Page where switch was initiated")
    destination_page: Union[str, None] = Field(None, description="Landing page after switch")

    @computed_field
    @property
    def session_productivity_score(self) -> Decimal:
        """Calculate productivity score for the session."""
        if self.session_duration_minutes is None or self.session_duration_minutes == 0:
            return Decimal("0.00")

        # Calculate actions per minute
        actions_per_minute = Decimal(self.actions_performed) / Decimal(
            self.session_duration_minutes
        )

        # Score based on actions per minute (capped at 100)
        score = min(
            (actions_per_minute / Decimal(str(EXCELLENT_ACTIONS_PER_MINUTE))) * 100, 100
        )

        return Decimal(str(score)).quantize(Decimal("0.01"))

    @computed_field
    @property
    def was_productive_session(self) -> bool:
        """Determine if session was productive (made meaningful progress)."""
        if self.session_duration_minutes is None:
            return False

        # Consider productive if:
        # - At least 5 minutes AND at least 1 action OR
        # - At least 1 decision made
        return (
            self.session_duration_minutes >= MIN_PRODUCTIVE_SESSION_MINUTES
            and self.actions_performed > 0
        ) or self.decisions_made > 0

    @computed_field
    @property
    def switch_type_description(self) -> str:
        """Generate human-readable switch type description."""
        type_map = {
            "manual": "User-initiated switch",
            "automatic": "Automatic context switch",
            "notification": "Triggered by notification",
            "alert": "Triggered by alert",
            "scheduled": "Scheduled context switch",
        }
        return type_map.get(self.triggered_by, "Unknown switch type")

    @computed_field
    @property
    def efficiency_rating(self) -> str:
        """Rate session efficiency."""
        score = float(self.session_productivity_score)

        if score >= 80:
            return "Excellent"
        elif score >= 60:
            return "Good"
        elif score >= 40:
            return "Fair"
        elif score > 0:
            return "Poor"
        else:
            return "No Activity"

    @field_validator("triggered_by")
    @classmethod
    def validate_triggered_by(cls, v: str) -> str:
        """Validate trigger type."""
        normalized = v.strip().lower()
        if normalized not in ACTIVITY_TRIGGERS:
            raise ValueError(
                f"Invalid trigger type: '{v}'. Valid types: {', '.join(ACTIVITY_TRIGGERS)}"
            )
        return normalized


class ContextHistory(BaseSchema):
    """
    Enhanced context switch history with analytics and insights.

    Provides comprehensive historical view of all context switches
    with usage patterns, productivity metrics, and recommendations.
    """
    
    model_config = ConfigDict()

    admin_id: UUID = Field(..., description="Admin user ID")
    admin_name: str = Field(..., min_length=1, description="Admin full name")

    # History period
    history_start: datetime = Field(..., description="History period start")
    history_end: datetime = Field(..., description="History period end")

    # Switch records
    switches: List[ContextSwitch] = Field(
        default_factory=list, description="Chronological list of context switches"
    )

    # Aggregate statistics
    total_switches: int = Field(0, ge=0, description="Total number of switches")
    unique_hostels_accessed: int = Field(0, ge=0, description="Unique hostels accessed")
    total_session_time_minutes: int = Field(
        0, ge=0, description="Total time across all sessions"
    )

    # Most accessed hostel
    most_accessed_hostel_id: Union[UUID, None] = Field(
        None, description="Most frequently accessed hostel"
    )
    most_accessed_hostel_name: Union[str, None] = Field(
        None, description="Most accessed hostel name"
    )
    most_accessed_count: int = Field(0, ge=0, description="Access count for most accessed hostel")

    # Usage patterns - Pydantic v2: Decimal with ge constraint
    avg_session_duration_minutes: Decimal = Field(
        Decimal("0.00"), ge=Decimal("0"), description="Average session duration"
    )
    avg_switches_per_day: Decimal = Field(
        Decimal("0.00"), ge=Decimal("0"), description="Average switches per day"
    )

    # Productivity metrics
    total_actions_performed: int = Field(0, ge=0, description="Total actions across all sessions")
    total_decisions_made: int = Field(0, ge=0, description="Total decisions across all sessions")
    productivity_score: Decimal = Field(
        Decimal("0.00"), ge=Decimal("0"), le=Decimal("100"), description="Overall productivity score"
    )

    @computed_field
    @property
    def history_duration_days(self) -> int:
        """Calculate history period duration in days."""
        duration = (self.history_end - self.history_start).days
        return max(1, duration)

    @computed_field
    @property
    def switch_frequency_pattern(self) -> str:
        """Determine switch frequency pattern."""
        switches_per_day = float(self.avg_switches_per_day)

        if switches_per_day < 2:
            return "Low Frequency"
        elif switches_per_day < 5:
            return "Moderate Frequency"
        elif switches_per_day < 10:
            return "High Frequency"
        else:
            return "Very High Frequency"

    @computed_field
    @property
    def session_efficiency_score(self) -> Decimal:
        """Calculate session efficiency score."""
        if self.total_switches == 0:
            return Decimal("0.00")

        # Calculate average actions per switch
        avg_actions = Decimal(self.total_actions_performed) / Decimal(self.total_switches)

        # Calculate average decisions per switch
        avg_decisions = Decimal(self.total_decisions_made) / Decimal(self.total_switches)

        # Combined efficiency score
        efficiency = (avg_actions * Decimal("0.6") + avg_decisions * Decimal("0.4")) * 10

        return Decimal(str(min(float(efficiency), 100))).quantize(Decimal("0.01"))

    @computed_field
    @property
    def hostel_focus_distribution(self) -> str:
        """Determine hostel focus distribution pattern."""
        if self.unique_hostels_accessed == 0:
            return "No Activity"

        if self.total_switches == 0:
            return "No Activity"

        # Calculate concentration: how focused admin is on specific hostels
        concentration_ratio = self.most_accessed_count / self.total_switches

        if concentration_ratio > 0.7:
            return "Highly Focused (70%+ on one hostel)"
        elif concentration_ratio > 0.5:
            return "Moderately Focused (50-70% on one hostel)"
        else:
            return "Distributed (Balanced across hostels)"

    @computed_field
    @property
    def recommendations(self) -> List[str]:
        """Generate context usage recommendations based on patterns."""
        recommendations = []

        # High switch frequency recommendation
        if float(self.avg_switches_per_day) > 10:
            recommendations.append(
                "Consider consolidating tasks to reduce frequent context switching"
            )

        # Short session duration recommendation
        if float(self.avg_session_duration_minutes) < 10 and self.total_switches > 5:
            recommendations.append(
                "Average session duration is short; consider focusing on one hostel at a time"
            )

        # Low productivity recommendation
        if float(self.productivity_score) < 50 and self.total_switches > 10:
            recommendations.append(
                "Productivity could be improved by spending more time per hostel session"
            )

        # Balanced usage recommendation
        if self.unique_hostels_accessed > 5:
            concentration_ratio = (
                self.most_accessed_count / self.total_switches if self.total_switches > 0 else 0
            )
            if concentration_ratio < 0.3:
                recommendations.append(
                    "You're managing many hostels; consider delegating to improve efficiency"
                )

        # High efficiency praise
        if float(self.productivity_score) > 80:
            recommendations.append("Excellent productivity! Keep up the good work")

        return recommendations if recommendations else ["Usage patterns are healthy"]

    @model_validator(mode="after")
    def validate_history_consistency(self) -> "ContextHistory":
        """Validate history data consistency."""
        if self.history_end < self.history_start:
            raise ValueError("history_end must be after history_start")

        # Validate switch count matches switches list
        # (Might be due to pagination, so we don't error)
        if len(self.switches) != self.total_switches:
            pass  # Application code should handle logging if needed

        return self