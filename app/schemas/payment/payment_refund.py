# --- File: app/schemas/payment/payment_refund.py ---
"""
Payment refund schemas.

This module defines schemas for refund requests, approvals,
and refund management operations.
"""

from datetime import datetime
from decimal import Decimal
from typing import List, Union
from uuid import UUID

from pydantic import Field, field_validator, model_validator, computed_field

from app.schemas.common.base import BaseCreateSchema, BaseResponseSchema, BaseSchema
from app.schemas.common.enums import PaymentStatus

__all__ = [
    "RefundRequest",
    "RefundResponse",
    "RefundStatus",
    "RefundApproval",
    "RefundList",
    "RefundListItem",
]


class RefundRequest(BaseCreateSchema):
    """
    Refund request schema.
    
    Used to request a refund for a payment.
    """

    payment_id: UUID = Field(
        ...,
        description="Payment ID to refund",
    )
    refund_amount: Decimal = Field(
        ...,
        ge=0,
        description="Amount to refund",
    )
    refund_reason: str = Field(
        ...,
        min_length=10,
        max_length=500,
        description="Reason for refund",
    )
    requested_by: UUID = Field(
        ...,
        description="User requesting the refund",
    )

    # Refund Options
    initiate_immediately: bool = Field(
        False,
        description="Whether to initiate refund immediately (if approved automatically)",
    )
    notify_customer: bool = Field(
        True,
        description="Send notification to customer",
    )

    # Additional Details
    notes: Union[str, None] = Field(
        None,
        max_length=1000,
        description="Additional notes",
    )

    @field_validator("refund_amount")
    @classmethod
    def validate_refund_amount(cls, v: Decimal) -> Decimal:
        """Validate refund amount."""
        if v <= 0:
            raise ValueError("Refund amount must be greater than zero")
        return v.quantize(Decimal("0.01"))

    @field_validator("refund_reason")
    @classmethod
    def validate_refund_reason(cls, v: str) -> str:
        """Validate refund reason."""
        v = v.strip()
        if len(v) < 10:
            raise ValueError("Refund reason must be at least 10 characters")
        return v


class RefundStatus(BaseSchema):
    """
    Refund status information.
    
    Contains current status of a refund.
    """

    refund_id: UUID = Field(
        ...,
        description="Refund ID",
    )
    payment_id: UUID = Field(
        ...,
        description="Associated payment ID",
    )

    # Status
    status: str = Field(
        ...,
        description="Current refund status",
    )
    is_completed: bool = Field(
        ...,
        description="Whether refund is completed",
    )
    is_pending: bool = Field(
        ...,
        description="Whether refund is pending",
    )
    is_failed: bool = Field(
        ...,
        description="Whether refund failed",
    )

    # Amount
    refund_amount: Decimal = Field(
        ...,
        ge=0,
        description="Refund amount",
    )
    processed_amount: Union[Decimal, None] = Field(
        None,
        ge=0,
        description="Actually processed amount",
    )

    # Timestamps
    requested_at: datetime = Field(
        ...,
        description="When refund was requested",
    )
    approved_at: Union[datetime, None] = Field(
        None,
        description="When refund was approved",
    )
    processed_at: Union[datetime, None] = Field(
        None,
        description="When refund was processed",
    )
    completed_at: Union[datetime, None] = Field(
        None,
        description="When refund was completed",
    )

    # Gateway Details
    gateway_refund_id: Union[str, None] = Field(
        None,
        description="Gateway refund ID",
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def processing_time_hours(self) -> Union[float, None]:
        """Calculate processing time in hours."""
        if self.completed_at and self.requested_at:
            delta = self.completed_at - self.requested_at
            return round(delta.total_seconds() / 3600, 2)
        return None


class RefundResponse(BaseResponseSchema):
    """
    Refund response schema.
    
    Complete refund information returned in API responses.
    """

    payment_id: UUID = Field(
        ...,
        description="Associated payment ID",
    )
    payment_reference: str = Field(
        ...,
        description="Payment reference number",
    )

    # Refund Details
    refund_amount: Decimal = Field(
        ...,
        ge=0,
        description="Refund amount",
    )
    original_amount: Decimal = Field(
        ...,
        ge=0,
        description="Original payment amount",
    )
    currency: str = Field(
        ...,
        description="Currency code",
    )

    # Refund Type
    is_partial: bool = Field(
        ...,
        description="Whether this is a partial refund",
    )
    is_full: bool = Field(
        ...,
        description="Whether this is a full refund",
    )

    # Status
    refund_status: str = Field(
        ...,
        description="Current refund status",
    )

    # Reason
    refund_reason: str = Field(
        ...,
        description="Refund reason",
    )

    # Users
    requested_by: UUID = Field(
        ...,
        description="User who requested refund",
    )
    requested_by_name: str = Field(
        ...,
        description="Requester name",
    )
    approved_by: Union[UUID, None] = Field(
        None,
        description="User who approved refund",
    )
    approved_by_name: Union[str, None] = Field(
        None,
        description="Approver name",
    )

    # Timestamps
    requested_at: datetime = Field(
        ...,
        description="Request timestamp",
    )
    approved_at: Union[datetime, None] = Field(
        None,
        description="Approval timestamp",
    )
    processed_at: Union[datetime, None] = Field(
        None,
        description="Processing timestamp",
    )
    completed_at: Union[datetime, None] = Field(
        None,
        description="Completion timestamp",
    )

    # Gateway Details
    gateway_refund_id: Union[str, None] = Field(
        None,
        description="Gateway refund ID",
    )
    transaction_id: Union[str, None] = Field(
        None,
        description="Refund transaction ID",
    )

    # Notes
    notes: Union[str, None] = Field(
        None,
        description="Additional notes",
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def remaining_amount(self) -> Decimal:
        """Calculate remaining amount after refund."""
        return (self.original_amount - self.refund_amount).quantize(Decimal("0.01"))

    @computed_field  # type: ignore[prop-decorator]
    @property
    def refund_percentage(self) -> float:
        """Calculate refund percentage."""
        if self.original_amount == 0:
            return 0.0
        return round((self.refund_amount / self.original_amount) * 100, 2)


class RefundApproval(BaseSchema):
    """
    Refund approval schema.
    
    Used by administrators to approve or reject refund requests.
    """

    refund_id: UUID = Field(
        ...,
        description="Refund ID to approve/reject",
    )
    is_approved: bool = Field(
        ...,
        description="Whether refund is approved",
    )
    approved_by: UUID = Field(
        ...,
        description="User approving/rejecting",
    )

    # Approval Details
    approval_notes: Union[str, None] = Field(
        None,
        max_length=1000,
        description="Approval/rejection notes",
    )

    # Processing Options
    process_immediately: bool = Field(
        True,
        description="Process refund immediately after approval",
    )

    @field_validator("approval_notes")
    @classmethod
    def validate_approval_notes(cls, v: Union[str, None]) -> Union[str, None]:
        """Validate approval notes."""
        if v is not None:
            v = v.strip()
            if not v:
                return None
        return v


class RefundListItem(BaseSchema):
    """
    Refund list item for summary views.
    
    Optimized schema for displaying multiple refunds.
    """

    id: UUID = Field(..., description="Refund ID")
    payment_id: UUID = Field(..., description="Payment ID")
    payment_reference: str = Field(..., description="Payment reference")

    refund_amount: Decimal = Field(..., ge=0, description="Refund amount")
    original_amount: Decimal = Field(..., ge=0, description="Original amount")

    refund_status: str = Field(..., description="Refund status")
    is_partial: bool = Field(..., description="Is partial refund")

    requested_by_name: str = Field(..., description="Requester name")
    requested_at: datetime = Field(..., description="Request time")

    approved_at: Union[datetime, None] = Field(None, description="Approval time")
    completed_at: Union[datetime, None] = Field(None, description="Completion time")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def status_display(self) -> str:
        """Get user-friendly status."""
        status_map = {
            "pending": "Pending Approval",
            "approved": "Approved",
            "processing": "Processing",
            "completed": "Completed",
            "rejected": "Rejected",
            "failed": "Failed",
        }
        return status_map.get(self.refund_status.lower(), self.refund_status)


class RefundList(BaseSchema):
    """
    Paginated refund list response.
    
    Contains list of refunds with pagination metadata.
    """

    items: List[RefundListItem] = Field(
        ...,
        description="List of refunds",
    )
    total: int = Field(
        ...,
        ge=0,
        description="Total number of refunds",
    )
    page: int = Field(
        ...,
        ge=1,
        description="Current page number",
    )
    page_size: int = Field(
        ...,
        ge=1,
        description="Items per page",
    )
    pages: int = Field(
        ...,
        ge=0,
        description="Total number of pages",
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def has_next(self) -> bool:
        """Check if there's a next page."""
        return self.page < self.pages

    @computed_field  # type: ignore[prop-decorator]
    @property
    def has_previous(self) -> bool:
        """Check if there's a previous page."""
        return self.page > 1