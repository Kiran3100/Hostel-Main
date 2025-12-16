# --- File: app/schemas/common/mixins.py ---
"""
Reusable schema mixins for address, contact info, media, audit, etc.
"""

from datetime import datetime
from typing import List, Union
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl

__all__ = [
    "AddressMixin",
    "ContactMixin",
    "LocationMixin",
    "MediaMixin",
    "EmergencyContactMixin",
    "AuditMixin",
    "ApprovalMixin",
    "SEOMixin",
]


class AddressMixin(BaseModel):
    """Address fields mixin."""

    address_line1: str = Field(
        ...,
        min_length=5,
        max_length=255,
        description="Address line 1",
    )
    address_line2: Union[str, None] = Field(
        default=None,
        max_length=255,
        description="Address line 2",
    )
    city: str = Field(
        ...,
        min_length=2,
        max_length=100,
        description="City",
    )
    state: str = Field(
        ...,
        min_length=2,
        max_length=100,
        description="State",
    )
    pincode: str = Field(
        ...,
        pattern=r"^\d{6}$",
        description="6-digit pincode",
    )
    country: str = Field(
        default="India",
        min_length=2,
        max_length=100,
        description="Country",
    )


class ContactMixin(BaseModel):
    """Contact information mixin."""

    contact_phone: str = Field(
        ...,
        pattern=r"^\+?[1-9]\d{9,14}$",
        description="Primary contact phone",
    )
    alternate_phone: Union[str, None] = Field(
        default=None,
        pattern=r"^\+?[1-9]\d{9,14}$",
        description="Alternate phone",
    )
    contact_email: Union[str, None] = Field(
        default=None,
        description="Contact email",
    )


class LocationMixin(BaseModel):
    """Geographic location mixin."""

    latitude: Union[float, None] = Field(
        default=None,
        ge=-90,
        le=90,
        description="Latitude",
    )
    longitude: Union[float, None] = Field(
        default=None,
        ge=-180,
        le=180,
        description="Longitude",
    )


class MediaMixin(BaseModel):
    """Media URLs mixin."""

    images: List[HttpUrl] = Field(
        default_factory=list,
        description="Image URLs",
    )
    videos: List[HttpUrl] = Field(
        default_factory=list,
        description="Video URLs",
    )
    documents: List[HttpUrl] = Field(
        default_factory=list,
        description="Document URLs",
    )


class EmergencyContactMixin(BaseModel):
    """Emergency contact mixin."""

    emergency_contact_name: Union[str, None] = Field(
        default=None,
        description="Emergency contact name",
    )
    emergency_contact_phone: Union[str, None] = Field(
        default=None,
        pattern=r"^\+?[1-9]\d{9,14}$",
        description="Emergency contact phone",
    )
    emergency_contact_relation: Union[str, None] = Field(
        default=None,
        description="Relation to person",
    )


class AuditMixin(BaseModel):
    """Audit trail mixin."""

    created_by: Union[UUID, None] = Field(
        default=None,
        description="User who created the record",
    )
    updated_by: Union[UUID, None] = Field(
        default=None,
        description="User who last updated the record",
    )


class ApprovalMixin(BaseModel):
    """Approval workflow mixin."""

    approved_by: Union[UUID, None] = Field(
        default=None,
        description="User who approved",
    )
    approved_at: Union[datetime, None] = Field(
        default=None,
        description="Approval timestamp",
    )
    rejection_reason: Union[str, None] = Field(
        default=None,
        description="Reason for rejection",
    )


class SEOMixin(BaseModel):
    """SEO fields mixin."""

    meta_title: Union[str, None] = Field(
        default=None,
        max_length=255,
        description="SEO meta title",
    )
    meta_description: Union[str, None] = Field(
        default=None,
        max_length=500,
        description="SEO meta description",
    )
    meta_keywords: Union[str, None] = Field(
        default=None,
        max_length=500,
        description="SEO keywords",
    )