# --- File: C:\Hostel-Main\app\models\hostel\hostel_settings.py ---
"""
Hostel settings model for operational configuration.
"""

from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Time,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base.base_model import TimestampModel
from app.models.base.mixins import UUIDMixin

if TYPE_CHECKING:
    from app.models.hostel.hostel import Hostel


class HostelSettings(TimestampModel, UUIDMixin):
    """
    Hostel operational settings and configuration.
    
    Centralized management of hostel operational settings,
    preferences, and business rules.
    """

    __tablename__ = "hostel_settings"

    # Foreign Keys (One-to-One with Hostel)
    hostel_id: Mapped[UUID] = mapped_column(
        ForeignKey("hostels.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
        comment="Reference to hostel",
    )

    # ===== Booking Settings =====
    auto_approve_bookings: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Automatically approve booking requests",
    )
    booking_advance_percentage: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("20.00"),
        comment="Required advance payment percentage",
    )
    max_booking_duration_months: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=12,
        comment="Maximum booking duration in months",
    )
    min_booking_duration_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=30,
        comment="Minimum booking duration in days",
    )
    allow_same_day_booking: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Allow same-day bookings",
    )
    booking_buffer_hours: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=24,
        comment="Minimum hours before check-in for booking",
    )

    # ===== Payment Settings =====
    payment_due_day: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=5,
        comment="Monthly payment due date (1-28)",
    )
    late_payment_grace_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=3,
        comment="Grace period for late payments (days)",
    )
    late_payment_penalty_percentage: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("5.00"),
        comment="Late payment penalty percentage",
    )
    allow_partial_payments: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Allow partial payment of dues",
    )
    min_partial_payment_percentage: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("50.00"),
        comment="Minimum partial payment percentage",
    )
    security_deposit_months: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=2,
        comment="Security deposit in months of rent",
    )

    # ===== Attendance Settings =====
    enable_attendance_tracking: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Enable attendance tracking system",
    )
    minimum_attendance_percentage: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("75.00"),
        comment="Minimum required attendance percentage",
    )
    attendance_grace_period_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=7,
        comment="Grace period for new students (days)",
    )
    auto_mark_absent_after_hours: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=24,
        comment="Auto-mark absent if no check-in after X hours",
    )
    attendance_alert_threshold: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("70.00"),
        comment="Alert if attendance falls below threshold",
    )

    # ===== Notification Settings =====
    notify_on_booking: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Send notifications for new bookings",
    )
    notify_on_complaint: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Send notifications for new complaints",
    )
    notify_on_payment: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Send notifications for payments",
    )
    notify_on_maintenance: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Send notifications for maintenance",
    )
    notify_on_low_attendance: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Send notifications for low attendance",
    )
    payment_reminder_days: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        default=list,
        comment="Days before due date to send reminders (JSON array)",
    )

    # ===== Mess Settings =====
    mess_included: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Mess facility included in rent",
    )
    mess_charges_monthly: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="Monthly mess charges (if separate)",
    )
    mess_advance_booking_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        comment="Days in advance for mess meal booking",
    )
    allow_mess_opt_out: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Allow students to opt-out of mess",
    )
    mess_menu_change_frequency: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="weekly",
        comment="Menu change frequency (daily, weekly, monthly)",
    )

    # ===== Security Settings =====
    visitor_entry_time_start: Mapped[Optional[Time]] = mapped_column(
        Time,
        nullable=True,
        comment="Visitor entry allowed from (HH:MM)",
    )
    visitor_entry_time_end: Mapped[Optional[Time]] = mapped_column(
        Time,
        nullable=True,
        comment="Visitor entry allowed until (HH:MM)",
    )
    late_entry_time: Mapped[Optional[Time]] = mapped_column(
        Time,
        nullable=True,
        comment="Late entry cutoff time (HH:MM)",
    )
    require_visitor_id: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Require ID proof for visitors",
    )
    max_visitors_per_student: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=2,
        comment="Maximum simultaneous visitors per student",
    )
    visitor_advance_approval_required: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Require advance approval for visitors",
    )

    # ===== Room Settings =====
    allow_room_transfer: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Allow room transfer requests",
    )
    room_transfer_charges: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="Charges for room transfer",
    )
    min_stay_before_transfer_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=90,
        comment="Minimum days before transfer allowed",
    )
    auto_assign_beds: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Automatically assign beds to students",
    )

    # ===== Maintenance Settings =====
    maintenance_sla_hours: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=48,
        comment="SLA for maintenance resolution (hours)",
    )
    urgent_maintenance_sla_hours: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=4,
        comment="SLA for urgent maintenance (hours)",
    )
    allow_student_maintenance_request: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Allow students to raise maintenance requests",
    )
    require_maintenance_approval_above: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="Require approval for maintenance above this amount",
    )

    # ===== Leave Settings =====
    max_leave_days_per_month: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=7,
        comment="Maximum leave days per month",
    )
    leave_advance_notice_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=2,
        comment="Advance notice required for leave (days)",
    )
    emergency_leave_allowed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Allow emergency leave without advance notice",
    )

    # ===== General Settings =====
    timezone: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="Asia/Kolkata",
        comment="Hostel timezone",
    )
    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="INR",
        comment="Default currency code",
    )
    language: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="en",
        comment="Default language code",
    )

    # ===== Feature Flags =====
    features_enabled: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        default=dict,
        comment="Feature flags and toggles",
    )

    # ===== Custom Settings =====
    custom_settings: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        default=dict,
        comment="Custom hostel-specific settings",
    )

    # Relationships
    hostel: Mapped["Hostel"] = relationship(
        "Hostel",
        back_populates="settings",
    )

    # Table Arguments
    __table_args__ = (
        # Indexes
        Index("idx_settings_hostel", "hostel_id"),
        
        # Check constraints for booking settings
        CheckConstraint(
            "booking_advance_percentage >= 0 AND booking_advance_percentage <= 100",
            name="check_booking_advance_range",
        ),
        CheckConstraint(
            "max_booking_duration_months >= 1 AND max_booking_duration_months <= 24",
            name="check_max_booking_duration_range",
        ),
        CheckConstraint(
            "min_booking_duration_days >= 1 AND min_booking_duration_days <= 365",
            name="check_min_booking_duration_range",
        ),
        CheckConstraint(
            "booking_buffer_hours >= 0",
            name="check_booking_buffer_positive",
        ),
        
        # Check constraints for payment settings
        CheckConstraint(
            "payment_due_day >= 1 AND payment_due_day <= 28",
            name="check_payment_due_day_range",
        ),
        CheckConstraint(
            "late_payment_grace_days >= 0 AND late_payment_grace_days <= 10",
            name="check_grace_days_range",
        ),
        CheckConstraint(
            "late_payment_penalty_percentage >= 0 AND late_payment_penalty_percentage <= 50",
            name="check_penalty_percentage_range",
        ),
        CheckConstraint(
            "min_partial_payment_percentage >= 0 AND min_partial_payment_percentage <= 100",
            name="check_min_partial_payment_range",
        ),
        CheckConstraint(
            "security_deposit_months >= 0 AND security_deposit_months <= 12",
            name="check_security_deposit_range",
        ),
        
        # Check constraints for attendance settings
        CheckConstraint(
            "minimum_attendance_percentage >= 0 AND minimum_attendance_percentage <= 100",
            name="check_min_attendance_range",
        ),
        CheckConstraint(
            "attendance_grace_period_days >= 0 AND attendance_grace_period_days <= 30",
            name="check_attendance_grace_range",
        ),
        CheckConstraint(
            "attendance_alert_threshold >= 0 AND attendance_alert_threshold <= 100",
            name="check_attendance_alert_range",
        ),
        
        # Check constraints for mess settings
        CheckConstraint(
            "mess_charges_monthly IS NULL OR mess_charges_monthly >= 0",
            name="check_mess_charges_positive",
        ),
        CheckConstraint(
            "mess_advance_booking_days >= 0 AND mess_advance_booking_days <= 7",
            name="check_mess_booking_days_range",
        ),
        CheckConstraint(
            "mess_menu_change_frequency IN ('daily', 'weekly', 'monthly')",
            name="check_menu_frequency_valid",
        ),
        
        # Check constraints for security settings
        CheckConstraint(
            "max_visitors_per_student >= 0 AND max_visitors_per_student <= 10",
            name="check_max_visitors_range",
        ),
        
        # Check constraints for room settings
        CheckConstraint(
            "room_transfer_charges IS NULL OR room_transfer_charges >= 0",
            name="check_transfer_charges_positive",
        ),
        CheckConstraint(
            "min_stay_before_transfer_days >= 0",
            name="check_min_stay_positive",
        ),
        
        # Check constraints for maintenance settings
        CheckConstraint(
            "maintenance_sla_hours > 0",
            name="check_maintenance_sla_positive",
        ),
        CheckConstraint(
            "urgent_maintenance_sla_hours > 0",
            name="check_urgent_sla_positive",
        ),
        CheckConstraint(
            "require_maintenance_approval_above IS NULL OR require_maintenance_approval_above >= 0",
            name="check_maintenance_approval_positive",
        ),
        
        # Check constraints for leave settings
        CheckConstraint(
            "max_leave_days_per_month >= 0 AND max_leave_days_per_month <= 31",
            name="check_max_leave_days_range",
        ),
        CheckConstraint(
            "leave_advance_notice_days >= 0",
            name="check_leave_notice_positive",
        ),
        
        {"comment": "Hostel operational settings and configuration"},
    )

    def __repr__(self) -> str:
        return f"<HostelSettings(id={self.id}, hostel_id={self.hostel_id})>"

    def get_payment_reminder_days(self) -> list:
        """Get payment reminder days as a list."""
        if self.payment_reminder_days:
            return self.payment_reminder_days.get("days", [7, 3, 1])
        return [7, 3, 1]  # Default: 7, 3, and 1 day before

    def is_feature_enabled(self, feature_name: str) -> bool:
        """Check if a specific feature is enabled."""
        if self.features_enabled:
            return self.features_enabled.get(feature_name, False)
        return False

    def get_custom_setting(self, key: str, default=None):
        """Get a custom setting value."""
        if self.custom_settings:
            return self.custom_settings.get(key, default)
        return default