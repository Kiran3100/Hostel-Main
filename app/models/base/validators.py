# --- File: C:\Hostel-Main\app\models\base\validators.py ---
"""
Database-level validators and constraint helpers.

Provides validation functions for complex business rules
and data integrity checks at the model level.
"""

from datetime import datetime, date
from decimal import Decimal
from typing import Any, Optional, List
import re


def validate_email(email: str) -> bool:
    """
    Validate email address format.
    
    Args:
        email: Email address to validate
        
    Returns:
        True if valid, False otherwise
    """
    if not email:
        return False
    
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def validate_phone(phone: str) -> bool:
    """
    Validate phone number format.
    
    Args:
        phone: Phone number to validate
        
    Returns:
        True if valid, False otherwise
    """
    if not phone:
        return False
    
    # Remove non-numeric characters
    cleaned = re.sub(r'\D', '', phone)
    
    # Check length (minimum 10 digits)
    return len(cleaned) >= 10


def validate_postal_code(postal_code: str, country: Optional[str] = None) -> bool:
    """
    Validate postal code format.
    
    Args:
        postal_code: Postal code to validate
        country: Country code for specific validation
        
    Returns:
        True if valid, False otherwise
    """
    if not postal_code:
        return False
    
    # Basic validation - alphanumeric with optional spaces/hyphens
    pattern = r'^[A-Z0-9\s-]{3,10}$'
    return bool(re.match(pattern, postal_code.upper()))


def validate_url(url: str) -> bool:
    """
    Validate URL format.
    
    Args:
        url: URL to validate
        
    Returns:
        True if valid, False otherwise
    """
    if not url:
        return False
    
    pattern = r'^https?:\/\/(www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b([-a-zA-Z0-9()@:%_\+.~#?&//=]*)$'
    return bool(re.match(pattern, url))


def validate_coordinate(value: Decimal, coord_type: str) -> bool:
    """
    Validate geographic coordinate.
    
    Args:
        value: Coordinate value
        coord_type: Type of coordinate ('latitude' or 'longitude')
        
    Returns:
        True if valid, False otherwise
    """
    if value is None:
        return True
    
    if coord_type == 'latitude':
        return -90 <= value <= 90
    elif coord_type == 'longitude':
        return -180 <= value <= 180
    
    return False


def validate_date_range(start_date: date, end_date: date) -> bool:
    """
    Validate date range (end must be after start).
    
    Args:
        start_date: Start date
        end_date: End date
        
    Returns:
        True if valid, False otherwise
    """
    if not start_date or not end_date:
        return True
    
    return end_date >= start_date


def validate_amount(amount: Decimal, min_value: Decimal = Decimal('0')) -> bool:
    """
    Validate monetary amount.
    
    Args:
        amount: Amount to validate
        min_value: Minimum allowed value
        
    Returns:
        True if valid, False otherwise
    """
    if amount is None:
        return False
    
    return amount >= min_value


def validate_percentage(value: Decimal) -> bool:
    """
    Validate percentage value (0-100).
    
    Args:
        value: Percentage value
        
    Returns:
        True if valid, False otherwise
    """
    if value is None:
        return False
    
    return Decimal('0') <= value <= Decimal('100')


def validate_slug(slug: str) -> bool:
    """
    Validate URL slug format.
    
    Args:
        slug: Slug to validate
        
    Returns:
        True if valid, False otherwise
    """
    if not slug:
        return False
    
    # Only lowercase letters, numbers, and hyphens
    pattern = r'^[a-z0-9]+(?:-[a-z0-9]+)*$'
    return bool(re.match(pattern, slug))


def validate_json_structure(data: dict, required_keys: List[str]) -> bool:
    """
    Validate JSON structure has required keys.
    
    Args:
        data: JSON data dictionary
        required_keys: List of required keys
        
    Returns:
        True if all required keys present, False otherwise
    """
    if not data:
        return False
    
    return all(key in data for key in required_keys)


def normalize_phone(phone: str) -> str:
    """
    Normalize phone number to digits only.
    
    Args:
        phone: Phone number to normalize
        
    Returns:
        Normalized phone number
    """
    return re.sub(r'\D', '', phone)


def normalize_email(email: str) -> str:
    """
    Normalize email address.
    
    Args:
        email: Email to normalize
        
    Returns:
        Normalized email (lowercase, trimmed)
    """
    return email.strip().lower()


def normalize_slug(text: str) -> str:
    """
    Convert text to URL-friendly slug.
    
    Args:
        text: Text to convert
        
    Returns:
        URL-friendly slug
    """
    # Convert to lowercase
    slug = text.lower().strip()
    
    # Remove special characters
    slug = re.sub(r'[^\w\s-]', '', slug)
    
    # Replace spaces and multiple hyphens with single hyphen
    slug = re.sub(r'[-\s]+', '-', slug)
    
    return slug.strip('-')