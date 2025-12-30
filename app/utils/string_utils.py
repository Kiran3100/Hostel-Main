"""
String manipulation and formatting utilities
"""

import re
import unicodedata
import string
import random
import html
import os
import secrets
from typing import Optional, List, Dict, Union
from difflib import SequenceMatcher

class StringHelper:
    """General string manipulation utilities"""
    
    @staticmethod
    def clean_whitespace(text: str) -> str:
        """Remove extra whitespace and normalize"""
        if not text:
            return ""
        
        # Replace multiple spaces with single space
        text = re.sub(r'\s+', ' ', text)
        
        # Remove leading and trailing whitespace
        text = text.strip()
        
        return text
    
    @staticmethod
    def remove_special_chars(text: str, allowed_chars: str = '') -> str:
        """Remove special characters except allowed ones"""
        if not text:
            return ""
        
        # Create pattern for allowed characters
        if allowed_chars:
            # Escape special regex characters
            allowed_chars = re.escape(allowed_chars)
            pattern = f'[^a-zA-Z0-9\\s{allowed_chars}]'
        else:
            pattern = r'[^a-zA-Z0-9\s]'
        
        return re.sub(pattern, '', text)
    
    @staticmethod
    def normalize_unicode(text: str) -> str:
        """Normalize unicode characters"""
        if not text:
            return ""
        
        # Normalize to NFKD form and encode to ASCII
        normalized = unicodedata.normalize('NFKD', text)
        
        # Remove combining characters
        ascii_text = normalized.encode('ASCII', 'ignore').decode('ASCII')
        
        return ascii_text
    
    @staticmethod
    def capitalize_words(text: str) -> str:
        """Capitalize each word properly"""
        if not text:
            return ""
        
        # Use title() but handle special cases
        words = text.split()
        capitalized = []
        
        # Words that should stay lowercase unless at start
        small_words = {'a', 'an', 'and', 'as', 'at', 'but', 'by', 'for', 
                      'in', 'of', 'on', 'or', 'the', 'to', 'with'}
        
        for i, word in enumerate(words):
            if i == 0 or word.lower() not in small_words:
                capitalized.append(word.capitalize())
            else:
                capitalized.append(word.lower())
        
        return ' '.join(capitalized)
    
    @staticmethod
    def camel_case(text: str) -> str:
        """Convert string to camelCase"""
        if not text:
            return ""
        
        # Remove special characters and split
        text = StringHelper.remove_special_chars(text)
        words = text.split()
        
        if not words:
            return ""
        
        # First word lowercase, rest capitalized
        result = words[0].lower()
        for word in words[1:]:
            result += word.capitalize()
        
        return result
    
    @staticmethod
    def snake_case(text: str) -> str:
        """Convert string to snake_case"""
        if not text:
            return ""
        
        # Replace spaces with underscores
        text = re.sub(r'\s+', '_', text)
        
        # Insert underscore before uppercase letters
        text = re.sub(r'([A-Z])', r'_\1', text)
        
        # Convert to lowercase and clean up
        text = text.lower()
        text = re.sub(r'_+', '_', text)
        text = text.strip('_')
        
        # Remove special characters except underscores
        text = re.sub(r'[^a-z0-9_]', '', text)
        
        return text
    
    @staticmethod
    def kebab_case(text: str) -> str:
        """Convert string to kebab-case"""
        if not text:
            return ""
        
        # Replace spaces with hyphens
        text = re.sub(r'\s+', '-', text)
        
        # Insert hyphen before uppercase letters
        text = re.sub(r'([A-Z])', r'-\1', text)
        
        # Convert to lowercase and clean up
        text = text.lower()
        text = re.sub(r'-+', '-', text)
        text = text.strip('-')
        
        # Remove special characters except hyphens
        text = re.sub(r'[^a-z0-9-]', '', text)
        
        return text
    
    @staticmethod
    def pascal_case(text: str) -> str:
        """Convert string to PascalCase"""
        if not text:
            return ""
        
        # Remove special characters and split
        text = StringHelper.remove_special_chars(text)
        words = text.split()
        
        # Capitalize all words
        return ''.join(word.capitalize() for word in words)
    
    @staticmethod
    def truncate(text: str, max_length: int, suffix: str = '...') -> str:
        """Truncate string with suffix"""
        if not text or len(text) <= max_length:
            return text
        
        # Ensure suffix fits
        if len(suffix) >= max_length:
            return text[:max_length]
        
        # Truncate and add suffix
        truncated_length = max_length - len(suffix)
        return text[:truncated_length] + suffix
    
    @staticmethod
    def extract_numbers(text: str) -> List[str]:
        """Extract all numbers from text"""
        if not text:
            return []
        
        # Find all number patterns (including decimals)
        numbers = re.findall(r'-?\d+\.?\d*', text)
        
        return numbers
    
    @staticmethod
    def mask_string(text: str, mask_char: str = '*', 
                   visible_start: int = 2, visible_end: int = 2) -> str:
        """Mask string for privacy"""
        if not text:
            return ""
        
        text_length = len(text)
        
        # If string is too short, mask everything except first char
        if text_length <= visible_start + visible_end:
            if text_length <= 1:
                return mask_char * text_length
            return text[0] + mask_char * (text_length - 1)
        
        # Mask the middle part
        start_part = text[:visible_start]
        end_part = text[-visible_end:] if visible_end > 0 else ""
        masked_length = text_length - visible_start - visible_end
        
        return start_part + mask_char * masked_length + end_part
    
    @staticmethod
    def random_string(length: int, charset: str = None) -> str:
        """Generate random string"""
        if length <= 0:
            return ""
        
        if charset is None:
            charset = string.ascii_letters + string.digits
        
        return ''.join(secrets.choice(charset) for _ in range(length))
    
    @staticmethod
    def is_valid_identifier(text: str) -> bool:
        """Check if string is valid Python identifier"""
        if not text:
            return False
        
        return text.isidentifier()


class SlugGenerator:
    """URL-safe slug generation utilities"""
    
    @staticmethod
    def generate_slug(text: str, max_length: int = 50) -> str:
        """Generate URL-safe slug from text"""
        if not text:
            return ""
        
        # Convert to lowercase
        slug = text.lower()
        
        # Normalize unicode characters
        slug = StringHelper.normalize_unicode(slug)
        
        # Replace spaces and underscores with hyphens
        slug = re.sub(r'[\s_]+', '-', slug)
        
        # Remove special characters except hyphens
        slug = re.sub(r'[^a-z0-9-]', '', slug)
        
        # Remove multiple consecutive hyphens
        slug = re.sub(r'-+', '-', slug)
        
        # Remove leading and trailing hyphens
        slug = slug.strip('-')
        
        # Truncate if necessary
        if len(slug) > max_length:
            slug = slug[:max_length].rstrip('-')
        
        return slug or 'untitled'
    
    @staticmethod
    def generate_unique_slug(text: str, existing_slugs: List[str] = None, max_length: int = 50) -> str:
        """Generate unique slug avoiding duplicates"""
        if existing_slugs is None:
            existing_slugs = []
        
        base_slug = SlugGenerator.generate_slug(text, max_length - 10)  # Reserve space for suffix
        
        if base_slug not in existing_slugs:
            return base_slug
        
        # Add numeric suffix to make it unique
        counter = 1
        while True:
            suffix = f"-{counter}"
            unique_slug = base_slug + suffix
            
            if len(unique_slug) <= max_length and unique_slug not in existing_slugs:
                return unique_slug
            
            counter += 1
            
            # Prevent infinite loop
            if counter > 9999:
                # Use random suffix instead
                random_suffix = f"-{secrets.randbelow(10000)}"
                return base_slug + random_suffix
    
    @staticmethod
    def generate_seo_slug(title: str, max_length: int = 60) -> str:
        """Generate SEO-friendly slug"""
        if not title:
            return ""
        
        # Remove common stop words for SEO
        stop_words = {
            'a', 'an', 'and', 'are', 'as', 'at', 'be', 'by', 'for', 'from',
            'has', 'he', 'in', 'is', 'it', 'its', 'of', 'on', 'that', 'the',
            'to', 'was', 'will', 'with'
        }
        
        # Split title into words
        words = title.lower().split()
        
        # Filter out stop words (but keep at least first word)
        filtered_words = []
        for i, word in enumerate(words):
            if i == 0 or word not in stop_words:
                filtered_words.append(word)
        
        # Rejoin and generate slug
        filtered_title = ' '.join(filtered_words)
        return SlugGenerator.generate_slug(filtered_title, max_length)
    
    @staticmethod
    def validate_slug(slug: str) -> bool:
        """Validate if string is a proper slug"""
        if not slug:
            return False
        
        # Check if it matches slug pattern
        pattern = r'^[a-z0-9]+(?:-[a-z0-9]+)*$'
        
        return bool(re.match(pattern, slug))
    
    @staticmethod
    def humanize_slug(slug: str) -> str:
        """Convert slug back to human readable text"""
        if not slug:
            return ""
        
        # Replace hyphens with spaces
        text = slug.replace('-', ' ')
        
        # Capitalize words
        return StringHelper.capitalize_words(text)


class TextCleaner:
    """Text cleaning and sanitization utilities"""
    
    @staticmethod
    def remove_html_tags(html_text: str) -> str:
        """Remove HTML tags from text"""
        if not html_text:
            return ""
        
        # Remove HTML tags
        clean_text = re.sub(r'<[^>]+>', '', html_text)
        
        # Decode HTML entities
        clean_text = html.unescape(clean_text)
        
        # Clean whitespace
        clean_text = StringHelper.clean_whitespace(clean_text)
        
        return clean_text
    
    @staticmethod
    def sanitize_html(html_text: str, allowed_tags: List[str] = None) -> str:
        """Sanitize HTML keeping only allowed tags"""
        if not html_text:
            return ""
        
        if allowed_tags is None:
            allowed_tags = ['p', 'br', 'strong', 'em', 'u', 'a', 'ul', 'ol', 'li']
        
        # Create pattern for allowed tags
        allowed_pattern = '|'.join(allowed_tags)
        
        # Remove all tags except allowed ones
        def replace_tag(match):
            tag = match.group(1).split()[0].lower()  # Get tag name
            if tag in allowed_tags or f'/{tag}' == match.group(1):
                return match.group(0)  # Keep allowed tags
            return ''  # Remove disallowed tags
        
        sanitized = re.sub(r'<(/?\w+)[^>]*>', replace_tag, html_text)
        
        # Remove script and style content
        sanitized = re.sub(r'<script[^>]*>.*?</script>', '', sanitized, flags=re.DOTALL | re.IGNORECASE)
        sanitized = re.sub(r'<style[^>]*>.*?</style>', '', sanitized, flags=re.DOTALL | re.IGNORECASE)
        
        return sanitized
    
    @staticmethod
    def clean_filename(filename: str) -> str:
        """Clean filename for safe storage"""
        if not filename:
            return ""
        
        # Remove path separators
        filename = filename.replace('/', '_').replace('\\', '_')
        
        # Remove dangerous characters
        filename = re.sub(r'[<>:"|?*]', '', filename)
        
        # Replace spaces and multiple underscores
        filename = re.sub(r'\s+', '_', filename)
        filename = re.sub(r'_+', '_', filename)
        
        # Remove leading/trailing dots and underscores
        filename = filename.strip('._')
        
        # Limit length (keep extension)
        max_length = 255
        if len(filename) > max_length:
            name, ext = os.path.splitext(filename)
            name = name[:max_length - len(ext)]
            filename = name + ext
        
        return filename or 'file'
    
    @staticmethod
    def remove_profanity(text: str, replacement: str = '***') -> str:
        """Remove or replace profane words"""
        if not text:
            return ""
        
        # Common profane words list (abbreviated for example)
        profane_words = [
            'damn', 'hell', 'crap', 'shit', 'fuck', 'ass', 'bitch',
            # Add more as needed
        ]
        
        # Create case-insensitive pattern
        pattern = r'\b(' + '|'.join(re.escape(word) for word in profane_words) + r')\b'
        
        # Replace profane words
        cleaned = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
        
        return cleaned
    
    @staticmethod
    def normalize_text(text: str) -> str:
        """Comprehensive text normalization"""
        if not text:
            return ""
        
        # Remove extra whitespace
        text = StringHelper.clean_whitespace(text)
        
        # Normalize unicode
        text = StringHelper.normalize_unicode(text)
        
        # Convert to lowercase
        text = text.lower()
        
        # Remove punctuation from start and end
        text = text.strip(string.punctuation)
        
        return text
    
    @staticmethod
    def extract_emails(text: str) -> List[str]:
        """Extract email addresses from text"""
        if not text:
            return []
        
        # Email pattern
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        
        emails = re.findall(email_pattern, text)
        
        return list(set(emails))  # Remove duplicates
    
    @staticmethod
    def extract_urls(text: str) -> List[str]:
        """Extract URLs from text"""
        if not text:
            return []
        
        # URL pattern
        url_pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
        
        urls = re.findall(url_pattern, text)
        
        return list(set(urls))  # Remove duplicates
    
    @staticmethod
    def extract_phone_numbers(text: str) -> List[str]:
        """Extract phone numbers from text"""
        if not text:
            return []
        
        # Various phone number patterns
        patterns = [
            r'\+\d{1,3}[-.\s]?\d{3,4}[-.\s]?\d{3,4}[-.\s]?\d{3,4}',  # International
            r'\d{3}[-.\s]?\d{3}[-.\s]?\d{4}',  # US/Standard
            r'\(\d{3}\)\s*\d{3}[-.\s]?\d{4}',  # (XXX) XXX-XXXX
            r'\d{10}',  # 10 digits
        ]
        
        phone_numbers = []
        for pattern in patterns:
            phone_numbers.extend(re.findall(pattern, text))
        
        return list(set(phone_numbers))  # Remove duplicates


class NameFormatter:
    """Name formatting and validation utilities"""
    
    @staticmethod
    def format_full_name(first_name: str, 
                        last_name: str, 
                        middle_name: str = None,
                        title: str = None) -> str:
        """Format complete name"""
        parts = []
        
        if title:
            parts.append(title)
        
        if first_name:
            parts.append(first_name.strip().capitalize())
        
        if middle_name:
            parts.append(middle_name.strip().capitalize())
        
        if last_name:
            parts.append(last_name.strip().capitalize())
        
        return ' '.join(parts)
    
    @staticmethod
    def parse_full_name(full_name: str) -> Dict[str, str]:
        """Parse full name into components"""
        if not full_name:
            return {
                'title': None,
                'first_name': None,
                'middle_name': None,
                'last_name': None
            }
        
        # Common titles
        titles = ['mr', 'mrs', 'ms', 'miss', 'dr', 'prof', 'sir', 'madam']
        
        parts = full_name.strip().split()
        
        result = {
            'title': None,
            'first_name': None,
            'middle_name': None,
            'last_name': None
        }
        
        if not parts:
            return result
        
        # Check for title
        if parts[0].lower().rstrip('.') in titles:
            result['title'] = parts[0]
            parts = parts[1:]
        
        if len(parts) == 1:
            result['first_name'] = parts[0]
        elif len(parts) == 2:
            result['first_name'] = parts[0]
            result['last_name'] = parts[1]
        elif len(parts) >= 3:
            result['first_name'] = parts[0]
            result['middle_name'] = ' '.join(parts[1:-1])
            result['last_name'] = parts[-1]
        
        return result
    
    @staticmethod
    def get_initials(full_name: str) -> str:
        """Get initials from full name"""
        if not full_name:
            return ""
        
        words = full_name.strip().split()
        
        # Get first letter of each word
        initials = ''.join(word[0].upper() for word in words if word)
        
        return initials
    
    @staticmethod
    def format_display_name(full_name: str, max_length: int = 20) -> str:
        """Format name for display purposes"""
        if not full_name:
            return ""
        
        if len(full_name) <= max_length:
            return full_name
        
        # Try first name + last initial
        parts = full_name.split()
        if len(parts) >= 2:
            display = f"{parts[0]} {parts[-1][0]}."
            if len(display) <= max_length:
                return display
        
        # Truncate with ellipsis
        return StringHelper.truncate(full_name, max_length)
    
    @staticmethod
    def validate_name(name: str) -> bool:
        """Validate name format"""
        if not name:
            return False
        
        # Name should contain only letters, spaces, hyphens, and apostrophes
        pattern = r"^[a-zA-Z\s\-'\.]+$"
        
        if not re.match(pattern, name):
            return False
        
        # Should not be all numbers or special characters
        if not any(c.isalpha() for c in name):
            return False
        
        return True
    
    @staticmethod
    def normalize_name_case(name: str) -> str:
        """Normalize name capitalization"""
        if not name:
            return ""
        
        # Split on spaces and hyphens
        words = re.split(r'([\s\-])', name)
        
        normalized = []
        for word in words:
            if word in [' ', '-']:
                normalized.append(word)
            elif word:
                # Capitalize first letter, lowercase rest
                # Handle special cases like McDonald, O'Brien
                if word.startswith("Mc") and len(word) > 2:
                    normalized.append("Mc" + word[2:].capitalize())
                elif word.startswith("Mac") and len(word) > 3:
                    normalized.append("Mac" + word[3:].capitalize())
                elif word.startswith("O'") and len(word) > 2:
                    normalized.append("O'" + word[2:].capitalize())
                else:
                    normalized.append(word.capitalize())
        
        return ''.join(normalized)


class PhoneNumberFormatter:
    """Phone number formatting utilities"""
    
    @staticmethod
    def format_phone_number(phone: str, country_code: str = 'IN') -> str:
        """Format phone number according to country standards"""
        if not phone:
            return ""
        
        # Remove all non-digit characters
        digits = re.sub(r'\D', '', phone)
        
        if country_code == 'IN':
            # Indian format: +91 XXXXX XXXXX
            if len(digits) == 10:
                return f"+91 {digits[:5]} {digits[5:]}"
            elif len(digits) == 12 and digits.startswith('91'):
                return f"+91 {digits[2:7]} {digits[7:]}"
        elif country_code == 'US':
            # US format: +1 (XXX) XXX-XXXX
            if len(digits) == 10:
                return f"+1 ({digits[:3]}) {digits[3:6]}-{digits[6:]}"
            elif len(digits) == 11 and digits.startswith('1'):
                return f"+1 ({digits[1:4]}) {digits[4:7]}-{digits[7:]}"
        
        # Default: return with + if long enough
        if len(digits) > 10:
            return f"+{digits}"
        
        return digits
    
    @staticmethod
    def extract_country_code(phone: str) -> Optional[str]:
        """Extract country code from phone number"""
        if not phone:
            return None
        
        # Look for country code pattern
        match = re.match(r'^\+?(\d{1,3})', phone)
        
        if match:
            code = match.group(1)
            # Common country codes
            if code in ['1', '91', '44', '61', '86', '81']:
                return code
        
        return None
    
    @staticmethod
    def normalize_phone_number(phone: str) -> str:
        """Normalize phone number to standard format"""
        if not phone:
            return ""
        
        # Remove all non-digit characters except +
        normalized = re.sub(r'[^\d+]', '', phone)
        
        # Ensure it starts with +
        if not normalized.startswith('+'):
            # Assume Indian number if 10 digits
            digits = re.sub(r'\D', '', normalized)
            if len(digits) == 10:
                normalized = f"+91{digits}"
            else:
                normalized = f"+{digits}"
        
        return normalized
    
    @staticmethod
    def mask_phone_number(phone: str) -> str:
        """Mask phone number for privacy"""
        if not phone:
            return ""
        
        digits = re.sub(r'\D', '', phone)
        
        if len(digits) <= 4:
            return '*' * len(digits)
        
        # Show last 4 digits
        return '*' * (len(digits) - 4) + digits[-4:]
    
    @staticmethod
    def validate_phone_format(phone: str, country_code: str = 'IN') -> bool:
        """Validate phone number format"""
        if not phone:
            return False
        
        digits = re.sub(r'\D', '', phone)
        
        if country_code == 'IN':
            # Indian mobile: 10 digits starting with 6-9
            if len(digits) == 10 and digits[0] in '6789':
                return True
            # With country code
            if len(digits) == 12 and digits.startswith('91') and digits[2] in '6789':
                return True
        elif country_code == 'US':
            # US: 10 digits
            if len(digits) == 10:
                return True
            # With country code
            if len(digits) == 11 and digits.startswith('1'):
                return True
        
        return False
    
    @staticmethod
    def get_phone_type(phone: str) -> str:
        """Determine phone type (mobile, landline, etc.)"""
        if not phone:
            return "unknown"
        
        digits = re.sub(r'\D', '', phone)
        
        # For Indian numbers
        if len(digits) == 10:
            if digits[0] in '6789':
                return "mobile"
            else:
                return "landline"
        
        # For numbers with country code
        if len(digits) > 10:
            if digits.startswith('91'):
                if len(digits) == 12 and digits[2] in '6789':
                    return "mobile"
                return "landline"
        
        return "unknown"


class AddressFormatter:
    """Address formatting utilities"""
    
    @staticmethod
    def format_address(street: str,
                      city: str, 
                      state: str,
                      postal_code: str,
                      country: str = 'India') -> str:
        """Format complete address"""
        parts = []
        
        if street:
            parts.append(street.strip())
        
        if city:
            parts.append(city.strip())
        
        if state:
            parts.append(state.strip())
        
        if postal_code:
            parts.append(postal_code.strip())
        
        if country:
            parts.append(country.strip())
        
        return ', '.join(parts)
    
    @staticmethod
    def parse_address(address: str) -> Dict[str, str]:
        """Parse address into components"""
        if not address:
            return {
                'street': None,
                'city': None,
                'state': None,
                'postal_code': None,
                'country': None
            }
        
        # This is a simplified parser
        parts = [p.strip() for p in address.split(',')]
        
        result = {
            'street': None,
            'city': None,
            'state': None,
            'postal_code': None,
            'country': None
        }
        
        # Extract postal code (if matches pattern)
        postal_pattern = r'\b\d{5,6}\b'
        for part in parts:
            match = re.search(postal_pattern, part)
            if match:
                result['postal_code'] = match.group()
                break
        
        # Last part is usually country
        if len(parts) > 0:
            result['country'] = parts[-1]
        
        # Second to last is usually state
        if len(parts) > 1:
            result['state'] = parts[-2]
        
        # Third to last is usually city
        if len(parts) > 2:
            result['city'] = parts[-3]
        
        # Everything else is street
        if len(parts) > 3:
            result['street'] = ', '.join(parts[:-3])
        
        return result
    
    @staticmethod
    def normalize_address(address: str) -> str:
        """Normalize address format"""
        if not address:
            return ""
        
        # Clean whitespace
        address = StringHelper.clean_whitespace(address)
        
        # Standardize abbreviations
        replacements = {
            r'\bSt\b': 'Street',
            r'\bRd\b': 'Road',
            r'\bAve\b': 'Avenue',
            r'\bBlvd\b': 'Boulevard',
            r'\bDr\b': 'Drive',
            r'\bLn\b': 'Lane',
            r'\bApt\b': 'Apartment',
        }
        
        for pattern, replacement in replacements.items():
            address = re.sub(pattern, replacement, address, flags=re.IGNORECASE)
        
        return address
    
    @staticmethod
    def extract_postal_code(address: str) -> Optional[str]:
        """Extract postal code from address"""
        if not address:
            return None
        
        # Indian PIN code: 6 digits
        match = re.search(r'\b\d{6}\b', address)
        if match:
            return match.group()
        
        # US ZIP code: 5 digits or 5+4
        match = re.search(r'\b\d{5}(?:-\d{4})?\b', address)
        if match:
            return match.group()
        
        return None
    
    @staticmethod
    def validate_postal_code(postal_code: str, country: str = 'IN') -> bool:
        """Validate postal code format"""
        if not postal_code:
            return False
        
        if country == 'IN':
            # Indian PIN: 6 digits
            return bool(re.match(r'^\d{6}$', postal_code))
        elif country == 'US':
            # US ZIP: 5 digits or 5+4
            return bool(re.match(r'^\d{5}(?:-\d{4})?$', postal_code))
        elif country == 'UK':
            # UK postcode
            pattern = r'^[A-Z]{1,2}\d{1,2}[A-Z]?\s?\d[A-Z]{2}$'
            return bool(re.match(pattern, postal_code.upper()))
        
        return False


class PasswordGenerator:
    """Password generation utilities"""
    
    @staticmethod
    def generate_password(length: int = 12,
                         include_uppercase: bool = True,
                         include_lowercase: bool = True,
                         include_digits: bool = True,
                         include_symbols: bool = True,
                         exclude_ambiguous: bool = True) -> str:
        """Generate secure password"""
        if length < 4:
            length = 4
        
        # Build character set
        charset = ""
        required_chars = []
        
        # Ambiguous characters to exclude
        ambiguous = 'il1Lo0O'
        
        if include_uppercase:
            uppercase = string.ascii_uppercase
            if exclude_ambiguous:
                uppercase = ''.join(c for c in uppercase if c not in ambiguous)
            charset += uppercase
            required_chars.append(secrets.choice(uppercase))
        
        if include_lowercase:
            lowercase = string.ascii_lowercase
            if exclude_ambiguous:
                lowercase = ''.join(c for c in lowercase if c not in ambiguous)
            charset += lowercase
            required_chars.append(secrets.choice(lowercase))
        
        if include_digits:
            digits = string.digits
            if exclude_ambiguous:
                digits = ''.join(c for c in digits if c not in ambiguous)
            charset += digits
            required_chars.append(secrets.choice(digits))
        
        if include_symbols:
            symbols = '!@#$%^&*()_+-=[]{}|;:,.<>?'
            charset += symbols
            required_chars.append(secrets.choice(symbols))
        
        if not charset:
            charset = string.ascii_letters + string.digits
        
        # Generate random characters for remaining length
        remaining_length = length - len(required_chars)
        password_chars = required_chars + [secrets.choice(charset) for _ in range(remaining_length)]
        
        # Shuffle to avoid predictable pattern
        random.shuffle(password_chars)
        
        return ''.join(password_chars)
    
    @staticmethod
    def generate_pronounceable_password(length: int = 12) -> str:
        """Generate pronounceable password"""
        # Consonants and vowels for pronounceable passwords
        consonants = 'bcdfghjklmnprstvwxyz'
        vowels = 'aeiou'
        
        password = []
        
        for i in range(length):
            if i % 2 == 0:
                # Consonant
                password.append(secrets.choice(consonants))
            else:
                # Vowel
                password.append(secrets.choice(vowels))
        
        # Capitalize some letters and add digits
        result = ''.join(password)
        result = result.capitalize()
        
        # Add a digit at the end
        result += str(secrets.randbelow(100))
        
        return result
    
    @staticmethod
    def generate_passphrase(word_count: int = 4, separator: str = '-') -> str:
        """Generate passphrase using common words"""
        # Common word list (abbreviated)
        words = [
            'apple', 'banana', 'cherry', 'dragon', 'eagle', 'forest',
            'garden', 'house', 'island', 'jungle', 'kingdom', 'lemon',
            'mountain', 'night', 'ocean', 'palace', 'queen', 'river',
            'sunset', 'tiger', 'umbrella', 'valley', 'winter', 'yellow'
        ]
        
        # Select random words
        selected_words = [secrets.choice(words) for _ in range(word_count)]
        
        # Capitalize some words randomly
        selected_words = [w.capitalize() if secrets.randbelow(2) else w for w in selected_words]
        
        # Add a random number
        passphrase = separator.join(selected_words)
        passphrase += separator + str(secrets.randbelow(1000))
        
        return passphrase
    
    @staticmethod
    def check_password_strength(password: str) -> Dict[str, Union[int, bool, str]]:
        """Analyze password strength"""
        result = {
            'score': 0,
            'length': len(password),
            'has_uppercase': False,
            'has_lowercase': False,
            'has_digits': False,
            'has_symbols': False,
            'strength': 'very_weak',
            'feedback': []
        }
        
        if not password:
            result['feedback'].append('Password is empty')
            return result
        
        # Check character types
        if any(c.isupper() for c in password):
            result['has_uppercase'] = True
            result['score'] += 1
        else:
            result['feedback'].append('Add uppercase letters')
        
        if any(c.islower() for c in password):
            result['has_lowercase'] = True
            result['score'] += 1
        else:
            result['feedback'].append('Add lowercase letters')
        
        if any(c.isdigit() for c in password):
            result['has_digits'] = True
            result['score'] += 1
        else:
            result['feedback'].append('Add digits')
        
        if any(c in string.punctuation for c in password):
            result['has_symbols'] = True
            result['score'] += 1
        else:
            result['feedback'].append('Add special characters')
        
        # Length scoring
        length = len(password)
        if length >= 12:
            result['score'] += 2
        elif length >= 8:
            result['score'] += 1
        else:
            result['feedback'].append('Use at least 8 characters (12+ recommended)')
        
        # Determine strength
        if result['score'] <= 2:
            result['strength'] = 'very_weak'
        elif result['score'] <= 3:
            result['strength'] = 'weak'
        elif result['score'] <= 4:
            result['strength'] = 'medium'
        elif result['score'] <= 5:
            result['strength'] = 'strong'
        else:
            result['strength'] = 'very_strong'
        
        # Check for common patterns
        common_passwords = ['password', '123456', 'qwerty', 'admin', 'letmein']
        if password.lower() in common_passwords:
            result['score'] = 0
            result['strength'] = 'very_weak'
            result['feedback'].append('This is a commonly used password')
        
        return result


class SearchHelper:
    """Search and matching utilities"""
    
    @staticmethod
    def fuzzy_match(query: str, target: str, threshold: float = 0.6) -> bool:
        """Fuzzy string matching"""
        if not query or not target:
            return False
        
        score = SearchHelper.similarity_score(query.lower(), target.lower())
        
        return score >= threshold
    
    @staticmethod
    def similarity_score(str1: str, str2: str) -> float:
        """Calculate similarity between strings"""
        if not str1 or not str2:
            return 0.0
        
        # Use SequenceMatcher for similarity
        matcher = SequenceMatcher(None, str1.lower(), str2.lower())
        
        return matcher.ratio()
    
    @staticmethod
    def create_search_tokens(text: str) -> List[str]:
        """Create search tokens from text"""
        if not text:
            return []
        
        # Normalize text
        normalized = TextCleaner.normalize_text(text)
        
        # Split into words
        words = normalized.split()
        
        # Create n-grams for partial matching
        tokens = set(words)
        
        # Add character n-grams for fuzzy matching
        for word in words:
            if len(word) >= 3:
                # Add trigrams
                for i in range(len(word) - 2):
                    tokens.add(word[i:i+3])
        
        return list(tokens)
    
    @staticmethod
    def highlight_matches(text: str, query: str, 
                         highlight_start: str = '<mark>',
                         highlight_end: str = '</mark>') -> str:
        """Highlight search matches in text"""
        if not text or not query:
            return text
        
        # Escape special regex characters in query
        escaped_query = re.escape(query)
        
        # Create pattern for case-insensitive matching
        pattern = re.compile(f'({escaped_query})', re.IGNORECASE)
        
        # Replace matches with highlighted version
        highlighted = pattern.sub(f'{highlight_start}\\1{highlight_end}', text)
        
        return highlighted
    
    @staticmethod
    def soundex(text: str) -> str:
        """Generate Soundex code for phonetic matching"""
        if not text:
            return ""
        
        # Convert to uppercase and keep only letters
        text = ''.join(c for c in text.upper() if c.isalpha())
        
        if not text:
            return ""
        
        # Soundex mapping
        soundex_map = {
            'BFPV': '1',
            'CGJKQSXZ': '2',
            'DT': '3',
            'L': '4',
            'MN': '5',
            'R': '6'
        }
        
        # Keep first letter
        result = text[0]
        
        # Map remaining letters
        for char in text[1:]:
            for key, value in soundex_map.items():
                if char in key:
                    # Don't add consecutive duplicates
                    if not result or result[-1] != value:
                        result += value
                    break
        
        # Pad or truncate to 4 characters
        result = (result + '000')[:4]
        
        return result


class ValidationHelper:
    """String validation utilities"""
    
    @staticmethod
    def is_email(email: str) -> bool:
        """Validate email format"""
        if not email:
            return False
        
        # Email pattern
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        
        return bool(re.match(pattern, email))
    
    @staticmethod
    def is_url(url: str) -> bool:
        """Validate URL format"""
        if not url:
            return False
        
        # URL pattern
        pattern = r'^https?://(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b(?:[-a-zA-Z0-9()@:%_\+.~#?&/=]*)$'
        
        return bool(re.match(pattern, url))
    
    @staticmethod
    def is_alpha_numeric(text: str) -> bool:
        """Check if string contains only alphanumeric characters"""
        if not text:
            return False
        
        return text.isalnum()
    
    @staticmethod
    def contains_only(text: str, allowed_chars: str) -> bool:
        """Check if string contains only allowed characters"""
        if not text:
            return False
        
        return all(c in allowed_chars for c in text)
    
    @staticmethod
    def is_strong_password(password: str) -> bool:
        """Check if password meets strength requirements"""
        if not password or len(password) < 8:
            return False
        
        # Check for required character types
        has_upper = any(c.isupper() for c in password)
        has_lower = any(c.islower() for c in password)
        has_digit = any(c.isdigit() for c in password)
        has_special = any(c in string.punctuation for c in password)
        
        # Must have at least 3 of 4 character types
        score = sum([has_upper, has_lower, has_digit, has_special])
        
        return score >= 3
    
    @staticmethod
    def is_safe_html(html: str) -> bool:
        """Check if HTML is safe (no dangerous tags/scripts)"""
        if not html:
            return True
        
        # Dangerous tags and patterns
        dangerous_patterns = [
            r'<script[^>]*>.*?</script>',
            r'<iframe[^>]*>.*?</iframe>',
            r'javascript:',
            r'on\w+\s*=',  # Event handlers like onclick, onload
            r'<object[^>]*>',
            r'<embed[^>]*>',
        ]
        
        for pattern in dangerous_patterns:
            if re.search(pattern, html, re.IGNORECASE | re.DOTALL):
                return False
        
        return True