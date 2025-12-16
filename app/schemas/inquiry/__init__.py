"""
Visitor inquiry and contact schemas package.

This module exports all inquiry-related schemas for easy importing
across the application.

Migrated to Pydantic v2 with full compatibility.
"""

from app.schemas.inquiry.inquiry_base import (
    InquiryBase,
    InquiryCreate,
    InquiryUpdate,
)
from app.schemas.inquiry.inquiry_filters import (
    InquiryExportRequest,
    InquiryFilterParams,
    InquirySearchRequest,
    InquirySortOptions,
)
from app.schemas.inquiry.inquiry_response import (
    InquiryDetail,
    InquiryListItem,
    InquiryResponse,
    InquiryStats,
)
from app.schemas.inquiry.inquiry_status import (
    BulkInquiryStatusUpdate,
    InquiryAssignment,
    InquiryConversion,
    InquiryFollowUp,
    InquiryStatusUpdate,
    InquiryTimelineEntry,
)

__all__ = [
    # Base schemas
    "InquiryBase",
    "InquiryCreate",
    "InquiryUpdate",
    # Response
    "InquiryResponse",
    "InquiryDetail",
    "InquiryListItem",
    "InquiryStats",
    # Status Management
    "InquiryStatusUpdate",
    "InquiryAssignment",
    "InquiryFollowUp",
    "InquiryTimelineEntry",
    "InquiryConversion",
    "BulkInquiryStatusUpdate",
    # Filters
    "InquiryFilterParams",
    "InquirySearchRequest",
    "InquirySortOptions",
    "InquiryExportRequest",
]