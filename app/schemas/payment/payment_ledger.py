# --- File: app/schemas/payment/payment_ledger.py ---
"""
Payment ledger schemas.

This module defines schemas for payment ledger entries, account statements,
transaction history, and balance adjustments.
"""

from __future__ import annotations

from datetime import date as Date, datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from pydantic import Field, field_validator, model_validator, computed_field

from app.schemas.common.base import BaseCreateSchema, BaseResponseSchema, BaseSchema
from app.schemas.common.enums import PaymentType

__all__ = [
    "LedgerEntry",
    "LedgerSummary",
    "AccountStatement",
    "TransactionHistory",
    "TransactionItem",
    "BalanceAdjustment",
    "WriteOff",
]


class LedgerEntry(BaseResponseSchema):
    """
    Ledger entry schema.
    
    Represents a single entry in the payment ledger.
    """

    # Entity Reference
    student_id: UUID = Field(
        ...,
        description="Student ID",
    )
    hostel_id: UUID = Field(
        ...,
        description="Hostel ID",
    )

    # Entry Details
    entry_type: str = Field(
        ...,
        pattern=r"^(debit|credit|adjustment|writeoff)$",
        description="Type of ledger entry",
    )
    transaction_type: str = Field(
        ...,
        description="Specific transaction type",
    )

    # Amount
    amount: Decimal = Field(
        ...,
        description="Transaction amount (positive for credit, negative for debit)",
    )
    currency: str = Field(
        ...,
        min_length=3,
        max_length=3,
        description="Currency code",
    )

    # Balance
    balance_before: Decimal = Field(
        ...,
        description="Balance before this transaction",
    )
    balance_after: Decimal = Field(
        ...,
        description="Balance after this transaction",
    )

    # References
    payment_id: Optional[UUID] = Field(
        None,
        description="Associated payment ID",
    )
    payment_reference: Optional[str] = Field(
        None,
        description="Payment reference number",
    )
    reference_number: str = Field(
        ...,
        description="Unique ledger entry reference",
    )

    # Description
    description: str = Field(
        ...,
        max_length=500,
        description="Entry description",
    )
    notes: Optional[str] = Field(
        None,
        max_length=1000,
        description="Additional notes",
    )

    # Timestamps
    transaction_date: Date = Field(
        ...,
        description="Transaction date",
    )
    posted_at: datetime = Field(
        ...,
        description="When entry was posted to ledger",
    )

    # Audit
    posted_by: UUID = Field(
        ...,
        description="User who posted this entry",
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_debit(self) -> bool:
        """Check if this is a debit entry."""
        return self.entry_type == "debit" or self.amount < 0

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_credit(self) -> bool:
        """Check if this is a credit entry."""
        return self.entry_type == "credit" or self.amount > 0

    @computed_field  # type: ignore[prop-decorator]
    @property
    def absolute_amount(self) -> Decimal:
        """Get absolute value of amount."""
        return abs(self.amount)


class TransactionItem(BaseSchema):
    """
    Transaction item for account statement.
    
    Simplified transaction view for statements.
    """

    transaction_date: Date = Field(
        ...,
        description="Transaction date",
    )
    reference_number: str = Field(
        ...,
        description="Transaction reference",
    )
    description: str = Field(
        ...,
        description="Transaction description",
    )

    # Amount columns
    debit: Optional[Decimal] = Field(
        None,
        ge=0,
        description="Debit amount",
    )
    credit: Optional[Decimal] = Field(
        None,
        ge=0,
        description="Credit amount",
    )
    balance: Decimal = Field(
        ...,
        description="Running balance",
    )

    # Related Payment
    payment_reference: Optional[str] = Field(
        None,
        description="Payment reference if applicable",
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def transaction_type(self) -> str:
        """Determine transaction type."""
        if self.debit:
            return "debit"
        elif self.credit:
            return "credit"
        else:
            return "adjustment"


class AccountStatement(BaseSchema):
    """
    Account statement schema.
    
    Complete account statement for a student.
    """

    # Student Information
    student_id: UUID = Field(
        ...,
        description="Student ID",
    )
    student_name: str = Field(
        ...,
        description="Student name",
    )
    student_email: str = Field(
        ...,
        description="Student email",
    )

    # Hostel Information
    hostel_id: UUID = Field(
        ...,
        description="Hostel ID",
    )
    hostel_name: str = Field(
        ...,
        description="Hostel name",
    )

    # Statement Period
    period_start: Date = Field(
        ...,
        description="Statement period start",
    )
    period_end: Date = Field(
        ...,
        description="Statement period end",
    )

    # Opening/Closing Balance
    opening_balance: Decimal = Field(
        ...,
        description="Opening balance",
    )
    closing_balance: Decimal = Field(
        ...,
        description="Closing balance",
    )

    # Transactions
    transactions: List[TransactionItem] = Field(
        ...,
        description="List of transactions",
    )

    # Summary
    total_debits: Decimal = Field(
        ...,
        ge=0,
        description="Total debit amount",
    )
    total_credits: Decimal = Field(
        ...,
        ge=0,
        description="Total credit amount",
    )
    total_payments: Decimal = Field(
        ...,
        ge=0,
        description="Total payments received",
    )
    total_charges: Decimal = Field(
        ...,
        ge=0,
        description="Total charges",
    )

    # Generated Metadata
    generated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When statement was generated",
    )
    statement_number: str = Field(
        ...,
        description="Unique statement number",
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def net_movement(self) -> Decimal:
        """Calculate net movement during period."""
        return (self.closing_balance - self.opening_balance).quantize(Decimal("0.01"))

    @computed_field  # type: ignore[prop-decorator]
    @property
    def transaction_count(self) -> int:
        """Get total number of transactions."""
        return len(self.transactions)


class LedgerSummary(BaseSchema):
    """
    Ledger summary schema.
    
    Provides summary of ledger for a student or hostel.
    """

    # Entity Information
    entity_id: UUID = Field(
        ...,
        description="Entity ID (student or hostel)",
    )
    entity_type: str = Field(
        ...,
        pattern=r"^(student|hostel)$",
        description="Entity type",
    )

    # Current Balance
    current_balance: Decimal = Field(
        ...,
        description="Current balance",
    )
    currency: str = Field(
        ...,
        description="Currency code",
    )

    # Balance Status
    is_in_credit: bool = Field(
        ...,
        description="Whether account is in credit",
    )
    is_in_debit: bool = Field(
        ...,
        description="Whether account is in debit",
    )

    # Totals (All Time)
    total_charges: Decimal = Field(
        ...,
        ge=0,
        description="Total charges (all time)",
    )
    total_payments: Decimal = Field(
        ...,
        ge=0,
        description="Total payments (all time)",
    )
    total_adjustments: Decimal = Field(
        Decimal("0.00"),
        description="Total adjustments (all time)",
    )
    total_writeoffs: Decimal = Field(
        Decimal("0.00"),
        ge=0,
        description="Total write-offs (all time)",
    )

    # Outstanding
    outstanding_amount: Decimal = Field(
        ...,
        ge=0,
        description="Current outstanding amount",
    )
    overdue_amount: Decimal = Field(
        ...,
        ge=0,
        description="Overdue amount",
    )

    # Last Activity
    last_payment_date: Optional[Date] = Field(
        None,
        description="Date of last payment",
    )
    last_charge_date: Optional[Date] = Field(
        None,
        description="Date of last charge",
    )
    last_transaction_date: Optional[Date] = Field(
        None,
        description="Date of last transaction",
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def balance_status(self) -> str:
        """Get balance status description."""
        if self.current_balance > 0:
            return "credit"
        elif self.current_balance < 0:
            return "debit"
        else:
            return "zero"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def payment_ratio(self) -> float:
        """Calculate payment to charges ratio."""
        if self.total_charges == 0:
            return 0.0
        return round((self.total_payments / self.total_charges) * 100, 2)


class TransactionHistory(BaseSchema):
    """
    Transaction history request/response.
    
    Paginated transaction history for an entity.
    """

    # Entity
    entity_id: UUID = Field(
        ...,
        description="Entity ID",
    )
    entity_type: str = Field(
        ...,
        pattern=r"^(student|hostel)$",
        description="Entity type",
    )

    # Filter Period
    period_start: Optional[Date] = Field(
        None,
        description="Filter from this date",
    )
    period_end: Optional[Date] = Field(
        None,
        description="Filter to this date",
    )

    # Transactions
    transactions: List[LedgerEntry] = Field(
        ...,
        description="List of ledger entries",
    )

    # Pagination
    total: int = Field(
        ...,
        ge=0,
        description="Total number of transactions",
    )
    page: int = Field(
        ...,
        ge=1,
        description="Current page",
    )
    page_size: int = Field(
        ...,
        ge=1,
        description="Items per page",
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def pages(self) -> int:
        """Calculate total pages."""
        if self.page_size == 0:
            return 0
        return (self.total + self.page_size - 1) // self.page_size


class BalanceAdjustment(BaseCreateSchema):
    """
    Balance adjustment schema.
    
    Used to manually adjust account balance.
    """

    student_id: UUID = Field(
        ...,
        description="Student ID to adjust",
    )
    hostel_id: UUID = Field(
        ...,
        description="Hostel ID",
    )

    # Adjustment Details
    adjustment_amount: Decimal = Field(
        ...,
        description="Adjustment amount (positive for credit, negative for debit)",
    )
    adjustment_type: str = Field(
        ...,
        pattern=r"^(correction|refund|discount|penalty|other)$",
        description="Type of adjustment",
    )

    # Reason
    reason: str = Field(
        ...,
        min_length=10,
        max_length=500,
        description="Reason for adjustment",
    )
    notes: Optional[str] = Field(
        None,
        max_length=1000,
        description="Additional notes",
    )

    # Approval
    approved_by: UUID = Field(
        ...,
        description="User approving this adjustment",
    )
    requires_verification: bool = Field(
        True,
        description="Whether this requires additional verification",
    )

    @field_validator("adjustment_amount")
    @classmethod
    def validate_adjustment_amount(cls, v: Decimal) -> Decimal:
        """Validate adjustment amount."""
        if v == 0:
            raise ValueError("Adjustment amount cannot be zero")
        
        # Reasonable limit check
        max_adjustment = Decimal("100000.00")
        if abs(v) > max_adjustment:
            raise ValueError(
                f"Adjustment amount ({abs(v)}) exceeds maximum ({max_adjustment})"
            )
        
        return v.quantize(Decimal("0.01"))

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, v: str) -> str:
        """Validate reason."""
        v = v.strip()
        if len(v) < 10:
            raise ValueError("Reason must be at least 10 characters")
        return v


class WriteOff(BaseCreateSchema):
    """
    Write-off schema.
    
    Used to write off uncollectible amounts.
    """

    student_id: UUID = Field(
        ...,
        description="Student ID",
    )
    hostel_id: UUID = Field(
        ...,
        description="Hostel ID",
    )

    # Write-off Amount
    writeoff_amount: Decimal = Field(
        ...,
        ge=0,
        description="Amount to write off",
    )
    outstanding_amount: Decimal = Field(
        ...,
        ge=0,
        description="Current outstanding amount",
    )

    # Reason
    writeoff_reason: str = Field(
        ...,
        pattern=r"^(bad_debt|student_dropout|uncollectible|dispute_settled|other)$",
        description="Reason for write-off",
    )
    detailed_reason: str = Field(
        ...,
        min_length=20,
        max_length=1000,
        description="Detailed explanation",
    )

    # Approval
    approved_by: UUID = Field(
        ...,
        description="User approving write-off",
    )
    approval_level: str = Field(
        ...,
        pattern=r"^(manager|director|cfo)$",
        description="Approval level required",
    )

    # Documentation
    supporting_documents: Optional[List[str]] = Field(
        None,
        description="URLs/IDs of supporting documents",
    )

    @field_validator("writeoff_amount")
    @classmethod
    def validate_writeoff_amount(cls, v: Decimal) -> Decimal:
        """Validate write-off amount."""
        if v <= 0:
            raise ValueError("Write-off amount must be greater than zero")
        return v.quantize(Decimal("0.01"))

    @model_validator(mode="after")
    def validate_writeoff_limits(self) -> "WriteOff":
        """Validate write-off doesn't exceed outstanding amount."""
        if self.writeoff_amount > self.outstanding_amount:
            raise ValueError(
                f"Write-off amount ({self.writeoff_amount}) cannot exceed "
                f"outstanding amount ({self.outstanding_amount})"
            )
        return self

    @field_validator("detailed_reason")
    @classmethod
    def validate_detailed_reason(cls, v: str) -> str:
        """Validate detailed reason."""
        v = v.strip()
        if len(v) < 20:
            raise ValueError("Detailed reason must be at least 20 characters")
        return v