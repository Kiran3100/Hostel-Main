# --- File: app/schemas/referral/referral_rewards.py ---
"""
Referral reward tracking schemas.

This module provides schemas for managing reward calculations,
payouts, and tracking for referral programs.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.schemas.common.base import BaseCreateSchema, BaseResponseSchema, BaseSchema
from app.schemas.common.enums import PaymentMethod, RewardStatus

__all__ = [
    "RewardConfig",
    "RewardTracking",
    "RewardCalculation",
    "PayoutRequest",
    "PayoutRequestResponse",
    "PayoutHistory",
    "RewardSummary",
]


class RewardConfig(BaseSchema):
    """
    Global referral reward configuration.

    Defines payout rules, minimum thresholds, and payment methods.
    """

    # Payout thresholds
    min_payout_amount: Decimal = Field(
        default=Decimal("100.00"),
        ge=0,
        description="Minimum amount required before payout",
    )
    max_payout_amount: Decimal = Field(
        default=Decimal("100000.00"),
        ge=0,
        description="Maximum amount per payout transaction",
    )

    # Payment methods
    payout_methods: List[PaymentMethod] = Field(
        default_factory=lambda: [
            PaymentMethod.BANK_TRANSFER,
            PaymentMethod.UPI,
        ],
        min_length=1,
        description="Allowed payout methods",
    )

    # Processing settings
    auto_approve_payouts: bool = Field(
        default=False,
        description="Auto-approve payout requests",
    )
    payout_processing_time_days: int = Field(
        default=7,
        ge=1,
        le=30,
        description="Estimated processing time in days",
    )

    # Fees and charges
    payout_fee_percentage: Decimal = Field(
        default=Decimal("0.00"),
        ge=0,
        le=10,
        description="Payout processing fee percentage",
    )
    min_payout_fee: Decimal = Field(
        default=Decimal("0.00"),
        ge=0,
        description="Minimum payout fee",
    )
    max_payout_fee: Decimal = Field(
        default=Decimal("100.00"),
        ge=0,
        description="Maximum payout fee",
    )

    # Frequency limits
    max_payouts_per_month: int = Field(
        default=4,
        ge=1,
        le=30,
        description="Maximum payouts allowed per month",
    )
    min_days_between_payouts: int = Field(
        default=7,
        ge=1,
        le=30,
        description="Minimum days between payout requests",
    )

    # Tax settings
    tax_deduction_applicable: bool = Field(
        default=False,
        description="Whether tax deduction is applicable",
    )
    tax_deduction_percentage: Decimal = Field(
        default=Decimal("0.00"),
        ge=0,
        le=30,
        description="Tax deduction percentage",
    )

    @field_validator("payout_methods")
    @classmethod
    def validate_payout_methods(cls, v: List[PaymentMethod]) -> List[PaymentMethod]:
        """Ensure unique payout methods."""
        return list(set(v))

    @field_validator(
        "min_payout_amount",
        "max_payout_amount",
        "payout_fee_percentage",
        "min_payout_fee",
        "max_payout_fee",
        "tax_deduction_percentage",
    )
    @classmethod
    def validate_decimal_places(cls, v: Decimal) -> Decimal:
        """Ensure decimal values have at most 2 decimal places."""
        return v.quantize(Decimal("0.01"))


class RewardTracking(BaseSchema):
    """
    Track rewards earned by a user across all programs.

    Provides comprehensive reward balance and history.
    """

    user_id: UUID = Field(..., description="User ID")
    user_name: str = Field(..., description="User name")

    # Overall balances
    total_rewards_earned: Decimal = Field(
        ...,
        ge=0,
        description="Total rewards earned (all time)",
    )
    total_rewards_paid: Decimal = Field(
        ...,
        ge=0,
        description="Total rewards paid out",
    )
    pending_rewards: Decimal = Field(
        ...,
        ge=0,
        description="Pending rewards awaiting payout",
    )
    available_for_payout: Decimal = Field(
        ...,
        ge=0,
        description="Amount available for immediate payout",
    )
    currency: str = Field(default="INR", description="Currency code")

    # Breakdown by program
    rewards_by_program: Dict[str, Decimal] = Field(
        default_factory=dict,
        description="Rewards earned per program",
    )

    # Breakdown by status
    approved_rewards: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description="Approved but not paid rewards",
    )
    pending_approval: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description="Rewards pending approval",
    )
    cancelled_rewards: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description="Cancelled reward amount",
    )

    # Payout information
    last_payout_date: Optional[datetime] = Field(
        None,
        description="Date of last payout",
    )
    last_payout_amount: Optional[Decimal] = Field(
        None,
        ge=0,
        description="Amount of last payout",
    )
    next_payout_eligible_date: Optional[datetime] = Field(
        None,
        description="When user is eligible for next payout",
    )

    # Statistics
    total_payouts: int = Field(
        default=0,
        ge=0,
        description="Total number of payouts received",
    )
    average_payout_amount: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description="Average payout amount",
    )

    @field_validator(
        "total_rewards_earned",
        "total_rewards_paid",
        "pending_rewards",
        "available_for_payout",
        "approved_rewards",
        "pending_approval",
        "cancelled_rewards",
        "last_payout_amount",
        "average_payout_amount",
    )
    @classmethod
    def validate_decimal_places(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        """Ensure decimal values have at most 2 decimal places."""
        if v is None:
            return None
        return v.quantize(Decimal("0.01"))


class RewardCalculation(BaseSchema):
    """
    Reward calculation for a referral.

    Shows breakdown of reward amounts and eligibility.
    """

    referral_id: UUID = Field(..., description="Referral ID")
    program_id: UUID = Field(..., description="Program ID")
    
    # Booking details
    booking_amount: Decimal = Field(
        ...,
        ge=0,
        description="Booking amount",
    )
    stay_duration_months: int = Field(
        ...,
        ge=1,
        description="Stay duration in months",
    )

    # Eligibility
    is_eligible: bool = Field(..., description="Whether referral is eligible for reward")
    eligibility_reasons: List[str] = Field(
        default_factory=list,
        description="Reasons for eligibility/ineligibility",
    )

    # Calculated rewards
    referrer_base_reward: Decimal = Field(
        ...,
        ge=0,
        description="Base reward for referrer",
    )
    referrer_bonus: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description="Bonus for referrer (if any)",
    )
    referrer_total_reward: Decimal = Field(
        ...,
        ge=0,
        description="Total reward for referrer",
    )

    referee_base_reward: Decimal = Field(
        ...,
        ge=0,
        description="Base reward for referee",
    )
    referee_bonus: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description="Bonus for referee (if any)",
    )
    referee_total_reward: Decimal = Field(
        ...,
        ge=0,
        description="Total reward for referee",
    )

    # Deductions
    tax_deduction: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description="Tax deduction amount",
    )
    processing_fee: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description="Processing fee",
    )

    # Net amounts
    referrer_net_amount: Decimal = Field(
        ...,
        ge=0,
        description="Net amount for referrer after deductions",
    )
    referee_net_amount: Decimal = Field(
        ...,
        ge=0,
        description="Net amount for referee after deductions",
    )

    currency: str = Field(default="INR", description="Currency code")
    calculated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Calculation timestamp",
    )

    @field_validator(
        "booking_amount",
        "referrer_base_reward",
        "referrer_bonus",
        "referrer_total_reward",
        "referee_base_reward",
        "referee_bonus",
        "referee_total_reward",
        "tax_deduction",
        "processing_fee",
        "referrer_net_amount",
        "referee_net_amount",
    )
    @classmethod
    def validate_decimal_places(cls, v: Decimal) -> Decimal:
        """Ensure decimal values have at most 2 decimal places."""
        return v.quantize(Decimal("0.01"))


class PayoutRequest(BaseCreateSchema):
    """
    Request payout of accumulated referral rewards.

    User initiates withdrawal of earned rewards.
    """

    user_id: UUID = Field(..., description="User requesting payout")
    
    amount: Decimal = Field(
        ...,
        ge=0,
        description="Amount to withdraw",
    )

    # Payment details
    payout_method: PaymentMethod = Field(
        ...,
        description="Preferred payout method",
    )
    payout_details: Dict[str, str] = Field(
        ...,
        description="Method-specific payout details",
    )

    # Optional preferences
    currency: str = Field(
        default="INR",
        min_length=3,
        max_length=3,
        description="Currency for payout",
    )
    urgent_payout: bool = Field(
        default=False,
        description="Request urgent processing (may incur extra fees)",
    )

    # Notes
    notes: Optional[str] = Field(
        None,
        max_length=500,
        description="Additional notes or instructions",
    )

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v: Decimal) -> Decimal:
        """Validate payout amount."""
        v = v.quantize(Decimal("0.01"))
        if v <= 0:
            raise ValueError("Payout amount must be greater than zero")
        if v < Decimal("100.00"):
            raise ValueError("Minimum payout amount is ₹100.00")
        if v > Decimal("100000.00"):
            raise ValueError("Maximum payout amount is ₹100,000.00")
        return v

    @model_validator(mode="after")
    def validate_payout_details(self) -> "PayoutRequest":
        """Validate payout details based on method."""
        if self.payout_method == PaymentMethod.UPI:
            if "upi_id" not in self.payout_details:
                raise ValueError("UPI ID required for UPI payout")
            # Validate UPI ID format
            upi_id = self.payout_details["upi_id"]
            if "@" not in upi_id:
                raise ValueError("Invalid UPI ID format")

        elif self.payout_method == PaymentMethod.BANK_TRANSFER:
            required_fields = [
                "account_number",
                "account_holder_name",
                "ifsc_code",
                "bank_name",
            ]
            for field in required_fields:
                if field not in self.payout_details:
                    raise ValueError(f"{field} required for bank transfer")

        return self


class PayoutRequestResponse(BaseResponseSchema):
    """
    Payout request status and tracking.

    Tracks the lifecycle of a payout request.
    """

    payout_request_id: UUID = Field(..., description="Payout request ID")
    user_id: UUID = Field(..., description="User ID")
    user_name: str = Field(..., description="User name")

    # Amount details
    amount: Decimal = Field(
        ...,
        ge=0,
        description="Requested payout amount",
    )
    processing_fee: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description="Processing fee",
    )
    tax_deduction: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description="Tax deduction",
    )
    net_amount: Decimal = Field(
        ...,
        ge=0,
        description="Net amount to be paid",
    )
    currency: str = Field(..., description="Currency code")

    # Payment details
    payout_method: PaymentMethod = Field(..., description="Payout method")
    payout_details_masked: Dict[str, str] = Field(
        default_factory=dict,
        description="Masked payout details for security",
    )

    # Status tracking
    status: RewardStatus = Field(..., description="Payout status")
    requested_at: datetime = Field(..., description="Request timestamp")
    approved_at: Optional[datetime] = Field(None, description="Approval timestamp")
    processed_at: Optional[datetime] = Field(None, description="Processing timestamp")
    completed_at: Optional[datetime] = Field(None, description="Completion timestamp")

    # Additional information
    transaction_id: Optional[str] = Field(
        None,
        description="External transaction ID",
    )
    failure_reason: Optional[str] = Field(
        None,
        max_length=500,
        description="Reason for failure (if applicable)",
    )
    admin_notes: Optional[str] = Field(
        None,
        description="Admin notes",
    )

    # Estimated completion
    estimated_completion_date: Optional[datetime] = Field(
        None,
        description="Estimated completion date",
    )

    # Audit
    approved_by: Optional[UUID] = Field(None, description="Admin who approved")
    processed_by: Optional[UUID] = Field(None, description="Admin who processed")

    @field_validator("amount", "processing_fee", "tax_deduction", "net_amount")
    @classmethod
    def validate_decimal_places(cls, v: Decimal) -> Decimal:
        """Ensure decimal values have at most 2 decimal places."""
        return v.quantize(Decimal("0.01"))


class PayoutHistory(BaseSchema):
    """
    Payout history for a user.

    Lists all payout transactions.
    """

    user_id: UUID = Field(..., description="User ID")
    total_payouts: int = Field(..., ge=0, description="Total payout count")
    total_amount_paid: Decimal = Field(
        ...,
        ge=0,
        description="Total amount paid out",
    )
    currency: str = Field(default="INR", description="Currency")

    payouts: List[PayoutRequestResponse] = Field(
        ...,
        description="List of payout transactions",
    )

    @field_validator("total_amount_paid")
    @classmethod
    def validate_decimal_places(cls, v: Decimal) -> Decimal:
        """Ensure decimal values have at most 2 decimal places."""
        return v.quantize(Decimal("0.01"))


class RewardSummary(BaseSchema):
    """
    Summary of rewards for reporting.

    Provides aggregated reward data for a time period.
    """

    # Time period
    period_start: datetime = Field(..., description="Period start date")
    period_end: datetime = Field(..., description="Period end date")

    # User filter (optional)
    user_id: Optional[UUID] = Field(None, description="User ID (null for all users)")
    program_id: Optional[UUID] = Field(None, description="Program ID (null for all)")

    # Reward statistics
    total_rewards_earned: Decimal = Field(
        ...,
        ge=0,
        description="Total rewards earned in period",
    )
    total_rewards_approved: Decimal = Field(
        ...,
        ge=0,
        description="Total rewards approved",
    )
    total_rewards_paid: Decimal = Field(
        ...,
        ge=0,
        description="Total rewards paid out",
    )
    total_rewards_pending: Decimal = Field(
        ...,
        ge=0,
        description="Total rewards pending",
    )
    total_rewards_cancelled: Decimal = Field(
        ...,
        ge=0,
        description="Total rewards cancelled",
    )

    # Breakdown
    rewards_by_status: Dict[str, Decimal] = Field(
        default_factory=dict,
        description="Rewards by status",
    )
    rewards_by_program: Dict[str, Decimal] = Field(
        default_factory=dict,
        description="Rewards by program",
    )
    rewards_by_month: Dict[str, Decimal] = Field(
        default_factory=dict,
        description="Monthly reward distribution",
    )

    # Payout statistics
    total_payout_requests: int = Field(
        default=0,
        ge=0,
        description="Total payout requests",
    )
    successful_payouts: int = Field(
        default=0,
        ge=0,
        description="Successful payouts",
    )
    failed_payouts: int = Field(
        default=0,
        ge=0,
        description="Failed payouts",
    )

    # Averages
    average_reward_amount: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description="Average reward amount",
    )
    average_payout_amount: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description="Average payout amount",
    )

    currency: str = Field(default="INR", description="Currency code")

    @field_validator(
        "total_rewards_earned",
        "total_rewards_approved",
        "total_rewards_paid",
        "total_rewards_pending",
        "total_rewards_cancelled",
        "average_reward_amount",
        "average_payout_amount",
    )
    @classmethod
    def validate_decimal_places(cls, v: Decimal) -> Decimal:
        """Ensure decimal values have at most 2 decimal places."""
        return v.quantize(Decimal("0.01"))