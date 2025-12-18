# --- File: app/models/attendance/attendance_record.py ---
"""
Attendance record models with comprehensive tracking and validation.

Provides models for daily attendance records, corrections, and audit trails
with support for multiple check-in methods and geolocation tracking.
"""

from datetime import date, datetime, time
from decimal import Decimal
from typing import Optional
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base.base_model import BaseModel, TimestampModel
from app.models.base.enums import AttendanceMode, AttendanceStatus

__all__ = [
    "AttendanceRecord",
    "AttendanceCorrection",
    "BulkAttendanceLog",
]


class AttendanceRecord(TimestampModel, BaseModel):
    """
    Daily attendance record with comprehensive tracking.
    
    Tracks student check-in/check-out times, attendance status, late arrivals,
    and marking metadata including location and device information.
    """

    __tablename__ = "attendance_records"

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
    student_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    marked_by: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=False,
        index=True,
    )
    supervisor_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("supervisors.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Core attendance data
    attendance_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
    )
    check_in_time: Mapped[Optional[time]] = mapped_column(
        Time,
        nullable=True,
    )
    check_out_time: Mapped[Optional[time]] = mapped_column(
        Time,
        nullable=True,
    )
    status: Mapped[AttendanceStatus] = mapped_column(
        Enum(AttendanceStatus, name="attendance_status_enum"),
        nullable=False,
        default=AttendanceStatus.PRESENT,
        index=True,
    )

    # Late tracking
    is_late: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
    )
    late_minutes: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )

    # Marking metadata
    attendance_mode: Mapped[AttendanceMode] = mapped_column(
        Enum(AttendanceMode, name="attendance_mode_enum"),
        nullable=False,
        default=AttendanceMode.MANUAL,
        index=True,
    )
    notes: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )

    # Geolocation data (for mobile check-ins)
    location_lat: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 7),
        nullable=True,
    )
    location_lng: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 7),
        nullable=True,
    )

    # Device information (for mobile check-ins)
    device_info: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
    )

    # Correction tracking
    is_corrected: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
    )
    correction_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    # Relationships
    hostel: Mapped["Hostel"] = relationship(
        "Hostel",
        back_populates="attendance_records",
        lazy="joined",
    )
    student: Mapped["Student"] = relationship(
        "Student",
        back_populates="attendance_records",
        lazy="joined",
    )
    marked_by_user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[marked_by],
        lazy="select",
    )
    supervisor: Mapped[Optional["Supervisor"]] = relationship(
        "Supervisor",
        foreign_keys=[supervisor_id],
        lazy="select",
    )
    corrections: Mapped[list["AttendanceCorrection"]] = relationship(
        "AttendanceCorrection",
        back_populates="attendance_record",
        cascade="all, delete-orphan",
        lazy="select",
    )

    # Constraints
    __table_args__ = (
        UniqueConstraint(
            "student_id",
            "attendance_date",
            name="uq_student_attendance_date",
        ),
        CheckConstraint(
            "late_minutes >= 0 AND late_minutes <= 1440",
            name="ck_attendance_late_minutes_range",
        ),
        CheckConstraint(
            "location_lat >= -90 AND location_lat <= 90",
            name="ck_attendance_latitude_range",
        ),
        CheckConstraint(
            "location_lng >= -180 AND location_lng <= 180",
            name="ck_attendance_longitude_range",
        ),
        CheckConstraint(
            "correction_count >= 0",
            name="ck_attendance_correction_count",
        ),
        Index(
            "idx_attendance_hostel_date",
            "hostel_id",
            "attendance_date",
        ),
        Index(
            "idx_attendance_student_date_range",
            "student_id",
            "attendance_date",
        ),
        Index(
            "idx_attendance_status_date",
            "status",
            "attendance_date",
        ),
        Index(
            "idx_attendance_late_date",
            "is_late",
            "attendance_date",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<AttendanceRecord(id={self.id}, student_id={self.student_id}, "
            f"date={self.attendance_date}, status={self.status.value})>"
        )


class AttendanceCorrection(TimestampModel, BaseModel):
    """
    Attendance correction audit trail.
    
    Records all corrections made to attendance records with complete
    before/after values and mandatory correction reasons for compliance.
    """

    __tablename__ = "attendance_corrections"

    # Primary key
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        index=True,
    )

    # Foreign keys
    attendance_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("attendance_records.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    corrected_by: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=False,
        index=True,
    )

    # Original values
    original_status: Mapped[AttendanceStatus] = mapped_column(
        Enum(AttendanceStatus, name="attendance_status_enum"),
        nullable=False,
    )
    original_check_in_time: Mapped[Optional[time]] = mapped_column(
        Time,
        nullable=True,
    )
    original_check_out_time: Mapped[Optional[time]] = mapped_column(
        Time,
        nullable=True,
    )
    original_is_late: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
    )
    original_late_minutes: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )

    # Corrected values
    corrected_status: Mapped[AttendanceStatus] = mapped_column(
        Enum(AttendanceStatus, name="attendance_status_enum"),
        nullable=False,
    )
    corrected_check_in_time: Mapped[Optional[time]] = mapped_column(
        Time,
        nullable=True,
    )
    corrected_check_out_time: Mapped[Optional[time]] = mapped_column(
        Time,
        nullable=True,
    )
    corrected_is_late: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
    )
    corrected_late_minutes: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )

    # Correction metadata
    correction_reason: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    correction_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        index=True,
    )
    approved_by: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    approved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    attendance_record: Mapped["AttendanceRecord"] = relationship(
        "AttendanceRecord",
        back_populates="corrections",
        lazy="joined",
    )
    corrected_by_user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[corrected_by],
        lazy="select",
    )
    approved_by_user: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[approved_by],
        lazy="select",
    )

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "original_late_minutes >= 0 AND original_late_minutes <= 1440",
            name="ck_correction_original_late_minutes",
        ),
        CheckConstraint(
            "corrected_late_minutes >= 0 AND corrected_late_minutes <= 1440",
            name="ck_correction_corrected_late_minutes",
        ),
        Index(
            "idx_correction_attendance_timestamp",
            "attendance_id",
            "correction_timestamp",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<AttendanceCorrection(id={self.id}, attendance_id={self.attendance_id}, "
            f"timestamp={self.correction_timestamp})>"
        )


class BulkAttendanceLog(TimestampModel, BaseModel):
    """
    Bulk attendance operation logging.
    
    Tracks bulk attendance marking operations for audit and debugging,
    including success/failure statistics and error details.
    """

    __tablename__ = "bulk_attendance_logs"

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
    marked_by: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=False,
        index=True,
    )

    # Operation details
    attendance_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
    )
    operation_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    total_students: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    successful_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    failed_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    # Error tracking
    errors: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
    )

    # Execution metadata
    execution_time_ms: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    hostel: Mapped["Hostel"] = relationship(
        "Hostel",
        lazy="select",
    )
    marked_by_user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[marked_by],
        lazy="select",
    )

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "total_students >= 0",
            name="ck_bulk_log_total_students",
        ),
        CheckConstraint(
            "successful_count >= 0",
            name="ck_bulk_log_successful_count",
        ),
        CheckConstraint(
            "failed_count >= 0",
            name="ck_bulk_log_failed_count",
        ),
        CheckConstraint(
            "execution_time_ms >= 0",
            name="ck_bulk_log_execution_time",
        ),
        Index(
            "idx_bulk_log_hostel_date",
            "hostel_id",
            "attendance_date",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<BulkAttendanceLog(id={self.id}, hostel_id={self.hostel_id}, "
            f"date={self.attendance_date}, total={self.total_students})>"
        )