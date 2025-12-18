# --- File: C:\Hostel-Main\app\models\hostel\hostel_analytics.py ---
"""
Hostel analytics model for performance tracking and insights.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base.base_model import TimestampModel
from app.models.base.mixins import UUIDMixin

if TYPE_CHECKING:
    from app.models.hostel.hostel import Hostel


class HostelAnalytic(TimestampModel, UUIDMixin):
    """
    Comprehensive hostel analytics and performance metrics.
    
    Stores aggregated analytics data for hostels across different time periods.
    """

    __tablename__ = "hostel_analytics"

    # Foreign Keys
    hostel_id: Mapped[UUID] = mapped_column(
        ForeignKey("hostels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Reference to hostel",
    )

    # Time Period
    period_start: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
        comment="Analytics period start date",
    )
    period_end: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
        comment="Analytics period end date",
    )
    period_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
        comment="Period type (daily, weekly, monthly, yearly)",
    )

    # Occupancy Metrics
    average_occupancy_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Average occupancy rate for period",
    )
    peak_occupancy_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Peak occupancy during period",
    )
    lowest_occupancy_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Lowest occupancy during period",
    )
    total_bed_nights: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
        comment="Total bed nights (occupied * days)",
    )

    # Revenue Metrics
    total_revenue: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Total revenue for period",
    )
    rent_revenue: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Revenue from rent",
    )
    mess_revenue: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Revenue from mess",
    )
    other_revenue: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Revenue from other sources",
    )
    total_collected: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Total amount collected",
    )
    total_pending: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Total pending amount",
    )
    collection_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Collection rate percentage",
    )
    average_revenue_per_bed: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Average revenue per occupied bed",
    )

    # Booking Metrics
    total_bookings: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
        comment="Total booking requests",
    )
    approved_bookings: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
        comment="Approved bookings",
    )
    rejected_bookings: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
        comment="Rejected bookings",
    )
    cancelled_bookings: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
        comment="Cancelled bookings",
    )
    conversion_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Booking conversion rate",
    )
    average_booking_value: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Average booking value",
    )

    # Student Metrics
    new_students: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
        comment="New students joined",
    )
    departed_students: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
        comment="Students who left",
    )
    total_students_end: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
        comment="Total students at period end",
    )
    student_retention_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Student retention rate",
    )

    # Complaint Metrics
    total_complaints: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
        comment="Total complaints",
    )
    resolved_complaints: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
        comment="Resolved complaints",
    )
    average_resolution_time_hours: Mapped[Decimal] = mapped_column(
        Numeric(8, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Average resolution time in hours",
    )
    complaint_resolution_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Complaint resolution rate",
    )

    # Maintenance Metrics
    total_maintenance_requests: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
        comment="Total maintenance requests",
    )
    completed_maintenance: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
        comment="Completed maintenance tasks",
    )
    total_maintenance_cost: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Total maintenance cost",
    )
    average_maintenance_time_hours: Mapped[Decimal] = mapped_column(
        Numeric(8, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Average maintenance completion time",
    )

    # Review Metrics
    new_reviews: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
        comment="New reviews received",
    )
    average_rating: Mapped[Decimal] = mapped_column(
        Numeric(3, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Average rating for period",
    )
    rating_trend: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="stable",
        comment="Rating trend (increasing, decreasing, stable)",
    )

    # Trend Data (JSONB for flexibility)
    occupancy_trend: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Daily/weekly occupancy trend data",
    )
    revenue_trend: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Daily/weekly revenue trend data",
    )
    booking_trend: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Daily/weekly booking trend data",
    )

    # Comparative Metrics
    revenue_vs_last_period: Mapped[Decimal] = mapped_column(
        Numeric(8, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Revenue change vs last period (%)",
    )
    occupancy_vs_last_period: Mapped[Decimal] = mapped_column(
        Numeric(8, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Occupancy change vs last period (%)",
    )

    # Performance Score
    overall_performance_score: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Overall performance score (0-100)",
    )

    # Metadata
    generated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=datetime.utcnow,
        comment="Analytics generation timestamp",
    )
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Additional notes or insights",
    )

    # Relationships
    hostel: Mapped["Hostel"] = relationship(
        "Hostel",
        back_populates="analytics",
    )

    # Table Arguments
    __table_args__ = (
        # Indexes
        Index("idx_analytics_hostel_period", "hostel_id", "period_start", "period_end"),
        Index("idx_analytics_period_type", "period_type"),
        Index("idx_analytics_performance", "overall_performance_score"),
        
        # Check constraints
        CheckConstraint(
            "period_end >= period_start",
            name="check_period_end_after_start",
        ),
        CheckConstraint(
            "period_type IN ('daily', 'weekly', 'monthly', 'quarterly', 'yearly')",
            name="check_period_type_valid",
        ),
        CheckConstraint(
            "average_occupancy_rate >= 0 AND average_occupancy_rate <= 100",
            name="check_avg_occupancy_range",
        ),
        CheckConstraint(
            "collection_rate >= 0 AND collection_rate <= 100",
            name="check_collection_rate_range",
        ),
        CheckConstraint(
            "conversion_rate >= 0 AND conversion_rate <= 100",
            name="check_conversion_rate_range",
        ),
        CheckConstraint(
            "overall_performance_score >= 0 AND overall_performance_score <= 100",
            name="check_performance_score_range",
        ),
        CheckConstraint(
            "rating_trend IN ('increasing', 'decreasing', 'stable')",
            name="check_rating_trend_valid",
        ),
        
        # Unique constraint
        UniqueConstraint(
            "hostel_id",
            "period_start",
            "period_end",
            "period_type",
            name="uq_hostel_analytics_period",
        ),
        
        {"comment": "Hostel analytics and performance metrics"},
    )

    def __repr__(self) -> str:
        return (
            f"<HostelAnalytic(id={self.id}, hostel_id={self.hostel_id}, "
            f"period={self.period_type}, score={self.overall_performance_score})>"
        )

    @property
    def revenue_growth_rate(self) -> Decimal:
        """Calculate revenue growth rate."""
        return self.revenue_vs_last_period

    @property
    def occupancy_growth_rate(self) -> Decimal:
        """Calculate occupancy growth rate."""
        return self.occupancy_vs_last_period

    def calculate_performance_score(self) -> Decimal:
        """
        Calculate overall performance score based on multiple metrics.
        
        Weights:
        - Occupancy: 30%
        - Revenue Collection: 25%
        - Customer Satisfaction (Rating): 20%
        - Complaint Resolution: 15%
        - Booking Conversion: 10%
        """
        occupancy_score = float(self.average_occupancy_rate) * 0.30
        collection_score = float(self.collection_rate) * 0.25
        rating_score = (float(self.average_rating) / 5.0 * 100) * 0.20
        complaint_score = float(self.complaint_resolution_rate) * 0.15
        conversion_score = float(self.conversion_rate) * 0.10
        
        total_score = (
            occupancy_score
            + collection_score
            + rating_score
            + complaint_score
            + conversion_score
        )
        
        self.overall_performance_score = Decimal(str(total_score)).quantize(
            Decimal("0.01")
        )
        return self.overall_performance_score


class OccupancyTrend(TimestampModel, UUIDMixin):
    """
    Detailed occupancy trend tracking with daily granularity.
    
    Stores daily occupancy data for detailed analysis and forecasting.
    """

    __tablename__ = "occupancy_trends"

    # Foreign Keys
    hostel_id: Mapped[UUID] = mapped_column(
        ForeignKey("hostels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Reference to hostel",
    )

    # Date and Metrics
    data_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
        comment="Date of occupancy data",
    )
    occupancy_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        comment="Occupancy rate for the day",
    )
    occupied_beds: Mapped[int] = mapped_column(
        nullable=False,
        comment="Number of occupied beds",
    )
    total_beds: Mapped[int] = mapped_column(
        nullable=False,
        comment="Total beds available",
    )
    available_beds: Mapped[int] = mapped_column(
        nullable=False,
        comment="Available beds",
    )

    # Additional Metrics
    new_checkins: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
        comment="New check-ins for the day",
    )
    checkouts: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
        comment="Checkouts for the day",
    )
    reservations: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
        comment="New reservations made",
    )

    # Day Type
    is_weekend: Mapped[bool] = mapped_column(
        nullable=False,
        default=False,
        comment="Is weekend day",
    )
    is_holiday: Mapped[bool] = mapped_column(
        nullable=False,
        default=False,
        comment="Is public holiday",
    )

    # Table Arguments
    __table_args__ = (
        Index("idx_occupancy_trend_hostel_date", "hostel_id", "data_date"),
        Index("idx_occupancy_trend_date", "data_date"),
        CheckConstraint(
            "occupancy_rate >= 0 AND occupancy_rate <= 100",
            name="check_occupancy_rate_range",
        ),
        CheckConstraint(
            "occupied_beds >= 0",
            name="check_occupied_beds_positive",
        ),
        CheckConstraint(
            "total_beds > 0",
            name="check_total_beds_positive",
        ),
        CheckConstraint(
            "available_beds >= 0",
            name="check_available_beds_positive",
        ),
        UniqueConstraint(
            "hostel_id",
            "data_date",
            name="uq_occupancy_trend_hostel_date",
        ),
        {"comment": "Daily occupancy trend tracking"},
    )

    def __repr__(self) -> str:
        return (
            f"<OccupancyTrend(hostel_id={self.hostel_id}, "
            f"date={self.data_date}, rate={self.occupancy_rate})>"
        )


class RevenueTrend(TimestampModel, UUIDMixin):
    """
    Revenue trend tracking with daily/monthly granularity.
    
    Stores revenue data for trend analysis and forecasting.
    """

    __tablename__ = "revenue_trends"

    # Foreign Keys
    hostel_id: Mapped[UUID] = mapped_column(
        ForeignKey("hostels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Reference to hostel",
    )

    # Period
    data_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
        comment="Date of revenue data",
    )
    period_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="daily",
        comment="Period type (daily, monthly)",
    )

    # Revenue Breakdown
    total_revenue: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Total revenue",
    )
    rent_revenue: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Revenue from rent",
    )
    mess_revenue: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Revenue from mess",
    )
    other_revenue: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Other revenue sources",
    )

    # Collection
    collected: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Amount collected",
    )
    pending: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Amount pending",
    )

    # Student Count
    student_count: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
        comment="Number of students",
    )
    average_revenue_per_student: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Average revenue per student",
    )

    # Table Arguments
    __table_args__ = (
        Index("idx_revenue_trend_hostel_date", "hostel_id", "data_date"),
        Index("idx_revenue_trend_period", "period_type", "data_date"),
        CheckConstraint(
            "period_type IN ('daily', 'monthly')",
            name="check_revenue_period_type_valid",
        ),
        UniqueConstraint(
            "hostel_id",
            "data_date",
            "period_type",
            name="uq_revenue_trend_hostel_date_period",
        ),
        {"comment": "Revenue trend tracking and analysis"},
    )

    def __repr__(self) -> str:
        return (
            f"<RevenueTrend(hostel_id={self.hostel_id}, "
            f"date={self.data_date}, revenue={self.total_revenue})>"
        )