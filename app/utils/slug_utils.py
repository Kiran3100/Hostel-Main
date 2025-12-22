"""
Slug generation utilities for hostel management system
"""

import re
import unicodedata
from typing import List, Optional, Set, Callable
import string
import random
from datetime import datetime

class SlugHelper:
    """Main slug generation utilities"""
    
    # Common stop words to remove from slugs
    STOP_WORDS = {
        'a', 'an', 'and', 'are', 'as', 'at', 'be', 'by', 'for', 'from', 'has',
        'he', 'in', 'is', 'it', 'its', 'of', 'on', 'that', 'the', 'to', 'was',
        'were', 'will', 'with', 'the', 'this', 'but', 'they', 'have', 'had',
        'what', 'said', 'each', 'which', 'their', 'time', 'if', 'up', 'out',
        'many', 'then', 'them', 'these', 'so', 'some', 'her', 'would', 'make',
        'like', 'into', 'him', 'two', 'more', 'very', 'after', 'first'
    }
    
    @staticmethod
    def create_slug(text: str, max_length: int = 50, 
                   remove_stop_words: bool = True,
                   preserve_case: bool = False) -> str:
        """Create a URL-safe slug from text"""
        if not text:
            return ''
        
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', text)
        
        # Normalize Unicode characters
        text = unicodedata.normalize('NFKD', text)
        
        # Convert to ASCII
        text = text.encode('ascii', 'ignore').decode('ascii')
        
        # Convert to lowercase unless preserving case
        if not preserve_case:
            text = text.lower()
        
        # Replace spaces and special characters with hyphens
        text = re.sub(r'[^\w\s-]', '', text)
        text = re.sub(r'[\s_-]+', '-', text)
        
        # Remove stop words if requested
        if remove_stop_words:
            words = text.split('-')
            filtered_words = []
            
            for word in words:
                if word and word.lower() not in SlugHelper.STOP_WORDS:
                    filtered_words.append(word)
            
            text = '-'.join(filtered_words)
        
        # Remove leading/trailing hyphens
        text = text.strip('-')
        
        # Truncate to max length
        if len(text) > max_length:
            # Try to cut at word boundary
            truncated = text[:max_length]
            last_hyphen = truncated.rfind('-')
            
            if last_hyphen > max_length * 0.7:  # If we can save a reasonable amount
                text = truncated[:last_hyphen]
            else:
                text = truncated
        
        return text or 'item'  # Fallback if slug becomes empty
    
    @staticmethod
    def create_slug_from_fields(fields: List[str], separator: str = '-',
                               max_length: int = 50) -> str:
        """Create slug from multiple fields"""
        # Filter out empty fields
        valid_fields = [field.strip() for field in fields if field and field.strip()]
        
        if not valid_fields:
            return ''
        
        # Create individual slugs
        field_slugs = []
        for field in valid_fields:
            slug = SlugHelper.create_slug(field, max_length=20, remove_stop_words=True)
            if slug:
                field_slugs.append(slug)
        
        # Join with separator
        combined_slug = separator.join(field_slugs)
        
        # Ensure it doesn't exceed max length
        if len(combined_slug) > max_length:
            combined_slug = combined_slug[:max_length].rstrip(separator)
        
        return combined_slug
    
    @staticmethod
    def is_valid_slug(slug: str) -> bool:
        """Check if a string is a valid slug"""
        if not slug:
            return False
        
        # Check if it contains only valid characters
        if not re.match(r'^[a-z0-9-]+$', slug):
            return False
        
        # Check if it starts or ends with hyphen
        if slug.startswith('-') or slug.endswith('-'):
            return False
        
        # Check for consecutive hyphens
        if '--' in slug:
            return False
        
        return True
    
    @staticmethod
    def sanitize_slug(slug: str) -> str:
        """Sanitize an existing slug to make it valid"""
        if not slug:
            return ''
        
        # Convert to lowercase and remove invalid characters
        slug = re.sub(r'[^a-z0-9-]', '', slug.lower())
        
        # Remove consecutive hyphens
        slug = re.sub(r'-+', '-', slug)
        
        # Remove leading/trailing hyphens
        slug = slug.strip('-')
        
        return slug

class URLSafeSlugger:
    """Advanced URL-safe slug generation"""
    
    # Character transliteration map for non-ASCII characters
    TRANSLITERATION_MAP = {
        'á': 'a', 'à': 'a', 'ä': 'a', 'â': 'a', 'ā': 'a', 'ã': 'a',
        'é': 'e', 'è': 'e', 'ë': 'e', 'ê': 'e', 'ē': 'e',
        'í': 'i', 'ì': 'i', 'ï': 'i', 'î': 'i', 'ī': 'i',
        'ó': 'o', 'ò': 'o', 'ö': 'o', 'ô': 'o', 'ō': 'o', 'õ': 'o',
        'ú': 'u', 'ù': 'u', 'ü': 'u', 'û': 'u', 'ū': 'u',
        'ñ': 'n', 'ç': 'c', 'ß': 'ss',
        # Add more as needed
    }
    
    @classmethod
    def create_url_safe_slug(cls, text: str, max_length: int = 100,
                            allow_unicode: bool = False) -> str:
        """Create URL-safe slug with advanced options"""
        if not text:
            return ''
        
        original_text = text
        
        # Handle Unicode characters
        if not allow_unicode:
            # Apply transliteration map
            for original, replacement in cls.TRANSLITERATION_MAP.items():
                text = text.replace(original, replacement)
                text = text.replace(original.upper(), replacement.upper())
            
            # Normalize and convert to ASCII
            text = unicodedata.normalize('NFKD', text)
            text = text.encode('ascii', 'ignore').decode('ascii')
        
        # Convert to lowercase
        text = text.lower()
        
        # Replace whitespace and special characters
        if allow_unicode:
            # More permissive pattern for Unicode
            text = re.sub(r'[^\w\s-]', '', text, flags=re.UNICODE)
        else:
            text = re.sub(r'[^a-z0-9\s-]', '', text)
        
        # Replace multiple spaces/hyphens with single hyphen
        text = re.sub(r'[\s-]+', '-', text)
        
        # Remove leading/trailing hyphens
        text = text.strip('-')
        
        # Truncate to max length
        if len(text) > max_length:
            text = text[:max_length].rstrip('-')
        
        return text or 'item'
    
    @classmethod
    def create_seo_slug(cls, title: str, keywords: List[str] = None,
                       max_length: int = 60) -> str:
        """Create SEO-optimized slug"""
        # Start with title slug
        slug = cls.create_url_safe_slug(title, max_length=max_length)
        
        # Add keywords if they're not already in the slug
        if keywords:
            slug_words = set(slug.split('-'))
            missing_keywords = []
            
            for keyword in keywords:
                keyword_slug = cls.create_url_safe_slug(keyword)
                keyword_words = set(keyword_slug.split('-'))
                
                # Check if keyword is not already represented
                if not keyword_words.intersection(slug_words):
                    missing_keywords.append(keyword_slug)
            
            # Add missing keywords if there's room
            if missing_keywords:
                additional_keywords = '-'.join(missing_keywords)
                potential_slug = f"{slug}-{additional_keywords}"
                
                if len(potential_slug) <= max_length:
                    slug = potential_slug
                else:
                    # Add as many keywords as possible
                    remaining_length = max_length - len(slug) - 1
                    if remaining_length > 0:
                        additional_keywords = additional_keywords[:remaining_length].rstrip('-')
                        if additional_keywords:
                            slug = f"{slug}-{additional_keywords}"
        
        return slug
    
    @classmethod
    def create_hierarchical_slug(cls, path_segments: List[str], 
                                separator: str = '/',
                                max_segment_length: int = 30) -> str:
        """Create hierarchical slug for nested content"""
        if not path_segments:
            return ''
        
        # Create slug for each segment
        slug_segments = []
        for segment in path_segments:
            if segment and segment.strip():
                segment_slug = cls.create_url_safe_slug(
                    segment, 
                    max_length=max_segment_length
                )
                if segment_slug:
                    slug_segments.append(segment_slug)
        
        return separator.join(slug_segments)

class UniqueSlugGenerator:
    """Generate unique slugs with conflict resolution"""
    
    def __init__(self, existing_slugs: Set[str] = None):
        self.existing_slugs = existing_slugs or set()
    
    def generate_unique_slug(self, text: str, max_length: int = 50,
                           check_function: Callable[[str], bool] = None) -> str:
        """Generate unique slug, adding suffix if conflicts exist"""
        base_slug = SlugHelper.create_slug(text, max_length=max_length)
        
        if not self._slug_exists(base_slug, check_function):
            self.existing_slugs.add(base_slug)
            return base_slug
        
        # Generate unique variants
        counter = 1
        max_attempts = 1000  # Prevent infinite loops
        
        while counter < max_attempts:
            # Calculate suffix
            suffix = f"-{counter}"
            max_base_length = max_length - len(suffix)
            
            # Ensure base slug fits with suffix
            if len(base_slug) > max_base_length:
                truncated_slug = base_slug[:max_base_length].rstrip('-')
            else:
                truncated_slug = base_slug
            
            candidate_slug = f"{truncated_slug}{suffix}"
            
            if not self._slug_exists(candidate_slug, check_function):
                self.existing_slugs.add(candidate_slug)
                return candidate_slug
            
            counter += 1
        
        # Fallback: random suffix
        random_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
        fallback_slug = f"{base_slug[:max_length-7]}-{random_suffix}"
        
        self.existing_slugs.add(fallback_slug)
        return fallback_slug
    
    def _slug_exists(self, slug: str, check_function: Callable[[str], bool] = None) -> bool:
        """Check if slug already exists"""
        # Check in-memory set first
        if slug in self.existing_slugs:
            return True
        
        # Use external check function if provided
        if check_function:
            return check_function(slug)
        
        return False
    
    def add_existing_slug(self, slug: str):
        """Add slug to existing set"""
        self.existing_slugs.add(slug)
    
    def remove_slug(self, slug: str):
        """Remove slug from existing set"""
        self.existing_slugs.discard(slug)
    
    def generate_time_based_slug(self, text: str, max_length: int = 50) -> str:
        """Generate slug with timestamp suffix"""
        timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        suffix = f"-{timestamp}"
        
        max_base_length = max_length - len(suffix)
        base_slug = SlugHelper.create_slug(text, max_length=max_base_length)
        
        return f"{base_slug}{suffix}"
    
    def generate_random_slug(self, text: str = None, max_length: int = 50,
                           random_length: int = 8) -> str:
        """Generate slug with random suffix"""
        if text:
            base_slug = SlugHelper.create_slug(text, max_length=max_length-random_length-1)
            random_part = ''.join(random.choices(string.ascii_lowercase + string.digits, k=random_length))
            return f"{base_slug}-{random_part}"
        else:
            return ''.join(random.choices(string.ascii_lowercase + string.digits, k=max_length))

class SlugValidator:
    """Slug validation utilities"""
    
    # Reserved slugs that shouldn't be used
    RESERVED_SLUGS = {
        'admin', 'api', 'www', 'mail', 'ftp', 'localhost', 'root',
        'index', 'home', 'about', 'contact', 'help', 'support',
        'terms', 'privacy', 'login', 'logout', 'register', 'signup',
        'dashboard', 'profile', 'settings', 'search', 'blog', 'news',
        'post', 'page', 'category', 'tag', 'archive', 'feed', 'rss',
        'sitemap', 'robots', 'humans', 'favicon', 'assets', 'static',
        'media', 'uploads', 'downloads', 'files', 'images', 'css', 'js'
    }
    
    @classmethod
    def validate_slug(cls, slug: str, min_length: int = 1, 
                     max_length: int = 100,
                     allow_reserved: bool = False) -> dict:
        """Comprehensive slug validation"""
        result = {
            'is_valid': True,
            'errors': [],
            'warnings': [],
            'suggestions': []
        }
        
        if not slug:
            result['is_valid'] = False
            result['errors'].append('Slug cannot be empty')
            return result
        
        # Check length
        if len(slug) < min_length:
            result['is_valid'] = False
            result['errors'].append(f'Slug must be at least {min_length} characters long')
        
        if len(slug) > max_length:
            result['is_valid'] = False
            result['errors'].append(f'Slug must be no more than {max_length} characters long')
            result['suggestions'].append(f'Suggested: {slug[:max_length]}')
        
        # Check format
        if not re.match(r'^[a-z0-9-]+$', slug):
            result['is_valid'] = False
            result['errors'].append('Slug can only contain lowercase letters, numbers, and hyphens')
            sanitized = SlugHelper.sanitize_slug(slug)
            if sanitized:
                result['suggestions'].append(f'Suggested: {sanitized}')
        
        # Check for leading/trailing hyphens
        if slug.startswith('-') or slug.endswith('-'):
            result['is_valid'] = False
            result['errors'].append('Slug cannot start or end with a hyphen')
            result['suggestions'].append(f'Suggested: {slug.strip("-")}')
        
        # Check for consecutive hyphens
        if '--' in slug:
            result['is_valid'] = False
            result['errors'].append('Slug cannot contain consecutive hyphens')
            fixed = re.sub(r'-+', '-', slug)
            result['suggestions'].append(f'Suggested: {fixed}')
        
        # Check for reserved words
        if not allow_reserved and slug in cls.RESERVED_SLUGS:
            result['is_valid'] = False
            result['errors'].append(f'"{slug}" is a reserved slug and cannot be used')
            result['suggestions'].append(f'Suggested: {slug}-page')
        
        # Check for numeric-only slugs
        if slug.isdigit():
            result['warnings'].append('Numeric-only slugs may cause URL confusion')
            result['suggestions'].append(f'Suggested: item-{slug}')
        
        # Check for very short slugs
        if len(slug) < 3:
            result['warnings'].append('Very short slugs may not be SEO-friendly')
        
        return result
    
    @classmethod
    def suggest_improvements(cls, slug: str) -> List[str]:
        """Suggest improvements for slug"""
        suggestions = []
        
        # Check for underscores
        if '_' in slug:
            suggestions.append(f'Replace underscores with hyphens: {slug.replace("_", "-")}')
        
        # Check for mixed case
        if slug != slug.lower():
            suggestions.append(f'Use lowercase: {slug.lower()}')
        
        # Check for redundant words
        words = slug.split('-')
        unique_words = []
        seen = set()
        
        for word in words:
            if word not in seen:
                unique_words.append(word)
                seen.add(word)
        
        if len(unique_words) < len(words):
            suggestions.append(f'Remove duplicate words: {"-".join(unique_words)}')
        
        # Check for common abbreviations that could be expanded
        expansions = {
            'info': 'information',
            'mgmt': 'management',
            'dept': 'department',
            'dev': 'development',
            'admin': 'administration'
        }
        
        expanded_words = []
        for word in words:
            if word in expansions and len(slug) < 40:  # Only suggest if slug isn't too long
                expanded_words.append(expansions[word])
            else:
                expanded_words.append(word)
        
        if expanded_words != words:
            expanded_slug = '-'.join(expanded_words)
            suggestions.append(f'Consider expanding abbreviations: {expanded_slug}')
        
        return suggestions

class HostelSlugGenerator:
    """Specialized slug generator for hostel management entities"""
    
    @staticmethod
    def generate_hostel_slug(hostel_name: str, city: str = None, 
                           area: str = None) -> str:
        """Generate slug for hostel"""
        segments = [hostel_name]
        
        if area:
            segments.append(area)
        elif city:
            segments.append(city)
        
        return SlugHelper.create_slug_from_fields(segments, max_length=60)
    
    @staticmethod
    def generate_room_slug(room_number: str, room_type: str = None,
                          hostel_slug: str = None) -> str:
        """Generate slug for room"""
        segments = []
        
        if hostel_slug:
            segments.append(hostel_slug)
        
        segments.append(f"room-{room_number}")
        
        if room_type:
            segments.append(room_type)
        
        return SlugHelper.create_slug_from_fields(segments, max_length=50)
    
    @staticmethod
    def generate_student_slug(first_name: str, last_name: str, 
                            student_id: str = None) -> str:
        """Generate slug for student profile"""
        segments = [first_name, last_name]
        
        if student_id:
            segments.append(student_id)
        
        return SlugHelper.create_slug_from_fields(segments, max_length=40)
    
    @staticmethod
    def generate_announcement_slug(title: str, date: datetime = None) -> str:
        """Generate slug for announcement"""
        slug = SlugHelper.create_slug(title, max_length=50)
        
        if date:
            date_str = date.strftime('%Y-%m-%d')
            return f"{slug}-{date_str}"
        
        return slug
    
    @staticmethod
    def generate_complaint_slug(category: str, room_number: str = None,
                              complaint_id: str = None) -> str:
        """Generate slug for complaint"""
        segments = ['complaint', category]
        
        if room_number:
            segments.append(f"room-{room_number}")
        
        if complaint_id:
            segments.append(complaint_id)
        
        return SlugHelper.create_slug_from_fields(segments, max_length=45)

class SlugBatch:
    """Batch slug generation utilities"""
    
    def __init__(self):
        self.slugs = {}
        self.conflicts = []
    
    def add_item(self, key: str, text: str, **kwargs):
        """Add item for slug generation"""
        slug = SlugHelper.create_slug(text, **kwargs)
        
        if slug in self.slugs.values():
            self.conflicts.append({'key': key, 'text': text, 'slug': slug})
        else:
            self.slugs[key] = slug
    
    def resolve_conflicts(self, strategy: str = 'suffix') -> dict:
        """Resolve slug conflicts"""
        if strategy == 'suffix':
            return self._resolve_with_suffix()
        elif strategy == 'random':
            return self._resolve_with_random()
        elif strategy == 'timestamp':
            return self._resolve_with_timestamp()
        else:
            raise ValueError(f"Unknown conflict resolution strategy: {strategy}")
    
    def _resolve_with_suffix(self) -> dict:
        """Resolve conflicts by adding numeric suffix"""
        resolved_slugs = self.slugs.copy()
        
        for conflict in self.conflicts:
            key = conflict['key']
            base_slug = conflict['slug']
            counter = 1
            
            while True:
                candidate_slug = f"{base_slug}-{counter}"
                if candidate_slug not in resolved_slugs.values():
                    resolved_slugs[key] = candidate_slug
                    break
                counter += 1
        
        return resolved_slugs
    
    def _resolve_with_random(self) -> dict:
        """Resolve conflicts by adding random suffix"""
        resolved_slugs = self.slugs.copy()
        
        for conflict in self.conflicts:
            key = conflict['key']
            base_slug = conflict['slug']
            
            while True:
                random_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=4))
                candidate_slug = f"{base_slug}-{random_suffix}"
                
                if candidate_slug not in resolved_slugs.values():
                    resolved_slugs[key] = candidate_slug
                    break
        
        return resolved_slugs
    
    def _resolve_with_timestamp(self) -> dict:
        """Resolve conflicts by adding timestamp"""
        resolved_slugs = self.slugs.copy()
        
        for conflict in self.conflicts:
            key = conflict['key']
            base_slug = conflict['slug']
            timestamp = datetime.now().strftime('%H%M%S')
            candidate_slug = f"{base_slug}-{timestamp}"
            resolved_slugs[key] = candidate_slug
        
        return resolved_slugs
    
    def get_results(self) -> dict:
        """Get final slug results"""
        return {
            'slugs': self.slugs,
            'conflicts': self.conflicts,
            'total_items': len(self.slugs) + len(self.conflicts),
            'conflict_count': len(self.conflicts)
        }