# --- File: C:\Hostel-Main\app\models\student\student_preferences.py ---
"""
Student preferences model.

Manages student-specific preferences for notifications, meals,
privacy settings, and communication preferences.
"""

from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    ForeignKey,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base.base_model import BaseModel
from app.models.base.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.student.student import Student


class StudentPreferences(BaseModel, TimestampMixin):
    """
    Student preferences model.
    
    Stores personalized preferences for each student including
    notification settings, meal preferences, privacy controls,
    and communication preferences.
    
    One-to-one relationship with Student.
    """

    __tablename__ = "student_preferences"

    # Foreign Key
    student_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("students.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
        comment="Reference to student",
    )

    # Meal Preferences (Beyond basic dietary preference)
    meal_plan_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="full",
        comment="Meal plan type (full, breakfast_only, lunch_dinner, custom)",
    )
    
    skip_breakfast: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Skip breakfast in meal plan",
    )
    
    skip_lunch: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Skip lunch in meal plan",
    )
    
    skip_dinner: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Skip dinner in meal plan",
    )
    
    meal_preferences_notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Additional meal preferences and notes",
    )

    # Notification Preferences - Channels
    email_notifications: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Enable email notifications",
    )
    
    sms_notifications: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Enable SMS notifications",
    )
    
    push_notifications: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Enable push notifications",
    )
    
    whatsapp_notifications: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Enable WhatsApp notifications",
    )

    # Notification Preferences - Types
    payment_reminders: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Receive payment reminders",
    )
    
    attendance_alerts: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Receive attendance alerts",
    )
    
    announcement_notifications: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Receive announcements",
    )
    
    complaint_updates: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Receive complaint status updates",
    )
    
    event_notifications: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Receive event notifications",
    )
    
    maintenance_notifications: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Receive maintenance notifications",
    )
    
    mess_menu_updates: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Receive mess menu updates",
    )
    
    promotional_notifications: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Receive promotional notifications",
    )

    # Notification Timing
    quiet_hours_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Enable quiet hours (no notifications)",
    )
    
    quiet_hours_start: Mapped[str | None] = mapped_column(
        String(5),
        nullable=True,
        comment="Quiet hours start time (HH:MM format)",
    )
    
    quiet_hours_end: Mapped[str | None] = mapped_column(
        String(5),
        nullable=True,
        comment="Quiet hours end time (HH:MM format)",
    )
    
    digest_mode: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Send daily digest instead of individual notifications",
    )
    
    digest_time: Mapped[str | None] = mapped_column(
        String(5),
        nullable=True,
        comment="Preferred digest delivery time (HH:MM format)",
    )

    # Communication Preferences
    preferred_language: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="en",
        comment="Preferred language (en, hi, ta, te, etc.)",
    )
    
    preferred_contact_method: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="email",
        comment="Preferred contact method (email, sms, phone, whatsapp)",
    )
    
    contact_time_preference: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Preferred contact time (morning, afternoon, evening)",
    )

    # Privacy Settings
    show_profile_to_others: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Show profile to other students",
    )
    
    show_room_number: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Show room number in profile",
    )
    
    show_phone_number: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Show phone number to other students",
    )
    
    show_email: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Show email to other students",
    )
    
    show_institutional_info: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Show college/company information",
    )
    
    show_social_media: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Show social media profiles",
    )

    # Contact Permissions
    allow_roommate_contact: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Allow roommates to view contact info",
    )
    
    allow_floormate_contact: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Allow floormates to view contact info",
    )
    
    allow_hostelmate_contact: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Allow all hostel residents to view contact info",
    )

    # Search and Discovery
    searchable_by_name: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Allow search by name",
    )
    
    searchable_by_institution: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Allow search by institution",
    )
    
    searchable_by_company: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Allow search by company",
    )
    
    appear_in_directory: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Appear in student directory",
    )

    # Activity and Presence
    show_last_seen: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Show last seen/activity status",
    )
    
    show_online_status: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Show online/offline status",
    )
    
    show_attendance_to_others: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Show attendance status to other students",
    )

    # Room and Roommate Preferences
    room_temperature_preference: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="Room temperature preference (cool, moderate, warm)",
    )
    
    light_preference: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="Light preference (bright, moderate, dim)",
    )
    
    noise_preference: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="Noise preference (quiet, moderate, doesn't mind)",
    )
    
    sleep_schedule: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Sleep schedule (early bird, night owl, flexible)",
    )
    
    study_time_preference: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Preferred study time",
    )
    
    visitor_policy: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Visitor policy preference (frequent, occasional, rare)",
    )
    
    cleanliness_level: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="Cleanliness preference (very clean, moderate, casual)",
    )

    # Dashboard and UI Preferences
    dashboard_layout: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="default",
        comment="Dashboard layout preference",
    )
    
    theme_preference: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="light",
        comment="UI theme (light, dark, auto)",
    )
    
    compact_view: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Use compact view for lists",
    )
    
    show_tips: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Show helpful tips and tutorials",
    )

    # Data and Analytics
    allow_analytics: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Allow usage analytics collection",
    )
    
    personalized_recommendations: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Enable personalized recommendations",
    )

    # Third-party Integrations
    calendar_sync_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Sync events to external calendar",
    )
    
    calendar_provider: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Calendar provider (google, outlook, etc.)",
    )

    # Additional Notes
    preference_notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Additional preference notes",
    )

    # Relationship
    student: Mapped["Student"] = relationship(
        "Student",
        back_populates="preferences",
        lazy="joined",
    )

    def __repr__(self) -> str:
        return f"<StudentPreferences(id={self.id}, student_id={self.student_id})>"

    @property
    def has_quiet_hours(self) -> bool:
        """Check if quiet hours are configured."""
        return (
            self.quiet_hours_enabled
            and self.quiet_hours_start is not None
            and self.quiet_hours_end is not None
        )

    @property
    def notifications_enabled(self) -> bool:
        """Check if any notification channel is enabled."""
        return any([
            self.email_notifications,
            self.sms_notifications,
            self.push_notifications,
            self.whatsapp_notifications,
        ])

    @property
    def is_public_profile(self) -> bool:
        """Check if profile is public."""
        return (
            self.show_profile_to_others
            and self.appear_in_directory
            and self.searchable_by_name
        )
