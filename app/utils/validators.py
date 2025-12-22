"""
Comprehensive validation utilities for hostel management system
"""

import re
import ipaddress
from typing import Any, Dict, List, Optional, Union, Callable
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
import mimetypes
from urllib.parse import urlparse
import string
import hashlib
import hmac

class ValidationResult:
    """Validation result container"""
    
    def __init__(self, is_valid: bool = True, errors: List[str] = None):
        self.is_valid = is_valid
        self.errors = errors or []
    
    def add_error(self, error: str):
        """Add validation error"""
        self.is_valid = False
        self.errors.append(error)
    
    def __bool__(self):
        """Allow boolean evaluation"""
        return self.is_valid
    
    def __str__(self):
        """String representation"""
        if self.is_valid:
            return "Validation passed"
        return f"Validation failed: {', '.join(self.errors)}"


class EmailValidator:
    """Email validation utilities"""
    
    EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    
    # Common disposable email domains
    DISPOSABLE_DOMAINS = {
        '10minutemail.com', 'guerrillamail.com', 'mailinator.com',
        'tempmail.org', 'yopmail.com', 'throwaway.email', 'maildrop.cc',
        'temp-mail.org', 'getnada.com', 'trashmail.com', 'fakeinbox.com'
    }
    
    @classmethod
    def validate(cls, email: str) -> ValidationResult:
        """Validate email format"""
        result = ValidationResult()
        
        if not email:
            result.add_error("Email address is required")
            return result
        
        # Convert to lowercase for validation
        email = email.strip().lower()
        
        # Check basic format
        if not cls.EMAIL_REGEX.match(email):
            result.add_error("Invalid email format")
            return result
        
        # Check length
        if len(email) > 254:  # RFC 5321
            result.add_error("Email address is too long")
        
        # Split into local and domain parts
        try:
            local, domain = email.split('@')
            
            # Validate local part
            if len(local) > 64:  # RFC 5321
                result.add_error("Email local part is too long")
            
            if local.startswith('.') or local.endswith('.'):
                result.add_error("Email local part cannot start or end with a dot")
            
            if '..' in local:
                result.add_error("Email local part cannot contain consecutive dots")
            
            # Validate domain part
            if not cls.is_valid_domain(domain):
                result.add_error("Invalid email domain")
            
        except ValueError:
            result.add_error("Invalid email format")
        
        return result
    
    @classmethod
    def is_valid_domain(cls, domain: str) -> bool:
        """Check if email domain is valid"""
        if not domain:
            return False
        
        # Domain should have at least one dot
        if '.' not in domain:
            return False
        
        # Check domain format
        domain_pattern = re.compile(
            r'^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$'
        )
        
        return bool(domain_pattern.match(domain))
    
    @classmethod
    def is_disposable_email(cls, email: str) -> bool:
        """Check if email is from disposable email provider"""
        if not email:
            return False
        
        try:
            domain = email.split('@')[1].lower()
            return domain in cls.DISPOSABLE_DOMAINS
        except (IndexError, AttributeError):
            return False
    
    @classmethod
    def normalize_email(cls, email: str) -> str:
        """Normalize email address"""
        if not email:
            return ""
        
        # Convert to lowercase
        email = email.strip().lower()
        
        # Remove dots from Gmail addresses (they're ignored)
        try:
            local, domain = email.split('@')
            
            if domain in ['gmail.com', 'googlemail.com']:
                # Remove dots from local part
                local = local.replace('.', '')
                # Remove everything after +
                if '+' in local:
                    local = local.split('+')[0]
            
            email = f"{local}@{domain}"
        except ValueError:
            pass
        
        return email


class PhoneValidator:
    """Phone number validation utilities"""
    
    # Indian phone number patterns
    MOBILE_PATTERNS = {
        'IN': re.compile(r'^(\+91|91)?[6-9]\d{9}$'),
        'US': re.compile(r'^(\+1|1)?[2-9]\d{2}[2-9]\d{2}\d{4}$'),
        'UK': re.compile(r'^(\+44|44)?[1-9]\d{9,10}$'),
        'AU': re.compile(r'^(\+61|61)?[4-5]\d{8}$')
    }
    
    @classmethod
    def validate(cls, phone: str, country_code: str = 'IN') -> ValidationResult:
        """Validate phone number format"""
        result = ValidationResult()
        
        if not phone:
            result.add_error("Phone number is required")
            return result
        
        # Extract digits only
        digits = cls.extract_digits(phone)
        
        # Check if pattern exists for country
        if country_code not in cls.MOBILE_PATTERNS:
            result.add_error(f"Validation not supported for country code: {country_code}")
            return result
        
        # Validate against country pattern
        pattern = cls.MOBILE_PATTERNS[country_code]
        
        if not pattern.match(phone):
            result.add_error(f"Invalid phone number format for {country_code}")
        
        # Additional validation for Indian numbers
        if country_code == 'IN':
            if len(digits) == 10 and digits[0] not in '6789':
                result.add_error("Indian mobile numbers must start with 6, 7, 8, or 9")
        
        return result
    
    @classmethod
    def extract_digits(cls, phone: str) -> str:
        """Extract only digits from phone number"""
        if not phone:
            return ""
        
        return re.sub(r'\D', '', phone)
    
    @classmethod
    def is_mobile(cls, phone: str, country_code: str = 'IN') -> bool:
        """Check if phone number is mobile"""
        if not phone:
            return False
        
        digits = cls.extract_digits(phone)
        
        if country_code == 'IN':
            # Indian mobile: 10 digits starting with 6-9
            if len(digits) == 10:
                return digits[0] in '6789'
            # With country code
            if len(digits) == 12 and digits.startswith('91'):
                return digits[2] in '6789'
        
        elif country_code == 'US':
            # US mobile numbers (no specific prefix, all could be mobile)
            return len(digits) in [10, 11]
        
        return False
    
    @classmethod
    def format_international(cls, phone: str, country_code: str = 'IN') -> str:
        """Format phone number in international format"""
        if not phone:
            return ""
        
        digits = cls.extract_digits(phone)
        
        if country_code == 'IN':
            if len(digits) == 10:
                return f"+91{digits}"
            elif len(digits) == 12 and digits.startswith('91'):
                return f"+{digits}"
        
        elif country_code == 'US':
            if len(digits) == 10:
                return f"+1{digits}"
            elif len(digits) == 11 and digits.startswith('1'):
                return f"+{digits}"
        
        # Default: add + if not present
        if not phone.startswith('+'):
            return f"+{digits}"
        
        return phone


class URLValidator:
    """URL validation utilities"""
    
    @classmethod
    def validate(cls, url: str) -> ValidationResult:
        """Validate URL format"""
        result = ValidationResult()
        
        if not url:
            result.add_error("URL is required")
            return result
        
        # Parse URL
        try:
            parsed = urlparse(url)
            
            # Check scheme
            if parsed.scheme not in ['http', 'https', 'ftp', 'ftps']:
                result.add_error("Invalid URL scheme (must be http, https, ftp, or ftps)")
            
            # Check if domain exists
            if not parsed.netloc:
                result.add_error("URL must include a domain")
            
            # Check domain format
            domain_pattern = re.compile(
                r'^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)*'
                r'[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?$'
            )
            
            if not domain_pattern.match(parsed.netloc.split(':')[0]):
                result.add_error("Invalid domain format")
            
        except Exception as e:
            result.add_error(f"Invalid URL: {str(e)}")
        
        return result
    
    @classmethod
    def is_secure(cls, url: str) -> bool:
        """Check if URL uses HTTPS"""
        if not url:
            return False
        
        parsed = urlparse(url)
        return parsed.scheme == 'https'
    
    @classmethod
    def extract_domain(cls, url: str) -> Optional[str]:
        """Extract domain from URL"""
        if not url:
            return None
        
        try:
            parsed = urlparse(url)
            # Remove port if present
            domain = parsed.netloc.split(':')[0]
            return domain
        except:
            return None
    
    @classmethod
    def is_internal_url(cls, url: str, allowed_domains: List[str]) -> bool:
        """Check if URL is internal/allowed"""
        if not url or not allowed_domains:
            return False
        
        domain = cls.extract_domain(url)
        
        if not domain:
            return False
        
        # Check if domain matches any allowed domain
        for allowed_domain in allowed_domains:
            if domain == allowed_domain or domain.endswith(f".{allowed_domain}"):
                return True
        
        return False


class FileValidator:
    """File validation utilities"""
    
    # File type configurations
    ALLOWED_IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/gif', 'image/webp', 'image/bmp']
    ALLOWED_DOCUMENT_TYPES = [
        'application/pdf', 
        'application/msword',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'application/vnd.ms-excel',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'text/plain',
        'text/csv'
    ]
    
    MAX_FILE_SIZES = {
        'image': 5 * 1024 * 1024,  # 5MB
        'document': 10 * 1024 * 1024,  # 10MB
        'video': 100 * 1024 * 1024,  # 100MB
    }
    
    # File extension to MIME type mapping
    EXTENSION_MIME_MAP = {
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.gif': 'image/gif',
        '.webp': 'image/webp',
        '.pdf': 'application/pdf',
        '.doc': 'application/msword',
        '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        '.xls': 'application/vnd.ms-excel',
        '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    }
    
    @classmethod
    def validate_file_type(cls, filename: str, allowed_types: List[str]) -> ValidationResult:
        """Validate file type"""
        result = ValidationResult()
        
        if not filename:
            result.add_error("Filename is required")
            return result
        
        # Get file extension
        extension = filename.lower().split('.')[-1] if '.' in filename else ''
        
        # Get MIME type
        mime_type, _ = mimetypes.guess_type(filename)
        
        if not mime_type:
            result.add_error("Unable to determine file type")
            return result
        
        # Check if MIME type is allowed
        if mime_type not in allowed_types:
            result.add_error(f"File type '{mime_type}' is not allowed")
        
        return result
    
    @classmethod
    def validate_file_size(cls, file_size: int, max_size: int) -> ValidationResult:
        """Validate file size"""
        result = ValidationResult()
        
        if file_size <= 0:
            result.add_error("Invalid file size")
            return result
        
        if file_size > max_size:
            max_mb = max_size / (1024 * 1024)
            actual_mb = file_size / (1024 * 1024)
            result.add_error(f"File size ({actual_mb:.2f}MB) exceeds maximum allowed size ({max_mb:.2f}MB)")
        
        return result
    
    @classmethod
    def validate_image(cls, filename: str, file_size: int) -> ValidationResult:
        """Validate image file"""
        result = ValidationResult()
        
        # Validate file type
        type_result = cls.validate_file_type(filename, cls.ALLOWED_IMAGE_TYPES)
        if not type_result.is_valid:
            result.errors.extend(type_result.errors)
            result.is_valid = False
        
        # Validate file size
        size_result = cls.validate_file_size(file_size, cls.MAX_FILE_SIZES['image'])
        if not size_result.is_valid:
            result.errors.extend(size_result.errors)
            result.is_valid = False
        
        return result
    
    @classmethod
    def validate_document(cls, filename: str, file_size: int) -> ValidationResult:
        """Validate document file"""
        result = ValidationResult()
        
        # Validate file type
        type_result = cls.validate_file_type(filename, cls.ALLOWED_DOCUMENT_TYPES)
        if not type_result.is_valid:
            result.errors.extend(type_result.errors)
            result.is_valid = False
        
        # Validate file size
        size_result = cls.validate_file_size(file_size, cls.MAX_FILE_SIZES['document'])
        if not size_result.is_valid:
            result.errors.extend(size_result.errors)
            result.is_valid = False
        
        return result
    
    @classmethod
    def is_safe_filename(cls, filename: str) -> bool:
        """Check if filename is safe"""
        if not filename:
            return False
        
        # Dangerous characters and patterns
        dangerous_chars = ['/', '\\', '..', '<', '>', ':', '"', '|', '?', '*']
        
        for char in dangerous_chars:
            if char in filename:
                return False
        
        # Check for null bytes
        if '\x00' in filename:
            return False
        
        # Reserved Windows names
        reserved_names = [
            'CON', 'PRN', 'AUX', 'NUL',
            'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9',
            'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'
        ]
        
        name_without_ext = filename.split('.')[0].upper()
        if name_without_ext in reserved_names:
            return False
        
        return True
    
    @classmethod
    def detect_file_type(cls, file_content: bytes) -> Optional[str]:
        """Detect file type from content (magic bytes)"""
        if not file_content or len(file_content) < 4:
            return None
        
        # Common file signatures (magic bytes)
        signatures = {
            b'\xFF\xD8\xFF': 'image/jpeg',
            b'\x89PNG\r\n\x1a\n': 'image/png',
            b'GIF87a': 'image/gif',
            b'GIF89a': 'image/gif',
            b'%PDF': 'application/pdf',
            b'PK\x03\x04': 'application/zip',  # Also used by docx, xlsx
        }
        
        for signature, mime_type in signatures.items():
            if file_content.startswith(signature):
                return mime_type
        
        return None


class BusinessRuleValidator:
    """Business rule validation utilities"""
    
    @classmethod
    def validate_age_requirement(cls, birth_date: date, min_age: int, max_age: int = None) -> ValidationResult:
        """Validate age requirements"""
        result = ValidationResult()
        
        if not birth_date:
            result.add_error("Birth date is required")
            return result
        
        # Calculate age
        today = date.today()
        age = today.year - birth_date.year
        
        # Adjust if birthday hasn't occurred yet this year
        if (today.month, today.day) < (birth_date.month, birth_date.day):
            age -= 1
        
        # Check minimum age
        if age < min_age:
            result.add_error(f"Minimum age requirement is {min_age} years")
        
        # Check maximum age if specified
        if max_age and age > max_age:
            result.add_error(f"Maximum age limit is {max_age} years")
        
        # Check if birth date is in the future
        if birth_date > today:
            result.add_error("Birth date cannot be in the future")
        
        return result
    
    @classmethod
    def validate_date_range(cls, start_date: date, end_date: date) -> ValidationResult:
        """Validate date range"""
        result = ValidationResult()
        
        if not start_date:
            result.add_error("Start date is required")
        
        if not end_date:
            result.add_error("End date is required")
        
        if start_date and end_date:
            if end_date < start_date:
                result.add_error("End date must be after start date")
        
        return result
    
    @classmethod
    def validate_booking_dates(cls, check_in: date, check_out: date) -> ValidationResult:
        """Validate booking date rules"""
        result = ValidationResult()
        
        # Validate date range
        range_result = cls.validate_date_range(check_in, check_out)
        if not range_result.is_valid:
            result.errors.extend(range_result.errors)
            result.is_valid = False
            return result
        
        today = date.today()
        
        # Check if check-in is in the past
        if check_in < today:
            result.add_error("Check-in date cannot be in the past")
        
        # Minimum stay duration (e.g., 1 day)
        duration = (check_out - check_in).days
        if duration < 1:
            result.add_error("Minimum stay duration is 1 day")
        
        # Maximum advance booking (e.g., 365 days)
        max_advance_days = 365
        if (check_in - today).days > max_advance_days:
            result.add_error(f"Bookings can only be made up to {max_advance_days} days in advance")
        
        return result
    
    @classmethod
    def validate_payment_amount(cls, amount: Decimal, min_amount: Decimal = None, 
                               max_amount: Decimal = None) -> ValidationResult:
        """Validate payment amount"""
        result = ValidationResult()
        
        if not isinstance(amount, Decimal):
            try:
                amount = Decimal(str(amount))
            except (InvalidOperation, ValueError):
                result.add_error("Invalid payment amount")
                return result
        
        # Check if amount is positive
        if amount <= 0:
            result.add_error("Payment amount must be greater than zero")
        
        # Check minimum amount
        if min_amount and amount < min_amount:
            result.add_error(f"Minimum payment amount is {min_amount}")
        
        # Check maximum amount
        if max_amount and amount > max_amount:
            result.add_error(f"Maximum payment amount is {max_amount}")
        
        # Check decimal places (max 2 for currency)
        if amount.as_tuple().exponent < -2:
            result.add_error("Payment amount cannot have more than 2 decimal places")
        
        return result
    
    @classmethod
    def validate_room_capacity(cls, occupants: int, max_capacity: int) -> ValidationResult:
        """Validate room capacity"""
        result = ValidationResult()
        
        if occupants < 1:
            result.add_error("Number of occupants must be at least 1")
        
        if occupants > max_capacity:
            result.add_error(f"Number of occupants ({occupants}) exceeds room capacity ({max_capacity})")
        
        return result
    
    @classmethod
    def validate_leave_period(cls, start_date: date, end_date: date, 
                             max_days: int = None) -> ValidationResult:
        """Validate leave period"""
        result = ValidationResult()
        
        # Validate date range
        range_result = cls.validate_date_range(start_date, end_date)
        if not range_result.is_valid:
            result.errors.extend(range_result.errors)
            result.is_valid = False
            return result
        
        # Calculate duration
        duration = (end_date - start_date).days + 1
        
        # Check maximum days if specified
        if max_days and duration > max_days:
            result.add_error(f"Leave period ({duration} days) exceeds maximum allowed ({max_days} days)")
        
        # Check if leave is too far in the future (e.g., 90 days)
        today = date.today()
        if (start_date - today).days > 90:
            result.add_error("Leave can only be applied up to 90 days in advance")
        
        return result


class SecurityValidator:
    """Security validation utilities"""
    
    @classmethod
    def validate_password_strength(cls, password: str) -> ValidationResult:
        """Validate password strength"""
        result = ValidationResult()
        
        if not password:
            result.add_error("Password is required")
            return result
        
        # Minimum length
        min_length = 8
        if len(password) < min_length:
            result.add_error(f"Password must be at least {min_length} characters long")
        
        # Maximum length
        max_length = 128
        if len(password) > max_length:
            result.add_error(f"Password must not exceed {max_length} characters")
        
        # Check for uppercase
        if not any(c.isupper() for c in password):
            result.add_error("Password must contain at least one uppercase letter")
        
        # Check for lowercase
        if not any(c.islower() for c in password):
            result.add_error("Password must contain at least one lowercase letter")
        
        # Check for digit
        if not any(c.isdigit() for c in password):
            result.add_error("Password must contain at least one digit")
        
        # Check for special character
        special_chars = "!@#$%^&*()_+-=[]{}|;:,.<>?"
        if not any(c in special_chars for c in password):
            result.add_error("Password must contain at least one special character")
        
        # Check for common passwords
        common_passwords = [
            'password', '12345678', 'qwerty', 'admin', 'letmein',
            'welcome', 'monkey', '123456789', 'password123'
        ]
        
        if password.lower() in common_passwords:
            result.add_error("This password is too common")
        
        return result
    
    @classmethod
    def validate_ip_address(cls, ip: str) -> ValidationResult:
        """Validate IP address"""
        result = ValidationResult()
        
        if not ip:
            result.add_error("IP address is required")
            return result
        
        try:
            # Try to parse as IPv4 or IPv6
            ipaddress.ip_address(ip)
        except ValueError:
            result.add_error("Invalid IP address format")
        
        return result
    
    @classmethod
    def is_safe_redirect_url(cls, url: str, allowed_domains: List[str]) -> bool:
        """Check if redirect URL is safe"""
        if not url:
            return False
        
        # Check if it's a relative URL (safe)
        if url.startswith('/') and not url.startswith('//'):
            return True
        
        # For absolute URLs, check domain
        return URLValidator.is_internal_url(url, allowed_domains)
    
    @classmethod
    def validate_csrf_token(cls, token: str, expected_token: str) -> bool:
        """Validate CSRF token"""
        if not token or not expected_token:
            return False
        
        # Use constant-time comparison to prevent timing attacks
        return hmac.compare_digest(token, expected_token)
    
    @classmethod
    def sanitize_input(cls, input_data: str) -> str:
        """Sanitize user input"""
        if not input_data:
            return ""
        
        # Remove null bytes
        sanitized = input_data.replace('\x00', '')
        
        # Strip leading/trailing whitespace
        sanitized = sanitized.strip()
        
        # Escape HTML entities
        html_escape_table = {
            "&": "&amp;",
            '"': "&quot;",
            "'": "&#x27;",
            ">": "&gt;",
            "<": "&lt;",
        }
        
        sanitized = "".join(html_escape_table.get(c, c) for c in sanitized)
        
        return sanitized
    
    @classmethod
    def detect_sql_injection(cls, input_data: str) -> bool:
        """Detect potential SQL injection"""
        if not input_data:
            return False
        
        # Common SQL injection patterns
        sql_patterns = [
            r"(\bOR\b|\bAND\b)\s+\d+\s*=\s*\d+",  # OR 1=1, AND 1=1
            r";\s*DROP\s+TABLE",  # ; DROP TABLE
            r";\s*DELETE\s+FROM",  # ; DELETE FROM
            r"UNION\s+SELECT",  # UNION SELECT
            r"--",  # SQL comment
            r"/\*.*\*/",  # /* comment */
            r"xp_cmdshell",  # SQL Server command execution
            r"EXEC\s*\(",  # EXEC command
        ]
        
        input_upper = input_data.upper()
        
        for pattern in sql_patterns:
            if re.search(pattern, input_upper, re.IGNORECASE):
                return True
        
        return False


class DataValidator:
    """Generic data validation utilities"""
    
    @classmethod
    def validate_required_fields(cls, data: Dict[str, Any], required_fields: List[str]) -> ValidationResult:
        """Validate required fields"""
        result = ValidationResult()
        
        if not data:
            result.add_error("Data is required")
            return result
        
        missing_fields = []
        
        for field in required_fields:
            if field not in data or data[field] is None or data[field] == '':
                missing_fields.append(field)
        
        if missing_fields:
            result.add_error(f"Missing required fields: {', '.join(missing_fields)}")
        
        return result
    
    @classmethod
    def validate_field_types(cls, data: Dict[str, Any], type_definitions: Dict[str, type]) -> ValidationResult:
        """Validate field types"""
        result = ValidationResult()
        
        if not data:
            result.add_error("Data is required")
            return result
        
        for field, expected_type in type_definitions.items():
            if field in data and data[field] is not None:
                if not isinstance(data[field], expected_type):
                    result.add_error(
                        f"Field '{field}' must be of type {expected_type.__name__}, "
                        f"got {type(data[field]).__name__}"
                    )
        
        return result
    
    @classmethod
    def validate_enum_values(cls, value: Any, allowed_values: List[Any]) -> ValidationResult:
        """Validate enum values"""
        result = ValidationResult()
        
        if value not in allowed_values:
            result.add_error(f"Value must be one of: {', '.join(str(v) for v in allowed_values)}")
        
        return result
    
    @classmethod
    def validate_range(cls, value: Union[int, float], min_val: Union[int, float] = None,
                      max_val: Union[int, float] = None) -> ValidationResult:
        """Validate numeric range"""
        result = ValidationResult()
        
        if not isinstance(value, (int, float)):
            result.add_error("Value must be a number")
            return result
        
        if min_val is not None and value < min_val:
            result.add_error(f"Value must be at least {min_val}")
        
        if max_val is not None and value > max_val:
            result.add_error(f"Value must not exceed {max_val}")
        
        return result
    
    @classmethod
    def validate_length(cls, text: str, min_length: int = None, max_length: int = None) -> ValidationResult:
        """Validate text length"""
        result = ValidationResult()
        
        if not isinstance(text, str):
            result.add_error("Value must be a string")
            return result
        
        text_length = len(text)
        
        if min_length is not None and text_length < min_length:
            result.add_error(f"Text must be at least {min_length} characters long")
        
        if max_length is not None and text_length > max_length:
            result.add_error(f"Text must not exceed {max_length} characters")
        
        return result


class StudentValidator:
    """Student-specific validation utilities"""
    
    @classmethod
    def validate_student_id(cls, student_id: str) -> ValidationResult:
        """Validate student ID format"""
        result = ValidationResult()
        
        if not student_id:
            result.add_error("Student ID is required")
            return result
        
        # Example format: STU-YYYY-NNNN (e.g., STU-2024-0001)
        pattern = r'^STU-\d{4}-\d{4}$'
        
        if not re.match(pattern, student_id):
            result.add_error("Student ID must be in format STU-YYYY-NNNN")
        
        return result
    
    @classmethod
    def validate_enrollment_data(cls, enrollment_data: Dict[str, Any]) -> ValidationResult:
        """Validate student enrollment data"""
        result = ValidationResult()
        
        # Required fields
        required_fields = ['first_name', 'last_name', 'email', 'phone', 'date_of_birth']
        required_result = DataValidator.validate_required_fields(enrollment_data, required_fields)
        
        if not required_result.is_valid:
            result.errors.extend(required_result.errors)
            result.is_valid = False
        
        # Validate email
        if enrollment_data.get('email'):
            email_result = EmailValidator.validate(enrollment_data['email'])
            if not email_result.is_valid:
                result.errors.extend(email_result.errors)
                result.is_valid = False
        
        # Validate phone
        if enrollment_data.get('phone'):
            phone_result = PhoneValidator.validate(enrollment_data['phone'])
            if not phone_result.is_valid:
                result.errors.extend(phone_result.errors)
                result.is_valid = False
        
        # Validate age (minimum 16 years for hostel)
        if enrollment_data.get('date_of_birth'):
            age_result = BusinessRuleValidator.validate_age_requirement(
                enrollment_data['date_of_birth'], 16, 35
            )
            if not age_result.is_valid:
                result.errors.extend(age_result.errors)
                result.is_valid = False
        
        return result
    
    @classmethod
    def validate_guardian_info(cls, guardian_data: Dict[str, Any]) -> ValidationResult:
        """Validate guardian information"""
        result = ValidationResult()
        
        required_fields = ['guardian_name', 'guardian_phone', 'relationship']
        required_result = DataValidator.validate_required_fields(guardian_data, required_fields)
        
        if not required_result.is_valid:
            result.errors.extend(required_result.errors)
            result.is_valid = False
        
        # Validate guardian phone
        if guardian_data.get('guardian_phone'):
            phone_result = PhoneValidator.validate(guardian_data['guardian_phone'])
            if not phone_result.is_valid:
                result.errors.extend(phone_result.errors)
                result.is_valid = False
        
        # Validate relationship
        valid_relationships = ['father', 'mother', 'guardian', 'other']
        if guardian_data.get('relationship'):
            if guardian_data['relationship'].lower() not in valid_relationships:
                result.add_error(f"Relationship must be one of: {', '.join(valid_relationships)}")
        
        return result
    
    @classmethod
    def validate_academic_info(cls, academic_data: Dict[str, Any]) -> ValidationResult:
        """Validate academic information"""
        result = ValidationResult()
        
        required_fields = ['institution_name', 'course', 'year']
        required_result = DataValidator.validate_required_fields(academic_data, required_fields)
        
        if not required_result.is_valid:
            result.errors.extend(required_result.errors)
            result.is_valid = False
        
        # Validate year
        valid_years = ['1st Year', '2nd Year', '3rd Year', '4th Year', 'Graduate', 'Post Graduate']
        if academic_data.get('year'):
            if academic_data['year'] not in valid_years:
                result.add_error(f"Year must be one of: {', '.join(valid_years)}")
        
        return result


class HostelValidator:
    """Hostel-specific validation utilities"""
    
    @classmethod
    def validate_hostel_code(cls, hostel_code: str) -> ValidationResult:
        """Validate hostel code format"""
        result = ValidationResult()
        
        if not hostel_code:
            result.add_error("Hostel code is required")
            return result
        
        # Example format: HST-CITY-NNNN (e.g., HST-MUM-0001)
        pattern = r'^HST-[A-Z]{3}-\d{4}$'
        
        if not re.match(pattern, hostel_code):
            result.add_error("Hostel code must be in format HST-CCC-NNNN (e.g., HST-MUM-0001)")
        
        return result
    
    @classmethod
    def validate_room_number(cls, room_number: str) -> ValidationResult:
        """Validate room number format"""
        result = ValidationResult()
        
        if not room_number:
            result.add_error("Room number is required")
            return result
        
        # Alphanumeric room numbers
        if not re.match(r'^[A-Z0-9]{1,10}$', room_number.upper()):
            result.add_error("Room number must be alphanumeric (max 10 characters)")
        
        return result
    
    @classmethod
    def validate_capacity_config(cls, total_capacity: int, room_configs: List[Dict]) -> ValidationResult:
        """Validate hostel capacity configuration"""
        result = ValidationResult()
        
        if total_capacity <= 0:
            result.add_error("Total capacity must be greater than zero")
        
        # Calculate sum of room capacities
        calculated_capacity = sum(
            config.get('capacity', 0) * config.get('count', 0)
            for config in room_configs
        )
        
        if calculated_capacity != total_capacity:
            result.add_error(
                f"Sum of room capacities ({calculated_capacity}) does not match "
                f"total capacity ({total_capacity})"
            )
        
        return result
    
    @classmethod
    def validate_pricing_structure(cls, pricing_data: Dict[str, Any]) -> ValidationResult:
        """Validate pricing structure"""
        result = ValidationResult()
        
        required_fields = ['monthly_rent', 'security_deposit']
        required_result = DataValidator.validate_required_fields(pricing_data, required_fields)
        
        if not required_result.is_valid:
            result.errors.extend(required_result.errors)
            result.is_valid = False
        
        # Validate amounts
        for field in ['monthly_rent', 'security_deposit', 'mess_fee']:
            if field in pricing_data and pricing_data[field] is not None:
                try:
                    amount = Decimal(str(pricing_data[field]))
                    amount_result = BusinessRuleValidator.validate_payment_amount(
                        amount, Decimal('0'), Decimal('100000')
                    )
                    if not amount_result.is_valid:
                        result.errors.extend(amount_result.errors)
                        result.is_valid = False
                except (InvalidOperation, ValueError):
                    result.add_error(f"Invalid amount for {field}")
        
        return result


class PaymentValidator:
    """Payment-specific validation utilities"""
    
    VALID_PAYMENT_METHODS = ['cash', 'card', 'upi', 'bank_transfer', 'cheque', 'online', 'wallet']
    
    @classmethod
    def validate_payment_method(cls, payment_method: str) -> ValidationResult:
        """Validate payment method"""
        result = ValidationResult()
        
        if not payment_method:
            result.add_error("Payment method is required")
            return result
        
        if payment_method.lower() not in cls.VALID_PAYMENT_METHODS:
            result.add_error(
                f"Invalid payment method. Must be one of: {', '.join(cls.VALID_PAYMENT_METHODS)}"
            )
        
        return result
    
    @classmethod
    def validate_transaction_id(cls, transaction_id: str) -> ValidationResult:
        """Validate transaction ID format"""
        result = ValidationResult()
        
        if not transaction_id:
            result.add_error("Transaction ID is required")
            return result
        
        # Transaction ID should be alphanumeric and between 10-50 characters
        if not re.match(r'^[A-Z0-9]{10,50}$', transaction_id.upper()):
            result.add_error("Transaction ID must be alphanumeric (10-50 characters)")
        
        return result
    
    @classmethod
    def validate_refund_amount(cls, refund_amount: Decimal, original_amount: Decimal) -> ValidationResult:
        """Validate refund amount"""
        result = ValidationResult()
        
        # Validate refund amount is positive
        amount_result = BusinessRuleValidator.validate_payment_amount(
            refund_amount, Decimal('0.01')
        )
        
        if not amount_result.is_valid:
            result.errors.extend(amount_result.errors)
            result.is_valid = False
        
        # Refund cannot exceed original amount
        if refund_amount > original_amount:
            result.add_error(
                f"Refund amount ({refund_amount}) cannot exceed original payment ({original_amount})"
            )
        
        return result
    
    @classmethod
    def validate_bank_details(cls, bank_data: Dict[str, Any]) -> ValidationResult:
        """Validate bank account details"""
        result = ValidationResult()
        
        required_fields = ['account_number', 'ifsc_code', 'account_holder_name', 'bank_name']
        required_result = DataValidator.validate_required_fields(bank_data, required_fields)
        
        if not required_result.is_valid:
            result.errors.extend(required_result.errors)
            result.is_valid = False
        
        # Validate IFSC code (Indian format)
        if bank_data.get('ifsc_code'):
            ifsc = bank_data['ifsc_code'].upper()
            # IFSC format: 4 letters + 0 + 6 alphanumeric
            if not re.match(r'^[A-Z]{4}0[A-Z0-9]{6}$', ifsc):
                result.add_error("Invalid IFSC code format")
        
        # Validate account number
        if bank_data.get('account_number'):
            account = str(bank_data['account_number'])
            # Account number should be 9-18 digits
            if not re.match(r'^\d{9,18}$', account):
                result.add_error("Account number must be 9-18 digits")
        
        return result


class CompositeValidator:
    """Composite validator for complex validation scenarios"""
    
    def __init__(self):
        self.validators: List[Callable] = []
    
    def add_validator(self, validator: Callable):
        """Add validator to chain"""
        self.validators.append(validator)
    
    def validate(self, data: Any) -> ValidationResult:
        """Run all validators"""
        result = ValidationResult()
        
        for validator in self.validators:
            validation_result = validator(data)
            
            if not validation_result.is_valid:
                result.is_valid = False
                result.errors.extend(validation_result.errors)
        
        return result


class CustomValidator:
    """Custom validation rule builder"""
    
    @staticmethod
    def create_regex_validator(pattern: str, error_message: str) -> Callable:
        """Create regex-based validator"""
        def validator(value: str) -> ValidationResult:
            result = ValidationResult()
            
            if not value:
                result.add_error("Value is required")
                return result
            
            if not re.match(pattern, value):
                result.add_error(error_message)
            
            return result
        
        return validator
    
    @staticmethod
    def create_length_validator(min_length: int = None, max_length: int = None) -> Callable:
        """Create length validator"""
        def validator(value: str) -> ValidationResult:
            return DataValidator.validate_length(value, min_length, max_length)
        
        return validator
    
    @staticmethod
    def create_range_validator(min_val: Union[int, float] = None,
                              max_val: Union[int, float] = None) -> Callable:
        """Create range validator"""
        def validator(value: Union[int, float]) -> ValidationResult:
            return DataValidator.validate_range(value, min_val, max_val)
        
        return validator