# --- File: app/schemas/payment/payment_status.py ---
"""
Payment status management schemas.

This module defines schemas for payment status updates, cancellations,
and bulk status operations.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import Field, field_validator

from app.schemas.common.base import BaseSchema
from app.schemas.common.enums import PaymentStatus

__all__ = [
    "PaymentStatusUpdate",
    "BulkPaymentStatusUpdate",
    "PaymentCancellation",
    "StatusUpdateResponse",
    "BulkStatusUpdateResponse",
]


class PaymentStatusUpdate(BaseSchema):
    """
    Payment status update schema.
    
    Used to update the status of a payment with optional metadata.
    """

    status: PaymentStatus = Field(
        ...,
        description="New payment status",
    )
    reason: Optional[str] = Field(
        None,
        max_length=500,
        description="Reason for status change",
    )
    transaction_id: Optional[str] = Field(
        None,
        max_length=100,
        description="Transaction ID if applicable",
    )
    gateway_response: Optional[Dict[str, Any]] = Field(
        None,
        description="Gateway response data if applicable",
    )
    notes: Optional[str] = Field(
        None,
        max_length=1000,
        description="Additional notes",
    )

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, v: Optional[str]) -> Optional[str]:
        """Validate reason based on status."""
        if v is not None:
            v = v.strip()
            if len(v) < 3:
                raise ValueError("Reason must be at least 3 characters")
        return v


class BulkPaymentStatusUpdate(BaseSchema):
    """
    Bulk payment status update schema.
    
    Used to update status for multiple payments at once.
    """

    payment_ids: List[UUID] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="List of payment IDs to update (max 100)",
    )
    status: PaymentStatus = Field(
        ...,
        description="New status for all payments",
    )
    reason: Optional[str] = Field(
        None,
        max_length=500,
        description="Reason for bulk status change",
    )
    notes: Optional[str] = Field(
        None,
        max_length=1000,
        description="Additional notes",
    )

    @field_validator("payment_ids")
    @classmethod
    def validate_payment_ids(cls, v: List[UUID]) -> List[UUID]:
        """Validate payment IDs list."""
        if len(v) == 0:
            raise ValueError("At least one payment ID is required")
        
        if len(v) > 100:
            raise ValueError("Maximum 100 payments allowed per bulk operation")
        
        # Check for duplicates
        if len(v) != len(set(v)):
            raise ValueError("Duplicate payment IDs found")
        
        return v

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, v: Optional[str]) -> Optional[str]:
        """Validate reason."""
        if v is not None:
            v = v.strip()
            if len(v) < 10:
                raise ValueError(
                    "Reason for bulk status update must be at least 10 characters"
                )
        return v


class PaymentCancellation(BaseSchema):
    """
    Payment cancellation schema.
    
    Used to cancel a payment with detailed information.
    """

    payment_id: UUID = Field(
        ...,
        description="Payment ID to cancel",
    )
    cancellation_reason: str = Field(
        ...,
        min_length=10,
        max_length=500,
        description="Detailed reason for cancellation",
    )
    refund_if_paid: bool = Field(
        False,
        description="Whether to initiate refund if payment is already completed",
    )
    notify_payer: bool = Field(
        True,
        description="Whether to send cancellation notification to payer",
    )
    internal_notes: Optional[str] = Field(
        None,
        max_length=1000,
        description="Internal notes (not visible to payer)",
    )

    @field_validator("cancellation_reason")
    @classmethod
    def validate_cancellation_reason(cls, v: str) -> str:
        """Validate cancellation reason."""
        v = v.strip()
        if len(v) < 10:
            raise ValueError("Cancellation reason must be at least 10 characters")
        return v


class StatusUpdateResponse(BaseSchema):
    """
    Response after status update.
    
    Contains confirmation and updated payment details.
    """

    payment_id: UUID = Field(
        ...,
        description="Payment ID",
    )
    previous_status: PaymentStatus = Field(
        ...,
        description="Previous payment status",
    )
    new_status: PaymentStatus = Field(
        ...,
        description="New payment status",
    )
    updated_at: datetime = Field(
        ...,
        description="Timestamp of update",
    )
    updated_by: UUID = Field(
        ...,
        description="User who performed the update",
    )
    is_successful: bool = Field(
        ...,
        description="Whether status update was successful",
    )
    message: Optional[str] = Field(
        None,
        description="Status update message",
    )


class BulkStatusUpdateResponse(BaseSchema):
    """
    Response after bulk status update.
    
    Contains summary of bulk operation results.
    """

    total_requested: int = Field(
        ...,
        ge=0,
        description="Total payments requested for update",
    )
    successful_updates: int = Field(
        ...,
        ge=0,
        description="Number of successful updates",
    )
    failed_updates: int = Field(
        ...,
        ge=0,
        description="Number of failed updates",
    )
    updated_payment_ids: List[UUID] = Field(
        default_factory=list,
        description="List of successfully updated payment IDs",
    )
    failed_payment_ids: List[UUID] = Field(
        default_factory=list,
        description="List of payment IDs that failed to update",
    )
    errors: Optional[List[Dict[str, Any]]] = Field(
        None,
        description="List of errors encountered",
    )
    new_status: PaymentStatus = Field(
        ...,
        description="The status that was applied",
    )