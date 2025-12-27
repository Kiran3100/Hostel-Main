"""
Input Validation Utilities

Comprehensive validation functions for various data types,
business rules, and security checks.
"""

import re
import ipaddress
import phonenumbers
from typing import Any, Dict, List, Optional, Union, Pattern
from datetime import datetime, date
from email_validator import validate_email as email_validate, EmailNotValidError
from pydantic import validator
import uuid

from .config import settings
from .exceptions import ValidationError
from .logging import get_logger

logger = get_logger(__name__)


class ValidationPatterns:
    """Common validation regex patterns"""
    
    # Basic patterns
    EMAIL = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    PHONE_BASIC = re.compile(r'^\+?1?-?\.?\s?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}$')
    
    # Identity patterns
    UUID = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$', re.I)
    SLUG = re.compile(r'^[a-z0-9]+(?:-[a-z0-9]+)*$')
    USERNAME = re.compile(r'^[a-zA-Z0-9_]{3,30}$')
    
    # Security patterns
    STRONG_PASSWORD = re.compile(r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$')
    SQL_INJECTION = re.compile(r'(\b(SELECT|INSERT|UPDATE|DELETE|DROP|UNION|CREATE|ALTER)\b)', re.I)
    XSS_BASIC = re.compile(r'<script.*?>.*?</script>', re.I | re.S)
    
    # Business patterns
    EMPLOYEE_ID = re.compile(r'^[A-Z]{2}\d{4,6}$')
    ROOM_NUMBER = re.compile(r'^[A-Z]?\d{1,4}[A-Z]?$')
    BOOKING_REF = re.compile(r'^BK[0-9]{8}$')
    
    # Financial patterns
    CURRENCY_CODE = re.compile(r'^[A-Z]{3}$')
    DECIMAL_MONEY = re.compile(r'^\d+(\.\d{1,2})?$')


class EmailValidator:
    """Enhanced email validation"""
    
    @staticmethod
    def validate_email(email: str, check_deliverability: bool = False) -> Dict[str, Any]:
        """
        Validate email address with optional deliverability check.
        
        Args:
            email: Email address to validate
            check_deliverability: Whether to check if email is deliverable
            
        Returns:
            Dictionary with validation results
        """
        result = {
            'is_valid': False,
            'normalized': None,
            'local': None,
            'domain': None,
            'errors': []
        }
        
        try:
            # Basic format validation
            if not email or not isinstance(email, str):
                result['errors'].append('Email must be a non-empty string')
                return result
            
            # Use email-validator library for comprehensive validation
            validation_result = email_validate(
                email,
                check_deliverability=check_deliverability
            )
            
            result.update({
                'is_valid': True,
                'normalized': validation_result.email,
                'local': validation_result.local,
                'domain': validation_result.domain
            })
            
            # Additional business rules
            if len(validation_result.local) > 64:
                result['errors'].append('Local part too long (max 64 characters)')
                result['is_valid'] = False
            
            if len(validation_result.domain) > 253:
                result['errors'].append('Domain part too long (max 253 characters)')
                result['is_valid'] = False
            
            # Check against blacklisted domains
            blacklisted_domains = ['tempmail.com', '10minutemail.com', 'guerrillamail.com']
            if validation_result.domain.lower() in blacklisted_domains:
                result['errors'].append('Email from temporary/disposable email provider')
                result['is_valid'] = False
            
        except EmailNotValidError as e:
            result['errors'].append(str(e))
        except Exception as e:
            result['errors'].append(f'Email validation failed: {str(e)}')
        
        return result


class PhoneValidator:
    """Enhanced phone number validation"""
    
    @staticmethod
    def validate_phone(
        phone: str, 
        country_code: Optional[str] = None,
        format_output: bool = True
    ) -> Dict[str, Any]:
        """
        Validate and format phone number.
        
        Args:
            phone: Phone number to validate
            country_code: ISO country code for validation context
            format_output: Whether to format the output
            
        Returns:
            Dictionary with validation results
        """
        result = {
            'is_valid': False,
            'formatted': None,
            'international': None,
            'national': None,
            'country_code': None,
            'carrier': None,
            'errors': []
        }
        
        try:
            if not phone or not isinstance(phone, str):
                result['errors'].append('Phone must be a non-empty string')
                return result
            
            # Parse phone number
            parsed = phonenumbers.parse(phone, country_code)
            
            # Validate phone number
            if not phonenumbers.is_valid_number(parsed):
                result['errors'].append('Invalid phone number')
                return result
            
            # Check if it's a possible number
            if not phonenumbers.is_possible_number(parsed):
                result['errors'].append('Phone number not possible')
                return result
            
            result['is_valid'] = True
            result['country_code'] = f"+{parsed.country_code}"
            
            if format_output:
                result['international'] = phonenumbers.format_number(
                    parsed, 
                    phonenumbers.PhoneNumberFormat.INTERNATIONAL
                )
                result['national'] = phonenumbers.format_number(
                    parsed, 
                    phonenumbers.PhoneNumberFormat.NATIONAL
                )
                result['formatted'] = result['international']
            
            # Get carrier information if available
            try:
                from phonenumbers.carrier import name_for_number
                carrier = name_for_number(parsed, 'en')
                if carrier:
                    result['carrier'] = carrier
            except ImportError:
                pass  # Carrier data not available
                
        except phonenumbers.NumberParseException as e:
            result['errors'].append(f'Phone parsing failed: {str(e)}')
        except Exception as e:
            result['errors'].append(f'Phone validation failed: {str(e)}')
        
        return result


class SecurityValidator:
    """Security-focused validation functions"""
    
    @staticmethod
    def validate_password_strength(password: str) -> Dict[str, Any]:
        """
        Validate password strength against security requirements.
        
        Args:
            password: Password to validate
            
        Returns:
            Dictionary with validation results
        """
        result = {
            'is_valid': True,
            'score': 0,
            'errors': [],
            'suggestions': []
        }
        
        if not password or not isinstance(password, str):
            result['is_valid'] = False
            result['errors'].append('Password must be a non-empty string')
            return result
        
        # Length check
        min_length = settings.security.PASSWORD_MIN_LENGTH
        if len(password) < min_length:
            result['is_valid'] = False
            result['errors'].append(f'Password must be at least {min_length} characters')
        else:
            result['score'] += 1
        
        # Character type checks
        if settings.security.PASSWORD_REQUIRE_UPPERCASE and not re.search(r'[A-Z]', password):
            result['is_valid'] = False
            result['errors'].append('Password must contain at least one uppercase letter')
        elif re.search(r'[A-Z]', password):
            result['score'] += 1
        
        if settings.security.PASSWORD_REQUIRE_LOWERCASE and not re.search(r'[a-z]', password):
            result['is_valid'] = False
            result['errors'].append('Password must contain at least one lowercase letter')
        elif re.search(r'[a-z]', password):
            result['score'] += 1
        
        if settings.security.PASSWORD_REQUIRE_NUMBERS and not re.search(r'\d', password):
            result['is_valid'] = False
            result['errors'].append('Password must contain at least one number')
        elif re.search(r'\d', password):
            result['score'] += 1
        
        if settings.security.PASSWORD_REQUIRE_SPECIAL and not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            result['is_valid'] = False
            result['errors'].append('Password must contain at least one special character')
        elif re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            result['score'] += 1
        
        # Common patterns
        common_patterns = ['password', '123456', 'qwerty', 'abc123', 'admin']
        if any(pattern in password.lower() for pattern in common_patterns):
            result['is_valid'] = False
            result['errors'].append('Password contains common patterns')
        
        # Repetitive characters
        if re.search(r'(.)\1{2,}', password):
            result['suggestions'].append('Avoid repeating characters')
        
        # Sequential characters
        sequences = ['123', 'abc', 'qwe', 'asd']
        if any(seq in password.lower() for seq in sequences):
            result['suggestions'].append('Avoid sequential characters')
        
        return result
    
    @staticmethod
    def check_sql_injection(input_string: str) -> bool:
        """
        Check for potential SQL injection patterns.
        
        Args:
            input_string: String to check for SQL injection
            
        Returns:
            True if potential SQL injection detected
        """
        if not isinstance(input_string, str):
            return False
        
        # Check for SQL keywords
        if ValidationPatterns.SQL_INJECTION.search(input_string):
            return True
        
        # Check for SQL comment patterns
        sql_comments = ['--', '/*', '*/', '#']
        if any(comment in input_string for comment in sql_comments):
            return True
        
        # Check for quote injection patterns
        quote_patterns = ["'", '"', ';', '\\']
        suspicious_count = sum(1 for pattern in quote_patterns if pattern in input_string)
        if suspicious_count > 2:  # Threshold for suspicion
            return True
        
        return False
    
    @staticmethod
    def check_xss(input_string: str) -> bool:
        """
        Check for potential XSS patterns.
        
        Args:
            input_string: String to check for XSS
            
        Returns:
            True if potential XSS detected
        """
        if not isinstance(input_string, str):
            return False
        
        # Check for script tags
        if ValidationPatterns.XSS_BASIC.search(input_string):
            return True
        
        # Check for other XSS patterns
        xss_patterns = [
            '<script', '</script>', 'javascript:', 'onerror=', 'onload=',
            'onclick=', 'onmouseover=', 'onfocus=', 'alert(', 'eval(',
            'document.cookie', 'window.location'
        ]
        
        input_lower = input_string.lower()
        if any(pattern in input_lower for pattern in xss_patterns):
            return True
        
        return False


class BusinessValidator:
    """Business rule validation functions"""
    
    @staticmethod
    def validate_employee_id(employee_id: str) -> Dict[str, Any]:
        """
        Validate employee ID format.
        
        Args:
            employee_id: Employee ID to validate
            
        Returns:
            Dictionary with validation results
        """
        result = {
            'is_valid': False,
            'formatted': None,
            'department': None,
            'errors': []
        }
        
        if not employee_id or not isinstance(employee_id, str):
            result['errors'].append('Employee ID must be a non-empty string')
            return result
        
        employee_id = employee_id.upper().strip()
        
        if not ValidationPatterns.EMPLOYEE_ID.match(employee_id):
            result['errors'].append('Employee ID must be in format XX1234 (2 letters + 4-6 digits)')
            return result
        
        result['is_valid'] = True
        result['formatted'] = employee_id
        result['department'] = employee_id[:2]  # First 2 letters are department code
        
        return result
    
    @staticmethod
    def validate_room_number(room_number: str) -> Dict[str, Any]:
        """
        Validate room number format.
        
        Args:
            room_number: Room number to validate
            
        Returns:
            Dictionary with validation results
        """
        result = {
            'is_valid': False,
            'formatted': None,
            'floor': None,
            'room_type': None,
            'errors': []
        }
        
        if not room_number or not isinstance(room_number, str):
            result['errors'].append('Room number must be a non-empty string')
            return result
        
        room_number = room_number.upper().strip()
        
        if not ValidationPatterns.ROOM_NUMBER.match(room_number):
            result['errors'].append('Invalid room number format')
            return result
        
        result['is_valid'] = True
        result['formatted'] = room_number
        
        # Extract floor from room number (first digit(s))
        match = re.match(r'^([A-Z]?)(\d+)([A-Z]?)$', room_number)
        if match:
            prefix, digits, suffix = match.groups()
            if len(digits) >= 2:
                result['floor'] = int(digits[0])
            result['room_type'] = prefix + suffix
        
        return result
    
    @staticmethod
    def validate_booking_reference(booking_ref: str) -> Dict[str, Any]:
        """
        Validate booking reference format.
        
        Args:
            booking_ref: Booking reference to validate
            
        Returns:
            Dictionary with validation results
        """
        result = {
            'is_valid': False,
            'formatted': None,
            'booking_id': None,
            'errors': []
        }
        
        if not booking_ref or not isinstance(booking_ref, str):
            result['errors'].append('Booking reference must be a non-empty string')
            return result
        
        booking_ref = booking_ref.upper().strip()
        
        if not ValidationPatterns.BOOKING_REF.match(booking_ref):
            result['errors'].append('Booking reference must be in format BK12345678')
            return result
        
        result['is_valid'] = True
        result['formatted'] = booking_ref
        result['booking_id'] = booking_ref[2:]  # Remove BK prefix
        
        return result


class DateValidator:
    """Date and time validation functions"""
    
    @staticmethod
    def validate_date_range(
        start_date: Union[str, date, datetime],
        end_date: Union[str, date, datetime],
        max_days: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Validate date range.
        
        Args:
            start_date: Start date
            end_date: End date
            max_days: Maximum allowed days between dates
            
        Returns:
            Dictionary with validation results
        """
        result = {
            'is_valid': True,
            'start_date': None,
            'end_date': None,
            'duration_days': 0,
            'errors': []
        }
        
        try:
            # Convert to date objects if strings
            if isinstance(start_date, str):
                start_date = datetime.fromisoformat(start_date).date()
            elif isinstance(start_date, datetime):
                start_date = start_date.date()
            
            if isinstance(end_date, str):
                end_date = datetime.fromisoformat(end_date).date()
            elif isinstance(end_date, datetime):
                end_date = end_date.date()
            
            result['start_date'] = start_date
            result['end_date'] = end_date
            
            # Check if start date is before end date
            if start_date >= end_date:
                result['is_valid'] = False
                result['errors'].append('Start date must be before end date')
            
            # Calculate duration
            duration = (end_date - start_date).days
            result['duration_days'] = duration
            
            # Check maximum duration
            if max_days and duration > max_days:
                result['is_valid'] = False
                result['errors'].append(f'Date range cannot exceed {max_days} days')
            
            # Check if dates are in the past
            today = date.today()
            if start_date < today:
                result['errors'].append('Start date cannot be in the past')
                # Don't mark as invalid for business rules flexibility
            
        except (ValueError, TypeError) as e:
            result['is_valid'] = False
            result['errors'].append(f'Invalid date format: {str(e)}')
        
        return result


class NetworkValidator:
    """Network and IP validation functions"""
    
    @staticmethod
    def validate_ip_address(ip: str) -> Dict[str, Any]:
        """
        Validate IP address (IPv4 or IPv6).
        
        Args:
            ip: IP address to validate
            
        Returns:
            Dictionary with validation results
        """
        result = {
            'is_valid': False,
            'version': None,
            'is_private': None,
            'is_loopback': None,
            'errors': []
        }
        
        if not ip or not isinstance(ip, str):
            result['errors'].append('IP address must be a non-empty string')
            return result
        
        try:
            ip_obj = ipaddress.ip_address(ip.strip())
            
            result['is_valid'] = True
            result['version'] = ip_obj.version
            result['is_private'] = ip_obj.is_private
            result['is_loopback'] = ip_obj.is_loopback
            
        except ValueError as e:
            result['errors'].append(f'Invalid IP address: {str(e)}')
        
        return result


class FileValidator:
    """File validation functions"""
    
    @staticmethod
    def validate_file_upload(
        filename: str,
        file_size: int,
        allowed_extensions: Optional[List[str]] = None,
        max_size_mb: int = 10
    ) -> Dict[str, Any]:
        """
        Validate file upload parameters.
        
        Args:
            filename: Name of the uploaded file
            file_size: Size of the file in bytes
            allowed_extensions: List of allowed file extensions
            max_size_mb: Maximum file size in MB
            
        Returns:
            Dictionary with validation results
        """
        result = {
            'is_valid': True,
            'filename': filename,
            'extension': None,
            'size_mb': round(file_size / (1024 * 1024), 2),
            'errors': []
        }
        
        if not filename:
            result['is_valid'] = False
            result['errors'].append('Filename cannot be empty')
            return result
        
        # Extract file extension
        if '.' in filename:
            result['extension'] = filename.rsplit('.', 1)[1].lower()
        else:
            result['is_valid'] = False
            result['errors'].append('File must have an extension')
            return result
        
        # Check allowed extensions
        if allowed_extensions and result['extension'] not in [ext.lower() for ext in allowed_extensions]:
            result['is_valid'] = False
            result['errors'].append(f'File type not allowed. Allowed: {", ".join(allowed_extensions)}')
        
        # Check file size
        max_size_bytes = max_size_mb * 1024 * 1024
        if file_size > max_size_bytes:
            result['is_valid'] = False
            result['errors'].append(f'File size exceeds {max_size_mb}MB limit')
        
        # Check for potentially dangerous filenames
        dangerous_patterns = ['..', '/', '\\', '<', '>', ':', '"', '|', '?', '*']
        if any(pattern in filename for pattern in dangerous_patterns):
            result['is_valid'] = False
            result['errors'].append('Filename contains invalid characters')
        
        return result


# Convenience functions
def validate_email(email: str, check_deliverability: bool = False) -> bool:
    """Simple email validation function"""
    result = EmailValidator.validate_email(email, check_deliverability)
    return result['is_valid']


def validate_phone(phone: str, country_code: Optional[str] = None) -> bool:
    """Simple phone validation function"""
    result = PhoneValidator.validate_phone(phone, country_code)
    return result['is_valid']


def validate_uuid(uuid_string: str) -> bool:
    """Validate UUID format"""
    try:
        uuid.UUID(uuid_string)
        return True
    except (ValueError, TypeError):
        return False


def validate_id(id_string: str, allow_uuid: bool = True, allow_numeric: bool = True) -> bool:
    """Validate ID format (UUID or numeric)"""
    if not id_string or not isinstance(id_string, str):
        return False
    
    id_string = id_string.strip()
    
    if allow_uuid and validate_uuid(id_string):
        return True
    
    if allow_numeric and id_string.isdigit():
        return True
    
    return False


def sanitize_input(input_string: str, max_length: Optional[int] = None) -> str:
    """Sanitize input string for security"""
    if not isinstance(input_string, str):
        return ""
    
    # Remove potential XSS and SQL injection patterns
    sanitized = input_string.strip()
    
    # Remove HTML tags
    sanitized = re.sub(r'<[^>]*>', '', sanitized)
    
    # Remove SQL comment patterns
    sanitized = re.sub(r'--.*$', '', sanitized, flags=re.MULTILINE)
    sanitized = re.sub(r'/\*.*?\*/', '', sanitized, flags=re.DOTALL)
    
    # Limit length if specified
    if max_length:
        sanitized = sanitized[:max_length]
    
    return sanitized


# Export main functions and classes
__all__ = [
    'ValidationPatterns',
    'EmailValidator',
    'PhoneValidator',
    'SecurityValidator',
    'BusinessValidator',
    'DateValidator',
    'NetworkValidator',
    'FileValidator',
    'validate_email',
    'validate_phone',
    'validate_uuid',
    'validate_id',
    'sanitize_input'
]