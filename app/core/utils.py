"""
Utility Functions and Helpers

Collection of common utility functions for the hostel management system
including data formatting, ID generation, datetime handling, and more.
"""

import secrets
import string
import hashlib
import base64
import json
import uuid
from typing import Any, Dict, List, Optional, Union, Callable
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from urllib.parse import quote, unquote
import re

from .config import settings
from .logging import get_logger

logger = get_logger(__name__)


class IDGenerator:
    """ID generation utilities"""
    
    @staticmethod
    def generate_uuid() -> str:
        """Generate a UUID4 string"""
        return str(uuid.uuid4())
    
    @staticmethod
    def generate_short_id(length: int = 8) -> str:
        """Generate a short alphanumeric ID"""
        alphabet = string.ascii_uppercase + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(length))
    
    @staticmethod
    def generate_secure_token(length: int = 32) -> str:
        """Generate a cryptographically secure token"""
        return secrets.token_urlsafe(length)
    
    @staticmethod
    def generate_numeric_id(length: int = 8) -> str:
        """Generate a numeric ID"""
        return ''.join(secrets.choice(string.digits) for _ in range(length))
    
    @staticmethod
    def generate_booking_reference() -> str:
        """Generate a booking reference in format BK12345678"""
        return f"BK{IDGenerator.generate_numeric_id(8)}"
    
    @staticmethod
    def generate_employee_id(department_code: str) -> str:
        """Generate employee ID in format XX1234"""
        if len(department_code) != 2:
            raise ValueError("Department code must be 2 characters")
        
        numeric_part = IDGenerator.generate_numeric_id(4)
        return f"{department_code.upper()}{numeric_part}"
    
    @staticmethod
    def generate_room_key() -> str:
        """Generate a room access key"""
        return IDGenerator.generate_short_id(6)


class DateTimeUtils:
    """Date and time utility functions"""
    
    @staticmethod
    def now_utc() -> datetime:
        """Get current UTC datetime"""
        return datetime.now(timezone.utc)
    
    @staticmethod
    def format_datetime(
        dt: datetime,
        format_type: str = "iso"
    ) -> str:
        """
        Format datetime to string.
        
        Args:
            dt: Datetime to format
            format_type: Format type (iso, human, short, long)
            
        Returns:
            Formatted datetime string
        """
        if format_type == "iso":
            return dt.isoformat()
        elif format_type == "human":
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        elif format_type == "short":
            return dt.strftime("%Y-%m-%d")
        elif format_type == "long":
            return dt.strftime("%A, %B %d, %Y at %I:%M %p")
        elif format_type == "time_only":
            return dt.strftime("%H:%M:%S")
        else:
            return dt.isoformat()
    
    @staticmethod
    def parse_datetime(
        dt_string: str,
        format_pattern: Optional[str] = None
    ) -> Optional[datetime]:
        """
        Parse datetime string to datetime object.
        
        Args:
            dt_string: Datetime string to parse
            format_pattern: Optional format pattern
            
        Returns:
            Parsed datetime or None if parsing fails
        """
        try:
            if format_pattern:
                return datetime.strptime(dt_string, format_pattern)
            else:
                # Try common formats
                formats = [
                    "%Y-%m-%d %H:%M:%S",
                    "%Y-%m-%dT%H:%M:%S",
                    "%Y-%m-%dT%H:%M:%S.%f",
                    "%Y-%m-%dT%H:%M:%SZ",
                    "%Y-%m-%d",
                    "%d/%m/%Y",
                    "%m/%d/%Y"
                ]
                
                for fmt in formats:
                    try:
                        return datetime.strptime(dt_string, fmt)
                    except ValueError:
                        continue
                
                # Try ISO format
                return datetime.fromisoformat(dt_string.replace('Z', '+00:00'))
                
        except (ValueError, TypeError) as e:
            logger.warning(f"Failed to parse datetime '{dt_string}': {str(e)}")
            return None
    
    @staticmethod
    def add_business_days(start_date: datetime, days: int) -> datetime:
        """Add business days to a date (excludes weekends)"""
        current_date = start_date
        added_days = 0
        
        while added_days < days:
            current_date += timedelta(days=1)
            # Monday = 0, Sunday = 6
            if current_date.weekday() < 5:  # Monday to Friday
                added_days += 1
        
        return current_date
    
    @staticmethod
    def get_time_ago(dt: datetime) -> str:
        """Get human-readable time ago string"""
        now = DateTimeUtils.now_utc()
        
        # Ensure both datetimes are timezone-aware
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        
        diff = now - dt
        seconds = diff.total_seconds()
        
        if seconds < 60:
            return "just now"
        elif seconds < 3600:
            minutes = int(seconds // 60)
            return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
        elif seconds < 86400:
            hours = int(seconds // 3600)
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        elif seconds < 604800:
            days = int(seconds // 86400)
            return f"{days} day{'s' if days != 1 else ''} ago"
        elif seconds < 2629746:
            weeks = int(seconds // 604800)
            return f"{weeks} week{'s' if weeks != 1 else ''} ago"
        elif seconds < 31556952:
            months = int(seconds // 2629746)
            return f"{months} month{'s' if months != 1 else ''} ago"
        else:
            years = int(seconds // 31556952)
            return f"{years} year{'s' if years != 1 else ''} ago"


class CurrencyUtils:
    """Currency and money handling utilities"""
    
    @staticmethod
    def format_currency(
        amount: Union[int, float, Decimal],
        currency_code: str = "USD",
        locale: str = "en_US"
    ) -> str:
        """
        Format amount as currency string.
        
        Args:
            amount: Amount to format
            currency_code: Currency code (USD, EUR, etc.)
            locale: Locale for formatting
            
        Returns:
            Formatted currency string
        """
        try:
            # Convert to Decimal for precision
            if isinstance(amount, (int, float)):
                amount = Decimal(str(amount))
            
            # Round to 2 decimal places
            amount = amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            
            # Simple formatting (can be enhanced with locale support)
            currency_symbols = {
                'USD': '$',
                'EUR': '€',
                'GBP': '£',
                'JPY': '¥',
                'INR': '₹'
            }
            
            symbol = currency_symbols.get(currency_code, currency_code)
            
            # Format with thousands separator
            formatted_amount = f"{amount:,.2f}"
            
            return f"{symbol}{formatted_amount}"
            
        except Exception as e:
            logger.error(f"Currency formatting failed: {str(e)}")
            return f"{currency_code} {amount}"
    
    @staticmethod
    def convert_currency(
        amount: Union[int, float, Decimal],
        from_currency: str,
        to_currency: str,
        exchange_rate: Optional[float] = None
    ) -> Decimal:
        """
        Convert currency amount (basic implementation).
        
        Args:
            amount: Amount to convert
            from_currency: Source currency
            to_currency: Target currency
            exchange_rate: Exchange rate (if None, would fetch from API)
            
        Returns:
            Converted amount
        """
        # Convert to Decimal
        if isinstance(amount, (int, float)):
            amount = Decimal(str(amount))
        
        # If same currency, return as-is
        if from_currency == to_currency:
            return amount
        
        # Use provided exchange rate or default to 1.0
        # In real implementation, this would fetch from exchange rate API
        rate = Decimal(str(exchange_rate or 1.0))
        
        converted = amount * rate
        return converted.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    
    @staticmethod
    def calculate_tax(
        amount: Union[int, float, Decimal],
        tax_rate: Union[int, float, Decimal],
        inclusive: bool = False
    ) -> Dict[str, Decimal]:
        """
        Calculate tax amount.
        
        Args:
            amount: Base amount
            tax_rate: Tax rate (e.g., 0.1 for 10%)
            inclusive: Whether tax is included in amount
            
        Returns:
            Dictionary with tax calculations
        """
        # Convert to Decimal
        amount = Decimal(str(amount))
        tax_rate = Decimal(str(tax_rate))
        
        if inclusive:
            # Tax is included in amount
            base_amount = amount / (1 + tax_rate)
            tax_amount = amount - base_amount
        else:
            # Tax is additional
            base_amount = amount
            tax_amount = amount * tax_rate
        
        total_amount = base_amount + tax_amount
        
        return {
            'base_amount': base_amount.quantize(Decimal('0.01')),
            'tax_amount': tax_amount.quantize(Decimal('0.01')),
            'total_amount': total_amount.quantize(Decimal('0.01')),
            'tax_rate': tax_rate
        }


class TextUtils:
    """Text processing and formatting utilities"""
    
    @staticmethod
    def slugify(text: str) -> str:
        """Convert text to URL-friendly slug"""
        # Convert to lowercase and replace spaces/special chars with hyphens
        slug = re.sub(r'[^\w\s-]', '', text.lower())
        slug = re.sub(r'[-\s]+', '-', slug)
        return slug.strip('-')
    
    @staticmethod
    def truncate(text: str, length: int, suffix: str = "...") -> str:
        """Truncate text to specified length"""
        if len(text) <= length:
            return text
        
        return text[:length - len(suffix)] + suffix
    
    @staticmethod
    def capitalize_words(text: str) -> str:
        """Capitalize each word in text"""
        return ' '.join(word.capitalize() for word in text.split())
    
    @staticmethod
    def extract_initials(full_name: str) -> str:
        """Extract initials from full name"""
        words = full_name.split()
        return ''.join(word[0].upper() for word in words if word)
    
    @staticmethod
    def mask_sensitive_data(
        text: str,
        mask_char: str = "*",
        show_last: int = 4,
        show_first: int = 0
    ) -> str:
        """Mask sensitive data showing only specified characters"""
        if len(text) <= show_first + show_last:
            return mask_char * len(text)
        
        first_part = text[:show_first] if show_first > 0 else ""
        last_part = text[-show_last:] if show_last > 0 else ""
        middle_length = len(text) - show_first - show_last
        middle_part = mask_char * middle_length
        
        return first_part + middle_part + last_part
    
    @staticmethod
    def generate_acronym(text: str) -> str:
        """Generate acronym from text"""
        words = re.findall(r'\b[A-Z][a-z]*', text)
        if not words:
            words = text.split()
        
        return ''.join(word[0].upper() for word in words)


class HashUtils:
    """Hashing and encoding utilities"""
    
    @staticmethod
    def hash_string(text: str, algorithm: str = "sha256") -> str:
        """Hash string using specified algorithm"""
        algorithms = {
            'md5': hashlib.md5,
            'sha1': hashlib.sha1,
            'sha256': hashlib.sha256,
            'sha512': hashlib.sha512
        }
        
        if algorithm not in algorithms:
            raise ValueError(f"Unsupported algorithm: {algorithm}")
        
        hasher = algorithms[algorithm]()
        hasher.update(text.encode('utf-8'))
        return hasher.hexdigest()
    
    @staticmethod
    def encode_base64(data: Union[str, bytes]) -> str:
        """Encode data to base64 string"""
        if isinstance(data, str):
            data = data.encode('utf-8')
        
        return base64.b64encode(data).decode('utf-8')
    
    @staticmethod
    def decode_base64(encoded_data: str) -> bytes:
        """Decode base64 string to bytes"""
        return base64.b64decode(encoded_data)
    
    @staticmethod
    def create_checksum(data: Union[str, bytes]) -> str:
        """Create MD5 checksum of data"""
        if isinstance(data, str):
            data = data.encode('utf-8')
        
        return hashlib.md5(data).hexdigest()


class CollectionUtils:
    """Collection manipulation utilities"""
    
    @staticmethod
    def chunk_list(lst: List[Any], chunk_size: int) -> List[List[Any]]:
        """Split list into chunks of specified size"""
        return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]
    
    @staticmethod
    def flatten_dict(
        nested_dict: Dict[str, Any],
        separator: str = "."
    ) -> Dict[str, Any]:
        """Flatten nested dictionary"""
        def _flatten(obj, parent_key="", sep="."):
            items = []
            if isinstance(obj, dict):
                for key, value in obj.items():
                    new_key = f"{parent_key}{sep}{key}" if parent_key else key
                    items.extend(_flatten(value, new_key, sep).items())
            else:
                return {parent_key: obj}
            return dict(items)
        
        return _flatten(nested_dict, separator=separator)
    
    @staticmethod
    def group_by(lst: List[Dict[str, Any]], key: str) -> Dict[str, List[Dict[str, Any]]]:
        """Group list of dictionaries by specified key"""
        grouped = {}
        for item in lst:
            group_key = item.get(key)
            if group_key not in grouped:
                grouped[group_key] = []
            grouped[group_key].append(item)
        return grouped
    
    @staticmethod
    def merge_dicts(*dicts: Dict[str, Any]) -> Dict[str, Any]:
        """Merge multiple dictionaries"""
        result = {}
        for d in dicts:
            result.update(d)
        return result
    
    @staticmethod
    def remove_empty_values(data: Dict[str, Any]) -> Dict[str, Any]:
        """Remove empty values from dictionary"""
        return {
            key: value for key, value in data.items()
            if value is not None and value != "" and value != []
        }


class URLUtils:
    """URL handling utilities"""
    
    @staticmethod
    def build_url(base_url: str, path: str = "", params: Optional[Dict[str, Any]] = None) -> str:
        """Build URL with path and query parameters"""
        # Ensure base_url doesn't end with slash if path is provided
        if path and base_url.endswith('/'):
            base_url = base_url.rstrip('/')
        
        # Ensure path starts with slash if it's not empty
        if path and not path.startswith('/'):
            path = '/' + path
        
        url = base_url + path
        
        # Add query parameters
        if params:
            query_string = '&'.join(
                f"{quote(str(key))}={quote(str(value))}"
                for key, value in params.items()
                if value is not None
            )
            if query_string:
                url += '?' + query_string
        
        return url
    
    @staticmethod
    def parse_query_params(query_string: str) -> Dict[str, str]:
        """Parse query string into dictionary"""
        params = {}
        if query_string:
            # Remove leading '?' if present
            if query_string.startswith('?'):
                query_string = query_string[1:]
            
            for param in query_string.split('&'):
                if '=' in param:
                    key, value = param.split('=', 1)
                    params[unquote(key)] = unquote(value)
                else:
                    params[unquote(param)] = ''
        
        return params


class FileUtils:
    """File handling utilities"""
    
    @staticmethod
    def get_file_extension(filename: str) -> str:
        """Get file extension from filename"""
        return filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    
    @staticmethod
    def get_file_size_string(size_bytes: int) -> str:
        """Convert file size in bytes to human-readable string"""
        units = ['B', 'KB', 'MB', 'GB', 'TB']
        size = float(size_bytes)
        
        for unit in units:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        
        return f"{size:.1f} PB"
    
    @staticmethod
    def is_safe_filename(filename: str) -> bool:
        """Check if filename is safe (no path traversal, etc.)"""
        dangerous_patterns = ['..', '/', '\\', '<', '>', ':', '"', '|', '?', '*']
        return not any(pattern in filename for pattern in dangerous_patterns)
    
    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """Sanitize filename for safe storage"""
        # Remove dangerous characters
        sanitized = re.sub(r'[<>:"/\\|?*]', '_', filename)
        
        # Remove leading/trailing spaces and dots
        sanitized = sanitized.strip(' .')
        
        # Limit length
        if len(sanitized) > 255:
            name, ext = sanitized.rsplit('.', 1) if '.' in sanitized else (sanitized, '')
            max_name_length = 255 - len(ext) - 1 if ext else 255
            sanitized = name[:max_name_length] + ('.' + ext if ext else '')
        
        return sanitized


# Convenience functions combining multiple utilities
def generate_id() -> str:
    """Generate a UUID4 ID"""
    return IDGenerator.generate_uuid()


def format_datetime(dt: datetime, format_type: str = "iso") -> str:
    """Format datetime to string"""
    return DateTimeUtils.format_datetime(dt, format_type)


def sanitize_input(text: str) -> str:
    """Basic input sanitization"""
    if not isinstance(text, str):
        return ""
    
    # Remove potential harmful content
    sanitized = re.sub(r'<script.*?</script>', '', text, flags=re.IGNORECASE | re.DOTALL)
    sanitized = re.sub(r'javascript:', '', sanitized, flags=re.IGNORECASE)
    sanitized = sanitized.strip()
    
    return sanitized


# Export main classes and functions
__all__ = [
    'IDGenerator',
    'DateTimeUtils',
    'CurrencyUtils',
    'TextUtils',
    'HashUtils',
    'CollectionUtils',
    'URLUtils',
    'FileUtils',
    'generate_id',
    'format_datetime',
    'sanitize_input'
]