# --- File: app/schemas/audit/audit_log_response.py ---
"""
Audit log response schemas with enhanced presentation.

Provides different views of audit log data for various use cases
including list views, detailed views, and aggregated summaries.
"""

from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional

from pydantic import Field, computed_field, field_validator
from uuid import UUID

from app.schemas.common.base import BaseResponseSchema
from app.schemas.common.enums import AuditActionCategory, UserRole

__all__ = [
    "AuditLogResponse",
    "AuditLogDetail",
    "AuditLogSummary",
    "AuditLogTimeline",
]


class AuditLogResponse(BaseResponseSchema):
    """
    Audit log list item for tables and lists.
    
    Provides essential information for displaying audit logs
    in list views with minimal data transfer.
    """
    
    # ID fields
    id: UUID = Field(..., description="Audit log entry ID")
    
    # Actor
    user_id: Optional[UUID] = Field(default=None, description="User who performed action")
    user_email: Optional[str] = Field(default=None, description="User email")
    user_role: Optional[UserRole] = Field(default=None, description="User role")
    
    # Action
    action_type: str = Field(..., description="Action type identifier")
    action_category: AuditActionCategory = Field(..., description="Action category")
    action_description: str = Field(..., description="Action description")
    
    # Entity
    entity_type: Optional[str] = Field(default=None, description="Affected entity type")
    entity_id: Optional[UUID] = Field(default=None, description="Affected entity ID")
    entity_name: Optional[str] = Field(default=None, description="Entity display name")
    
    # Context
    hostel_id: Optional[UUID] = Field(default=None, description="Hostel context")
    hostel_name: Optional[str] = Field(default=None, description="Hostel name")
    
    # Status
    status: str = Field(..., description="Action status")
    
    # Network
    ip_address: Optional[str] = Field(default=None, description="Source IP address")
    
    # Timestamps
    created_at: datetime = Field(..., description="When action occurred")
    
    # Security
    is_sensitive: bool = Field(default=False, description="Contains sensitive data")
    severity_level: Optional[str] = Field(default=None, description="Severity level")
    
    @computed_field
    @property
    def display_text(self) -> str:
        """Generate display-friendly text for UI."""
        parts = []
        
        if self.user_email:
            parts.append(self.user_email)
        
        parts.append(self.action_description)
        
        if self.entity_name:
            parts.append(f"({self.entity_name})")
        
        return " ".join(parts)
    
    @computed_field
    @property
    def status_badge_color(self) -> str:
        """Get color for status badge in UI."""
        status_colors = {
            "success": "green",
            "failure": "red",
            "partial": "yellow",
            "pending": "blue",
        }
        return status_colors.get(self.status, "gray")
    
    @computed_field
    @property
    def category_icon(self) -> str:
        """Get icon identifier for the action category."""
        icons = {
            AuditActionCategory.AUTHENTICATION: "lock",
            AuditActionCategory.AUTHORIZATION: "shield",
            AuditActionCategory.USER_MANAGEMENT: "users",
            AuditActionCategory.HOSTEL_MANAGEMENT: "building",
            AuditActionCategory.BOOKING: "calendar",
            AuditActionCategory.PAYMENT: "credit-card",
            AuditActionCategory.COMPLAINT: "alert-circle",
            AuditActionCategory.ATTENDANCE: "check-square",
            AuditActionCategory.MAINTENANCE: "tool",
            AuditActionCategory.ANNOUNCEMENT: "megaphone",
            AuditActionCategory.STUDENT_MANAGEMENT: "user-check",
            AuditActionCategory.SUPERVISOR_MANAGEMENT: "user-cog",
            AuditActionCategory.CONFIGURATION: "settings",
            AuditActionCategory.OTHER: "info",
        }
        return icons.get(self.action_category, "info")


class AuditLogDetail(BaseResponseSchema):
    """
    Detailed audit log view with complete information.
    
    Includes all fields and metadata for detailed inspection
    and forensic analysis.
    """
    
    # ID fields
    id: UUID = Field(..., description="Audit log entry ID")
    
    # Actor information
    user_id: Optional[UUID] = Field(default=None, description="User who performed action")
    user_email: Optional[str] = Field(default=None, description="User email")
    user_role: Optional[UserRole] = Field(default=None, description="User role at time of action")
    impersonator_id: Optional[UUID] = Field(
        default=None,
        description="User impersonating (if applicable)"
    )
    
    # Action details
    action_type: str = Field(..., description="Action type identifier")
    action_category: AuditActionCategory = Field(..., description="Action category")
    action_description: str = Field(..., description="Detailed action description")
    
    # Entity information
    entity_type: Optional[str] = Field(default=None, description="Affected entity type")
    entity_id: Optional[UUID] = Field(default=None, description="Affected entity ID")
    entity_name: Optional[str] = Field(default=None, description="Entity display name")
    
    # Related entity
    related_entity_type: Optional[str] = Field(default=None, description="Related entity type")
    related_entity_id: Optional[UUID] = Field(default=None, description="Related entity ID")
    
    # Context
    hostel_id: Optional[UUID] = Field(default=None, description="Hostel context")
    hostel_name: Optional[str] = Field(default=None, description="Hostel name")
    
    # Change tracking
    old_values: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Previous values"
    )
    new_values: Optional[Dict[str, Any]] = Field(
        default=None,
        description="New values"
    )
    changed_fields: List[str] = Field(
        default_factory=list,
        description="List of fields that changed"
    )
    
    # Request context
    ip_address: Optional[str] = Field(default=None, description="IP address")
    user_agent: Optional[str] = Field(default=None, description="User agent string")
    request_id: Optional[str] = Field(default=None, description="Request/trace ID")
    session_id: Optional[str] = Field(default=None, description="Session ID")
    
    # Geographic context
    country_code: Optional[str] = Field(default=None, description="Country code")
    region: Optional[str] = Field(default=None, description="Region/state")
    city: Optional[str] = Field(default=None, description="City")
    
    # Device context
    device_type: Optional[str] = Field(default=None, description="Device type")
    platform: Optional[str] = Field(default=None, description="Platform/OS")
    browser_name: Optional[str] = Field(default=None, description="Browser name")
    
    # API context
    api_version: Optional[str] = Field(default=None, description="API version")
    endpoint: Optional[str] = Field(default=None, description="API endpoint")
    http_method: Optional[str] = Field(default=None, description="HTTP method")
    
    # Status and result
    status: str = Field(..., description="Action status")
    error_message: Optional[str] = Field(default=None, description="Error message if failed")
    
    # Security
    is_sensitive: bool = Field(default=False, description="Contains sensitive data")
    severity_level: str = Field(..., description="Severity level")
    requires_review: bool = Field(default=False, description="Requires manual review")
    compliance_tags: List[str] = Field(
        default_factory=list,
        description="Compliance tags"
    )
    
    # Timestamps
    created_at: datetime = Field(..., description="When action occurred")
    
    # Retention
    retention_days: Optional[int] = Field(
        default=None,
        description="Retention period in days"
    )
    
    @computed_field
    @property
    def change_summary(self) -> Optional[str]:
        """Generate human-readable change summary."""
        if not self.changed_fields:
            return None
        
        if len(self.changed_fields) == 1:
            return f"Changed: {self.changed_fields[0]}"
        elif len(self.changed_fields) <= 3:
            return f"Changed: {', '.join(self.changed_fields)}"
        else:
            first_three = ', '.join(self.changed_fields[:3])
            remaining = len(self.changed_fields) - 3
            return f"Changed: {first_three} and {remaining} more"
    
    @computed_field
    @property
    def location_summary(self) -> Optional[str]:
        """Generate location summary string."""
        parts = []
        if self.city:
            parts.append(self.city)
        if self.region:
            parts.append(self.region)
        if self.country_code:
            parts.append(self.country_code)
        
        return ", ".join(parts) if parts else None
    
    def get_field_change(self, field_name: str) -> Optional[Dict[str, Any]]:
        """
        Get change details for a specific field.
        
        Args:
            field_name: Name of the field
            
        Returns:
            Dictionary with old_value and new_value, or None
        """
        if field_name not in self.changed_fields:
            return None
        
        return {
            "field": field_name,
            "old_value": self.old_values.get(field_name) if self.old_values else None,
            "new_value": self.new_values.get(field_name) if self.new_values else None,
        }


class AuditLogSummary(BaseResponseSchema):
    """
    Aggregated summary of audit logs.
    
    Provides statistical overview for dashboards and reports.
    """
    
    # Time period
    period_start: datetime = Field(..., description="Summary period start")
    period_end: datetime = Field(..., description="Summary period end")
    
    # Scope
    hostel_id: Optional[UUID] = Field(default=None, description="Hostel scope if applicable")
    user_id: Optional[UUID] = Field(default=None, description="User scope if applicable")
    
    # Overall metrics
    total_events: int = Field(..., ge=0, description="Total audit events")
    unique_users: int = Field(..., ge=0, description="Number of unique users")
    unique_ip_addresses: int = Field(..., ge=0, description="Number of unique IPs")
    
    # Status breakdown
    successful_actions: int = Field(..., ge=0, description="Successful actions")
    failed_actions: int = Field(..., ge=0, description="Failed actions")
    pending_actions: int = Field(..., ge=0, description="Pending actions")
    
    # Category breakdown
    events_by_category: Dict[str, int] = Field(
        default_factory=dict,
        description="Event count by category"
    )
    
    # User role breakdown
    events_by_role: Dict[str, int] = Field(
        default_factory=dict,
        description="Event count by user role"
    )
    
    # Top actions
    top_action_types: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Most frequent action types"
    )
    
    # Security metrics
    sensitive_events: int = Field(..., ge=0, description="Events with sensitive data")
    events_requiring_review: int = Field(
        ...,
        ge=0,
        description="Events requiring manual review"
    )
    critical_events: int = Field(..., ge=0, description="Critical severity events")
    high_severity_events: int = Field(..., ge=0, description="High severity events")
    
    # Anomaly indicators
    failed_login_attempts: int = Field(
        default=0,
        ge=0,
        description="Failed authentication attempts"
    )
    access_denied_count: int = Field(
        default=0,
        ge=0,
        description="Authorization failures"
    )
    unusual_activity_count: int = Field(
        default=0,
        ge=0,
        description="Flagged unusual activities"
    )
    
    @computed_field
    @property
    def success_rate(self) -> float:
        """Calculate success rate percentage."""
        if self.total_events == 0:
            return 100.0
        return round(
            (self.successful_actions / self.total_events) * 100,
            2
        )
    
    @computed_field
    @property
    def security_score(self) -> float:
        """
        Calculate security health score (0-100).
        
        Lower is better - indicates fewer security concerns.
        """
        if self.total_events == 0:
            return 100.0
        
        # Negative indicators
        penalties = (
            self.failed_login_attempts * 5 +
            self.access_denied_count * 3 +
            self.unusual_activity_count * 10 +
            self.critical_events * 15
        )
        
        # Normalize to 0-100 scale
        score = max(0, 100 - (penalties / self.total_events * 100))
        return round(score, 2)
    
    @computed_field
    @property
    def requires_attention(self) -> bool:
        """Check if summary indicates issues requiring attention."""
        return (
            self.security_score < 70 or
            self.failed_login_attempts > 10 or
            self.critical_events > 0 or
            self.unusual_activity_count > 5
        )


class AuditLogTimeline(BaseResponseSchema):
    """
    Timeline view of audit events.
    
    Organizes audit logs chronologically for timeline visualizations.
    """
    
    # Time bucket
    timestamp: datetime = Field(..., description="Timeline point timestamp")
    bucket_label: str = Field(..., description="Display label for time bucket")
    
    # Event counts
    event_count: int = Field(..., ge=0, description="Total events in bucket")
    
    # Category breakdown
    categories: Dict[str, int] = Field(
        default_factory=dict,
        description="Event count by category"
    )
    
    # Status breakdown
    successful: int = Field(..., ge=0, description="Successful events")
    failed: int = Field(..., ge=0, description="Failed events")
    
    # Severity
    critical_count: int = Field(default=0, ge=0, description="Critical events")
    high_count: int = Field(default=0, ge=0, description="High severity events")
    
    # Notable events (for highlighting)
    notable_events: List[AuditLogResponse] = Field(
        default_factory=list,
        max_length=5,
        description="Up to 5 notable events in this bucket"
    )
    
    @computed_field
    @property
    def severity_indicator(self) -> str:
        """Get overall severity indicator for this time bucket."""
        if self.critical_count > 0:
            return "critical"
        elif self.high_count > 0:
            return "high"
        elif self.failed > self.event_count * 0.1:  # >10% failures
            return "medium"
        else:
            return "normal"