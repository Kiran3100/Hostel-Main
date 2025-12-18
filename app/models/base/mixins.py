# --- File: C:\Hostel-Main\app\models\base\mixins.py ---
"""
SQLAlchemy model mixins for reusable functionality.

Provides mixins that mirror the schema mixins for consistent
field definitions across models.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import uuid4

from sqlalchemy import Column, DateTime, Boolean, String, Numeric, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.sql import func
from sqlalchemy.orm import validates


class TimestampMixin:
    """
    Mixin for automatic timestamp tracking.
    
    Provides created_at and updated_at fields with
    automatic timezone-aware timestamp management.
    """
    
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
        comment="Record creation timestamp (UTC)"
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="Record last update timestamp (UTC)"
    )


class SoftDeleteMixin:
    """
    Mixin for soft delete capability.
    
    Provides is_deleted flag and deleted_at timestamp
    for logical deletion without data loss.
    """
    
    is_deleted = Column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="Soft delete flag"
    )
    deleted_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Deletion timestamp (UTC)"
    )
    deleted_by = Column(
        PG_UUID(as_uuid=True),
        nullable=True,
        comment="User who deleted the record"
    )


class UUIDMixin:
    """
    Mixin for UUID primary key.
    
    Provides UUID-based primary key with automatic
    generation using uuid4.
    """
    
    id = Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        index=True,
        comment="Unique identifier (UUID v4)"
    )


class AddressMixin:
    """
    Mixin for standardized address fields.
    
    Provides complete address structure with validation.
    """
    
    address_line1 = Column(
        String(255),
        nullable=True,
        comment="Street address line 1"
    )
    address_line2 = Column(
        String(255),
        nullable=True,
        comment="Street address line 2"
    )
    city = Column(
        String(100),
        nullable=True,
        index=True,
        comment="City name"
    )
    state = Column(
        String(100),
        nullable=True,
        index=True,
        comment="State/Province"
    )
    country = Column(
        String(100),
        nullable=True,
        index=True,
        comment="Country name"
    )
    postal_code = Column(
        String(20),
        nullable=True,
        index=True,
        comment="Postal/ZIP code"
    )
    
    @validates('postal_code')
    def validate_postal_code(self, key: str, value: Optional[str]) -> Optional[str]:
        """Validate and normalize postal code."""
        if value:
            return value.strip().upper()
        return value


class ContactMixin:
    """
    Mixin for phone and email contact fields.
    
    Provides standardized contact information with validation.
    """
    
    phone = Column(
        String(20),
        nullable=True,
        index=True,
        comment="Primary phone number"
    )
    alternate_phone = Column(
        String(20),
        nullable=True,
        comment="Alternate phone number"
    )
    email = Column(
        String(255),
        nullable=True,
        index=True,
        comment="Email address"
    )
    
    @validates('email')
    def validate_email(self, key: str, value: Optional[str]) -> Optional[str]:
        """Validate and normalize email."""
        if value:
            import re
            value = value.strip().lower()
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, value):
                raise ValueError(f"Invalid email format: {value}")
        return value
    
    @validates('phone', 'alternate_phone')
    def validate_phone(self, key: str, value: Optional[str]) -> Optional[str]:
        """Validate and normalize phone number."""
        if value:
            # Remove non-numeric characters
            import re
            cleaned = re.sub(r'\D', '', value)
            if len(cleaned) < 10:
                raise ValueError(f"Phone number too short: {value}")
            return cleaned
        return value


class LocationMixin:
    """
    Mixin for geographic location fields.
    
    Provides latitude, longitude, and geohash for
    spatial queries and location-based features.
    """
    
    latitude = Column(
        Numeric(10, 7),
        nullable=True,
        comment="Latitude coordinate"
    )
    longitude = Column(
        Numeric(10, 7),
        nullable=True,
        comment="Longitude coordinate"
    )
    geohash = Column(
        String(20),
        nullable=True,
        index=True,
        comment="Geohash for spatial indexing"
    )
    
    @validates('latitude')
    def validate_latitude(self, key: str, value: Optional[Decimal]) -> Optional[Decimal]:
        """Validate latitude range."""
        if value is not None:
            if value < -90 or value > 90:
                raise ValueError(f"Latitude must be between -90 and 90: {value}")
        return value
    
    @validates('longitude')
    def validate_longitude(self, key: str, value: Optional[Decimal]) -> Optional[Decimal]:
        """Validate longitude range."""
        if value is not None:
            if value < -180 or value > 180:
                raise ValueError(f"Longitude must be between -180 and 180: {value}")
        return value


class MediaMixin:
    """
    Mixin for media URL handling.
    
    Provides fields for image, video, and document URLs.
    """
    
    image_url = Column(
        String(500),
        nullable=True,
        comment="Primary image URL"
    )
    thumbnail_url = Column(
        String(500),
        nullable=True,
        comment="Thumbnail image URL"
    )
    video_url = Column(
        String(500),
        nullable=True,
        comment="Video URL"
    )
    document_url = Column(
        String(500),
        nullable=True,
        comment="Document URL"
    )


class EmergencyContactMixin:
    """
    Mixin for emergency contact information.
    
    Provides standardized emergency contact fields.
    """
    
    emergency_contact_name = Column(
        String(255),
        nullable=True,
        comment="Emergency contact full name"
    )
    emergency_contact_relationship = Column(
        String(50),
        nullable=True,
        comment="Relationship to emergency contact"
    )
    emergency_contact_phone = Column(
        String(20),
        nullable=True,
        comment="Emergency contact phone number"
    )
    emergency_contact_email = Column(
        String(255),
        nullable=True,
        comment="Emergency contact email"
    )
    
    @validates('emergency_contact_phone')
    def validate_emergency_phone(self, key: str, value: Optional[str]) -> Optional[str]:
        """Validate emergency contact phone."""
        if value:
            import re
            cleaned = re.sub(r'\D', '', value)
            if len(cleaned) < 10:
                raise ValueError(f"Emergency phone too short: {value}")
            return cleaned
        return value


class AuditMixin:
    """
    Mixin for audit trail fields.
    
    Tracks who created/updated records and from where.
    """
    
    created_by = Column(
        PG_UUID(as_uuid=True),
        nullable=True,
        index=True,
        comment="User who created the record"
    )
    updated_by = Column(
        PG_UUID(as_uuid=True),
        nullable=True,
        index=True,
        comment="User who last updated the record"
    )
    ip_address = Column(
        String(45),
        nullable=True,
        comment="IP address of last modification"
    )


class ApprovalMixin:
    """
    Mixin for approval workflow fields.
    
    Provides approval status tracking and workflow support.
    """
    
    approval_status = Column(
        String(20),
        nullable=False,
        default="pending",
        index=True,
        comment="Current approval status"
    )
    approved_by = Column(
        PG_UUID(as_uuid=True),
        nullable=True,
        index=True,
        comment="User who approved"
    )
    approved_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Approval timestamp"
    )
    rejection_reason = Column(
        Text,
        nullable=True,
        comment="Reason for rejection"
    )
    
    @validates('approval_status')
    def validate_approval_status(self, key: str, value: str) -> str:
        """Validate approval status."""
        valid_statuses = ['pending', 'approved', 'rejected', 'cancelled']
        if value not in valid_statuses:
            raise ValueError(f"Invalid approval status: {value}")
        return value


class SEOMixin:
    """
    Mixin for SEO metadata fields.
    
    Provides meta title, description, and keywords
    for public-facing content.
    """
    
    meta_title = Column(
        String(255),
        nullable=True,
        comment="SEO meta title"
    )
    meta_description = Column(
        Text,
        nullable=True,
        comment="SEO meta description"
    )
    meta_keywords = Column(
        String(500),
        nullable=True,
        comment="SEO keywords (comma-separated)"
    )
    slug = Column(
        String(255),
        nullable=True,
        unique=True,
        index=True,
        comment="URL-friendly slug"
    )
    
    @validates('slug')
    def validate_slug(self, key: str, value: Optional[str]) -> Optional[str]:
        """Validate and normalize slug."""
        if value:
            import re
            # Convert to lowercase and replace spaces/special chars with hyphens
            slug = value.lower().strip()
            slug = re.sub(r'[^\w\s-]', '', slug)
            slug = re.sub(r'[-\s]+', '-', slug)
            return slug
        return value


class VersionMixin:
    """
    Mixin for version control.
    
    Provides version number tracking for versioned entities.
    """
    
    version = Column(
        Integer,
        nullable=False,
        default=1,
        comment="Version number"
    )
    is_current_version = Column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
        comment="Is this the current version"
    )
    version_notes = Column(
        Text,
        nullable=True,
        comment="Version change notes"
    )


class PriorityMixin:
    """
    Mixin for priority and urgency tracking.
    
    Provides priority level and urgency fields.
    """
    
    priority_level = Column(
        String(20),
        nullable=False,
        default="medium",
        index=True,
        comment="Priority level"
    )
    urgency = Column(
        String(20),
        nullable=False,
        default="normal",
        index=True,
        comment="Urgency level"
    )
    
    @validates('priority_level')
    def validate_priority(self, key: str, value: str) -> str:
        """Validate priority level."""
        valid_priorities = ['low', 'medium', 'high', 'urgent', 'critical']
        if value not in valid_priorities:
            raise ValueError(f"Invalid priority level: {value}")
        return value


class StatusMixin:
    """
    Mixin for status tracking.
    
    Provides status field with validation.
    """
    
    status = Column(
        String(50),
        nullable=False,
        default="active",
        index=True,
        comment="Current status"
    )
    status_changed_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Last status change timestamp"
    )
    status_changed_by = Column(
        PG_UUID(as_uuid=True),
        nullable=True,
        comment="User who changed status"
    )