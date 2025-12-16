# --- File: app/schemas/audit/audit_filters.py ---
"""
Enhanced audit log filtering schemas with advanced query capabilities.

Provides comprehensive filtering options for audit log queries
including time ranges, actors, entities, actions, and more.
"""

from datetime import date as Date, datetime

from typing import List, Union
from enum import Enum

from pydantic import Field, field_validator, model_validator, computed_field
from uuid import UUID

from app.schemas.common.base import BaseFilterSchema
from app.schemas.common.enums import AuditActionCategory, UserRole
from app.schemas.common.filters import DateTimeRangeFilter

__all__ = [
    "AuditSortField",
    "AuditFilterParams",
    "AuditSearchParams",
    "AuditExportParams",
]


class AuditSortField(str, Enum):
    """Available sort fields for audit logs."""
    
    CREATED_AT = "created_at"
    ACTION_TYPE = "action_type"
    USER_ID = "user_id"
    ENTITY_TYPE = "entity_type"
    STATUS = "status"
    SEVERITY = "severity_level"


class AuditFilterParams(BaseFilterSchema):
    """
    Comprehensive filter criteria for querying audit logs.
    
    Supports filtering by actor, action, entity, time, location,
    and various other dimensions for precise audit queries.
    """
    
    # Actor filters
    user_id: Union[UUID, None] = Field(
        default=None,
        description="Filter by specific user"
    )
    user_ids: Union[List[UUID], None] = Field(
        default=None,
        max_length=50,
        description="Filter by list of users"
    )
    user_role: Union[UserRole, None] = Field(
        default=None,
        description="Filter by user role"
    )
    user_roles: Union[List[UserRole], None] = Field(
        default=None,
        max_length=10,
        description="Filter by multiple user roles"
    )
    user_email: Union[str, None] = Field(
        default=None,
        max_length=255,
        description="Filter by user email (partial match)"
    )
    exclude_user_ids: Union[List[UUID], None] = Field(
        default=None,
        max_length=50,
        description="Exclude specific users"
    )
    
    # Impersonation
    impersonator_id: Union[UUID, None] = Field(
        default=None,
        description="Filter by impersonator"
    )
    include_impersonated: bool = Field(
        default=True,
        description="Include impersonated actions"
    )
    
    # Hostel context
    hostel_id: Union[UUID, None] = Field(
        default=None,
        description="Filter by hostel"
    )
    hostel_ids: Union[List[UUID], None] = Field(
        default=None,
        max_length=100,
        description="Filter by multiple hostels"
    )
    
    # Entity filters
    entity_type: Union[str, None] = Field(
        default=None,
        max_length=50,
        description="Filter by entity type"
    )
    entity_types: Union[List[str], None] = Field(
        default=None,
        max_length=20,
        description="Filter by multiple entity types"
    )
    entity_id: Union[UUID, None] = Field(
        default=None,
        description="Filter by specific entity"
    )
    entity_ids: Union[List[UUID], None] = Field(
        default=None,
        max_length=100,
        description="Filter by multiple entities"
    )
    
    # Action filters
    action_type: Union[str, None] = Field(
        default=None,
        max_length=100,
        description="Filter by action type"
    )
    action_types: Union[List[str], None] = Field(
        default=None,
        max_length=50,
        description="Filter by multiple action types"
    )
    action_category: Union[AuditActionCategory, None] = Field(
        default=None,
        description="Filter by action category"
    )
    action_categories: Union[List[AuditActionCategory], None] = Field(
        default=None,
        max_length=15,
        description="Filter by multiple categories"
    )
    action_pattern: Union[str, None] = Field(
        default=None,
        max_length=100,
        description="Filter by action type pattern (supports wildcards)"
    )
    
    # Time range filters
    datetime_range: Union[DateTimeRangeFilter, None] = Field(
        default=None,
        description="Filter by datetime range"
    )
    created_after: Union[datetime, None] = Field(
        default=None,
        description="Filter events after this datetime"
    )
    created_before: Union[datetime, None] = Field(
        default=None,
        description="Filter events before this datetime"
    )
    
    # Quick time filters
    last_hours: Union[int, None] = Field(
        default=None,
        ge=1,
        le=720,  # Max 30 days
        description="Filter events in last N hours"
    )
    last_days: Union[int, None] = Field(
        default=None,
        ge=1,
        le=365,
        description="Filter events in last N days"
    )
    
    # Status filters
    status: Union[str, None] = Field(
        default=None,
        pattern="^(success|failure|partial|pending)$",
        description="Filter by status"
    )
    statuses: Union[List[str], None] = Field(
        default=None,
        max_length=4,
        description="Filter by multiple statuses"
    )
    only_failures: bool = Field(
        default=False,
        description="Show only failed actions"
    )
    
    # Severity filters
    severity_level: Union[str, None] = Field(
        default=None,
        pattern="^(critical|high|medium|low|info)$",
        description="Filter by severity level"
    )
    min_severity: Union[str, None] = Field(
        default=None,
        pattern="^(critical|high|medium|low|info)$",
        description="Minimum severity level"
    )
    
    # Security filters
    is_sensitive: Union[bool, None] = Field(
        default=None,
        description="Filter by sensitive data flag"
    )
    requires_review: Union[bool, None] = Field(
        default=None,
        description="Filter by review requirement"
    )
    compliance_tag: Union[str, None] = Field(
        default=None,
        max_length=50,
        description="Filter by compliance tag"
    )
    
    # Network filters
    ip_address: Union[str, None] = Field(
        default=None,
        description="Filter by IP address"
    )
    ip_addresses: Union[List[str], None] = Field(
        default=None,
        max_length=100,
        description="Filter by multiple IP addresses"
    )
    country_code: Union[str, None] = Field(
        default=None,
        pattern=r"^[A-Z]{2}$",
        description="Filter by country code"
    )
    
    # Device filters
    device_type: Union[str, None] = Field(
        default=None,
        pattern="^(desktop|mobile|tablet|api|system)$",
        description="Filter by device type"
    )
    platform: Union[str, None] = Field(
        default=None,
        max_length=50,
        description="Filter by platform/OS"
    )
    
    # Request context
    request_id: Union[str, None] = Field(
        default=None,
        max_length=100,
        description="Filter by request ID"
    )
    session_id: Union[str, None] = Field(
        default=None,
        max_length=100,
        description="Filter by session ID"
    )
    
    # Change filters
    has_changes: Union[bool, None] = Field(
        default=None,
        description="Filter by presence of value changes"
    )
    changed_field: Union[str, None] = Field(
        default=None,
        max_length=100,
        description="Filter by specific changed field"
    )
    
    # Search
    search_query: Union[str, None] = Field(
        default=None,
        min_length=1,
        max_length=500,
        description="Full-text search in descriptions"
    )
    
    # Sorting
    sort_by: AuditSortField = Field(
        default=AuditSortField.CREATED_AT,
        description="Field to sort by"
    )
    sort_order: str = Field(
        default="desc",
        pattern="^(asc|desc)$",
        description="Sort order"
    )
    
    # Pagination
    page: int = Field(
        default=1,
        ge=1,
        description="Page number"
    )
    page_size: int = Field(
        default=50,
        ge=1,
        le=200,
        description="Items per page"
    )
    
    @model_validator(mode='after')
    def validate_time_filters(self) -> 'AuditFilterParams':
        """Validate time filter combinations."""
        
        time_filters = [
            self.datetime_range,
            self.created_after,
            self.created_before,
            self.last_hours,
            self.last_days
        ]
        
        # Count non-None time filters
        active_filters = sum(1 for f in time_filters if f is not None)
        
        # Can't use both datetime_range and individual datetime filters
        if self.datetime_range and (self.created_after or self.created_before):
            raise ValueError(
                "Cannot use datetime_range with created_after/created_before"
            )
        
        # Can't use both last_hours and last_days
        if self.last_hours and self.last_days:
            raise ValueError(
                "Cannot use both last_hours and last_days"
            )
        
        return self
    
    @model_validator(mode='after')
    def validate_list_filters(self) -> 'AuditFilterParams':
        """Validate that single and list filters aren't both used."""
        
        conflicts = [
            ('user_id', 'user_ids'),
            ('user_role', 'user_roles'),
            ('hostel_id', 'hostel_ids'),
            ('entity_type', 'entity_types'),
            ('entity_id', 'entity_ids'),
            ('action_type', 'action_types'),
            ('action_category', 'action_categories'),
            ('status', 'statuses'),
            ('ip_address', 'ip_addresses'),
        ]
        
        for single, multiple in conflicts:
            if getattr(self, single) and getattr(self, multiple):
                raise ValueError(
                    f"Cannot use both {single} and {multiple} filters"
                )
        
        return self
    
    @computed_field
    @property
    def has_active_filters(self) -> bool:
        """Check if any filters are active."""
        # Exclude pagination and sorting
        exclude_fields = {
            'page', 'page_size', 'sort_by', 'sort_order',
            'include_impersonated', 'only_failures'
        }
        
        for field_name, value in self.model_dump(exclude_unset=True).items():
            if field_name not in exclude_fields and value is not None:
                return True
        
        return False


class AuditSearchParams(BaseFilterSchema):
    """
    Advanced search parameters for audit logs.
    
    Provides text search capabilities with optional filters.
    """
    
    # Search query
    query: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Search query string"
    )
    
    # Search fields
    search_in_description: bool = Field(
        default=True,
        description="Search in action descriptions"
    )
    search_in_entity_names: bool = Field(
        default=True,
        description="Search in entity names"
    )
    search_in_user_emails: bool = Field(
        default=False,
        description="Search in user emails"
    )
    search_in_values: bool = Field(
        default=False,
        description="Search in old/new values"
    )
    
    # Search options
    case_sensitive: bool = Field(
        default=False,
        description="Case-sensitive search"
    )
    fuzzy_search: bool = Field(
        default=False,
        description="Enable fuzzy matching"
    )
    exact_phrase: bool = Field(
        default=False,
        description="Match exact phrase only"
    )
    
    # Additional filters (subset from AuditFilterParams)
    datetime_range: Union[DateTimeRangeFilter, None] = None
    action_category: Union[AuditActionCategory, None] = None
    severity_level: Union[str, None] = Field(
        default=None,
        pattern="^(critical|high|medium|low|info)$"
    )
    
    # Results
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class AuditExportParams(BaseFilterSchema):
    """
    Parameters for exporting audit logs.
    
    Defines export format, filters, and output options.
    """
    
    # Export format
    format: str = Field(
        ...,
        pattern="^(csv|json|xlsx|pdf)$",
        description="Export file format"
    )
    
    # Filters (reuse from AuditFilterParams)
    filters: AuditFilterParams = Field(
        default_factory=AuditFilterParams,
        description="Filter criteria for export"
    )
    
    # Field selection
    include_fields: Union[List[str], None] = Field(
        default=None,
        max_length=50,
        description="Specific fields to include (if None, include all)"
    )
    exclude_fields: Union[List[str], None] = Field(
        default=None,
        max_length=50,
        description="Fields to exclude from export"
    )
    
    # Privacy options
    redact_sensitive: bool = Field(
        default=True,
        description="Redact sensitive data in export"
    )
    mask_ip_addresses: bool = Field(
        default=False,
        description="Mask IP addresses in export"
    )
    anonymize_users: bool = Field(
        default=False,
        description="Anonymize user identifiers"
    )
    
    # Output options
    include_summary: bool = Field(
        default=True,
        description="Include summary statistics"
    )
    include_charts: bool = Field(
        default=False,
        description="Include charts (for PDF/XLSX)"
    )
    
    # Limits
    max_records: int = Field(
        default=10000,
        ge=1,
        le=100000,
        description="Maximum records to export"
    )
    
    @model_validator(mode='after')
    def validate_field_selections(self) -> 'AuditExportParams':
        """Validate field inclusion/exclusion."""
        
        if self.include_fields and self.exclude_fields:
            # Check for conflicts
            overlap = set(self.include_fields) & set(self.exclude_fields)
            if overlap:
                raise ValueError(
                    f"Fields cannot be both included and excluded: {overlap}"
                )
        
        return self