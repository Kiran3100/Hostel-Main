"""
User Profile model configuration.
"""
from sqlalchemy import Column, Date, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.models.base.base_model import BaseModel
from app.models.common.mixins import TimestampMixin, UUIDMixin
from app.schemas.common.enums import Gender

class UserProfile(BaseModel, UUIDMixin, TimestampMixin):
    """
    Extended user profile information.
    
    Stores demographic data, preferences, personalization settings,
    and non-authentication related details.
    """
    __tablename__ = "user_profiles"
    __table_args__ = (
        {"comment": "Extended user profile and personalization data"}
    )

    user_id = Column(
        ForeignKey("users.id", ondelete="CASCADE"), 
        unique=True, 
        nullable=False,
        index=True,
        comment="Foreign key to users table"
    )
    
    # Demographics
    gender = Column(
        Enum(Gender), 
        nullable=True,
        comment="Gender identification"
    )
    date_of_birth = Column(
        Date, 
        nullable=True,
        index=True,
        comment="Date of birth (for age verification)"
    )
    nationality = Column(
        String(100), 
        nullable=True,
        comment="Nationality/citizenship"
    )
    
    # Personal Information
    bio = Column(
        Text, 
        nullable=True,
        comment="User biography/about me"
    )
    occupation = Column(
        String(100), 
        nullable=True,
        comment="Current occupation"
    )
    organization = Column(
        String(255), 
        nullable=True,
        comment="Company/institution name"
    )
    
    # Media & Branding
    profile_image_url = Column(
        String(500), 
        nullable=True,
        comment="Profile image URL (cloud storage)"
    )
    cover_image_url = Column(
        String(500), 
        nullable=True,
        comment="Cover/banner image URL"
    )
    
    # Profile Completeness
    profile_completion_percentage = Column(
        Integer, 
        default=0, 
        nullable=False,
        comment="Calculated profile completion (0-100)"
    )
    
    # Language & Localization
    preferred_language = Column(
        String(10), 
        default="en", 
        nullable=False,
        comment="ISO 639-1 language code"
    )
    timezone = Column(
        String(50), 
        default="UTC", 
        nullable=False,
        comment="IANA timezone identifier"
    )
    
    # Notification Preferences (stored as JSONB for flexibility)
    notification_preferences = Column(
        JSONB,
        nullable=True,
        default={
            "email_notifications": True,
            "sms_notifications": True,
            "push_notifications": True,
            "booking_notifications": True,
            "payment_notifications": True,
            "complaint_notifications": True,
            "announcement_notifications": True,
            "maintenance_notifications": True,
            "marketing_notifications": False,
            "digest_frequency": "immediate",
            "quiet_hours_start": None,
            "quiet_hours_end": None
        },
        comment="Granular notification preferences"
    )
    
    # Privacy Settings
    privacy_settings = Column(
        JSONB,
        nullable=True,
        default={
            "profile_visibility": "public",  # public, friends, private
            "show_email": False,
            "show_phone": False,
            "show_date_of_birth": False,
            "allow_friend_requests": True,
            "show_online_status": True
        },
        comment="Privacy and visibility controls"
    )
    
    # Communication Preferences
    communication_preferences = Column(
        JSONB,
        nullable=True,
        default={
            "preferred_contact_method": "email",
            "best_contact_time": "anytime",
            "do_not_disturb": False
        },
        comment="Communication channel preferences"
    )
    
    # Profile Metadata
    last_profile_update = Column(
        DateTime(timezone=True), 
        nullable=True,
        comment="Last time profile was updated"
    )
    profile_views = Column(
        Integer, 
        default=0, 
        nullable=False,
        comment="Number of profile views (if applicable)"
    )
    
    # Social Links
    social_links = Column(
        JSONB,
        nullable=True,
        comment="Social media profile links"
    )
    
    # Custom Fields (extensible)
    custom_fields = Column(
        JSONB,
        nullable=True,
        comment="Extensible custom profile fields"
    )

    # Relationships
    user = relationship("User", back_populates="profile")

    def __repr__(self):
        return f"<UserProfile user_id={self.user_id} completion={self.profile_completion_percentage}%>"
    
    @property
    def age(self):
        """Calculate age from date of birth."""
        if self.date_of_birth:
            from datetime import date
            today = date.today()
            return today.year - self.date_of_birth.year - (
                (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day)
            )
        return None