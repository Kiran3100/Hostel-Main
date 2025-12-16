# --- File: app/schemas/announcement/announcement_targeting.py ---
"""
Announcement targeting schemas for audience selection.

This module defines schemas for configuring and managing
announcement targeting rules and audience selection.
"""

from enum import Enum
from typing import Optional, Union
from uuid import UUID

from pydantic import Field, field_validator, model_validator, ConfigDict

from app.schemas.common.base import BaseCreateSchema, BaseSchema
from app.schemas.common.enums import RoomType

__all__ = [
    "TargetType",
    "CombineMode",
    "TargetingConfig",
    "AudienceSelection",
    "TargetRooms",
    "TargetFloors",
    "IndividualTargeting",
    "TargetingSummary",
    "BulkTargeting",
    "TargetingPreview",
]


class TargetType(str, Enum):
    """Targeting type enumeration."""
    
    ALL = "all"
    SPECIFIC_ROOMS = "specific_rooms"
    SPECIFIC_FLOORS = "specific_floors"
    SPECIFIC_STUDENTS = "specific_students"
    CUSTOM = "custom"


class CombineMode(str, Enum):
    """Rule combination mode."""
    
    UNION = "union"  # Recipients matching ANY rule
    INTERSECTION = "intersection"  # Recipients matching ALL rules


class TargetingConfig(BaseSchema):
    """
    Targeting configuration for announcement.
    
    Defines who should receive the announcement based
    on various targeting criteria.
    """
    
    model_config = ConfigDict(from_attributes=True)
    
    target_type: TargetType = Field(
        ...,
        description="Type of targeting strategy",
    )
    
    # Specific targets
    room_ids: list[UUID] = Field(
        default_factory=list,
        description="Specific room UUIDs to target",
    )
    floor_numbers: list[int] = Field(
        default_factory=list,
        description="Specific floor numbers to target",
    )
    student_ids: list[UUID] = Field(
        default_factory=list,
        description="Specific student UUIDs to target",
    )
    
    # Exclusions
    exclude_student_ids: list[UUID] = Field(
        default_factory=list,
        description="Students to exclude from targeting",
    )
    exclude_room_ids: list[UUID] = Field(
        default_factory=list,
        description="Rooms to exclude from targeting",
    )
    
    @field_validator("floor_numbers")
    @classmethod
    def validate_floors(cls, v: list[int]) -> list[int]:
        """Validate and deduplicate floor numbers."""
        if v:
            if any(f < 0 for f in v):
                raise ValueError("Floor numbers must be non-negative")
            return sorted(set(v))
        return v
    
    @model_validator(mode="after")
    def validate_targeting_consistency(self) -> "TargetingConfig":
        """Validate targeting configuration consistency."""
        target_type = self.target_type
        
        if target_type == TargetType.SPECIFIC_ROOMS and not self.room_ids:
            raise ValueError("room_ids required for SPECIFIC_ROOMS targeting")
        
        if target_type == TargetType.SPECIFIC_FLOORS and not self.floor_numbers:
            raise ValueError("floor_numbers required for SPECIFIC_FLOORS targeting")
        
        if target_type == TargetType.SPECIFIC_STUDENTS and not self.student_ids:
            raise ValueError("student_ids required for SPECIFIC_STUDENTS targeting")
        
        # Check for overlap between targets and exclusions
        if self.student_ids and self.exclude_student_ids:
            overlap = set(self.student_ids) & set(self.exclude_student_ids)
            if overlap:
                raise ValueError(
                    f"Students cannot be both targeted and excluded: {overlap}"
                )
        
        if self.room_ids and self.exclude_room_ids:
            overlap = set(self.room_ids) & set(self.exclude_room_ids)
            if overlap:
                raise ValueError(
                    f"Rooms cannot be both targeted and excluded: {overlap}"
                )
        
        return self


class AudienceSelection(BaseCreateSchema):
    """
    Comprehensive audience selection for announcement.
    
    Provides granular control over recipient selection
    with various filtering options.
    """
    
    model_config = ConfigDict(from_attributes=True)
    
    announcement_id: UUID = Field(
        ...,
        description="Announcement UUID to configure targeting for",
    )
    
    # Selection criteria
    include_all: bool = Field(
        False,
        description="Include all students in hostel",
    )
    include_active_students: bool = Field(
        True,
        description="Include students with active status",
    )
    include_inactive_students: bool = Field(
        False,
        description="Include students with inactive status",
    )
    include_notice_period_students: bool = Field(
        True,
        description="Include students in notice period",
    )
    
    # Filters
    room_types: Union[list[RoomType], None] = Field(
        None,
        description="Filter by room types",
    )
    floors: Union[list[int], None] = Field(
        None,
        description="Filter by floor numbers",
    )
    
    # Specific selection
    specific_room_ids: list[UUID] = Field(
        default_factory=list,
        description="Specifically include these rooms",
    )
    specific_student_ids: list[UUID] = Field(
        default_factory=list,
        description="Specifically include these students",
    )
    
    # Exclusions
    exclude_student_ids: list[UUID] = Field(
        default_factory=list,
        description="Specifically exclude these students",
    )
    exclude_room_ids: list[UUID] = Field(
        default_factory=list,
        description="Specifically exclude these rooms",
    )
    
    @field_validator("floors")
    @classmethod
    def validate_floors(cls, v: Union[list[int], None]) -> Union[list[int], None]:
        """Validate floor numbers."""
        if v:
            if any(f < 0 for f in v):
                raise ValueError("Floor numbers must be non-negative")
            return sorted(set(v))
        return v
    
    @model_validator(mode="after")
    def validate_selection(self) -> "AudienceSelection":
        """Validate audience selection is not empty."""
        has_selection = (
            self.include_all
            or self.specific_room_ids
            or self.specific_student_ids
            or self.floors
            or self.room_types
        )
        
        if not has_selection:
            raise ValueError(
                "At least one selection criteria must be specified"
            )
        
        return self


class TargetRooms(BaseCreateSchema):
    """
    Target specific rooms for announcement.
    
    Simple schema for room-based targeting.
    """
    
    model_config = ConfigDict(from_attributes=True)
    
    announcement_id: UUID = Field(
        ...,
        description="Announcement UUID",
    )
    room_ids: list[UUID] = Field(
        ...,
        min_length=1,
        description="Room UUIDs to target (at least 1)",
    )
    
    # Options
    include_all_students: bool = Field(
        True,
        description="Include all students in these rooms",
    )
    exclude_checked_out: bool = Field(
        True,
        description="Exclude students who have checked out",
    )
    
    @field_validator("room_ids")
    @classmethod
    def validate_unique_rooms(cls, v: list[UUID]) -> list[UUID]:
        """Ensure room IDs are unique."""
        if len(v) != len(set(v)):
            raise ValueError("Duplicate room IDs not allowed")
        return v


class TargetFloors(BaseCreateSchema):
    """
    Target specific floors for announcement.
    
    Simple schema for floor-based targeting.
    """
    
    model_config = ConfigDict(from_attributes=True)
    
    announcement_id: UUID = Field(
        ...,
        description="Announcement UUID",
    )
    floor_numbers: list[int] = Field(
        ...,
        min_length=1,
        description="Floor numbers to target (at least 1)",
    )
    
    # Options
    include_all_rooms: bool = Field(
        True,
        description="Include all rooms on these floors",
    )
    exclude_maintenance_rooms: bool = Field(
        True,
        description="Exclude rooms under maintenance",
    )
    
    @field_validator("floor_numbers")
    @classmethod
    def validate_floors(cls, v: list[int]) -> list[int]:
        """Validate and deduplicate floor numbers."""
        if any(f < 0 for f in v):
            raise ValueError("Floor numbers must be non-negative")
        unique_floors = sorted(set(v))
        if len(unique_floors) != len(v):
            # Deduplicated, return unique
            return unique_floors
        return v


class IndividualTargeting(BaseCreateSchema):
    """
    Target individual students for announcement.
    
    Used for direct communication to specific students.
    """
    
    model_config = ConfigDict(from_attributes=True)
    
    announcement_id: UUID = Field(
        ...,
        description="Announcement UUID",
    )
    student_ids: list[UUID] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Student UUIDs to target (1-100)",
    )
    
    @field_validator("student_ids")
    @classmethod
    def validate_unique_students(cls, v: list[UUID]) -> list[UUID]:
        """Ensure student IDs are unique."""
        if len(v) != len(set(v)):
            raise ValueError("Duplicate student IDs not allowed")
        return v


class TargetingSummary(BaseSchema):
    """
    Summary of announcement targeting configuration.
    
    Shows who will receive the announcement based on
    current targeting rules.
    """
    
    model_config = ConfigDict(from_attributes=True)
    
    announcement_id: UUID = Field(
        ...,
        description="Announcement UUID",
    )
    
    # Targeting type
    targeting_type: TargetType = Field(
        ...,
        description="Type of targeting used",
    )
    
    # Counts
    total_recipients: int = Field(
        ...,
        ge=0,
        description="Total number of recipients",
    )
    students_count: int = Field(
        ...,
        ge=0,
        description="Number of students targeted",
    )
    rooms_count: int = Field(
        ...,
        ge=0,
        description="Number of rooms targeted",
    )
    floors_count: int = Field(
        ...,
        ge=0,
        description="Number of floors targeted",
    )
    
    # Exclusion counts
    excluded_students_count: int = Field(
        0,
        ge=0,
        description="Number of students excluded",
    )
    
    # Breakdown
    recipients_by_room: dict[str, int] = Field(
        default_factory=dict,
        description="Room ID/number -> student count",
    )
    recipients_by_floor: dict[str, int] = Field(
        default_factory=dict,
        description="Floor number -> student count",
    )
    
    # Validation
    has_valid_recipients: bool = Field(
        ...,
        description="Whether there are any valid recipients",
    )
    validation_warnings: list[str] = Field(
        default_factory=list,
        description="Any warnings about targeting",
    )


class BulkTargeting(BaseCreateSchema):
    """
    Apply multiple targeting rules at once.
    
    Used for complex targeting scenarios requiring
    multiple rule combinations.
    """
    
    model_config = ConfigDict(from_attributes=True)
    
    announcement_id: UUID = Field(
        ...,
        description="Announcement UUID",
    )
    
    targeting_rules: list[TargetingConfig] = Field(
        ...,
        min_length=1,
        max_length=10,
        description="Targeting rules to apply (1-10)",
    )
    
    # How to combine rules
    combine_mode: CombineMode = Field(
        CombineMode.UNION,
        description="How to combine multiple rules",
    )
    
    # Global exclusions (applied after combining)
    global_exclude_student_ids: list[UUID] = Field(
        default_factory=list,
        description="Students to exclude from final result",
    )
    
    @model_validator(mode="after")
    def validate_rules(self) -> "BulkTargeting":
        """Validate targeting rules don't conflict."""
        # Check for conflicting rules
        has_all = any(r.target_type == TargetType.ALL for r in self.targeting_rules)
        
        if has_all and len(self.targeting_rules) > 1:
            if self.combine_mode == CombineMode.INTERSECTION:
                raise ValueError(
                    "Cannot use INTERSECTION mode with 'all' targeting type"
                )
        
        return self


class TargetingPreview(BaseCreateSchema):
    """
    Request a preview of targeting results.
    
    Returns estimated recipient count without creating
    the announcement.
    """
    
    model_config = ConfigDict(from_attributes=True)
    
    hostel_id: UUID = Field(
        ...,
        description="Hostel UUID",
    )
    targeting_config: TargetingConfig = Field(
        ...,
        description="Targeting configuration to preview",
    )
    
    # Preview options
    include_student_list: bool = Field(
        False,
        description="Include list of student IDs in preview",
    )
    max_preview_students: int = Field(
        50,
        ge=1,
        le=100,
        description="Maximum students to include in preview list",
    )