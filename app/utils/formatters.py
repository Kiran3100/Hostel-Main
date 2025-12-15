# app/utils/formatters.py
from __future__ import annotations

"""
Formatting utilities:
- Currency formatting (including Indian system).
- Conversion of amounts to words (INR-focused).
- Date and datetime formatting.
- Duration and percentage humanization.
- Masking of email/phone/Aadhar/PAN.
- File size and generic number formatting.
- Text truncation.
"""

import logging
import re
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

logger = logging.getLogger(__name__)

# Constants for formatting
CURRENCY_SYMBOLS = {
    "INR": "₹",
    "USD": "$",
    "EUR": "€",
    "GBP": "£",
    "JPY": "¥",
}


class FormatterError(Exception):
    """Custom exception for formatter errors."""
    pass


def safe_decimal(value: Any, field_name: str = "value") -> Decimal:
    """
    Safely convert value to Decimal with error handling.

    Non-numeric characters (except digits, '.' and '-') are removed
    before parsing when the input is a string.
    """
    try:
        if isinstance(value, Decimal):
            return value
        if isinstance(value, (int, float)):
            return Decimal(str(value))
        if isinstance(value, str):
            # Remove currency symbols and spaces and any non-numeric characters
            cleaned = re.sub(r'[^\d.-]', '', value.strip())
            if not cleaned:
                raise FormatterError(f"Invalid {field_name}: empty after cleaning")
            return Decimal(cleaned)
        raise FormatterError(f"Invalid {field_name} type: {type(value)}")
    except (InvalidOperation, ValueError) as e:
        logger.error(f"Failed to convert {field_name} '{value}' to Decimal: {e}")
        raise FormatterError(f"Invalid {field_name} format: {value}") from e


def format_currency(
    amount: Decimal | float | int | str, 
    currency: str = "INR",
    *,
    show_symbol: bool = True,
    show_code: bool = False,
    decimals: int = 2,
    indian_format: bool = True,
) -> str:
    """
    Format a numeric amount with currency formatting.
    
    Args:
        amount: The amount to format.
        currency: Currency code (INR, USD, EUR, etc.).
        show_symbol: Whether to show currency symbol (₹, $, etc.).
        show_code: Whether to show currency code (INR, USD, etc.).
        decimals: Number of decimal places.
        indian_format: Use Indian number formatting (1,00,000 vs 100,000)
                       when currency is INR.
    """
    try:
        dec = safe_decimal(amount, "amount")
        
        # Validate currency
        currency = currency.upper().strip()
        if not currency:
            raise FormatterError("Currency cannot be empty")
        
        # Validate decimals
        if not isinstance(decimals, int) or decimals < 0:
            raise FormatterError("Decimals must be a non-negative integer")
        
        # Format the number
        if decimals == 0:
            formatted_amount = str(int(dec))
        else:
            formatted_amount = f"{dec:.{decimals}f}"
        
        # Apply number formatting
        if indian_format and currency == "INR":
            formatted_amount = format_indian_number(formatted_amount)
        else:
            # Standard Western formatting
            parts = formatted_amount.split('.')
            parts[0] = f"{int(parts[0]):,}"
            formatted_amount = '.'.join(parts)
        
        # Build result with symbols/codes
        result_parts = []
        
        if show_symbol and currency in CURRENCY_SYMBOLS:
            result_parts.append(CURRENCY_SYMBOLS[currency])
        
        result_parts.append(formatted_amount)
        
        if show_code:
            result_parts.append(currency)
        
        # If neither symbol nor code requested, default to code
        if not show_symbol and not show_code:
            result_parts.append(currency)
        
        return " ".join(result_parts)
        
    except Exception as e:
        logger.error(f"Failed to format currency: {e}")
        raise FormatterError(f"Failed to format currency: {e}") from e


def format_indian_number(number_str: str) -> str:
    """Format number with Indian numbering system (lakhs, crores)."""
    try:
        # Split into integer and decimal parts
        if '.' in number_str:
            integer_part, decimal_part = number_str.split('.')
            decimal_part = '.' + decimal_part
        else:
            integer_part = number_str
            decimal_part = ''
        
        # Reverse for easier processing
        reversed_digits = integer_part[::-1]
        
        # Apply Indian grouping: first group of 3, then groups of 2
        groups = []
        if len(reversed_digits) > 3:
            groups.append(reversed_digits[:3])
            remaining = reversed_digits[3:]
            while remaining:
                groups.append(remaining[:2])
                remaining = remaining[2:]
        else:
            groups.append(reversed_digits)
        
        # Join groups and reverse back
        formatted = ','.join(groups)[::-1]
        return formatted + decimal_part
        
    except Exception as e:
        logger.warning(f"Failed to apply Indian number formatting: {e}")
        return number_str  # Return original on error


def format_currency_words(amount: Decimal | float | int | str, currency: str = "INR") -> str:
    """Convert amount to words (Indian system for INR, simple units for others)."""
    try:
        dec = safe_decimal(amount, "amount")
        
        if currency.upper() == "INR":
            return format_inr_words(dec)
        else:
            return format_number_words(dec) + f" {currency.upper()}"
            
    except Exception as e:
        logger.error(f"Failed to format currency words: {e}")
        return f"{amount} {currency}"


def format_inr_words(amount: Decimal) -> str:
    """Convert INR amount to words using Indian system (Rupees and Paise)."""
    try:
        # Split into rupees and paise
        rupees = int(amount)
        paise = int((amount - rupees) * 100)
        
        def convert_to_words(n: int) -> str:
            ones = [
                "", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
                "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen",
                "seventeen", "eighteen", "nineteen",
            ]
            
            tens = [
                "", "", "twenty", "thirty", "forty", "fifty",
                "sixty", "seventy", "eighty", "ninety",
            ]
            
            if n == 0:
                return ""
            elif n < 20:
                return ones[n]
            elif n < 100:
                return tens[n // 10] + ("" if n % 10 == 0 else " " + ones[n % 10])
            elif n < 1000:
                return ones[n // 100] + " hundred" + ("" if n % 100 == 0 else " " + convert_to_words(n % 100))
            elif n < 100000:  # thousands
                return convert_to_words(n // 1000) + " thousand" + ("" if n % 1000 == 0 else " " + convert_to_words(n % 1000))
            elif n < 10000000:  # lakhs
                return convert_to_words(n // 100000) + " lakh" + ("" if n % 100000 == 0 else " " + convert_to_words(n % 100000))
            else:  # crores
                return convert_to_words(n // 10000000) + " crore" + ("" if n % 10000000 == 0 else " " + convert_to_words(n % 10000000))
        
        result: list[str] = []
        
        if rupees > 0:
            result.append(convert_to_words(rupees).strip())
            result.append("rupee" if rupees == 1 else "rupees")
        
        if paise > 0:
            if result:
                result.append("and")
            result.append(convert_to_words(paise).strip())
            result.append("paisa" if paise == 1 else "paise")
        
        if not result:
            return "zero rupees"
        
        return " ".join(result).title()
        
    except Exception as e:
        logger.error(f"Failed to convert INR to words: {e}")
        return f"₹{amount}"


def format_number_words(amount: Decimal) -> str:
    """Convert number to words (simplified, Western system)."""
    try:
        return f"{amount} units"
    except Exception as e:
        logger.error(f"Failed to convert number to words: {e}")
        return str(amount)


def format_date_short(d: date | datetime | None, format_type: str = "short") -> str:
    """
    Format a date with various format options.
    
    Args:
        d: Date or datetime to format. If datetime, only the date part is used.
        format_type: 'short', 'medium', 'long', 'iso', 'indian'.
    """
    if d is None:
        return ""
    
    try:
        # Extract date if datetime
        if isinstance(d, datetime):
            d = d.date()
        
        if not isinstance(d, date):
            raise FormatterError(f"Expected date or datetime, got {type(d)}")
        
        formats = {
            "short": "%d %b %Y",           # 05 Jan 2025
            "medium": "%d %B %Y",          # 05 January 2025  
            "long": "%A, %d %B %Y",        # Sunday, 05 January 2025
            "iso": "%Y-%m-%d",             # 2025-01-05
            "indian": "%d/%m/%Y",          # 05/01/2025
        }
        
        fmt = formats.get(format_type, formats["short"])
        return d.strftime(fmt)
        
    except Exception as e:
        logger.error(f"Failed to format date: {e}")
        return str(d) if d else ""


def format_datetime_short(dt: datetime | None, format_type: str = "short", include_seconds: bool = False) -> str:
    """
    Format a datetime with various options.
    
    Args:
        dt: Datetime to format.
        format_type: 'short', 'medium', 'long', 'iso', 'indian'.
        include_seconds: Whether to include seconds.
    """
    if dt is None:
        return ""
    
    try:
        if not isinstance(dt, datetime):
            raise FormatterError(f"Expected datetime, got {type(dt)}")
        
        time_format = "%H:%M:%S" if include_seconds else "%H:%M"
        
        formats = {
            "short": f"%d %b %Y {time_format}",           # 05 Jan 2025 14:30
            "medium": f"%d %B %Y {time_format}",          # 05 January 2025 14:30:45
            "long": f"%A, %d %B %Y {time_format}",        # Sunday, 05 January 2025 14:30:45
            "iso": f"%Y-%m-%dT{time_format}",             # 2025-01-05T14:30:45
            "indian": f"%d/%m/%Y {time_format}",          # 05/01/2025 14:30
        }
        
        fmt = formats.get(format_type, formats["short"])
        return dt.strftime(fmt)
        
    except Exception as e:
        logger.error(f"Failed to format datetime: {e}")
        return str(dt) if dt else ""


def format_date_range(
    start: date | datetime | None, 
    end: date | datetime | None, 
    format_type: str = "short"
) -> str:
    """Return a human-friendly representation of a date range."""
    try:
        start_str = format_date_short(start, format_type) if start else None
        end_str = format_date_short(end, format_type) if end else None
        
        if start_str and end_str:
            # Check if same date
            if start_str == end_str:
                return start_str
            return f"{start_str} – {end_str}"
        
        if start_str:
            return f"from {start_str}"
        
        if end_str:
            return f"until {end_str}"
        
        return ""
        
    except Exception as e:
        logger.error(f"Failed to format date range: {e}")
        return ""


def format_duration(
    start: datetime, 
    end: datetime | None = None, 
    precision: Literal["days", "hours", "minutes", "seconds"] = "minutes"
) -> str:
    """Format duration between two datetimes."""
    try:
        if end is None:
            end = datetime.now()
        
        if not isinstance(start, datetime) or not isinstance(end, datetime):
            raise FormatterError("Both start and end must be datetime objects")
        
        if start > end:
            start, end = end, start
        
        delta = end - start
        
        if precision == "days":
            return f"{delta.days} day{'s' if delta.days != 1 else ''}"
        
        total_seconds = int(delta.total_seconds())
        
        if precision == "seconds":
            return f"{total_seconds} second{'s' if total_seconds != 1 else ''}"
        
        total_minutes = total_seconds // 60
        if precision == "minutes":
            return f"{total_minutes} minute{'s' if total_minutes != 1 else ''}"
        
        hours = total_minutes // 60
        minutes = total_minutes % 60
        
        if hours == 0:
            return f"{minutes} minute{'s' if minutes != 1 else ''}"
        elif minutes == 0:
            return f"{hours} hour{'s' if hours != 1 else ''}"
        else:
            return f"{hours}h {minutes}m"
            
    except Exception as e:
        logger.error(f"Failed to format duration: {e}")
        return "Unknown duration"


def mask_email(email: str, mask_char: str = "*", show_domain: bool = True) -> str:
    """
    Mask an email address for privacy.
    
    Args:
        email: Email to mask. Will be lowercased.
        mask_char: Character to use for masking.
        show_domain: Whether to show the domain part.
    """
    try:
        if not isinstance(email, str) or not email.strip():
            return email
        
        email = email.strip().lower()
        
        if "@" not in email:
            # Not a valid email, mask most of it
            if len(email) <= 2:
                return mask_char * len(email)
            return email[0] + mask_char * (len(email) - 2) + email[-1]
        
        name, domain = email.split("@", 1)
        
        if not name:
            return f"{mask_char * 3}@{domain if show_domain else mask_char * len(domain)}"
        
        # Mask the name part
        if len(name) == 1:
            masked_name = mask_char
        elif len(name) == 2:
            masked_name = name[0] + mask_char
        else:
            masked_name = name[0] + mask_char * (len(name) - 2) + name[-1]
        
        if show_domain:
            return f"{masked_name}@{domain}"
        else:
            return f"{masked_name}@{mask_char * len(domain)}"
            
    except Exception as e:
        logger.error(f"Failed to mask email: {e}")
        return email


def mask_phone(phone: str, mask_char: str = "*", show_last: int = 4) -> str:
    """
    Mask a phone number for privacy.
    
    Args:
        phone: Phone number to mask.
        mask_char: Character to use for masking.
        show_last: Number of digits to show at the end.
    """
    try:
        if not isinstance(phone, str) or not phone.strip():
            return phone
        
        # Extract only digits
        digits = "".join(ch for ch in phone if ch.isdigit())
        
        if not digits:
            return phone  # Return original if no digits found
        
        if len(digits) <= show_last:
            return mask_char * len(digits)
        
        # Preserve original formatting structure
        masked = phone
        digits_replaced = 0
        digits_to_mask = len(digits) - show_last
        
        for i, char in enumerate(phone):
            if char.isdigit() and digits_replaced < digits_to_mask:
                masked = masked[:i] + mask_char + masked[i+1:]
                digits_replaced += 1
        
        return masked
        
    except Exception as e:
        logger.error(f"Failed to mask phone: {e}")
        return phone


def mask_aadhar(aadhar: str, mask_char: str = "*") -> str:
    """Mask Aadhar number showing only last 4 digits."""
    try:
        if not isinstance(aadhar, str):
            return aadhar
        
        # Remove spaces and extract digits
        digits = "".join(ch for ch in aadhar if ch.isdigit())
        
        if len(digits) != 12:
            return aadhar  # Return original if not valid Aadhar format
        
        # Format: XXXX XXXX 1234
        masked_digits = mask_char * 8 + digits[-4:]
        return f"{masked_digits[:4]} {masked_digits[4:8]} {masked_digits[8:]}"
        
    except Exception as e:
        logger.error(f"Failed to mask Aadhar: {e}")
        return aadhar


def mask_pan(pan: str, mask_char: str = "*") -> str:
    """Mask PAN number showing only last character."""
    try:
        if not isinstance(pan, str) or len(pan) != 10:
            return pan
        
        # Format: ABCD*****Z
        return pan[:4] + mask_char * 5 + pan[-1:]
        
    except Exception as e:
        logger.error(f"Failed to mask PAN: {e}")
        return pan


def humanize_percentage(
    value: Decimal | float | int | str, 
    *, 
    decimals: int = 2,
    show_sign: bool = True
) -> str:
    """Format a number as percentage with given decimals."""
    try:
        dec = safe_decimal(value, "percentage value")
        
        if decimals < 0:
            raise FormatterError("Decimals must be non-negative")
        
        formatted = f"{dec:.{decimals}f}"
        
        if show_sign:
            formatted += "%"
        
        return formatted
        
    except Exception as e:
        logger.error(f"Failed to format percentage: {e}")
        return str(value)


def format_file_size(size_bytes: int, binary: bool = True) -> str:
    """
    Format file size in human readable format.
    
    Args:
        size_bytes: Size in bytes.
        binary: Use binary (1024) or decimal (1000) units.
    """
    try:
        if not isinstance(size_bytes, int) or size_bytes < 0:
            raise FormatterError("Size must be a non-negative integer")
        
        if size_bytes == 0:
            return "0 B"
        
        base = 1024 if binary else 1000
        units = (
            ["B", "KiB", "MiB", "GiB", "TiB", "PiB"]
            if binary
            else ["B", "KB", "MB", "GB", "TB", "PB"]
        )
        
        import math
        unit_index = min(int(math.log(size_bytes, base)), len(units) - 1)
        
        if unit_index == 0:
            return f"{size_bytes} {units[0]}"
        
        size = size_bytes / (base ** unit_index)
        
        # Format with appropriate precision
        if size >= 100:
            return f"{size:.0f} {units[unit_index]}"
        elif size >= 10:
            return f"{size:.1f} {units[unit_index]}"
        else:
            return f"{size:.2f} {units[unit_index]}"
            
    except Exception as e:
        logger.error(f"Failed to format file size: {e}")
        return f"{size_bytes} bytes"


def format_number(
    value: Decimal | float | int | str,
    *,
    decimals: int = 2,
    thousands_separator: str = ",",
    decimal_separator: str = ".",
    indian_format: bool = False
) -> str:
    """
    Format a number with custom separators and precision.
    
    Args:
        value: Number to format.
        decimals: Number of decimal places.
        thousands_separator: Separator for thousands.
        decimal_separator: Separator for decimals.
        indian_format: Use Indian number formatting when True.
    """
    try:
        dec = safe_decimal(value, "number")
        
        if decimals < 0:
            raise FormatterError("Decimals must be non-negative")
        
        # Format with specified decimals
        if decimals == 0:
            formatted = str(int(dec))
        else:
            formatted = f"{dec:.{decimals}f}"
        
        # Apply number grouping
        if indian_format:
            formatted = format_indian_number(formatted)
        else:
            # Standard formatting
            parts = formatted.split('.')
            # Add thousands separators
            integer_part = parts[0]
            if len(integer_part) > 3:
                # Reverse, add separators every 3 digits, reverse back
                reversed_int = integer_part[::-1]
                grouped = thousands_separator.join(
                    [reversed_int[i:i+3] for i in range(0, len(reversed_int), 3)]
                )
                integer_part = grouped[::-1]
            
            formatted = integer_part
            if len(parts) > 1:
                formatted += decimal_separator + parts[1]
        
        # Replace default separators if different
        if thousands_separator != "," or decimal_separator != ".":
            formatted = formatted.replace(",", "TEMP_THOUSANDS")
            formatted = formatted.replace(".", decimal_separator)
            formatted = formatted.replace("TEMP_THOUSANDS", thousands_separator)
        
        return formatted
        
    except Exception as e:
        logger.error(f"Failed to format number: {e}")
        return str(value)


def truncate_text(
    text: str, 
    max_length: int, 
    suffix: str = "…",
    word_boundary: bool = True
) -> str:
    """
    Truncate text to specified length with options.
    
    Args:
        text: Text to truncate.
        max_length: Maximum length including suffix.
        suffix: Suffix to add when truncating.
        word_boundary: Whether to break at word boundaries (using spaces).
    """
    try:
        if not isinstance(text, str):
            text = str(text)
        
        if not isinstance(max_length, int) or max_length < 1:
            raise FormatterError("max_length must be a positive integer")
        
        if len(text) <= max_length:
            return text
        
        if max_length <= len(suffix):
            return suffix[:max_length]
        
        available_length = max_length - len(suffix)
        
        if word_boundary:
            # Find the last space within the available length
            truncated = text[:available_length]
            last_space = truncated.rfind(' ')
            
            if last_space > 0:
                truncated = text[:last_space]
            
            return truncated + suffix
        else:
            return text[:available_length] + suffix
            
    except Exception as e:
        logger.error(f"Failed to truncate text: {e}")
        return text