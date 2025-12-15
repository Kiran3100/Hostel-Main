# --- File: app/schemas/audit/admin_override_log.py ---
"""
Admin override audit log schemas with enhanced tracking.

Tracks admin interventions and overrides of supervisor decisions
for accountability, performance review, and governance.
"""

from datetime import datetime, date 
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional

from pydantic import Field, field_validator, computed_field, model_validator
from uuid import UUID

from app.schemas.common.base import BaseSchema, BaseCreateSchema, BaseResponseSchema
from app.schemas.common.filters import DateTimeRangeFilter

__all__ = [
    "AdminOverrideBase",
    "AdminOverrideCreate",
    "AdminOverrideLogResponse",
    "AdminOverrideDetail",
    "AdminOverrideSummary",
    "AdminOverrideTimelinePoint",
    "AdminOverrideAnalytics",
    "SupervisorImpactAnalysis",
]


class AdminOverrideBase(BaseSchema):
    """
    Base admin override log fields.
    
    Comprehensive tracking of admin interventions in supervisor
    decisions for oversight, accountability, and process improvement.
    """
    
    # Actors
    admin_id: UUID = Field(
        ...,
        description="Admin who performed the override"
    )
    admin_name: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Admin name (for display)"
    )
    
    supervisor_id: Optional[UUID] = Field(
        default=None,
        description="Supervisor whose decision was overridden (if applicable)"
    )
    supervisor_name: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Supervisor name (for display)"
    )
    
    # Context
    hostel_id: UUID = Field(
        ...,
        description="Hostel where the override occurred"
    )
    hostel_name: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Hostel name (for display)"
    )
    
    # Override details
    override_type: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Type of override (e.g., 'complaint_reassignment', 'maintenance_approval')"
    )
    override_category: str = Field(
        ...,
        pattern="^(decision_reversal|task_reassignment|priority_change|approval|rejection|other)$",
        description="Category of override"
    )
    
    # Entity affected
    entity_type: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Entity type affected (e.g., 'complaint', 'maintenance_request')"
    )
    entity_id: UUID = Field(
        ...,
        description="Primary key of affected entity"
    )
    entity_name: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Display name of entity"
    )
    
    # Reason and justification
    reason: str = Field(
        ...,
        min_length=10,
        max_length=2000,
        description="Why the admin override was performed"
    )
    justification_category: Optional[str] = Field(
        default=None,
        pattern="^(quality_issue|policy_violation|emergency|customer_complaint|other)$",
        description="Category of justification"
    )
    
    # Original and override actions
    original_action: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Snapshot of supervisor's original action/decision"
    )
    override_action: Dict[str, Any] = Field(
        ...,
        description="Admin's override decision and details"
    )
    
    # Impact assessment
    severity: str = Field(
        default="medium",
        pattern="^(low|medium|high|critical)$",
        description="Severity/impact of the override"
    )
    urgency: str = Field(
        default="normal",
        pattern="^(low|normal|high|urgent)$",
        description="Urgency of the override"
    )
    
    # Notification
    supervisor_notified: bool = Field(
        default=False,
        description="Whether supervisor was notified"
    )
    notification_sent_at: Optional[datetime] = Field(
        default=None,
        description="When notification was sent"
    )
    
    # Approval workflow (if override requires approval)
    requires_approval: bool = Field(
        default=False,
        description="Whether override requires higher approval"
    )
    approved_by: Optional[UUID] = Field(
        default=None,
        description="Senior admin who approved override"
    )
    approved_at: Optional[datetime] = Field(
        default=None,
        description="When override was approved"
    )
    
    # Outcome
    outcome: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Outcome of the override"
    )
    outcome_status: str = Field(
        default="pending",
        pattern="^(pending|successful|failed|reversed)$",
        description="Status of override outcome"
    )
    
    # Timestamp
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp when override was recorded"
    )
    
    # Follow-up
    follow_up_required: bool = Field(
        default=False,
        description="Whether follow-up action is required"
    )
    follow_up_completed: Optional[bool] = Field(
        default=None,
        description="Whether follow-up was completed"
    )
    
    @computed_field
    @property
    def impact_score(self) -> Decimal:
        """
        Calculate impact score (0-100) based on severity and urgency.
        
        Higher score indicates greater impact.
        Note: Returns Decimal rounded to 2 decimal places.
        """
        severity_scores = {
            "low": 25,
            "medium": 50,
            "high": 75,
            "critical": 100,
        }
        
        urgency_multipliers = {
            "low": 0.7,
            "normal": 1.0,
            "high": 1.3,
            "urgent": 1.5,
        }
        
        base_score = severity_scores.get(self.severity, 50)
        multiplier = urgency_multipliers.get(self.urgency, 1.0)
        
        score = min(100, base_score * multiplier)
        result = Decimal(str(score)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return result


class AdminOverrideCreate(AdminOverrideBase, BaseCreateSchema):
    """
    Payload for creating new admin override log entries.
    
    Used by services to record admin interventions and
    maintain governance audit trail.
    """
    
    @classmethod
    def for_complaint_override(
        cls,
        admin_id: UUID,
        supervisor_id: UUID,
        hostel_id: UUID,
        complaint_id: UUID,
        reason: str,
        original_action: Dict[str, Any],
        override_action: Dict[str, Any],
        **kwargs
    ) -> "AdminOverrideCreate":
        """
        Factory method for complaint-related overrides.
        
        Args:
            admin_id: Admin performing override
            supervisor_id: Supervisor being overridden
            hostel_id: Hostel context
            complaint_id: Complaint being overridden
            reason: Justification for override
            original_action: Original supervisor action
            override_action: Admin's override action
            **kwargs: Additional fields
            
        Returns:
            AdminOverrideCreate instance
        """
        return cls(
            admin_id=admin_id,
            supervisor_id=supervisor_id,
            hostel_id=hostel_id,
            override_type="complaint_override",
            override_category="decision_reversal",
            entity_type="complaint",
            entity_id=complaint_id,
            reason=reason,
            original_action=original_action,
            override_action=override_action,
            **kwargs
        )


class AdminOverrideLogResponse(BaseResponseSchema):
    """
    List item representation of an admin override log.
    
    Optimized for audit tables and oversight dashboards.
    """
    
    id: UUID = Field(..., description="Override log entry ID")
    
    # Actors
    admin_id: UUID
    admin_name: Optional[str] = None
    
    supervisor_id: Optional[UUID]
    supervisor_name: Optional[str] = None
    
    # Context
    hostel_id: UUID
    hostel_name: Optional[str] = None
    
    # Override details
    override_type: str
    override_category: str
    
    # Entity
    entity_type: str
    entity_id: UUID
    entity_name: Optional[str]
    
    # Reason
    reason: str
    justification_category: Optional[str]
    
    # Impact (Note: Decimal with 2 decimal places expected)
    severity: str
    urgency: str
    impact_score: Decimal
    
    # Status
    outcome_status: str
    
    # Timestamp
    created_at: datetime
    
    @field_validator('impact_score')
    @classmethod
    def validate_impact_score(cls, v: Decimal) -> Decimal:
        """Ensure impact_score has max 2 decimal places and is in range."""
        if v < 0 or v > 100:
            raise ValueError("impact_score must be between 0 and 100")
        return v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    
    @computed_field
    @property
    def display_text(self) -> str:
        """Generate display text for UI."""
        parts = []
        
        if self.admin_name:
            parts.append(f"{self.admin_name} overrode")
        else:
            parts.append("Admin overrode")
        
        if self.supervisor_name:
            parts.append(f"{self.supervisor_name}'s")
        
        parts.append(f"{self.override_type}")
        
        if self.entity_name:
            parts.append(f"for {self.entity_name}")
        
        return " ".join(parts)
    
    @computed_field
    @property
    def severity_badge_color(self) -> str:
        """Get color for severity badge."""
        colors = {
            "low": "blue",
            "medium": "yellow",
            "high": "orange",
            "critical": "red",
        }
        return colors.get(self.severity, "gray")


class AdminOverrideDetail(BaseResponseSchema):
    """
    Detailed view of a single admin override entry.
    
    Includes complete information for investigation and review.
    """
    
    id: UUID = Field(..., description="Override log entry ID")
    
    # Actors
    admin_id: UUID
    admin_name: Optional[str] = None
    admin_email: Optional[str] = None
    
    supervisor_id: Optional[UUID]
    supervisor_name: Optional[str] = None
    supervisor_email: Optional[str] = None
    
    # Context
    hostel_id: UUID
    hostel_name: Optional[str] = None
    
    # Override details
    override_type: str
    override_category: str
    
    # Entity
    entity_type: str
    entity_id: UUID
    entity_name: Optional[str]
    
    # Reason and justification
    reason: str
    justification_category: Optional[str]
    
    # Actions
    original_action: Optional[Dict[str, Any]]
    override_action: Dict[str, Any]
    
    # Impact (Note: Decimal with 2 decimal places expected)
    severity: str
    urgency: str
    impact_score: Decimal
    
    # Notification
    supervisor_notified: bool
    notification_sent_at: Optional[datetime]
    
    # Approval
    requires_approval: bool
    approved_by: Optional[UUID]
    approved_by_name: Optional[str]
    approved_at: Optional[datetime]
    
    # Outcome
    outcome: Optional[str]
    outcome_status: str
    
    # Follow-up
    follow_up_required: bool
    follow_up_completed: Optional[bool]
    
    # Timestamps
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    @field_validator('impact_score')
    @classmethod
    def validate_impact_score(cls, v: Decimal) -> Decimal:
        """Ensure impact_score has max 2 decimal places."""
        return v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    
    @computed_field
    @property
    def is_pending_approval(self) -> bool:
        """Check if override is pending approval."""
        return self.requires_approval and self.approved_at is None
    
    @computed_field
    @property
    def time_to_resolution(self) -> Optional[int]:
        """Calculate hours from creation to outcome completion."""
        if self.outcome_status not in ["successful", "failed"]:
            return None
        
        if not self.updated_at:
            return None
        
        delta = self.updated_at - self.created_at
        return int(delta.total_seconds() / 3600)


class AdminOverrideTimelinePoint(BaseSchema):
    """
    Time-bucketed view of admin overrides.
    
    Aggregates overrides for trend analysis and
    pattern identification.
    """
    
    bucket_label: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Label for time bucket (e.g., '2025-01-15', 'Week 02')"
    )
    bucket_start: datetime = Field(..., description="Bucket start")
    bucket_end: datetime = Field(..., description="Bucket end")
    
    # Counts
    override_count: int = Field(..., ge=0, description="Total overrides")
    
    # By category
    by_category: Dict[str, int] = Field(
        default_factory=dict,
        description="Overrides by category"
    )
    
    # By severity
    critical_count: int = Field(default=0, ge=0)
    high_count: int = Field(default=0, ge=0)
    medium_count: int = Field(default=0, ge=0)
    low_count: int = Field(default=0, ge=0)
    
    # Top supervisors affected
    top_affected_supervisors: List[UUID] = Field(
        default_factory=list,
        max_length=5,
        description="Top 5 supervisors with overrides"
    )
    
    # Average impact (Note: Decimal with 2 decimal places expected)
    avg_impact_score: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        le=100,
        description="Average impact score (2 decimal places)"
    )
    
    @field_validator('avg_impact_score')
    @classmethod
    def validate_avg_impact(cls, v: Decimal) -> Decimal:
        """Ensure avg_impact_score has max 2 decimal places."""
        return v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    
    @computed_field
    @property
    def alert_level(self) -> str:
        """Determine alert level based on override volume and severity."""
        if self.critical_count > 0 or self.override_count > 20:
            return "critical"
        elif self.high_count > 3 or self.override_count > 10:
            return "high"
        elif self.override_count > 5:
            return "medium"
        else:
            return "normal"


class SupervisorImpactAnalysis(BaseSchema):
    """
    Analysis of override impact on a specific supervisor.
    
    Tracks how frequently a supervisor's decisions are
    overridden for performance feedback.
    """
    
    supervisor_id: UUID
    supervisor_name: Optional[str] = None
    hostel_id: UUID
    hostel_name: Optional[str] = None
    
    period_start: datetime
    period_end: datetime
    
    # Override metrics
    total_overrides: int = Field(..., ge=0)
    overrides_by_type: Dict[str, int] = Field(default_factory=dict)
    overrides_by_category: Dict[str, int] = Field(default_factory=dict)
    
    # Severity distribution
    critical_overrides: int = Field(default=0, ge=0)
    high_overrides: int = Field(default=0, ge=0)
    medium_overrides: int = Field(default=0, ge=0)
    low_overrides: int = Field(default=0, ge=0)
    
    # Performance context
    total_decisions_made: int = Field(..., ge=0, description="Total decisions by supervisor")
    override_rate: Decimal = Field(
        ...,
        ge=0,
        le=100,
        description="Percentage of decisions overridden (2 decimal places)"
    )
    
    # Reasons for overrides
    top_override_reasons: List[str] = Field(
        default_factory=list,
        max_length=5,
        description="Top 5 reasons for overrides"
    )
    
    # Trend
    trend_direction: Optional[str] = Field(
        default=None,
        pattern="^(improving|worsening|stable)$",
        description="Trend in override frequency"
    )
    
    # Impact on performance score (Note: Decimal with 2 decimal places)
    performance_impact_score: Decimal = Field(
        ...,
        description="Negative impact on performance (-100 to 0, 2 decimal places)"
    )
    
    @field_validator('override_rate', 'performance_impact_score')
    @classmethod
    def validate_decimal_precision(cls, v: Decimal) -> Decimal:
        """Ensure decimal fields have max 2 decimal places."""
        return v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    
    @computed_field
    @property
    def override_risk_level(self) -> str:
        """Assess risk level based on override rate."""
        rate = float(self.override_rate)
        
        if rate >= 20:
            return "high"
        elif rate >= 10:
            return "medium"
        elif rate >= 5:
            return "low"
        else:
            return "minimal"
    
    @computed_field
    @property
    def needs_training(self) -> bool:
        """Determine if supervisor needs additional training."""
        return (
            self.override_rate > 15 or
            self.critical_overrides > 2 or
            self.total_overrides > 20
        )


class AdminOverrideSummary(BaseSchema):
    """
    Summary statistics for admin overrides.
    
    Provides aggregated view for oversight dashboards
    and governance reporting.
    """
    
    period_start: datetime
    period_end: datetime
    
    # Scope
    supervisor_id: Optional[UUID] = Field(
        default=None,
        description="If summarizing overrides for specific supervisor"
    )
    hostel_id: Optional[UUID] = Field(
        default=None,
        description="If summarizing for specific hostel"
    )
    
    # Overall stats
    total_overrides: int = Field(..., ge=0)
    unique_supervisors_affected: int = Field(..., ge=0)
    unique_admins_performing: int = Field(..., ge=0)
    
    # Distribution
    overrides_by_type: Dict[str, int] = Field(
        default_factory=dict,
        description="override_type -> count"
    )
    overrides_by_category: Dict[str, int] = Field(
        default_factory=dict,
        description="override_category -> count"
    )
    overrides_by_admin: Dict[str, int] = Field(
        default_factory=dict,
        description="admin_id -> count"
    )
    overrides_by_severity: Dict[str, int] = Field(
        default_factory=dict,
        description="severity -> count"
    )
    
    # Performance impact (Note: Decimal with 2 decimal places)
    override_rate_for_supervisor: Optional[Decimal] = Field(
        default=None,
        ge=0,
        le=100,
        description="For a given supervisor: overridden_actions / total_actions (2 decimal places)"
    )
    
    # Impact analysis
    supervisor_impacts: List[SupervisorImpactAnalysis] = Field(
        default_factory=list,
        description="Impact analysis per supervisor"
    )
    
    # Trends (Note: Decimal with 2 decimal places)
    trend_direction: str = Field(
        ...,
        pattern="^(increasing|decreasing|stable)$",
        description="Overall trend in override frequency"
    )
    percentage_change: Decimal = Field(
        ...,
        description="Percentage change vs previous period (2 decimal places)"
    )
    
    # Timeline
    timeline: List[AdminOverrideTimelinePoint] = Field(
        default_factory=list,
        description="Override activity over time"
    )
    
    @field_validator('override_rate_for_supervisor', 'percentage_change')
    @classmethod
    def validate_decimal_precision(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        """Ensure decimal fields have max 2 decimal places."""
        if v is None:
            return v
        return v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    
    @computed_field
    @property
    def most_common_override_type(self) -> Optional[str]:
        """Identify most common override type."""
        if not self.overrides_by_type:
            return None
        return max(self.overrides_by_type, key=self.overrides_by_type.get)
    
    @computed_field
    @property
    def most_overriding_admin(self) -> Optional[str]:
        """Identify admin performing most overrides."""
        if not self.overrides_by_admin:
            return None
        return max(self.overrides_by_admin, key=self.overrides_by_admin.get)


class AdminOverrideAnalytics(BaseSchema):
    """
    Advanced analytics for admin override patterns.
    
    Provides insights for process improvement and
    supervisory training needs identification.
    """
    
    period: DateTimeRangeFilter
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Summary
    summary: AdminOverrideSummary
    
    # Pattern analysis
    common_patterns: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Identified common override patterns"
    )
    
    # Root cause analysis
    root_causes: Dict[str, int] = Field(
        default_factory=dict,
        description="Root causes of overrides"
    )
    
    # Recommendations
    training_needs: List[str] = Field(
        default_factory=list,
        description="Identified training needs"
    )
    process_improvements: List[str] = Field(
        default_factory=list,
        description="Recommended process improvements"
    )
    
    # Supervisor rankings (by override frequency)
    supervisors_needing_support: List[UUID] = Field(
        default_factory=list,
        description="Supervisors who may need additional support"
    )
    
    @computed_field
    @property
    def overall_health_score(self) -> Decimal:
        """
        Calculate overall health score (0-100).
        
        Lower override rates and severity indicate better health.
        Note: Returns Decimal with 2 decimal places.
        """
        if self.summary.total_overrides == 0:
            return Decimal("100.00")
        
        # Factors
        volume_penalty = min(50, self.summary.total_overrides)
        severity_penalty = (
            self.summary.overrides_by_severity.get("critical", 0) * 10 +
            self.summary.overrides_by_severity.get("high", 0) * 5
        )
        
        total_penalty = min(100, volume_penalty + severity_penalty)
        score = 100 - total_penalty
        
        result = Decimal(str(max(0, score))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return result