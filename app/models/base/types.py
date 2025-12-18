# --- File: C:\Hostel-Main\app\models\base\types.py ---
"""
Custom SQLAlchemy types for specialized data handling.

Provides custom column types for encrypted data, validated
fields, and domain-specific data types.
"""

from decimal import Decimal
from typing import Any, Optional
import json

from sqlalchemy import TypeDecorator, String, Text, Numeric
from sqlalchemy.dialects.postgresql import JSONB


class EncryptedType(TypeDecorator):
    """
    Custom type for encrypted sensitive data.
    
    Automatically encrypts data on write and decrypts on read.
    """
    
    impl = Text
    cache_ok = True
    
    def __init__(self, *args, **kwargs):
        """Initialize encrypted type."""
        super().__init__(*args, **kwargs)
        # In production, use proper encryption library (e.g., cryptography)
        # This is a placeholder
    
    def process_bind_param(self, value: Optional[str], dialect) -> Optional[str]:
        """Encrypt value before storing."""
        if value is None:
            return value
        
        # TODO: Implement actual encryption
        # For now, just return the value
        # In production: return encrypt(value, encryption_key)
        return value
    
    def process_result_value(self, value: Optional[str], dialect) -> Optional[str]:
        """Decrypt value after retrieving."""
        if value is None:
            return value
        
        # TODO: Implement actual decryption
        # For now, just return the value
        # In production: return decrypt(value, encryption_key)
        return value


class JSONType(TypeDecorator):
    """
    Enhanced JSON type with validation.
    
    Provides JSON storage with automatic serialization/deserialization
    and optional schema validation.
    """
    
    impl = JSONB
    cache_ok = True
    
    def process_bind_param(self, value: Any, dialect) -> Optional[str]:
        """Serialize value to JSON."""
        if value is None:
            return value
        
        if not isinstance(value, (dict, list)):
            raise ValueError(f"JSONType requires dict or list, got {type(value)}")
        
        return value
    
    def process_result_value(self, value: Any, dialect) -> Any:
        """Deserialize JSON value."""
        return value


class MoneyType(TypeDecorator):
    """
    Money type with currency handling.
    
    Stores monetary values with fixed precision (2 decimal places).
    """
    
    impl = Numeric(15, 2)
    cache_ok = True
    
    def process_bind_param(self, value: Optional[Decimal], dialect) -> Optional[Decimal]:
        """Validate and round monetary value."""
        if value is None:
            return value
        
        if not isinstance(value, Decimal):
            value = Decimal(str(value))
        
        # Round to 2 decimal places
        return value.quantize(Decimal('0.01'))
    
    def process_result_value(self, value: Optional[Decimal], dialect) -> Optional[Decimal]:
        """Return monetary value."""
        return value


class PhoneNumberType(TypeDecorator):
    """
    Phone number type with validation and formatting.
    
    Stores phone numbers in normalized format.
    """
    
    impl = String(20)
    cache_ok = True
    
    def process_bind_param(self, value: Optional[str], dialect) -> Optional[str]:
        """Normalize and validate phone number."""
        if value is None:
            return value
        
        # Remove non-numeric characters
        import re
        cleaned = re.sub(r'\D', '', value)
        
        if len(cleaned) < 10:
            raise ValueError(f"Phone number too short: {value}")
        
        return cleaned
    
    def process_result_value(self, value: Optional[str], dialect) -> Optional[str]:
        """Return phone number."""
        return value


class EmailType(TypeDecorator):
    """
    Email type with validation and normalization.
    
    Stores email addresses in lowercase.
    """
    
    impl = String(255)
    cache_ok = True
    
    def process_bind_param(self, value: Optional[str], dialect) -> Optional[str]:
        """Normalize and validate email."""
        if value is None:
            return value
        
        # Normalize to lowercase
        email = value.strip().lower()
        
        # Basic validation
        import re
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(pattern, email):
            raise ValueError(f"Invalid email format: {value}")
        
        return email
    
    def process_result_value(self, value: Optional[str], dialect) -> Optional[str]:
        """Return email."""
        return value


class URLType(TypeDecorator):
    """
    URL type with validation.
    
    Validates and stores URLs.
    """
    
    impl = String(500)
    cache_ok = True
    
    def process_bind_param(self, value: Optional[str], dialect) -> Optional[str]:
        """Validate URL format."""
        if value is None:
            return value
        
        import re
        pattern = r'^https?:\/\/(www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b([-a-zA-Z0-9()@:%_\+.~#?&//=]*)$'
        
        if not re.match(pattern, value):
            raise ValueError(f"Invalid URL format: {value}")
        
        return value
    
    def process_result_value(self, value: Optional[str], dialect) -> Optional[str]:
        """Return URL."""
        return value


class SlugType(TypeDecorator):
    """
    Slug type for URL-friendly strings.
    
    Automatically generates URL-friendly slugs.
    """
    
    impl = String(255)
    cache_ok = True
    
    def process_bind_param(self, value: Optional[str], dialect) -> Optional[str]:
        """Normalize to slug format."""
        if value is None:
            return value
        
        import re
        
        # Convert to lowercase
        slug = value.lower().strip()
        
        # Remove special characters
        slug = re.sub(r'[^\w\s-]', '', slug)
        
        # Replace spaces with hyphens
        slug = re.sub(r'[-\s]+', '-', slug)
        
        # Remove leading/trailing hyphens
        slug = slug.strip('-')
        
        return slug
    
    def process_result_value(self, value: Optional[str], dialect) -> Optional[str]:
        """Return slug."""
        return value


class CoordinateType(TypeDecorator):
    """
    Geographic coordinate type with validation.
    
    Validates latitude/longitude values.
    """
    
    impl = Numeric(10, 7)
    cache_ok = True
    
    def __init__(self, coord_type: str, *args, **kwargs):
        """
        Initialize coordinate type.
        
        Args:
            coord_type: 'latitude' or 'longitude'
        """
        super().__init__(*args, **kwargs)
        self.coord_type = coord_type
    
    def process_bind_param(self, value: Optional[Decimal], dialect) -> Optional[Decimal]:
        """Validate coordinate value."""
        if value is None:
            return value
        
        if not isinstance(value, Decimal):
            value = Decimal(str(value))
        
        # Validate range
        if self.coord_type == 'latitude':
            if not -90 <= value <= 90:
                raise ValueError(f"Latitude must be between -90 and 90: {value}")
        elif self.coord_type == 'longitude':
            if not -180 <= value <= 180:
                raise ValueError(f"Longitude must be between -180 and 180: {value}")
        
        return value
    
    def process_result_value(self, value: Optional[Decimal], dialect) -> Optional[Decimal]:
        """Return coordinate value."""
        return value