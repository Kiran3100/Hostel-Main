# --- File: C:\Hostel-Main\app\models\inquiry\__init__.py ---
"""
Inquiry models package.

This package contains all models related to visitor inquiries,
lead management, and conversion tracking.
"""

from app.models.inquiry.inquiry import Inquiry
from app.models.inquiry.inquiry_follow_up import (
    ContactMethod,
    ContactOutcome,
    InquiryFollowUp,
)

__all__ = [
    "Inquiry",
    "InquiryFollowUp",
    "ContactMethod",
    "ContactOutcome",
]