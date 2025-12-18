"""
User model configuration.
"""
from sqlalchemy import Boolean, Column, DateTime, Enum, Integer, String, Text
from sqlalchemy.orm import relationship

from app.models.base.base_model import BaseModel
from app.models.common.mixins import SoftDeleteMixin, TimestampMixin, UUIDMixin
from app.schemas.common.enums import UserRole

class User(BaseModel, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    """
    Core User entity.
    
    Manages authentication credentials, role-based access control,
    and links to detailed profile information. Serves as the root
    entity for Student, Admin, Supervisor, and Visitor roles.
    """
    __tablename__ = "users"
    __table_args__ = (
        {"comment": "Core user authentication and identity management"}
    )

    # Authentication & Identity
    email = Column(
        String(255), 
        unique=True, 
        index=True, 
        nullable=False,
        comment="Unique email address (normalized to lowercase)"
    )
    phone = Column(
        String(20), 
        unique=True, 
        index=True, 
        nullable=False,
        comment="Unique phone number (E.164 format)"
    )
    full_name = Column(
        String(255), 
        nullable=False, 
        index=True,
        comment="Full name of the user"
    )
    password_hash = Column(
        String(255), 
        nullable=False,
        comment="Bcrypt hashed password"
    )
    
    # Role & Access Control
    user_role = Column(
        Enum(UserRole), 
        nullable=False, 
        default=UserRole.STUDENT,
        index=True,
        comment="Primary user role for RBAC"
    )
    
    # Account Status & Verification
    is_active = Column(
        Boolean, 
        default=True, 
        nullable=False,
        index=True,
        comment="Account active status (can login)"
    )
    is_email_verified = Column(
        Boolean, 
        default=False, 
        nullable=False,
        comment="Email verification status"
    )
    is_phone_verified = Column(
        Boolean, 
        default=False, 
        nullable=False,
        comment="Phone verification status"
    )
    email_verified_at = Column(
        DateTime(timezone=True), 
        nullable=True,
        comment="Timestamp of email verification"
    )
    phone_verified_at = Column(
        DateTime(timezone=True), 
        nullable=True,
        comment="Timestamp of phone verification"
    )
    
    # Security Tracking
    last_login_at = Column(
        DateTime(timezone=True), 
        nullable=True,
        index=True,
        comment="Last successful login timestamp"
    )
    last_password_change_at = Column(
        DateTime(timezone=True), 
        nullable=True,
        comment="Last password change timestamp"
    )
    failed_login_attempts = Column(
        Integer, 
        default=0, 
        nullable=False,
        comment="Consecutive failed login attempts for lockout"
    )
    account_locked_until = Column(
        DateTime(timezone=True), 
        nullable=True,
        comment="Account lockout expiration timestamp"
    )
    
    # Password Management
    password_reset_required = Column(
        Boolean, 
        default=False,
        comment="Force password reset on next login"
    )
    
    # Terms & Privacy
    terms_accepted_at = Column(
        DateTime(timezone=True), 
        nullable=True,
        comment="Terms of service acceptance timestamp"
    )
    privacy_policy_accepted_at = Column(
        DateTime(timezone=True), 
        nullable=True,
        comment="Privacy policy acceptance timestamp"
    )
    
    # Account Metadata
    registration_ip = Column(
        String(45), 
        nullable=True,
        comment="IP address at registration"
    )
    registration_source = Column(
        String(50), 
        nullable=True,
        comment="Registration source (web, mobile, admin)"
    )
    referral_code = Column(
        String(50), 
        nullable=True,
        index=True,
        comment="Referral code used during registration"
    )
    
    # Deactivation/Deletion
    deactivated_at = Column(
        DateTime(timezone=True), 
        nullable=True,
        comment="Account deactivation timestamp"
    )
    deactivation_reason = Column(
        Text, 
        nullable=True,
        comment="Reason for account deactivation"
    )

    # Relationships (1-to-1)
    profile = relationship(
        "UserProfile", 
        back_populates="user", 
        uselist=False, 
        cascade="all, delete-orphan",
        lazy="joined"
    )
    address = relationship(
        "UserAddress", 
        back_populates="user", 
        uselist=False, 
        cascade="all, delete-orphan"
    )
    emergency_contact = relationship(
        "EmergencyContact", 
        back_populates="user", 
        uselist=False, 
        cascade="all, delete-orphan"
    )
    
    # Relationships (1-to-Many)
    sessions = relationship(
        "UserSession", 
        back_populates="user", 
        cascade="all, delete-orphan",
        order_by="desc(UserSession.last_activity)"
    )
    login_history = relationship(
        "LoginHistory", 
        back_populates="user", 
        cascade="all, delete-orphan",
        order_by="desc(LoginHistory.created_at)"
    )
    password_history = relationship(
        "PasswordHistory", 
        back_populates="user", 
        cascade="all, delete-orphan"
    )
    
    # Role-specific relationships (defined with string references to avoid circular imports)
    admin_profile = relationship(
        "AdminUser", 
        back_populates="user", 
        uselist=False,
        cascade="all, delete-orphan"
    )
    supervisor_profile = relationship(
        "Supervisor", 
        back_populates="user", 
        uselist=False,
        cascade="all, delete-orphan"
    )
    student_profile = relationship(
        "Student", 
        back_populates="user", 
        uselist=False,
        cascade="all, delete-orphan"
    )
    visitor_profile = relationship(
        "Visitor", 
        back_populates="user", 
        uselist=False,
        cascade="all, delete-orphan"
    )
    
    # Activity relationships
    notifications = relationship(
        "Notification",
        foreign_keys="[Notification.user_id]",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self):
        return f"<User {self.email} ({self.user_role.value})>"
    
    @property
    def is_verified(self):
        """Check if both email and phone are verified."""
        return self.is_email_verified and self.is_phone_verified
    
    @property
    def is_locked(self):
        """Check if account is currently locked."""
        if self.account_locked_until:
            from datetime import datetime, timezone
            return datetime.now(timezone.utc) < self.account_locked_until
        return False