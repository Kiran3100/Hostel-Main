# --- File: app/models/attendance/attendance_report.py ---
"""
Attendance report models with caching and analytics.

Provides models for generated reports, summaries, and trend analysis
with caching for performance optimization.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base.base_model import BaseModel, TimestampModel

__all__ = [
    "AttendanceReport",
    "AttendanceSummary",
    "AttendanceTrend",
]


class AttendanceReport(TimestampModel, BaseModel):
    """
    Generated attendance report with caching.
    
    Stores pre-generated reports with complete data and metadata
    for performance optimization and historical tracking.
    """

    __tablename__ = "attendance_reports"

    # Primary key
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        index=True,
    )

    # Foreign keys
    hostel_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hostels.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    student_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    generated_by: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=False,
    )

    # Report metadata
    report_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    report_title: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )
    report_format: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="json",
    )

    # Date range
    period_start: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
    )
    period_end: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
    )

    # Report data (stored as JSON for flexibility)
    summary_data: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    detailed_data: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
    )
    analytics_data: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
    )

    # Generation metadata
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        index=True,
    )
    generation_time_ms: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )

    # Cache control
    is_cached: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    cache_expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    cache_key: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        unique=True,
        index=True,
    )

    # File storage
    file_path: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )
    file_size_bytes: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )

    # Access tracking
    view_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    last_viewed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    hostel: Mapped[Optional["Hostel"]] = relationship(
        "Hostel",
        lazy="select",
    )
    student: Mapped[Optional["Student"]] = relationship(
        "Student",
        lazy="select",
    )
    generator: Mapped["User"] = relationship(
        "User",
        foreign_keys=[generated_by],
        lazy="select",
    )

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "period_end >= period_start",
            name="ck_report_period_dates",
        ),
        CheckConstraint(
            "generation_time_ms >= 0",
            name="ck_report_generation_time",
        ),
        CheckConstraint(
            "file_size_bytes >= 0",
            name="ck_report_file_size",
        ),
        CheckConstraint(
            "view_count >= 0",
            name="ck_report_view_count",
        ),
        Index(
            "idx_report_hostel_period",
            "hostel_id",
            "period_start",
            "period_end",
        ),
        Index(
            "idx_report_student_period",
            "student_id",
            "period_start",
            "period_end",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<AttendanceReport(id={self.id}, type={self.report_type}, "
            f"period={self.period_start} to {self.period_end})>"
        )


class AttendanceSummary(TimestampModel, BaseModel):
    """
    Student-wise attendance summary with cached metrics.
    
    Stores aggregated attendance statistics per student for
    quick retrieval and dashboard display.
    """

    __tablename__ = "attendance_summaries"

    # Primary key
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        index=True,
    )

    # Foreign keys
    student_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    hostel_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hostels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Summary period
    period_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
    )
    period_start: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
    )
    period_end: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
    )

    # Attendance metrics
    total_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    total_present: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    total_absent: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    total_late: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    total_on_leave: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    total_half_day: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    # Calculated percentages
    attendance_percentage: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("0.00"),
    )
    late_percentage: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("0.00"),
    )

    # Streak tracking
    current_present_streak: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    longest_present_streak: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    current_absent_streak: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    longest_absent_streak: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    # Status assessment
    attendance_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="good",
    )
    meets_minimum_requirement: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    # Cache metadata
    last_calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        index=True,
    )
    calculation_version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )

    # Relationships
    student: Mapped["Student"] = relationship(
        "Student",
        back_populates="attendance_summaries",
        lazy="joined",
    )
    hostel: Mapped["Hostel"] = relationship(
        "Hostel",
        lazy="select",
    )

    # Constraints
    __table_args__ = (
        UniqueConstraint(
            "student_id",
            "period_type",
            "period_start",
            "period_end",
            name="uq_summary_student_period",
        ),
        CheckConstraint(
            "period_end >= period_start",
            name="ck_summary_period_dates",
        ),
        CheckConstraint(
            "total_days >= 0",
            name="ck_summary_total_days",
        ),
        CheckConstraint(
            "total_present >= 0",
            name="ck_summary_total_present",
        ),
        CheckConstraint(
            "total_absent >= 0",
            name="ck_summary_total_absent",
        ),
        CheckConstraint(
            "total_late >= 0",
            name="ck_summary_total_late",
        ),
        CheckConstraint(
            "attendance_percentage >= 0 AND attendance_percentage <= 100",
            name="ck_summary_attendance_percentage",
        ),
        CheckConstraint(
            "late_percentage >= 0 AND late_percentage <= 100",
            name="ck_summary_late_percentage",
        ),
        Index(
            "idx_summary_student_period",
            "student_id",
            "period_start",
            "period_end",
        ),
        Index(
            "idx_summary_hostel_period",
            "hostel_id",
            "period_type",
            "period_start",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<AttendanceSummary(id={self.id}, student_id={self.student_id}, "
            f"period={self.period_start} to {self.period_end}, "
            f"percentage={self.attendance_percentage})>"
        )


class AttendanceTrend(TimestampModel, BaseModel):
    """
    Attendance trend analysis over time.
    
    Stores trend data for analytics, forecasting, and
    performance monitoring at various aggregation levels.
    """

    __tablename__ = "attendance_trends"

    # Primary key
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        index=True,
    )

    # Foreign keys
    hostel_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hostels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    student_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    # Trend period
    trend_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
    )
    period_identifier: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    period_start: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
    )
    period_end: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    # Trend metrics
    average_attendance: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("0.00"),
    )
    trend_direction: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="stable",
    )
    change_percentage: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
    )

    # Aggregated data
    total_students: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    average_present: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00"),
    )
    average_absent: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00"),
    )
    average_late: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00"),
    )

    # Forecasting
    forecasted_attendance: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
    )
    confidence_score: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(3, 2),
        nullable=True,
    )

    # Additional analytics
    anomaly_detected: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    anomaly_details: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
    )

    # Calculation metadata
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        index=True,
    )

    # Relationships
    hostel: Mapped["Hostel"] = relationship(
        "Hostel",
        lazy="select",
    )
    student: Mapped[Optional["Student"]] = relationship(
        "Student",
        lazy="select",
    )

    # Constraints
    __table_args__ = (
        UniqueConstraint(
            "hostel_id",
            "student_id",
            "trend_type",
            "period_identifier",
            name="uq_trend_hostel_student_period",
        ),
        CheckConstraint(
            "period_end >= period_start",
            name="ck_trend_period_dates",
        ),
        CheckConstraint(
            "average_attendance >= 0 AND average_attendance <= 100",
            name="ck_trend_average_attendance",
        ),
        CheckConstraint(
            "confidence_score >= 0 AND confidence_score <= 1",
            name="ck_trend_confidence_score",
        ),
        Index(
            "idx_trend_hostel_type_period",
            "hostel_id",
            "trend_type",
            "period_start",
        ),
        Index(
            "idx_trend_anomaly",
            "hostel_id",
            "anomaly_detected",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<AttendanceTrend(id={self.id}, hostel_id={self.hostel_id}, "
            f"type={self.trend_type}, period={self.period_identifier})>"
        )