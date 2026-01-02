# --- File: app/schemas/notification/notification_template.py ---
"""
Notification template schemas.

This module provides schemas for managing reusable notification templates
with variable substitution and template rendering.
"""

from datetime import datetime
from typing import Dict, List, Union
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.schemas.common.base import (
    BaseCreateSchema,
    BaseResponseSchema,
    BaseSchema,
    BaseUpdateSchema,
)
from app.schemas.common.enums import NotificationType

__all__ = [
    "TemplateCreate",
    "TemplateUpdate",
    "TemplateResponse",
    "VariableMapping",
    "TemplatePreview",
    "TemplatePreviewResponse",
    "TemplateList",
    "TemplateCategory",
    "TemplateCopyRequest",
    # Aliases for API
    "NotificationTemplate",
    "NotificationTemplateCreate",
    "NotificationTemplateUpdate",
    "TemplatePreviewRequest",
]


class TemplateCreate(BaseCreateSchema):
    """
    Schema for creating a notification template.

    Templates support variable substitution using {{variable_name}} syntax.
    """

    template_code: str = Field(
        ...,
        min_length=3,
        max_length=100,
        pattern="^[a-z0-9_]+$",
        description="Unique template code (lowercase, numbers, underscores only)",
    )
    template_name: str = Field(
        ...,
        min_length=3,
        max_length=255,
        description="Human-readable template name",
    )

    # Template type
    template_type: NotificationType = Field(
        ...,
        description="Notification channel this template is for",
    )

    # Content with variable support
    subject: Union[str, None] = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Subject template (required for email/push, supports {{variables}})",
    )
    body_template: str = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="Body template with {{variable}} placeholders",
    )

    # Variables
    variables: List[str] = Field(
        default_factory=list,
        description="List of required template variables",
    )
    optional_variables: List[str] = Field(
        default_factory=list,
        description="List of optional template variables",
    )

    # Metadata
    category: Union[str, None] = Field(
        default=None,
        max_length=100,
        description="Template category for organization",
    )
    tags: List[str] = Field(
        default_factory=list,
        max_length=20,
        description="Tags for template discovery",
    )

    # Settings
    is_active: bool = Field(
        default=True,
        description="Whether template is active and available for use",
    )
    description: Union[str, None] = Field(
        default=None,
        max_length=500,
        description="Template description and usage notes",
    )

    # Localization
    language: str = Field(
        default="en",
        min_length=2,
        max_length=5,
        description="Template language code (e.g., 'en', 'hi')",
    )

    @field_validator("template_code")
    @classmethod
    def validate_template_code(cls, v: str) -> str:
        """Ensure template code follows naming conventions."""
        if not v.islower():
            raise ValueError("Template code must be lowercase")
        if "__" in v:
            raise ValueError("Template code cannot contain consecutive underscores")
        if v.startswith("_") or v.endswith("_"):
            raise ValueError("Template code cannot start or end with underscore")
        return v

    @field_validator("variables", "optional_variables")
    @classmethod
    def validate_variable_names(cls, v: List[str]) -> List[str]:
        """Validate variable names are valid identifiers."""
        for var in v:
            if not var.replace("_", "").isalnum():
                raise ValueError(
                    f"Invalid variable name '{var}'. Must contain only letters, numbers, and underscores"
                )
            if var.startswith("_"):
                raise ValueError(f"Variable name '{var}' cannot start with underscore")
        return v

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: List[str]) -> List[str]:
        """Validate and normalize tags."""
        # Remove duplicates and normalize
        normalized = list(set(tag.lower().strip() for tag in v if tag.strip()))
        if len(normalized) > 20:
            raise ValueError("Maximum 20 tags allowed")
        return normalized

    @model_validator(mode="after")
    def validate_subject_for_type(self) -> "TemplateCreate":
        """Ensure subject is provided for email and push templates."""
        if self.template_type in [NotificationType.EMAIL, NotificationType.PUSH]:
            if not self.subject:
                raise ValueError(
                    f"Subject is required for {self.template_type.value} templates"
                )
        return self

    @model_validator(mode="after")
    def validate_variables_in_template(self) -> "TemplateCreate":
        """Validate that declared variables exist in templates."""
        import re

        # Extract variables from templates
        variable_pattern = r"\{\{(\w+)\}\}"
        subject_vars = set(re.findall(variable_pattern, self.subject or ""))
        body_vars = set(re.findall(variable_pattern, self.body_template))
        all_template_vars = subject_vars | body_vars

        # Check declared variables
        declared_vars = set(self.variables + self.optional_variables)

        # Undeclared variables
        undeclared = all_template_vars - declared_vars
        if undeclared:
            raise ValueError(
                f"Template contains undeclared variables: {', '.join(undeclared)}"
            )

        # Unused variables (warning-level, but we'll allow it)
        # unused = declared_vars - all_template_vars

        return self


class TemplateUpdate(BaseUpdateSchema):
    """
    Schema for updating an existing template.

    Template code cannot be changed after creation.
    """

    template_name: Union[str, None] = Field(
        default=None,
        min_length=3,
        max_length=255,
        description="Updated template name",
    )
    subject: Union[str, None] = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Updated subject template",
    )
    body_template: Union[str, None] = Field(
        default=None,
        min_length=1,
        max_length=10000,
        description="Updated body template",
    )
    variables: Union[List[str], None] = Field(
        default=None,
        description="Updated required variables list",
    )
    optional_variables: Union[List[str], None] = Field(
        default=None,
        description="Updated optional variables list",
    )
    category: Union[str, None] = Field(
        default=None,
        max_length=100,
        description="Updated category",
    )
    tags: Union[List[str], None] = Field(
        default=None,
        description="Updated tags",
    )
    is_active: Union[bool, None] = Field(
        default=None,
        description="Updated active status",
    )
    description: Union[str, None] = Field(
        default=None,
        max_length=500,
        description="Updated description",
    )


class TemplateResponse(BaseResponseSchema):
    """
    Template response schema.

    Includes template details and usage statistics.
    """

    template_code: str = Field(
        ...,
        description="Unique template identifier",
    )
    template_name: str = Field(
        ...,
        description="Template name",
    )
    template_type: NotificationType = Field(
        ...,
        description="Notification channel",
    )

    # Content
    subject: Union[str, None] = Field(
        default=None,
        description="Subject template",
    )
    body_template: str = Field(
        ...,
        description="Body template",
    )

    # Variables
    variables: List[str] = Field(
        ...,
        description="Required variables",
    )
    optional_variables: List[str] = Field(
        default_factory=list,
        description="Optional variables",
    )

    # Metadata
    category: Union[str, None] = Field(
        default=None,
        description="Template category",
    )
    tags: List[str] = Field(
        default_factory=list,
        description="Template tags",
    )
    language: str = Field(
        ...,
        description="Template language",
    )

    # Status
    is_active: bool = Field(
        ...,
        description="Active status",
    )
    description: Union[str, None] = Field(
        default=None,
        description="Template description",
    )

    # Usage statistics
    usage_count: int = Field(
        default=0,
        ge=0,
        description="Number of times template has been used",
    )
    last_used_at: Union[datetime, None] = Field(
        default=None,
        description="When template was last used",
    )

    # Audit
    created_at: datetime = Field(
        ...,
        description="Creation timestamp",
    )
    updated_at: datetime = Field(
        ...,
        description="Last update timestamp",
    )
    created_by: Union[UUID, None] = Field(
        default=None,
        description="User who created the template",
    )


class VariableMapping(BaseSchema):
    """
    Variable mapping for template rendering.

    Maps template variable names to their runtime values.
    """

    template_code: str = Field(
        ...,
        min_length=3,
        max_length=100,
        description="Template code to render",
    )
    variables: Dict[str, str] = Field(
        ...,
        description="Variable name to value mapping",
    )

    @field_validator("variables")
    @classmethod
    def validate_variable_values(cls, v: Dict[str, str]) -> Dict[str, str]:
        """Validate variable values are non-empty strings."""
        for key, value in v.items():
            if not isinstance(value, str):
                raise ValueError(f"Variable '{key}' must be a string value")
            if not value.strip():
                raise ValueError(f"Variable '{key}' cannot be empty")
        return v


class TemplatePreview(BaseCreateSchema):
    """
    Request schema for previewing a rendered template.

    Useful for testing templates before deployment.
    """

    template_code: str = Field(
        ...,
        description="Template code to preview",
    )
    variables: Dict[str, str] = Field(
        ...,
        description="Variable values for rendering",
    )
    use_defaults: bool = Field(
        default=False,
        description="Use default values for missing optional variables",
    )


class TemplatePreviewResponse(BaseSchema):
    """
    Rendered template preview response.

    Shows the final rendered content and validation results.
    """

    template_code: str = Field(
        ...,
        description="Template code",
    )
    subject: Union[str, None] = Field(
        default=None,
        description="Rendered subject",
    )
    rendered_body: str = Field(
        ...,
        description="Rendered message body",
    )

    # Validation results
    all_variables_provided: bool = Field(
        ...,
        description="Whether all required variables were provided",
    )
    missing_variables: List[str] = Field(
        default_factory=list,
        description="List of missing required variables",
    )
    unused_variables: List[str] = Field(
        default_factory=list,
        description="Provided variables not used in template",
    )

    # Character counts (useful for SMS)
    subject_length: Union[int, None] = Field(
        default=None,
        description="Length of rendered subject",
    )
    body_length: int = Field(
        ...,
        description="Length of rendered body",
    )
    estimated_sms_segments: Union[int, None] = Field(
        default=None,
        description="Estimated SMS segments (if applicable)",
    )


class TemplateList(BaseSchema):
    """
    List of templates with summary statistics.
    """

    total_templates: int = Field(
        ...,
        ge=0,
        description="Total number of templates",
    )
    active_templates: int = Field(
        ...,
        ge=0,
        description="Number of active templates",
    )
    templates_by_type: Dict[str, int] = Field(
        default_factory=dict,
        description="Template count by notification type",
    )
    templates: List[TemplateResponse] = Field(
        ...,
        description="List of templates",
    )


class TemplateCategory(BaseSchema):
    """
    Templates grouped by category.

    Useful for organizing templates in UI.
    """

    category_name: str = Field(
        ...,
        description="Category name",
    )
    category_description: Union[str, None] = Field(
        default=None,
        description="Category description",
    )
    template_count: int = Field(
        ...,
        ge=0,
        description="Number of templates in category",
    )
    templates: List[TemplateResponse] = Field(
        ...,
        description="Templates in this category",
    )


class TemplateCopyRequest(BaseCreateSchema):
    """
    Request to copy an existing template.

    Creates a new template based on an existing one.
    """

    source_template_code: str = Field(
        ...,
        description="Template code to copy from",
    )
    new_template_code: str = Field(
        ...,
        min_length=3,
        max_length=100,
        pattern="^[a-z0-9_]+$",
        description="New template code",
    )
    new_template_name: str = Field(
        ...,
        min_length=3,
        max_length=255,
        description="New template name",
    )
    copy_metadata: bool = Field(
        default=True,
        description="Copy category, tags, and description",
    )


# Type aliases for API consistency
NotificationTemplate = TemplateResponse
NotificationTemplateCreate = TemplateCreate
NotificationTemplateUpdate = TemplateUpdate
TemplatePreviewRequest = TemplatePreview