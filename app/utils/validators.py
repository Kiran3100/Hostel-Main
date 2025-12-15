# app/utils/validators.py
from __future__ import annotations

"""
Validation helpers:
- Email, phone, pincode, Aadhar, PAN format validation.
- Monetary amount and percentage validation.
- String non-empty and length checks.
- Choices membership validation.
- Safe filename sanitization.
"""

import re
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable

# Compiled regex patterns for better performance
_email_regex = re.compile(
    r"^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?"
    r"(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$"
)
_phone_regex = re.compile(r"^\+?[1-9]\d{6,14}$")
_pincode_regex = re.compile(r"^\d{4,10}$")
_aadhar_regex = re.compile(r"^\d{4}\s?\d{4}\s?\d{4}$")
_pan_regex = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]{1}$")


class ValidationError(Exception):
    """Custom exception for validation errors."""
    pass


def is_valid_email(value: str) -> bool:
    """Return True if value is a valid email address."""
    if not isinstance(value, str):
        return False
    
    value = value.strip().lower()
    if len(value) > 254:  # RFC 5321 limit
        return False
    
    return bool(_email_regex.match(value))


def is_valid_phone(value: str) -> bool:
    """
    Return True if value is a valid phone number.
    Supports international format with optional '+' prefix.
    """
    if not isinstance(value, str):
        return False
    
    # Remove spaces and dashes and parentheses
    cleaned = re.sub(r"[\s\-()]", "", value.strip())
    return bool(_phone_regex.match(cleaned))


def is_valid_pincode(value: str) -> bool:
    """Return True if value is a valid pincode/postal code (4-10 digits)."""
    if not isinstance(value, str):
        return False
    
    value = value.strip()
    return bool(_pincode_regex.match(value))


def is_valid_aadhar(value: str) -> bool:
    """Return True if value is a valid Aadhar number format (12 digits)."""
    if not isinstance(value, str):
        return False
    
    # Remove spaces for validation
    cleaned = value.replace(" ", "")
    return bool(_aadhar_regex.match(value)) and len(cleaned) == 12


def is_valid_pan(value: str) -> bool:
    """Return True if value is a valid PAN format."""
    if not isinstance(value, str):
        return False
    
    return bool(_pan_regex.match(value.upper().strip()))


def is_valid_amount(value: Any) -> bool:
    """Return True if value is a valid non-negative monetary amount."""
    try:
        if isinstance(value, (int, float)):
            return value >= 0
        
        if isinstance(value, str):
            decimal_value = Decimal(value.strip())
            return decimal_value >= 0
        
        if isinstance(value, Decimal):
            return value >= 0
        
        return False
    except (ValueError, InvalidOperation):
        return False


def is_valid_percentage(value: Any) -> bool:
    """Return True if value is a valid percentage (0-100)."""
    try:
        if isinstance(value, (int, float)):
            return 0 <= value <= 100
        
        if isinstance(value, str):
            decimal_value = Decimal(value.strip())
            return Decimal('0') <= decimal_value <= Decimal('100')
        
        if isinstance(value, Decimal):
            return Decimal('0') <= value <= Decimal('100')
        
        return False
    except (ValueError, InvalidOperation):
        return False


def require_non_empty(value: str, field_name: str = "Field") -> str:
    """Validate and return a non-empty string (stripped)."""
    if not isinstance(value, str):
        raise ValidationError(f"{field_name} must be a string")
    
    stripped = value.strip()
    if not stripped:
        raise ValidationError(f"{field_name} cannot be empty")
    
    return stripped


def require_valid_email(value: str, field_name: str = "Email") -> str:
    """Validate and return a valid email (lowercased)."""
    cleaned = require_non_empty(value, field_name)
    
    if not is_valid_email(cleaned):
        raise ValidationError(f"{field_name} must be a valid email address")
    
    return cleaned.lower()


def require_valid_phone(value: str, field_name: str = "Phone") -> str:
    """Validate and return a valid phone number (normalized)."""
    cleaned = require_non_empty(value, field_name)
    
    if not is_valid_phone(cleaned):
        raise ValidationError(f"{field_name} must be a valid phone number")
    
    # Normalize format by removing spaces, dashes and parentheses
    return re.sub(r"[\s\-()]", "", cleaned)


def require_in_choices(
    value: Any, 
    choices: Iterable[Any], 
    field_name: str = "Value"
) -> Any:
    """Validate that value is in the allowed choices."""
    choices_list = list(choices)
    if value not in choices_list:
        raise ValidationError(
            f"{field_name} must be one of: {', '.join(str(c) for c in choices_list)}"
        )
    return value


def require_valid_amount(
    value: Any, 
    field_name: str = "Amount",
    min_value: Decimal | None = None,
    max_value: Decimal | None = None,
) -> Decimal:
    """Validate and return a valid monetary amount as Decimal."""
    if not is_valid_amount(value):
        raise ValidationError(f"{field_name} must be a valid positive amount")
    
    # Convert to Decimal
    if isinstance(value, str):
        decimal_value = Decimal(value.strip())
    elif isinstance(value, (int, float)):
        decimal_value = Decimal(str(value))
    else:
        decimal_value = value
    
    if min_value is not None and decimal_value < min_value:
        raise ValidationError(f"{field_name} must be at least {min_value}")
    
    if max_value is not None and decimal_value > max_value:
        raise ValidationError(f"{field_name} must be at most {max_value}")
    
    return decimal_value


def require_string_length(
    value: str,
    min_length: int | None = None,
    max_length: int | None = None,
    field_name: str = "Field",
) -> str:
    """Validate string length requirements and return the cleaned string."""
    cleaned = require_non_empty(value, field_name)
    
    if min_length is not None and len(cleaned) < min_length:
        raise ValidationError(f"{field_name} must be at least {min_length} characters")
    
    if max_length is not None and len(cleaned) > max_length:
        raise ValidationError(f"{field_name} must be at most {max_length} characters")
    
    return cleaned


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename for safe storage.

    - Removes directory components.
    - Replaces unsafe characters with '_'.
    - Collapses multiple underscores.
    - Trims leading/trailing underscores and dots.
    - Enforces a maximum length of 255 characters.
    """
    if not filename or not isinstance(filename, str):
        raise ValidationError("Filename must be a non-empty string")
    
    # Remove directory components
    import os
    name = os.path.basename(filename)
    
    # Replace unsafe characters
    safe_name = re.sub(r'[^a-zA-Z0-9._-]', '_', name)
    
    # Remove multiple underscores
    safe_name = re.sub(r'_{2,}', '_', safe_name)
    
    # Remove leading/trailing underscores and dots
    safe_name = safe_name.strip('_.')
    
    if not safe_name:
        raise ValidationError("Filename contains no valid characters")
    
    # Limit length
    if len(safe_name) > 255:
        base, ext = os.path.splitext(safe_name)
        safe_name = base[:250] + ext
    
    return safe_name