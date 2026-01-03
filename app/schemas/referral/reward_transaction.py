# --- File: app/schemas/referral/reward_transaction.py ---
"""
Reward transaction tracking schemas.

This module provides schemas for individual reward transactions
including credits, debits, and balance tracking.
"""

from datetime import datetime
from decimal import Decimal
from typing import Union, Dict, Any
from uuid import UUID

from pydantic import Field, field_validator

from app.schemas.common.base import BaseResponseSchema, BaseSchema

__all__ = [
    "RewardTransaction",
    "RewardTransactionDetail",
]


class RewardTransaction(BaseResponseSchema):
    """
    Individual reward transaction record.
    
    Represents a single credit or debit in the reward ledger.
    """
    
    transaction_id: UUID = Field(
        ...,
        description="Unique transaction identifier",
    )
    user_id: UUID = Field(
        ...,
        description="User ID",
    )
    
    # Transaction details
    transaction_type: str = Field(
        ...,
        pattern="^(earned|paid|pending|reversed|cancelled)$",
        description="Type of transaction",
    )
    amount: Decimal = Field(
        ...,
        description="Transaction amount (positive for credit, negative for debit)",
    )
    currency: str = Field(
        default="INR",
        min_length=3,
        max_length=3,
        description="Currency code",
    )
    
    # Balance tracking
    balance_before: Decimal = Field(
        ...,
        ge=0,
        description="Balance before this transaction",
    )
    balance_after: Decimal = Field(
        ...,
        ge=0,
        description="Balance after this transaction",
    )
    
    # Source information
    referral_id: Union[UUID, None] = Field(
        None,
        description="Associated referral ID (for earned rewards)",
    )
    payout_id: Union[UUID, None] = Field(
        None,
        description="Associated payout ID (for paid/pending)",
    )
    program_id: Union[UUID, None] = Field(
        None,
        description="Associated program ID",
    )
    
    # Description and metadata
    description: str = Field(
        ...,
        max_length=500,
        description="Transaction description",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional transaction metadata",
    )
    
    # Status
    status: str = Field(
        ...,
        pattern="^(completed|pending|reversed|failed)$",
        description="Transaction status",
    )
    
    # Timestamps
    transaction_date: datetime = Field(
        ...,
        description="Transaction timestamp",
    )
    created_at: datetime = Field(
        ...,
        description="Record creation timestamp",
    )
    
    @field_validator("amount", "balance_before", "balance_after")
    @classmethod
    def validate_decimal_places(cls, v: Decimal) -> Decimal:
        """Ensure decimal values have at most 2 decimal places."""
        return v.quantize(Decimal("0.01"))


class RewardTransactionDetail(RewardTransaction):
    """
    Detailed reward transaction information.
    
    Extends base transaction with additional context and audit information.
    """
    
    # User information
    user_name: str = Field(
        ...,
        description="User name",
    )
    user_email: Union[str, None] = Field(
        None,
        description="User email",
    )
    
    # Program information (if applicable)
    program_name: Union[str, None] = Field(
        None,
        description="Associated program name",
    )
    
    # Referral information (if applicable)
    referrer_name: Union[str, None] = Field(
        None,
        description="Referrer name (for earned rewards)",
    )
    referee_name: Union[str, None] = Field(
        None,
        description="Referee name (for earned rewards)",
    )
    
    # Payout information (if applicable)
    payout_method: Union[str, None] = Field(
        None,
        description="Payout method (for paid transactions)",
    )
    payout_reference: Union[str, None] = Field(
        None,
        description="External payout reference",
    )
    
    # Audit information
    processed_by: Union[UUID, None] = Field(
        None,
        description="Admin user who processed this transaction",
    )
    processed_by_name: Union[str, None] = Field(
        None,
        description="Name of admin who processed",
    )
    
    # Notes
    admin_notes: Union[str, None] = Field(
        None,
        max_length=2000,
        description="Admin notes",
    )