# app/models/maintenance/maintenance_analytics.py
"""
Maintenance analytics models.

Comprehensive analytics tracking for maintenance operations
with trends, metrics, and performance indicators.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship, validates
from sqlalchemy.ext.hybrid import hybrid_property

from app.models.base.base_model import BaseModel
from app.models.base.mixins import UUIDMixin


class MaintenanceAnalytic(UUIDMixin, BaseModel):
    """
    Core maintenance analytics aggregation.
    
    Stores aggregated analytics data for various time periods
    and dimensions for reporting and dashboards.
    """
    
    __tablename__ = "maintenance_analytics"
    
    hostel_id = Column(
        UUID(as_uuid=True),
        ForeignKey("hostels.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment="Hostel ID (NULL for system-wide analytics)",
    )
    
    # Analytics period
    period_type = Column(
        String(20),
        nullable=False,
        comment="Period type (daily, weekly, monthly, quarterly, yearly)",
    )
    
    period_start = Column(
        Date,
        nullable=False,
        comment="Period start date",
    )
    
    period_end = Column(
        Date,
        nullable=False,
        comment="Period end date",
    )
    
    period_label = Column(
        String(50),
        nullable=False,
        comment="Period label (e.g., '2024-01', 'Q1 2024')",
    )
    
    # Request metrics
    total_requests = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Total maintenance requests",
    )
    
    completed_requests = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Completed requests",
    )
    
    pending_requests = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Pending requests",
    )
    
    cancelled_requests = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Cancelled requests",
    )
    
    # Completion metrics
    completion_rate = Column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Overall completion rate percentage",
    )
    
    average_completion_time_hours = Column(
        Numeric(8, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Average time to complete (hours)",
    )
    
    average_completion_time_days = Column(
        Numeric(6, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Average time to complete (days)",
    )
    
    median_completion_time_days = Column(
        Numeric(6, 2),
        nullable=True,
        comment="Median completion time (days)",
    )
    
    on_time_completion_rate = Column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Percentage completed on time",
    )
    
    # Cost metrics
    total_cost = Column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Total maintenance cost",
    )
    
    average_cost_per_request = Column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Average cost per request",
    )
    
    cost_variance_percentage = Column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Average cost variance from estimates",
    )
    
    within_budget_rate = Column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Percentage completed within budget",
    )
    
    # Quality metrics
    quality_check_rate = Column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Percentage of requests quality checked",
    )
    
    quality_pass_rate = Column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Quality check pass rate",
    )
    
    average_quality_rating = Column(
        Numeric(3, 2),
        nullable=True,
        comment="Average quality rating (1-5)",
    )
    
    rework_rate = Column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Percentage requiring rework",
    )
    
    # Response metrics
    average_response_time_hours = Column(
        Numeric(8, 2),
        nullable=True,
        comment="Average time to assign/respond (hours)",
    )
    
    average_assignment_time_hours = Column(
        Numeric(8, 2),
        nullable=True,
        comment="Average time to assign (hours)",
    )
    
    # Priority distribution
    critical_requests = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Critical priority requests",
    )
    
    urgent_requests = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Urgent priority requests",
    )
    
    high_requests = Column(
        Integer,
        nullable=False,
        default=0,
        comment="High priority requests",
    )
    
    # Category breakdown
    requests_by_category = Column(
        JSONB,
        nullable=False,
        default={},
        comment="Request count by category",
    )
    
    cost_by_category = Column(
        JSONB,
        nullable=False,
        default={},
        comment="Cost breakdown by category",
    )
    
    # Trend data
    trend_direction = Column(
        String(20),
        nullable=True,
        comment="Trend direction (increasing, decreasing, stable)",
    )
    
    trend_percentage = Column(
        Numeric(5, 2),
        nullable=True,
        comment="Trend change percentage from previous period",
    )
    
    # Efficiency score
    efficiency_score = Column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Overall efficiency score (0-100)",
    )
    
    # Metadata - renamed from 'metadata' to avoid SQLAlchemy conflict
    analytics_metadata = Column(
        "metadata",  # Column name in database
        JSONB,
        nullable=True,
        default={},
        comment="Additional analytics metadata",
    )
    
    # Relationships
    hostel = relationship("Hostel", back_populates="maintenance_analytics")
    
    # Table constraints
    __table_args__ = (
        CheckConstraint(
            "total_requests >= 0",
            name="ck_analytics_total_requests_positive"
        ),
        CheckConstraint(
            "completed_requests >= 0",
            name="ck_analytics_completed_requests_positive"
        ),
        CheckConstraint(
            "completion_rate >= 0 AND completion_rate <= 100",
            name="ck_analytics_completion_rate_range"
        ),
        CheckConstraint(
            "total_cost >= 0",
            name="ck_analytics_total_cost_positive"
        ),
        CheckConstraint(
            "efficiency_score >= 0 AND efficiency_score <= 100",
            name="ck_analytics_efficiency_score_range"
        ),
        Index("idx_analytics_hostel_period", "hostel_id", "period_start"),
        Index("idx_analytics_period_type", "period_type", "period_start"),
        {"comment": "Maintenance analytics aggregation"}
    )
    
    def __repr__(self) -> str:
        return f"<MaintenanceAnalytic {self.period_label} - {self.hostel_id}>"
    
    @validates("average_quality_rating")
    def validate_quality_rating(self, key: str, value: Optional[Decimal]) -> Optional[Decimal]:
        """Validate quality rating is in valid range."""
        if value is not None and (value < 1 or value > 5):
            raise ValueError("Quality rating must be between 1 and 5")
        return value
    
    def calculate_efficiency_score(self) -> None:
        """
        Calculate overall efficiency score.
        
        Composite metric based on completion rate, timeliness, and quality.
        """
        weights = {
            "completion": 0.4,
            "timeliness": 0.3,
            "quality": 0.3,
        }
        
        completion_score = float(self.completion_rate)
        timeliness_score = float(self.on_time_completion_rate)
        quality_score = float(self.quality_pass_rate)
        
        efficiency = (
            completion_score * weights["completion"]
            + timeliness_score * weights["timeliness"]
            + quality_score * weights["quality"]
        )
        
        self.efficiency_score = round(Decimal(str(efficiency)), 2)


class CategoryPerformanceMetric(UUIDMixin, BaseModel):
    """
    Performance metrics by maintenance category.
    
    Detailed breakdown of performance for each maintenance category
    for targeted improvement and resource allocation.
    """
    
    __tablename__ = "category_performance_metrics"
    
    hostel_id = Column(
        UUID(as_uuid=True),
        ForeignKey("hostels.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment="Hostel ID (NULL for system-wide)",
    )
    
    # Period
    period_start = Column(
        Date,
        nullable=False,
        comment="Period start date",
    )
    
    period_end = Column(
        Date,
        nullable=False,
        comment="Period end date",
    )
    
    # Category
    category = Column(
        String(100),
        nullable=False,
        comment="Maintenance category",
    )
    
    category_code = Column(
        String(50),
        nullable=True,
        comment="Category code",
    )
    
    # Request metrics
    total_requests = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Total requests in category",
    )
    
    completed_requests = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Completed requests",
    )
    
    pending_requests = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Pending requests",
    )
    
    cancelled_requests = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Cancelled requests",
    )
    
    # Cost metrics
    total_cost = Column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Total cost for category",
    )
    
    average_cost = Column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Average cost per request",
    )
    
    median_cost = Column(
        Numeric(10, 2),
        nullable=True,
        comment="Median cost",
    )
    
    # Time metrics
    average_completion_time_hours = Column(
        Numeric(8, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Average completion time in hours",
    )
    
    average_completion_time_days = Column(
        Numeric(6, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Average completion time in days",
    )
    
    on_time_completion_rate = Column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Percentage completed on time",
    )
    
    # Priority distribution
    high_priority_count = Column(
        Integer,
        nullable=False,
        default=0,
        comment="High priority requests",
    )
    
    urgent_priority_count = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Urgent priority requests",
    )
    
    # Quality metrics
    quality_check_pass_rate = Column(
        Numeric(5, 2),
        nullable=True,
        comment="Quality check pass rate",
    )
    
    average_quality_rating = Column(
        Numeric(3, 2),
        nullable=True,
        comment="Average quality rating",
    )
    
    # Performance score
    category_performance_score = Column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Overall category performance score (0-100)",
    )
    
    # Metadata - renamed from 'metadata' to avoid SQLAlchemy conflict
    category_metadata = Column(
        "metadata",  # Column name in database
        JSONB,
        nullable=True,
        default={},
        comment="Additional category metrics metadata",
    )
    
    # Relationships
    hostel = relationship("Hostel")
    
    # Table constraints
    __table_args__ = (
        CheckConstraint(
            "total_requests >= 0",
            name="ck_category_metric_total_requests_positive"
        ),
        CheckConstraint(
            "total_cost >= 0",
            name="ck_category_metric_total_cost_positive"
        ),
        CheckConstraint(
            "average_quality_rating >= 1 AND average_quality_rating <= 5",
            name="ck_category_metric_quality_rating_range"
        ),
        Index("idx_category_metric_hostel_period", "hostel_id", "period_start", "category"),
        {"comment": "Performance metrics by maintenance category"}
    )
    
    def __repr__(self) -> str:
        return f"<CategoryPerformanceMetric {self.category} - {self.period_start}>"
    
    @hybrid_property
    def completion_rate(self) -> Decimal:
        """Calculate completion rate."""
        if self.total_requests == 0:
            return Decimal("0.00")
        return round(
            Decimal(self.completed_requests) / Decimal(self.total_requests) * 100,
            2
        )
    
    @hybrid_property
    def cost_per_completed(self) -> Decimal:
        """Calculate cost per completed request."""
        if self.completed_requests == 0:
            return Decimal("0.00")
        return round(
            self.total_cost / Decimal(self.completed_requests),
            2
        )