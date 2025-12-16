"""
Admin override schemas for supervisor decision management.

Provides structured requests and logs for admin overrides of supervisor actions,
with comprehensive analytics and audit trail support.

Fully migrated to Pydantic v2.
"""

from datetime import datetime
from datetime import date as Date
from decimal import Decimal
from typing import Any, Dict, List, Union
from uuid import UUID

from pydantic import Field, computed_field, field_validator, model_validator, ConfigDict

from app.schemas.common.base import BaseCreateSchema, BaseResponseSchema, BaseSchema

__all__ = [
    "AdminOverrideRequest",
    "OverrideLog",
    "OverrideReason",
    "OverrideSummary",
    "SupervisorOverrideStats",
]


# Constants
VALID_OVERRIDE_TYPES = {
    "complaint_reassignment",
    "complaint_closure",
    "maintenance_approval",
    "maintenance_rejection",
    "fee_waiver",
    "booking_override",
    "student_action",
    "policy_exception",
}

VALID_ENTITY_TYPES = {
    "complaint",
    "maintenance_request",
    "booking",
    "fee_transaction",
    "student_record",
    "policy_violation",
}

VALID_TRENDS = {"increasing", "decreasing", "stable"}
VALID_SUPERVISOR_TRENDS = {"improving", "declining", "stable"}

MIN_REASON_LENGTH = 20
MAX_REASON_LENGTH = 1000


class AdminOverrideRequest(BaseCreateSchema):
    """
    Request to override supervisor decision with comprehensive validation.

    Ensures all override requests are properly documented and justified
    with appropriate context and reasoning.
    """
    
    model_config = ConfigDict(validate_assignment=True)

    supervisor_id: Union[UUID, None] = Field(
        None, description="Supervisor whose action is being overridden"
    )
    hostel_id: UUID = Field(..., description="Hostel where override occurs")

    override_type: str = Field(
        ...,
        description="Type of override (complaint_reassignment, maintenance_approval, etc.)",
    )

    entity_type: str = Field(
        ..., description="Type of entity (complaint, maintenance_request, etc.)"
    )
    entity_id: UUID = Field(..., description="ID of entity being modified")

    reason: str = Field(
        ...,
        min_length=MIN_REASON_LENGTH,
        max_length=MAX_REASON_LENGTH,
        description="Detailed reason for override",
    )

    # Original and new values
    original_action: Union[Dict[str, Any], None] = Field(
        None, description="Original supervisor action"
    )
    override_action: Dict[str, Any] = Field(..., description="Admin's override action")

    # Notification
    notify_supervisor: bool = Field(True, description="Notify supervisor of override")

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, v: str) -> str:
        """Normalize and validate reason text."""
        text = " ".join(v.strip().split())
        if len(text) < MIN_REASON_LENGTH:
            raise ValueError(
                f"Reason must be at least {MIN_REASON_LENGTH} characters after normalization"
            )

        # Check for placeholder text
        placeholder_phrases = [
            "override",
            "because",
            "admin decision",
            "test",
            "no reason",
        ]
        if text.lower() in placeholder_phrases:
            raise ValueError(
                "Please provide a specific, meaningful reason for the override"
            )

        return text

    @field_validator("override_type")
    @classmethod
    def validate_override_type(cls, v: str) -> str:
        """Validate and normalize override type."""
        normalized = v.strip().lower()
        if normalized not in VALID_OVERRIDE_TYPES:
            raise ValueError(
                f"Invalid override type: '{v}'. Valid types: {', '.join(sorted(VALID_OVERRIDE_TYPES))}"
            )
        return normalized

    @field_validator("entity_type")
    @classmethod
    def validate_entity_type(cls, v: str) -> str:
        """Validate and normalize entity type."""
        normalized = v.strip().lower()
        if normalized not in VALID_ENTITY_TYPES:
            raise ValueError(
                f"Invalid entity type: '{v}'. Valid types: {', '.join(sorted(VALID_ENTITY_TYPES))}"
            )
        return normalized

    @field_validator("override_action")
    @classmethod
    def validate_override_action(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        """Validate override action is not empty."""
        if not v:
            raise ValueError("Override action cannot be empty")
        return v

    @model_validator(mode="after")
    def validate_supervisor_requirement(self) -> "AdminOverrideRequest":
        """Validate supervisor_id is required for certain override types."""
        supervisor_required_types = {
            "complaint_reassignment",
            "complaint_closure",
            "maintenance_approval",
            "maintenance_rejection",
        }

        if self.override_type in supervisor_required_types and not self.supervisor_id:
            raise ValueError(
                f"supervisor_id is required for override type: {self.override_type}"
            )

        return self


class OverrideLog(BaseResponseSchema):
    """
    Override log entry with comprehensive tracking.

    Maintains complete audit trail of all override actions
    for accountability and analysis.
    """
    
    model_config = ConfigDict()

    admin_id: UUID = Field(..., description="Admin who performed override")
    admin_name: str = Field(..., min_length=1, description="Admin full name")
    supervisor_id: Union[UUID, None] = Field(None, description="Affected supervisor ID")
    supervisor_name: Union[str, None] = Field(None, description="Affected supervisor name")

    hostel_id: UUID = Field(..., description="Hostel where override occurred")
    hostel_name: str = Field(..., min_length=1, description="Hostel name")

    override_type: str = Field(..., description="Type of override")
    entity_type: str = Field(..., description="Type of entity")
    entity_id: UUID = Field(..., description="Entity ID")

    reason: str = Field(..., description="Override reason")

    original_action: Union[Dict[str, Any], None] = Field(
        None, description="Original supervisor action"
    )
    override_action: Dict[str, Any] = Field(..., description="Override action taken")

    created_at: datetime = Field(..., description="Override timestamp")

    @computed_field
    @property
    def short_reason(self) -> str:
        """Shortened reason for list displays."""
        max_length = 80
        if len(self.reason) <= max_length:
            return self.reason
        return self.reason[: max_length - 3] + "..."

    @computed_field
    @property
    def override_category(self) -> str:
        """Categorize override by entity type."""
        category_map = {
            "complaint": "Complaint Management",
            "maintenance_request": "Maintenance Operations",
            "booking": "Booking Management",
            "fee_transaction": "Financial Operations",
            "student_record": "Student Management",
            "policy_violation": "Policy Enforcement",
        }
        return category_map.get(self.entity_type, "Other")

    @computed_field
    @property
    def hours_since_override(self) -> int:
        """Calculate hours since override occurred."""
        delta = datetime.utcnow() - self.created_at
        return int(delta.total_seconds() // 3600)


class OverrideReason(BaseSchema):
    """
    Predefined override reasons for standardization.

    Provides common override reasons to ensure consistency
    and facilitate analytics.
    """
    
    model_config = ConfigDict()

    reason_code: str = Field(..., min_length=1, description="Unique reason code")
    reason_text: str = Field(..., min_length=10, description="Reason description")
    category: str = Field(..., min_length=1, description="Reason category")
    requires_detailed_explanation: bool = Field(
        ..., description="Whether detailed explanation is required"
    )

    @field_validator("reason_code")
    @classmethod
    def validate_reason_code(cls, v: str) -> str:
        """Validate and normalize reason code."""
        code = v.strip().upper()
        if not code:
            raise ValueError("Reason code cannot be empty")
        # Ensure alphanumeric with underscores
        if not code.replace("_", "").isalnum():
            raise ValueError(
                "Reason code must contain only letters, numbers, and underscores"
            )
        return code


class OverrideSummary(BaseSchema):
    """
    Summary of admin overrides for a specific period.

    Provides aggregated view of override patterns and trends
    for management oversight and decision-making.
    """
    
    model_config = ConfigDict()

    admin_id: UUID = Field(..., description="Admin user ID")
    period_start: Date = Field(..., description="Summary period start Date")
    period_end: Date = Field(..., description="Summary period end Date")

    total_overrides: int = Field(..., ge=0, description="Total overrides in period")

    # By type
    overrides_by_type: Dict[str, int] = Field(
        default_factory=dict, description="Breakdown by override type"
    )

    # By supervisor - Pydantic v2: Dict keys must be JSON-serializable (strings)
    overrides_by_supervisor: Dict[str, int] = Field(
        default_factory=dict, description="Breakdown by supervisor"
    )

    # By hostel - Pydantic v2: Dict keys must be JSON-serializable (strings)
    overrides_by_hostel: Dict[str, int] = Field(
        default_factory=dict, description="Breakdown by hostel"
    )

    # Trend
    override_trend: str = Field(
        ..., description="Override trend (increasing/decreasing/stable)"
    )

    @computed_field
    @property
    def average_overrides_per_day(self) -> Decimal:
        """Average overrides per day in the period."""
        days = max(1, (self.period_end - self.period_start).days)
        avg = Decimal(self.total_overrides) / Decimal(days)
        return avg.quantize(Decimal("0.01"))

    @computed_field
    @property
    def most_overridden_supervisor(self) -> Union[str, None]:
        """Identify supervisor with most overrides."""
        if not self.overrides_by_supervisor:
            return None
        return max(self.overrides_by_supervisor, key=self.overrides_by_supervisor.get)  # type: ignore

    @computed_field
    @property
    def most_common_override_type(self) -> Union[str, None]:
        """Identify most common override type."""
        if not self.overrides_by_type:
            return None
        return max(self.overrides_by_type, key=self.overrides_by_type.get)  # type: ignore

    @computed_field
    @property
    def override_concentration(self) -> Decimal:
        """
        Calculate override concentration (0-100).
        Higher values indicate overrides concentrated on few supervisors.
        """
        if not self.overrides_by_supervisor or self.total_overrides == 0:
            return Decimal("0.00")

        # Calculate Herfindahl-Hirschman Index (HHI) simplified
        supervisor_counts = list(self.overrides_by_supervisor.values())
        shares = [
            (count / self.total_overrides) ** 2 for count in supervisor_counts
        ]
        hhi = sum(shares) * 100

        return Decimal(str(hhi)).quantize(Decimal("0.01"))

    @field_validator("override_trend")
    @classmethod
    def validate_trend(cls, v: str) -> str:
        """Validate trend value."""
        if v not in VALID_TRENDS:
            raise ValueError(
                f"Invalid trend value: '{v}'. Must be one of: {', '.join(VALID_TRENDS)}"
            )
        return v

    @model_validator(mode="after")
    def validate_period_dates(self) -> "OverrideSummary":
        """Validate period dates are logical."""
        if self.period_end < self.period_start:
            raise ValueError("period_end must be after period_start")

        if (self.period_end - self.period_start).days > 365:
            raise ValueError("Summary period cannot exceed 365 days")

        return self


class SupervisorOverrideStats(BaseSchema):
    """
    Override statistics for a specific supervisor.

    Provides detailed override metrics to identify patterns
    and areas for supervisor development or support.
    """
    
    model_config = ConfigDict()

    supervisor_id: UUID = Field(..., description="Supervisor user ID")
    supervisor_name: str = Field(..., min_length=1, description="Supervisor full name")

    total_actions: int = Field(..., ge=0, description="Total actions taken by supervisor")
    total_overrides: int = Field(..., ge=0, description="Total actions overridden")
    
    # Pydantic v2: Decimal with ge/le constraints
    override_rate: Decimal = Field(
        ..., ge=Decimal("0"), le=Decimal("100"), description="Percentage of actions overridden"
    )

    # By type
    overrides_by_type: Dict[str, int] = Field(
        default_factory=dict, description="Breakdown by override type"
    )

    # Common reasons
    common_override_reasons: List[str] = Field(
        default_factory=list, description="Most common override reasons"
    )

    # Trend
    recent_trend: str = Field(
        ...,
        description="Recent trend in override rate (improving/declining/stable)",
    )

    @computed_field
    @property
    def is_concerning(self) -> bool:
        """Whether override rate is concerning (> 10%)."""
        return float(self.override_rate) > 10.0

    @computed_field
    @property
    def performance_indicator(self) -> str:
        """Overall performance indicator based on override rate."""
        rate = float(self.override_rate)
        if rate <= 5:
            return "Excellent"
        elif rate <= 10:
            return "Good"
        elif rate <= 20:
            return "Needs Improvement"
        else:
            return "Critical"

    @computed_field
    @property
    def most_overridden_category(self) -> Union[str, None]:
        """Identify category with most overrides."""
        if not self.overrides_by_type:
            return None
        return max(self.overrides_by_type, key=self.overrides_by_type.get)  # type: ignore

    @field_validator("override_rate")
    @classmethod
    def validate_override_rate(cls, v: Decimal) -> Decimal:
        """Validate override rate is within bounds."""
        if v < 0 or v > 100:
            raise ValueError("Override rate must be between 0 and 100")
        return v.quantize(Decimal("0.01"))

    @field_validator("recent_trend")
    @classmethod
    def validate_trend(cls, v: str) -> str:
        """Validate trend value."""
        if v not in VALID_SUPERVISOR_TRENDS:
            raise ValueError(
                f"Invalid trend: '{v}'. Must be one of: {', '.join(VALID_SUPERVISOR_TRENDS)}"
            )
        return v

    @model_validator(mode="after")
    def validate_stats_consistency(self) -> "SupervisorOverrideStats":
        """Validate statistical consistency."""
        if self.total_overrides > self.total_actions:
            raise ValueError("total_overrides cannot exceed total_actions")

        # Validate override rate calculation
        if self.total_actions > 0:
            calculated_rate = Decimal(self.total_overrides) / Decimal(
                self.total_actions
            ) * 100
            calculated_rate = calculated_rate.quantize(Decimal("0.01"))

            # Allow small rounding difference
            if abs(calculated_rate - self.override_rate) > Decimal("0.1"):
                raise ValueError(
                    f"override_rate {self.override_rate} doesn't match calculated rate {calculated_rate}"
                )

        return self