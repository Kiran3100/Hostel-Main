# app/utils/date_utils.py
from __future__ import annotations

"""
Date and time utility functions used across the project.

Notes:
- All "UTC" helpers use timezone-aware datetimes with `timezone.utc`.
- `to_utc` assumes naïve datetimes are already in UTC and only attaches tzinfo
  (it does not perform any timezone conversion for naïve datetimes).
"""

import logging
from datetime import date, datetime, time, timedelta, timezone
from typing import Iterator, Tuple

logger = logging.getLogger(__name__)

UTC = timezone.utc


class DateUtilsError(Exception):
    """Custom exception for date utilities errors."""
    pass


def now_utc() -> datetime:
    """Return current UTC datetime (timezone-aware)."""
    try:
        return datetime.now(UTC)
    except Exception as e:
        logger.error(f"Failed to get current UTC time: {e}")
        raise DateUtilsError("Failed to get current UTC time") from e


def today_utc() -> date:
    """Return today's date in UTC."""
    try:
        return now_utc().date()
    except Exception as e:
        logger.error(f"Failed to get today's UTC date: {e}")
        raise DateUtilsError("Failed to get today's UTC date") from e


def start_of_day(d: date, tz: timezone | None = UTC) -> datetime:
    """Return the start (00:00:00) of a given date in the given timezone."""
    if not isinstance(d, date):
        raise DateUtilsError("Input must be a date object")
    
    try:
        return datetime.combine(d, time.min).replace(tzinfo=tz)
    except Exception as e:
        logger.error(f"Failed to get start of day for {d}: {e}")
        raise DateUtilsError(f"Failed to get start of day for {d}") from e


def end_of_day(d: date, tz: timezone | None = UTC) -> datetime:
    """Return the end (23:59:59.999999) of a given date in the given timezone."""
    if not isinstance(d, date):
        raise DateUtilsError("Input must be a date object")
    
    try:
        return datetime.combine(d, time.max).replace(tzinfo=tz)
    except Exception as e:
        logger.error(f"Failed to get end of day for {d}: {e}")
        raise DateUtilsError(f"Failed to get end of day for {d}") from e


def to_utc(dt: datetime) -> datetime:
    """
    Convert a datetime to UTC.

    - If naive, assumes it's already in UTC and only attaches tzinfo.
    - If aware, converts to UTC.
    """
    if not isinstance(dt, datetime):
        raise DateUtilsError("Input must be a datetime object")
    
    try:
        if dt.tzinfo is None:
            return dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC)
    except Exception as e:
        logger.error(f"Failed to convert datetime to UTC: {e}")
        raise DateUtilsError("Failed to convert datetime to UTC") from e


def strip_tz(dt: datetime) -> datetime:
    """Return a naive datetime (drop timezone info) without converting."""
    if not isinstance(dt, datetime):
        raise DateUtilsError("Input must be a datetime object")
    
    return dt.replace(tzinfo=None)


def parse_date(value: str, fmt: str = "%Y-%m-%d") -> date:
    """Parse a date string with the given format (default 'YYYY-MM-DD')."""
    if not isinstance(value, str) or not value.strip():
        raise DateUtilsError("Date string cannot be empty")
    
    try:
        return datetime.strptime(value.strip(), fmt).date()
    except ValueError as e:
        logger.error(f"Failed to parse date '{value}' with format '{fmt}': {e}")
        raise DateUtilsError(f"Invalid date format. Expected format: {fmt}") from e


def format_date(d: date, fmt: str = "%Y-%m-%d") -> str:
    """Format a date as string with the given format."""
    if not isinstance(d, date):
        raise DateUtilsError("Input must be a date object")
    
    try:
        return d.strftime(fmt)
    except Exception as e:
        logger.error(f"Failed to format date {d} with format '{fmt}': {e}")
        raise DateUtilsError("Failed to format date") from e


def parse_datetime(value: str, fmt: str = "%Y-%m-%dT%H:%M:%S") -> datetime:
    """Parse a datetime string with the given format."""
    if not isinstance(value, str) or not value.strip():
        raise DateUtilsError("Datetime string cannot be empty")
    
    try:
        return datetime.strptime(value.strip(), fmt)
    except ValueError as e:
        logger.error(f"Failed to parse datetime '{value}' with format '{fmt}': {e}")
        raise DateUtilsError(f"Invalid datetime format. Expected format: {fmt}") from e


def format_datetime(dt: datetime, fmt: str = "%Y-%m-%dT%H:%M:%S") -> str:
    """Format a datetime as string with the given format."""
    if not isinstance(dt, datetime):
        raise DateUtilsError("Input must be a datetime object")
    
    try:
        return dt.strftime(fmt)
    except Exception as e:
        logger.error(f"Failed to format datetime {dt} with format '{fmt}': {e}")
        raise DateUtilsError("Failed to format datetime") from e


def month_range(year: int, month: int) -> Tuple[date, date]:
    """Return (first_day, last_day) of a given month."""
    if not (1 <= month <= 12):
        raise DateUtilsError("Month must be between 1 and 12")
    
    if not (1 <= year <= 9999):
        raise DateUtilsError("Year must be between 1 and 9999")
    
    try:
        from calendar import monthrange as _monthrange
        first = date(year, month, 1)
        last = date(year, month, _monthrange(year, month)[1])
        return first, last
    except Exception as e:
        logger.error(f"Failed to get month range for {year}-{month}: {e}")
        raise DateUtilsError(f"Failed to get month range for {year}-{month}") from e


def daterange(start: date, end: date) -> Iterator[date]:
    """
    Yield all dates from start to end inclusive.
    If start > end, yields nothing.
    """
    if not isinstance(start, date) or not isinstance(end, date):
        raise DateUtilsError("Both start and end must be date objects")
    
    if start > end:
        return
    
    try:
        delta = (end - start).days
        for i in range(delta + 1):
            yield start + timedelta(days=i)
    except Exception as e:
        logger.error(f"Failed to generate date range from {start} to {end}: {e}")
        raise DateUtilsError("Failed to generate date range") from e


def weeks_between(start: date, end: date) -> int:
    """Return number of full weeks between two dates."""
    if not isinstance(start, date) or not isinstance(end, date):
        raise DateUtilsError("Both start and end must be date objects")
    
    if start > end:
        start, end = end, start
    
    try:
        return (end - start).days // 7
    except Exception as e:
        logger.error(f"Failed to calculate weeks between {start} and {end}: {e}")
        raise DateUtilsError("Failed to calculate weeks between dates") from e


def is_business_day(d: date) -> bool:
    """Return True if the date is a business day (Monday-Friday)."""
    if not isinstance(d, date):
        raise DateUtilsError("Input must be a date object")
    
    return d.weekday() < 5  # 0-4 are Monday-Friday


def add_business_days(start: date, days: int) -> date:
    """Add business days to a date, skipping weekends."""
    if not isinstance(start, date):
        raise DateUtilsError("Start must be a date object")
    
    if not isinstance(days, int):
        raise DateUtilsError("Days must be an integer")
    
    try:
        current = start
        remaining_days = abs(days)
        direction = 1 if days >= 0 else -1
        
        while remaining_days > 0:
            current += timedelta(days=direction)
            if is_business_day(current):
                remaining_days -= 1
        
        return current
    except Exception as e:
        logger.error(f"Failed to add business days: {e}")
        raise DateUtilsError("Failed to add business days") from e