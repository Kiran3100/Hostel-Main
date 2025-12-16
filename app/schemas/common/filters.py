# --- File: app/schemas/common/filters.py ---
"""
Common filter schemas used for query/filter parameters across the API.
"""

from datetime import date as Date, datetime, time
from typing import Dict, List, Union

from pydantic import Field, field_validator, model_validator

from app.schemas.common.base import BaseFilterSchema

__all__ = [
    "DateRangeFilter",
    "DateTimeRangeFilter",
    "TimeRangeFilter",
    "PriceRangeFilter",
    "SearchFilter",
    "SortOptions",
    "StatusFilter",
    "NumericRangeFilter",
    "LocationFilter",
    "MultiSelectFilter",
    "BooleanFilter",
    "TextSearchFilter",
]


class DateRangeFilter(BaseFilterSchema):
    """Date range filter."""

    start_date: Union[Date, None] = Field(
        default=None,
        description="Start Date (inclusive)",
    )
    end_date: Union[Date, None] = Field(
        default=None,
        description="End Date (inclusive)",
    )

    @model_validator(mode="after")
    def validate_date_range(self):
        """Validate end_date is after or equal to start_date."""
        if (
            self.end_date is not None
            and self.start_date is not None
            and self.end_date < self.start_date
        ):
            raise ValueError("end_date must be after or equal to start_date")
        return self


class DateTimeRangeFilter(BaseFilterSchema):
    """Datetime range filter."""

    start_datetime: Union[datetime, None] = Field(
        default=None,
        description="Start datetime (inclusive)",
    )
    end_datetime: Union[datetime, None] = Field(
        default=None,
        description="End datetime (inclusive)",
    )

    @model_validator(mode="after")
    def validate_datetime_range(self):
        """Validate end_datetime is after or equal to start_datetime."""
        if (
            self.end_datetime is not None
            and self.start_datetime is not None
            and self.end_datetime < self.start_datetime
        ):
            raise ValueError(
                "end_datetime must be after or equal to start_datetime"
            )
        return self


class TimeRangeFilter(BaseFilterSchema):
    """Time range filter."""

    start_time: Union[time, None] = Field(
        default=None,
        description="Start time",
    )
    end_time: Union[time, None] = Field(
        default=None,
        description="End time",
    )


class PriceRangeFilter(BaseFilterSchema):
    """Price range filter."""

    min_price: Union[float, None] = Field(
        default=None,
        ge=0,
        description="Minimum price",
    )
    max_price: Union[float, None] = Field(
        default=None,
        ge=0,
        description="Maximum price",
    )

    @model_validator(mode="after")
    def validate_price_range(self):
        """Validate max_price is greater than or equal to min_price."""
        if (
            self.max_price is not None
            and self.min_price is not None
            and self.max_price < self.min_price
        ):
            raise ValueError(
                "max_price must be greater than or equal to min_price"
            )
        return self


class SearchFilter(BaseFilterSchema):
    """Generic search filter."""

    search_query: Union[str, None] = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Search query string",
    )


class SortOptions(BaseFilterSchema):
    """Sorting options."""

    sort_by: str = Field(..., description="Field to sort by")
    sort_order: str = Field(
        default="asc",
        pattern=r"^(asc|desc)$",
        description="Sort order: asc or desc (case-insensitive input allowed)",
    )

    @field_validator("sort_order")
    @classmethod
    def validate_sort_order(cls, v: str) -> str:
        """Validate and normalize sort order."""
        return v.lower()


class StatusFilter(BaseFilterSchema):
    """Status filter."""

    statuses: Union[List[str], None] = Field(
        default=None,
        description="Filter by status values",
    )
    exclude_statuses: Union[List[str], None] = Field(
        default=None,
        description="Exclude status values",
    )


class NumericRangeFilter(BaseFilterSchema):
    """Generic numeric range filter."""

    min_value: Union[float, None] = Field(
        default=None,
        description="Minimum value",
    )
    max_value: Union[float, None] = Field(
        default=None,
        description="Maximum value",
    )

    @model_validator(mode="after")
    def validate_range(self):
        """Validate max_value is greater than or equal to min_value."""
        if (
            self.max_value is not None
            and self.min_value is not None
            and self.max_value < self.min_value
        ):
            raise ValueError(
                "max_value must be greater than or equal to min_value"
            )
        return self


class LocationFilter(BaseFilterSchema):
    """Location-based filter."""

    latitude: Union[float, None] = Field(
        default=None,
        ge=-90,
        le=90,
        description="Latitude",
    )
    longitude: Union[float, None] = Field(
        default=None,
        ge=-180,
        le=180,
        description="Longitude",
    )
    radius_km: Union[float, None] = Field(
        default=None,
        ge=0,
        le=100,
        description="Search radius in kilometers",
    )
    city: Union[str, None] = Field(
        default=None,
        description="City name",
    )
    state: Union[str, None] = Field(
        default=None,
        description="State name",
    )
    pincode: Union[str, None] = Field(
        default=None,
        pattern=r"^\d{6}$",
        description="Pincode",
    )


class MultiSelectFilter(BaseFilterSchema):
    """Multi-select filter with include/exclude."""

    include: Union[List[str], None] = Field(
        default=None,
        description="Include these values",
    )
    exclude: Union[List[str], None] = Field(
        default=None,
        description="Exclude these values",
    )


class BooleanFilter(BaseFilterSchema):
    """Boolean filter (yes/no/all)."""

    value: Union[bool, None] = Field(
        default=None,
        description="Boolean filter value",
    )


class TextSearchFilter(BaseFilterSchema):
    """Full-text search filter."""

    query: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Search query",
    )
    fields: Union[List[str], None] = Field(
        default=None,
        description="Fields to search in",
    )
    fuzzy: bool = Field(
        default=False,
        description="Enable fuzzy search",
    )
    boost: Union[Dict[str, float], None] = Field(
        default=None,
        description="Field boost weights",
    )