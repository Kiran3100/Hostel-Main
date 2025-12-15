# --- File: app/schemas/mess/mess_menu_base.py ---
"""
Base mess menu schemas with comprehensive validation and type safety.

This module provides foundational schemas for mess/cafeteria menu management
including creation, updates, and core validation logic.
"""

from __future__ import annotations

from datetime import date as Date, time
from typing import List, Optional

from pydantic import Field, field_validator, model_validator
from uuid import UUID

from app.schemas.common.base import BaseCreateSchema, BaseSchema, BaseUpdateSchema

__all__ = [
    "MessMenuBase",
    "MessMenuCreate",
    "MessMenuUpdate",
]


class MessMenuBase(BaseSchema):
    """
    Base mess menu schema with core fields.
    
    Provides common menu attributes and validation logic used across
    create/update operations for hostel meal planning.
    """

    hostel_id: UUID = Field(
        ...,
        description="Hostel unique identifier",
    )
    menu_date: Date = Field(
        ...,
        description="Date for which menu is planned",
    )
    day_of_week: str = Field(
        ...,
        pattern=r"^(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)$",
        description="Day of the week",
    )

    # Meal items
    breakfast_items: List[str] = Field(
        default_factory=list,
        min_length=0,
        max_length=20,
        description="Breakfast menu items",
    )
    lunch_items: List[str] = Field(
        default_factory=list,
        min_length=0,
        max_length=30,
        description="Lunch menu items",
    )
    snacks_items: List[str] = Field(
        default_factory=list,
        min_length=0,
        max_length=15,
        description="Snacks/evening tea items",
    )
    dinner_items: List[str] = Field(
        default_factory=list,
        min_length=0,
        max_length=30,
        description="Dinner menu items",
    )

    # Meal timings
    breakfast_time: Optional[time] = Field(
        None,
        description="Breakfast serving time",
    )
    lunch_time: Optional[time] = Field(
        None,
        description="Lunch serving time",
    )
    snacks_time: Optional[time] = Field(
        None,
        description="Snacks serving time",
    )
    dinner_time: Optional[time] = Field(
        None,
        description="Dinner serving time",
    )

    # Special menu flags
    is_special_menu: bool = Field(
        False,
        description="Whether this is a special occasion menu",
    )
    special_occasion: Optional[str] = Field(
        None,
        max_length=255,
        description="Special occasion name (festival, celebration, etc.)",
    )
    special_notes: Optional[str] = Field(
        None,
        max_length=500,
        description="Additional notes about the special menu",
    )

    # Dietary options availability
    vegetarian_available: bool = Field(
        True,
        description="Vegetarian options available",
    )
    non_vegetarian_available: bool = Field(
        False,
        description="Non-vegetarian options available",
    )
    vegan_available: bool = Field(
        False,
        description="Vegan options available",
    )
    jain_available: bool = Field(
        False,
        description="Jain dietary options available",
    )

    @field_validator("menu_date", mode="after")
    @classmethod
    def validate_menu_date(cls, v: Date) -> Date:
        """
        Validate menu Date constraints.
        
        Menu can be created for today or future dates, but not too far ahead.
        """
        today = Date.today()
        
        # Can't create menu for past dates (except today)
        if v < today:
            raise ValueError("Menu Date cannot be in the past")
        
        # Limit advance menu planning to 90 days
        days_ahead = (v - today).days
        if days_ahead > 90:
            raise ValueError(
                "Menu cannot be created more than 90 days in advance"
            )
        
        return v

    @field_validator("day_of_week", mode="after")
    @classmethod
    def validate_day_consistency(cls, v: str, info) -> str:
        """
        Validate day of week matches the menu Date.
        
        Ensures data consistency between Date and day name.
        """
        # Pydantic v2: Use info.data to access other fields
        if info.data.get("menu_date"):
            menu_date = info.data["menu_date"]
            expected_day = menu_date.strftime("%A")
            
            if v != expected_day:
                raise ValueError(
                    f"Day of week '{v}' doesn't match menu Date {menu_date} "
                    f"(should be {expected_day})"
                )
        
        return v

    @field_validator(
        "breakfast_items",
        "lunch_items",
        "snacks_items",
        "dinner_items",
        mode="after"
    )
    @classmethod
    def validate_menu_items(cls, v: List[str]) -> List[str]:
        """
        Validate and normalize menu items.
        
        Ensures items are properly formatted and not empty.
        """
        if not v:
            return v
        
        # Normalize and validate each item
        normalized_items = []
        for item in v:
            item = item.strip()
            
            if not item:
                continue
            
            if len(item) < 2:
                raise ValueError("Menu items must be at least 2 characters long")
            
            if len(item) > 100:
                raise ValueError("Menu items cannot exceed 100 characters")
            
            normalized_items.append(item)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_items = []
        for item in normalized_items:
            item_lower = item.lower()
            if item_lower not in seen:
                seen.add(item_lower)
                unique_items.append(item)
        
        return unique_items

    @field_validator("special_occasion", "special_notes", mode="before")
    @classmethod
    def normalize_text_fields(cls, v: Optional[str]) -> Optional[str]:
        """Normalize text fields by stripping whitespace."""
        if v is not None:
            v = v.strip()
            return v if v else None
        return None

    @model_validator(mode="after")
    def validate_special_menu_requirements(self) -> "MessMenuBase":
        """
        Validate special menu configuration.
        
        Special menus should have occasion name and at least one meal.
        """
        if self.is_special_menu:
            if not self.special_occasion:
                raise ValueError(
                    "special_occasion is required when is_special_menu is True"
                )
            
            # Special menus should have at least one meal with items
            has_items = any([
                self.breakfast_items,
                self.lunch_items,
                self.snacks_items,
                self.dinner_items,
            ])
            
            if not has_items:
                raise ValueError(
                    "Special menu must have at least one meal with items"
                )
        
        return self

    @model_validator(mode="after")
    def validate_meal_times_sequence(self) -> "MessMenuBase":
        """
        Validate meal times are in logical sequence.
        
        Breakfast < Lunch < Snacks < Dinner
        """
        times = []
        
        if self.breakfast_time:
            times.append(("breakfast", self.breakfast_time))
        if self.lunch_time:
            times.append(("lunch", self.lunch_time))
        if self.snacks_time:
            times.append(("snacks", self.snacks_time))
        if self.dinner_time:
            times.append(("dinner", self.dinner_time))
        
        # Check sequence
        for i in range(len(times) - 1):
            current_meal, current_time = times[i]
            next_meal, next_time = times[i + 1]
            
            if current_time >= next_time:
                raise ValueError(
                    f"{next_meal.capitalize()} time must be after {current_meal} time"
                )
        
        return self

    @model_validator(mode="after")
    def validate_dietary_options(self) -> "MessMenuBase":
        """
        Validate at least one dietary option is available.
        
        Menu must cater to at least one dietary preference.
        """
        if not any([
            self.vegetarian_available,
            self.non_vegetarian_available,
            self.vegan_available,
            self.jain_available,
        ]):
            raise ValueError(
                "At least one dietary option must be available"
            )
        
        return self


class MessMenuCreate(MessMenuBase, BaseCreateSchema):
    """
    Create mess menu with creator tracking.
    
    Extends base schema with creation context and additional validation.
    """

    created_by: UUID = Field(
        ...,
        description="Supervisor/Admin user ID who created the menu",
    )
    
    # Additional creation flags
    auto_publish: bool = Field(
        default=False,
        description="Automatically publish menu after creation",
    )
    send_notification: bool = Field(
        default=True,
        description="Send notification to students about new menu",
    )

    @model_validator(mode="after")
    def validate_menu_completeness(self) -> "MessMenuCreate":
        """
        Validate menu has sufficient items for creation.
        
        At least main meals (breakfast and lunch/dinner) should have items.
        """
        main_meals_count = sum([
            bool(self.breakfast_items),
            bool(self.lunch_items),
            bool(self.dinner_items),
        ])
        
        if main_meals_count < 2:
            raise ValueError(
                "Menu must have items for at least 2 main meals "
                "(breakfast, lunch, or dinner)"
            )
        
        return self


class MessMenuUpdate(BaseUpdateSchema):
    """
    Update mess menu with partial fields.
    
    All fields are optional for flexible updates. Typically used
    to modify draft menus before publication.
    """

    breakfast_items: Optional[List[str]] = Field(
        None,
        max_length=20,
        description="Updated breakfast items",
    )
    lunch_items: Optional[List[str]] = Field(
        None,
        max_length=30,
        description="Updated lunch items",
    )
    snacks_items: Optional[List[str]] = Field(
        None,
        max_length=15,
        description="Updated snacks items",
    )
    dinner_items: Optional[List[str]] = Field(
        None,
        max_length=30,
        description="Updated dinner items",
    )

    breakfast_time: Optional[time] = Field(
        None,
        description="Updated breakfast time",
    )
    lunch_time: Optional[time] = Field(
        None,
        description="Updated lunch time",
    )
    snacks_time: Optional[time] = Field(
        None,
        description="Updated snacks time",
    )
    dinner_time: Optional[time] = Field(
        None,
        description="Updated dinner time",
    )

    is_special_menu: Optional[bool] = Field(
        None,
        description="Updated special menu flag",
    )
    special_occasion: Optional[str] = Field(
        None,
        max_length=255,
        description="Updated special occasion",
    )
    special_notes: Optional[str] = Field(
        None,
        max_length=500,
        description="Updated special notes",
    )

    vegetarian_available: Optional[bool] = None
    non_vegetarian_available: Optional[bool] = None
    vegan_available: Optional[bool] = None
    jain_available: Optional[bool] = None

    @field_validator(
        "breakfast_items",
        "lunch_items",
        "snacks_items",
        "dinner_items",
        mode="after"
    )
    @classmethod
    def validate_menu_items(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        """Validate and normalize menu items if provided."""
        if v is None:
            return None
        
        # Apply same validation as base schema
        normalized_items = []
        for item in v:
            item = item.strip()
            
            if not item:
                continue
            
            if len(item) < 2:
                raise ValueError("Menu items must be at least 2 characters long")
            
            if len(item) > 100:
                raise ValueError("Menu items cannot exceed 100 characters")
            
            normalized_items.append(item)
        
        # Remove duplicates
        seen = set()
        unique_items = []
        for item in normalized_items:
            item_lower = item.lower()
            if item_lower not in seen:
                seen.add(item_lower)
                unique_items.append(item)
        
        return unique_items if unique_items else None

    @field_validator("special_occasion", "special_notes", mode="before")
    @classmethod
    def normalize_text(cls, v: Optional[str]) -> Optional[str]:
        """Normalize text fields."""
        if v is not None:
            v = v.strip()
            return v if v else None
        return None