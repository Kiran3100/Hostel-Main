"""
Inquiry repositories package.

This package contains all repository implementations for inquiry management,
follow-up tracking, and analytics.
"""

from app.repositories.inquiry.inquiry_repository import InquiryRepository
from app.repositories.inquiry.inquiry_follow_up_repository import InquiryFollowUpRepository
from app.repositories.inquiry.inquiry_aggregate_repository import InquiryAggregateRepository

__all__ = [
    "InquiryRepository",
    "InquiryFollowUpRepository",
    "InquiryAggregateRepository",
]