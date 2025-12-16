# --- File: app/schemas/mess/menu_duplication.py ---
"""
Menu duplication and bulk creation schemas.

Provides efficient menu replication capabilities for
recurring patterns and multi-hostel deployment.
"""

from datetime import date as Date, timedelta
from decimal import Decimal
from typing import Dict, List, Union
from uuid import UUID

from pydantic import Field, field_validator, model_validator, computed_field

from app.schemas.common.base import BaseCreateSchema, BaseSchema

__all__ = [
    "DuplicateMenuRequest",
    "BulkMenuCreate",
    "DuplicateResponse",
    "CrossHostelDuplication",
    "MenuCloneConfig",
]


class DuplicateMenuRequest(BaseCreateSchema):
    """
    Duplicate existing menu to another Date.
    
    Creates copy of menu with optional modifications for
    efficient menu planning.
    """

    source_menu_id: UUID = Field(
        ...,
        description="Menu to duplicate",
    )
    target_date: Date = Field(
        ...,
        description="Date for duplicated menu",
    )
    
    # Duplication options
    copy_all_meals: bool = Field(
        default=True,
        description="Copy all meal items",
    )
    copy_breakfast: bool = Field(
        default=True,
        description="Copy breakfast items",
    )
    copy_lunch: bool = Field(
        default=True,
        description="Copy lunch items",
    )
    copy_snacks: bool = Field(
        default=True,
        description="Copy snacks items",
    )
    copy_dinner: bool = Field(
        default=True,
        description="Copy dinner items",
    )
    
    # Modification options
    modify_items: bool = Field(
        False,
        description="Allow item modifications during duplication",
    )
    modifications: Union[Dict[str, List[str]], None] = Field(
        None,
        description="Meal-wise item modifications {meal_type: [items]}",
    )
    
    # Additional settings
    preserve_special_status: bool = Field(
        default=True,
        description="Keep special menu status",
    )
    auto_publish: bool = Field(
        default=False,
        description="Automatically publish duplicated menu",
    )
    created_by: UUID = Field(
        ...,
        description="User creating the duplicate",
    )

    @field_validator("target_date", mode="after")
    @classmethod
    def validate_target_date(cls, v: Date) -> Date:
        """Validate target Date is appropriate for duplication."""
        # Can't duplicate to past dates
        if v < Date.today():
            raise ValueError("Cannot duplicate menu to past dates")
        
        # Limit advance duplication
        days_ahead = (v - Date.today()).days
        if days_ahead > 90:
            raise ValueError(
                "Cannot duplicate menu more than 90 days in advance"
            )
        
        return v

    @model_validator(mode="after")
    def validate_meal_selection(self) -> "DuplicateMenuRequest":
        """Ensure at least one meal is selected for copying."""
        if not self.copy_all_meals:
            if not any([
                self.copy_breakfast,
                self.copy_lunch,
                self.copy_snacks,
                self.copy_dinner,
            ]):
                raise ValueError(
                    "At least one meal must be selected for duplication"
                )
        
        return self


class BulkMenuCreate(BaseCreateSchema):
    """
    Create menus for multiple dates using template or pattern.
    
    Efficiently generates menus for Date range using various sources.
    """

    hostel_id: UUID = Field(
        ...,
        description="Hostel unique identifier",
    )
    
    # Date range
    start_date: Date = Field(
        ...,
        description="Start Date for menu creation",
    )
    end_date: Date = Field(
        ...,
        description="End Date for menu creation",
    )
    
    # Source configuration
    source_type: str = Field(
        ...,
        pattern=r"^(template|existing_menu|weekly_pattern|daily_rotation)$",
        description="Source for menu creation",
    )
    
    # Template-based
    template_id: Union[UUID, None] = Field(
        None,
        description="Template ID (if source_type is 'template')",
    )
    
    # Existing menu-based
    source_menu_id: Union[UUID, None] = Field(
        None,
        description="Source menu ID (if source_type is 'existing_menu')",
    )
    
    # Weekly pattern-based
    weekly_pattern: Union[Dict[str, Dict[str, List[str]]], None] = Field(
        None,
        description="Day of week -> meal_type -> items mapping",
    )
    
    # Daily rotation
    rotation_items: Union[List[Dict[str, List[str]]], None] = Field(
        None,
        description="List of daily menus to rotate through",
    )
    rotation_interval_days: Union[int, None] = Field(
        None,
        ge=1,
        le=30,
        description="Days before rotation repeats",
    )
    
    # Creation options
    skip_existing: bool = Field(
        True,
        description="Skip dates that already have menus",
    )
    override_existing: bool = Field(
        False,
        description="Override existing menus",
    )
    skip_weekends: bool = Field(
        False,
        description="Skip Saturday and Sunday",
    )
    skip_holidays: bool = Field(
        False,
        description="Skip public holidays",
    )
    
    # Auto-publish
    auto_publish_all: bool = Field(
        default=False,
        description="Automatically publish all created menus",
    )
    
    # Creator
    created_by: UUID = Field(
        ...,
        description="User creating menus",
    )

    @field_validator("start_date", mode="after")
    @classmethod
    def validate_start_date(cls, v: Date) -> Date:
        """Validate start Date constraints."""
        # Allow starting from yesterday for convenience
        if v < Date.today() - timedelta(days=1):
            raise ValueError(
                "Start Date cannot be more than 1 day in the past"
            )
        return v

    @model_validator(mode="after")
    def validate_bulk_create(self) -> "BulkMenuCreate":
        """Validate bulk creation configuration."""
        # Validate Date range
        if self.end_date < self.start_date:
            raise ValueError("End Date must be after start Date")
        
        # Limit bulk creation period
        days_span = (self.end_date - self.start_date).days + 1
        if days_span > 90:
            raise ValueError(
                "Bulk creation period cannot exceed 90 days"
            )
        
        # Validate source-specific requirements
        if self.source_type == "template":
            if not self.template_id:
                raise ValueError(
                    "template_id is required when source_type is 'template'"
                )
        
        elif self.source_type == "existing_menu":
            if not self.source_menu_id:
                raise ValueError(
                    "source_menu_id is required when source_type is 'existing_menu'"
                )
        
        elif self.source_type == "weekly_pattern":
            if not self.weekly_pattern:
                raise ValueError(
                    "weekly_pattern is required when source_type is 'weekly_pattern'"
                )
        
        elif self.source_type == "daily_rotation":
            if not self.rotation_items:
                raise ValueError(
                    "rotation_items is required when source_type is 'daily_rotation'"
                )
        
        # Can't both skip and override existing
        if self.skip_existing and self.override_existing:
            raise ValueError(
                "Cannot both skip and override existing menus"
            )
        
        return self


class DuplicateResponse(BaseSchema):
    """
    Menu duplication response with results.
    
    Provides summary of duplication operation results.
    """

    source_menu_id: UUID = Field(
        ...,
        description="Source menu ID",
    )
    source_menu_date: Date = Field(
        ...,
        description="Source menu Date",
    )
    created_menus: List[UUID] = Field(
        ...,
        description="IDs of created menus",
    )
    created_dates: List[Date] = Field(
        ...,
        description="Dates for which menus were created",
    )
    total_created: int = Field(
        ...,
        ge=0,
        description="Total menus created",
    )
    skipped: int = Field(
        default=0,
        ge=0,
        description="Dates skipped (already had menus)",
    )
    failed: int = Field(
        default=0,
        ge=0,
        description="Failed creation attempts",
    )
    message: str = Field(
        ...,
        description="Operation summary message",
    )
    warnings: List[str] = Field(
        default_factory=list,
        description="Warnings during operation",
    )
    errors: List[str] = Field(
        default_factory=list,
        description="Errors encountered",
    )

    @computed_field
    @property
    def success_rate(self) -> Decimal:
        """Calculate success rate percentage."""
        total_attempted = self.total_created + self.failed
        
        if total_attempted == 0:
            return Decimal("0.00")
        
        return round(
            Decimal(self.total_created) / Decimal(total_attempted) * 100,
            2,
        )


class CrossHostelDuplication(BaseCreateSchema):
    """
    Duplicate menu across multiple hostels.
    
    Replicates menu to other hostels with optional adaptation
    for hostel-specific preferences.
    """

    source_menu_id: UUID = Field(
        ...,
        description="Source menu unique identifier",
    )
    source_hostel_id: UUID = Field(
        ...,
        description="Source hostel ID",
    )
    target_hostel_ids: List[UUID] = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Target hostel IDs",
    )
    target_date: Date = Field(
        ...,
        description="Date for duplicated menus in target hostels",
    )
    
    # Adaptation options
    adapt_to_hostel_preferences: bool = Field(
        True,
        description="Adapt menu to each hostel's dietary preferences",
    )
    adapt_dietary_options: bool = Field(
        default=True,
        description="Adjust vegetarian/non-veg based on hostel settings",
    )
    adapt_regional_preferences: bool = Field(
        default=True,
        description="Adapt to regional food preferences",
    )
    
    # Item substitution
    allow_item_substitution: bool = Field(
        default=True,
        description="Allow substituting unavailable items",
    )
    substitution_rules: Union[Dict[str, str], None] = Field(
        None,
        description="Item substitution mapping {original: substitute}",
    )
    
    # Cost adjustment
    adjust_for_hostel_budget: bool = Field(
        default=False,
        description="Adjust menu to fit hostel budget",
    )
    
    # Creation options
    skip_existing: bool = Field(
        default=True,
        description="Skip hostels that already have menu for Date",
    )
    created_by: UUID = Field(
        ...,
        description="User performing cross-hostel duplication",
    )

    @field_validator("target_hostel_ids", mode="after")
    @classmethod
    def validate_unique_hostels(cls, v: List[UUID]) -> List[UUID]:
        """Ensure no duplicate hostel IDs."""
        if len(v) != len(set(v)):
            raise ValueError("Duplicate hostel IDs not allowed")
        return v

    @model_validator(mode="after")
    def validate_source_not_in_targets(self) -> "CrossHostelDuplication":
        """Ensure source hostel is not in target list."""
        if self.source_hostel_id in self.target_hostel_ids:
            raise ValueError(
                "Source hostel cannot be in target hostel list"
            )
        return self


class MenuCloneConfig(BaseSchema):
    """
    Configuration for menu cloning operations.
    
    Defines rules and preferences for menu duplication.
    """

    preserve_special_occasions: bool = Field(
        default=True,
        description="Keep special menu flags when cloning",
    )
    preserve_meal_timings: bool = Field(
        default=True,
        description="Copy meal serving times",
    )
    preserve_dietary_options: bool = Field(
        default=True,
        description="Copy dietary option flags",
    )
    
    # Item handling
    remove_seasonal_items: bool = Field(
        default=False,
        description="Remove seasonal items from cloned menu",
    )
    remove_expensive_items: bool = Field(
        default=False,
        description="Remove high-cost items",
    )
    cost_threshold: Union[Decimal, None] = Field(
        None,
        ge=0,
        description="Cost threshold for expensive items",
    )
    
    # Auto-adjustments
    auto_adjust_portions: bool = Field(
        default=False,
        description="Automatically adjust portion sizes",
    )
    target_cost_per_person: Union[Decimal, None] = Field(
        None,
        ge=0,
        description="Target cost per person for adjustments",
    )
    
    # Naming
    add_clone_suffix: bool = Field(
        default=False,
        description="Add '(Copy)' suffix to cloned menu names",
    )
    custom_suffix: Union[str, None] = Field(
        None,
        max_length=50,
        description="Custom suffix for cloned menus",
    )

    @field_validator("cost_threshold", "target_cost_per_person", mode="after")
    @classmethod
    def round_decimals(cls, v: Union[Decimal, None]) -> Union[Decimal, None]:
        """Round decimal values to 2 decimal places."""
        if v is not None:
            return v.quantize(Decimal("0.01"))
        return v