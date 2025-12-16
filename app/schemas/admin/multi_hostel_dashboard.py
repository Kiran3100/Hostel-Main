"""
Multi‑hostel admin dashboard schemas.

Provides aggregated portfolio statistics, per‑hostel quick stats,
and cross‑hostel comparisons for the multi‑hostel admin dashboard.

Key points:
- No assignment CRUD here (that lives in admin_hostel_assignment.py)
- Focused on read‑only dashboard views and analytics
"""

from datetime import date as Date, datetime
from decimal import Decimal
from typing import Dict, List, Union
from uuid import UUID

from pydantic import Field, computed_field, field_validator, model_validator

from app.schemas.common.base import BaseResponseSchema, BaseSchema
from app.schemas.common.enums import PermissionLevel

__all__ = [
    "MultiHostelDashboard",
    "AggregatedStats",
    "HostelQuickStats",
    "CrossHostelComparison",
    "TopPerformer",
    "BottomPerformer",
    "HostelMetricComparison",
    "HostelTaskSummary",
]


# ---------------------------------------------------------------------------
# Helpers / constants
# ---------------------------------------------------------------------------

def _normalize_hostel_type(value: str) -> str:
    """Normalize hostel type to canonical values and validate."""
    valid_types = {"boys", "girls", "co-ed", "coed", "mixed"}
    normalized = value.strip().lower()
    if normalized not in valid_types:
        raise ValueError(
            f"Invalid hostel type '{value}'. Must be one of: {', '.join(sorted(valid_types))}"
        )
    # Normalize co-ed variants
    return "co-ed" if normalized in {"coed", "mixed"} else normalized


ATTENTION_LOW_OCCUPANCY = Decimal("50.00")
ATTENTION_PENDING_TASKS = 20
ATTENTION_URGENT_ALERTS = 5


# ---------------------------------------------------------------------------
# Per‑hostel quick stats
# ---------------------------------------------------------------------------

class HostelQuickStats(BaseSchema):
    """
    Quick statistics for a single hostel in the multi‑hostel dashboard.
    """

    hostel_id: UUID = Field(..., description="Hostel ID")
    hostel_name: str = Field(..., min_length=1, description="Hostel name")
    hostel_city: str = Field(..., min_length=1, description="Hostel city")
    hostel_type: str = Field(..., description="Hostel type (boys/girls/co-ed)")

    # Assignment / access info for current admin
    is_primary: bool = Field(False, description="Primary hostel for this admin")
    permission_level: PermissionLevel = Field(
        ..., description="Admin permission level for this hostel"
    )
    has_management_access: bool = Field(
        True,
        description="Admin has management-level capabilities for this hostel",
    )

    # Capacity / occupancy
    total_students: int = Field(0, ge=0, description="Total students currently in hostel")
    capacity: int = Field(0, ge=0, description="Total bed capacity")
    occupancy_percentage: Decimal = Field(
        Decimal("0.00"),
        ge=0,
        le=100,
        description="Current occupancy percentage",
    )
    available_beds: int = Field(0, ge=0, description="Available beds count")

    # Operational workload
    pending_tasks: int = Field(0, ge=0, description="Pending tasks")
    urgent_alerts: int = Field(0, ge=0, description="Urgent alerts")
    pending_bookings: int = Field(0, ge=0, description="Pending booking requests")
    open_complaints: int = Field(0, ge=0, description="Open complaints")

    # Financials
    revenue_this_month: Decimal = Field(
        Decimal("0.00"), ge=0, description="Revenue collected this month"
    )
    outstanding_payments: Decimal = Field(
        Decimal("0.00"), ge=0, description="Outstanding (due) amount"
    )

    # Satisfaction / quality signals
    avg_student_rating: Union[Decimal, None] = Field(
        None, ge=0, le=5, description="Average student rating for this hostel"
    )
    admin_satisfaction_score: Union[Decimal, None] = Field(
        None, ge=0, le=5, description="Internal satisfaction score for this hostel"
    )

    # Activity from this admin
    last_activity: Union[datetime, None] = Field(
        None, description="Last time this admin interacted with this hostel"
    )
    access_count: int = Field(0, ge=0, description="Total accesses by this admin")

    @field_validator("hostel_type")
    @classmethod
    def validate_hostel_type(cls, v: str) -> str:
        return _normalize_hostel_type(v)

    @computed_field  # type: ignore[misc]
    @property
    def financial_risk(self) -> bool:
        """Whether outstanding payments exceed current month revenue."""
        return self.outstanding_payments > self.revenue_this_month

    @computed_field  # type: ignore[misc]
    @property
    def requires_attention(self) -> bool:
        """
        Whether this hostel should be highlighted as needing attention
        on the multi‑hostel dashboard.
        """
        return (
            self.urgent_alerts > 0
            or self.pending_tasks > ATTENTION_PENDING_TASKS
            or self.open_complaints > 10
            or self.occupancy_percentage < ATTENTION_LOW_OCCUPANCY
            or self.financial_risk
        )

    @computed_field  # type: ignore[misc]
    @property
    def status_indicator(self) -> str:
        """
        High‑level status indicator for UI (critical/warning/normal).
        """
        if self.urgent_alerts > ATTENTION_URGENT_ALERTS or self.open_complaints > 20:
            return "critical"
        if (
            self.urgent_alerts > 0
            or self.pending_tasks > ATTENTION_PENDING_TASKS
            or self.open_complaints > 10
            or self.occupancy_percentage < ATTENTION_LOW_OCCUPANCY
        ):
            return "warning"
        return "normal"

    @computed_field  # type: ignore[misc]
    @property
    def occupancy_status(self) -> str:
        """Human‑readable occupancy status."""
        if self.occupancy_percentage < Decimal("40.00"):
            return "Underutilized"
        elif self.occupancy_percentage < Decimal("90.00"):
            return "Healthy"
        else:
            return "Near Full"

    @computed_field  # type: ignore[misc]
    @property
    def hours_since_last_activity(self) -> Union[int, None]:
        """Hours since this admin last interacted with this hostel."""
        if not self.last_activity:
            return None
        # Pydantic v2: Use timezone-aware datetime.now() or UTC consistently
        delta = datetime.utcnow() - self.last_activity
        return int(delta.total_seconds() // 3600)


# ---------------------------------------------------------------------------
# Aggregated / portfolio stats
# ---------------------------------------------------------------------------

class AggregatedStats(BaseSchema):
    """
    Aggregated statistics across all hostels managed by the admin.
    """

    admin_id: UUID = Field(..., description="Admin user ID")

    total_hostels: int = Field(..., ge=0, description="Total hostels assigned")
    active_hostels: int = Field(..., ge=0, description="Hostels with active assignments")

    total_students: int = Field(0, ge=0, description="Total students across hostels")
    active_students: int = Field(0, ge=0, description="Active/checked‑in students")
    total_capacity: int = Field(0, ge=0, description="Total bed capacity")

    avg_occupancy_percentage: Decimal = Field(
        Decimal("0.00"), ge=0, le=100, description="Average occupancy across hostels"
    )

    total_pending_tasks: int = Field(0, ge=0, description="Total pending tasks")
    total_urgent_alerts: int = Field(0, ge=0, description="Total urgent alerts")
    total_open_complaints: int = Field(0, ge=0, description="Total open complaints")

    total_revenue_this_month: Decimal = Field(
        Decimal("0.00"), ge=0, description="Total revenue this month"
    )
    total_outstanding_payments: Decimal = Field(
        Decimal("0.00"), ge=0, description="Total outstanding payments"
    )

    avg_student_rating: Union[Decimal, None] = Field(
        None, ge=0, le=5, description="Average student rating across hostels"
    )
    avg_admin_satisfaction_score: Union[Decimal, None] = Field(
        None, ge=0, le=5, description="Average internal satisfaction score"
    )

    @computed_field  # type: ignore[misc]
    @property
    def hostel_utilization_rate(self) -> Decimal:
        """Percentage of hostels that are actively managed."""
        if self.total_hostels == 0:
            return Decimal("0.00")
        rate = Decimal(self.active_hostels) / Decimal(self.total_hostels) * 100
        return rate.quantize(Decimal("0.01"))

    @computed_field  # type: ignore[misc]
    @property
    def student_occupancy_rate(self) -> Decimal:
        """Overall bed occupancy rate across the portfolio."""
        if self.total_capacity == 0:
            return Decimal("0.00")
        rate = Decimal(self.active_students) / Decimal(self.total_capacity) * 100
        return rate.quantize(Decimal("0.01"))

    @computed_field  # type: ignore[misc]
    @property
    def has_critical_issues(self) -> bool:
        """Whether the portfolio has clearly critical issues."""
        return (
            self.total_urgent_alerts > 0
            or self.total_open_complaints > 20
            or self.total_pending_tasks > 100
        )

    @computed_field  # type: ignore[misc]
    @property
    def financial_health_indicator(self) -> str:
        """Basic financial health indicator."""
        if self.total_revenue_this_month == 0 and self.total_outstanding_payments == 0:
            return "neutral"
        if self.total_outstanding_payments > self.total_revenue_this_month:
            return "at_risk"
        if self.total_outstanding_payments > self.total_revenue_this_month * Decimal("0.5"):
            return "watch"
        return "healthy"

    @model_validator(mode="after")
    def validate_consistency(self) -> "AggregatedStats":
        """Basic consistency checks on aggregated counts."""
        if self.active_hostels > self.total_hostels:
            raise ValueError("active_hostels cannot exceed total_hostels")
        if self.active_students > self.total_students:
            raise ValueError("active_students cannot exceed total_students")
        if self.total_students > self.total_capacity and self.total_capacity > 0:
            # Allow, but this is suspicious; don't raise to avoid breaking clients.
            pass
        return self


# ---------------------------------------------------------------------------
# Task summary
# ---------------------------------------------------------------------------

class HostelTaskSummary(BaseSchema):
    """
    Portfolio‑wide task summary for the dashboard.
    """

    total_tasks: int = Field(0, ge=0, description="Total tasks in the selected period")
    pending_tasks: int = Field(0, ge=0, description="Currently pending tasks")
    overdue_tasks: int = Field(0, ge=0, description="Overdue tasks")
    urgent_tasks: int = Field(0, ge=0, description="Urgent tasks")
    completed_today: int = Field(0, ge=0, description="Tasks completed today")

    # Optional breakdown by hostel
    tasks_by_hostel: Dict[UUID, int] = Field(
        default_factory=dict, description="Total tasks per hostel (optional)"
    )

    @computed_field  # type: ignore[misc]
    @property
    def pending_ratio(self) -> Decimal:
        """Percentage of tasks that are pending."""
        if self.total_tasks == 0:
            return Decimal("0.00")
        ratio = Decimal(self.pending_tasks) / Decimal(self.total_tasks) * 100
        return ratio.quantize(Decimal("0.01"))

    @computed_field  # type: ignore[misc]
    @property
    def overdue_ratio(self) -> Decimal:
        """Percentage of tasks that are overdue."""
        if self.total_tasks == 0:
            return Decimal("0.00")
        ratio = Decimal(self.overdue_tasks) / Decimal(self.total_tasks) * 100
        return ratio.quantize(Decimal("0.01"))

    @computed_field  # type: ignore[misc]
    @property
    def health_status(self) -> str:
        """High‑level health indicator based on task backlog."""
        if self.urgent_tasks == 0 and self.overdue_tasks == 0:
            return "good"
        if self.urgent_tasks > 20 or self.overdue_ratio > Decimal("25.00"):
            return "critical"
        if self.urgent_tasks > 0 or self.overdue_ratio > Decimal("10.00"):
            return "attention"
        return "good"

    @model_validator(mode="after")
    def validate_counts(self) -> "HostelTaskSummary":
        """Ensure basic numeric consistency."""
        if self.pending_tasks > self.total_tasks:
            raise ValueError("pending_tasks cannot exceed total_tasks")
        if self.overdue_tasks > self.total_tasks:
            raise ValueError("overdue_tasks cannot exceed total_tasks")
        return self


# ---------------------------------------------------------------------------
# Top / bottom performers
# ---------------------------------------------------------------------------

class TopPerformer(BaseSchema):
    """
    Top performing hostel in a given dimension.
    """

    hostel_id: UUID = Field(..., description="Hostel ID")
    hostel_name: str = Field(..., min_length=1, description="Hostel name")
    hostel_city: str = Field(..., min_length=1, description="Hostel city")
    hostel_type: str = Field(..., description="Hostel type")

    performance_score: Decimal = Field(
        ..., ge=0, le=100, description="Composite performance score (0‑100)"
    )
    rank: int = Field(..., ge=1, description="Rank among hostels")
    key_metric: str = Field(..., min_length=1, description="Primary metric driving this ranking")
    key_metric_value: Union[Decimal, None] = Field(
        None, description="Value of the primary metric (e.g. occupancy %)"
    )

    @field_validator("hostel_type")
    @classmethod
    def validate_hostel_type(cls, v: str) -> str:
        return _normalize_hostel_type(v)

    @computed_field  # type: ignore[misc]
    @property
    def label(self) -> str:
        """Convenient display label."""
        return f"#{self.rank} {self.hostel_name}"


class BottomPerformer(BaseSchema):
    """
    Bottom performing hostel in a given dimension.
    """

    hostel_id: UUID = Field(..., description="Hostel ID")
    hostel_name: str = Field(..., min_length=1, description="Hostel name")
    hostel_city: str = Field(..., min_length=1, description="Hostel city")
    hostel_type: str = Field(..., description="Hostel type")

    performance_score: Decimal = Field(
        ..., ge=0, le=100, description="Composite performance score (0‑100)"
    )
    rank: int = Field(..., ge=1, description="Rank among hostels (1 = worst)")
    key_metric: str = Field(..., min_length=1, description="Primary metric driving this ranking")
    key_metric_value: Union[Decimal, None] = Field(
        None, description="Value of the primary metric (e.g. complaints count)"
    )

    @field_validator("hostel_type")
    @classmethod
    def validate_hostel_type(cls, v: str) -> str:
        return _normalize_hostel_type(v)

    @computed_field  # type: ignore[misc]
    @property
    def label(self) -> str:
        """Convenient display label."""
        return f"#{self.rank} {self.hostel_name}"


# ---------------------------------------------------------------------------
# Metric comparison
# ---------------------------------------------------------------------------

class HostelMetricComparison(BaseSchema):
    """
    Comparison of a single metric across hostels (best/worst vs portfolio average).
    """

    metric_name: str = Field(..., min_length=1, description="Metric name (e.g. occupancy)")
    unit: str = Field(..., min_length=1, description="Display unit (%, count, currency, etc.)")

    portfolio_average: Decimal = Field(
        Decimal("0.00"), description="Portfolio‑wide average for this metric"
    )

    best_hostel_id: Union[UUID, None] = Field(None, description="Best performing hostel ID")
    best_hostel_name: Union[str, None] = Field(None, description="Best performing hostel name")
    best_value: Union[Decimal, None] = Field(
        None, description="Best value for the metric (direction depends on metric)"
    )

    worst_hostel_id: Union[UUID, None] = Field(None, description="Worst performing hostel ID")
    worst_hostel_name: Union[str, None] = Field(None, description="Worst performing hostel name")
    worst_value: Union[Decimal, None] = Field(
        None, description="Worst value for the metric (direction depends on metric)"
    )

    @computed_field  # type: ignore[misc]
    @property
    def spread(self) -> Decimal:
        """Absolute spread between best and worst values."""
        if self.best_value is None or self.worst_value is None:
            return Decimal("0.00")
        diff = abs(Decimal(self.best_value) - Decimal(self.worst_value))
        return diff.quantize(Decimal("0.01"))

    @computed_field  # type: ignore[misc]
    @property
    def variation_index(self) -> Decimal:
        """
        Relative variation vs portfolio average (percentage).
        Higher = more variation between hostels for this metric.
        """
        if self.portfolio_average == 0 or self.spread == 0:
            return Decimal("0.00")
        ratio = self.spread / abs(self.portfolio_average) * 100
        return ratio.quantize(Decimal("0.01"))


# ---------------------------------------------------------------------------
# Cross‑hostel comparison wrapper
# ---------------------------------------------------------------------------

class CrossHostelComparison(BaseSchema):
    """
    Cross‑hostel comparison section for the dashboard, containing
    metric comparisons and top/bottom performers.
    """

    metrics: List[HostelMetricComparison] = Field(
        default_factory=list, description="Per‑metric comparisons"
    )
    top_performers: List[TopPerformer] = Field(
        default_factory=list, description="Top performing hostels"
    )
    bottom_performers: List[BottomPerformer] = Field(
        default_factory=list, description="Bottom performing hostels"
    )

    @computed_field  # type: ignore[misc]
    @property
    def has_significant_variation(self) -> bool:
        """
        Whether any metric shows large variation across hostels.
        """
        return any(m.variation_index > Decimal("20.00") for m in self.metrics)

    @computed_field  # type: ignore[misc]
    @property
    def metrics_by_name(self) -> Dict[str, HostelMetricComparison]:
        """Index metrics by name for quicker lookup in clients."""
        return {m.metric_name: m for m in self.metrics}


# ---------------------------------------------------------------------------
# Root multi‑hostel dashboard schema
# ---------------------------------------------------------------------------

class MultiHostelDashboard(BaseResponseSchema):
    """
    Root schema for the multi‑hostel admin dashboard response.
    """

    admin_id: UUID = Field(..., description="Admin user ID")
    admin_name: str = Field(..., min_length=1, description="Admin full name")

    generated_at: datetime = Field(
        default_factory=datetime.utcnow, description="Timestamp when dashboard was generated"
    )

    period_start: Date = Field(..., description="Start of reporting period")
    period_end: Date = Field(..., description="End of reporting period (inclusive)")

    # Portfolio‑level aggregates
    aggregated_stats: AggregatedStats = Field(
        ..., description="Aggregated statistics across all hostels"
    )

    # Per‑hostel quick stats
    hostels: List[HostelQuickStats] = Field(
        default_factory=list, description="Quick stats for each hostel"
    )

    # Tasks / workload
    task_summary: HostelTaskSummary = Field(
        ..., description="Portfolio‑wide task summary"
    )

    # Comparisons / rankings
    cross_hostel_comparison: Union[CrossHostelComparison, None] = Field(
        None, description="Cross‑hostel comparisons and rankings"
    )

    # UI helpers
    active_hostel_id: Union[UUID, None] = Field(
        None, description="Hostel currently focused in UI (optional)"
    )

    @computed_field  # type: ignore[misc]
    @property
    def period_days(self) -> int:
        """Length of the reporting period in days (at least 1)."""
        days = (self.period_end - self.period_start).days + 1
        return max(1, days)

    @computed_field  # type: ignore[misc]
    @property
    def hostels_requiring_attention(self) -> List[UUID]:
        """IDs of hostels that require attention."""
        return [h.hostel_id for h in self.hostels if h.requires_attention]

    @computed_field  # type: ignore[misc]
    @property
    def total_critical_hostels(self) -> int:
        """Number of hostels in warning/critical state."""
        return len(self.hostels_requiring_attention)

    @computed_field  # type: ignore[misc]
    @property
    def overall_attention_level(self) -> str:
        """
        Overall portfolio attention level based on how many hostels
        are in a concerning state.
        """
        n = self.total_critical_hostels
        if n == 0:
            return "low"
        if n <= 2:
            return "medium"
        if n <= 5:
            return "high"
        return "critical"

    @model_validator(mode="after")
    def validate_period(self) -> "MultiHostelDashboard":
        """Validate reporting period and basic consistency."""
        if self.period_end < self.period_start:
            raise ValueError("period_end must be on or after period_start")

        # Optional soft check: aggregated_stats.total_hostels vs hostels list
        if self.aggregated_stats.total_hostels and self.hostels:
            # Don't hard‑fail, but this is a useful invariant to watch.
            if self.aggregated_stats.total_hostels < len(self.hostels):
                # Could log a warning in application code.
                pass

        if self.aggregated_stats.admin_id != self.admin_id:
            # Ensure we didn't accidentally mix data for different admins
            raise ValueError("aggregated_stats.admin_id must match admin_id")

        return self