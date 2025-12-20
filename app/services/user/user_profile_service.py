# --- File: C:\Hostel-Main\app\services\user\user_profile_service.py ---
"""
User Profile Service - Profile management and personalization.
"""
from datetime import date, datetime, timezone
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.user import User, UserProfile
from app.repositories.user import UserProfileRepository, UserRepository
from app.schemas.common.enums import Gender
from app.core.exceptions import EntityNotFoundError, BusinessRuleViolationError


class UserProfileService:
    """
    Service for user profile operations including personalization,
    preferences, demographics, and profile completion tracking.
    """

    def __init__(self, db: Session):
        self.db = db
        self.profile_repo = UserProfileRepository(db)
        self.user_repo = UserRepository(db)

    # ==================== Profile Management ====================

    def create_profile(
        self,
        user_id: str,
        profile_data: Optional[Dict[str, Any]] = None,
        auto_calculate_completion: bool = True
    ) -> UserProfile:
        """
        Create user profile with optional initial data.
        
        Args:
            user_id: User ID
            profile_data: Initial profile data
            auto_calculate_completion: Auto-calculate completion percentage
            
        Returns:
            Created UserProfile
            
        Raises:
            EntityNotFoundError: If user not found
            BusinessRuleViolationError: If profile already exists
        """
        # Validate user exists
        user = self.user_repo.get_by_id(user_id)
        
        # Check if profile already exists
        existing = self.profile_repo.find_by_user_id(user_id)
        if existing:
            raise BusinessRuleViolationError(
                f"Profile already exists for user {user_id}"
            )
        
        # Prepare profile data with defaults
        data = profile_data or {}
        data['user_id'] = user_id
        
        # Set default preferences if not provided
        if 'notification_preferences' not in data:
            data['notification_preferences'] = self._get_default_notification_preferences()
        
        if 'privacy_settings' not in data:
            data['privacy_settings'] = self._get_default_privacy_settings()
        
        if 'communication_preferences' not in data:
            data['communication_preferences'] = self._get_default_communication_preferences()
        
        # Set default localization
        if 'preferred_language' not in data:
            data['preferred_language'] = 'en'
        
        if 'timezone' not in data:
            data['timezone'] = 'UTC'
        
        # Create profile
        profile = self.profile_repo.create(data)
        
        # Calculate and update completion
        if auto_calculate_completion:
            profile = self.profile_repo.update_completion_percentage(user_id)
        
        self._log_profile_event(user_id, "profile_created", {})
        
        return profile

    def update_profile(
        self,
        user_id: str,
        profile_data: Dict[str, Any],
        auto_calculate_completion: bool = True,
        validate_data: bool = True
    ) -> UserProfile:
        """
        Update user profile with validation.
        
        Args:
            user_id: User ID
            profile_data: Profile data to update
            auto_calculate_completion: Auto-recalculate completion
            validate_data: Validate profile data
            
        Returns:
            Updated UserProfile
            
        Raises:
            BusinessRuleViolationError: If validation fails
        """
        profile = self.profile_repo.get_by_user_id(user_id)
        
        # Validate data if requested
        if validate_data:
            profile_data = self._validate_profile_data(profile_data)
        
        # Track what fields are being updated
        updated_fields = list(profile_data.keys())
        
        # Update last_profile_update timestamp
        profile_data['last_profile_update'] = datetime.now(timezone.utc)
        
        # Update profile
        updated_profile = self.profile_repo.update(profile.id, profile_data)
        
        # Recalculate completion if requested
        if auto_calculate_completion:
            updated_profile = self.profile_repo.update_completion_percentage(user_id)
        
        self._log_profile_event(user_id, "profile_updated", {
            "fields": updated_fields
        })
        
        return updated_profile

    def get_or_create_profile(
        self,
        user_id: str,
        profile_data: Optional[Dict[str, Any]] = None
    ) -> UserProfile:
        """
        Get existing profile or create new one.
        
        Args:
            user_id: User ID
            profile_data: Optional profile data for creation
            
        Returns:
            UserProfile
        """
        profile = self.profile_repo.find_by_user_id(user_id)
        
        if not profile:
            profile = self.create_profile(user_id, profile_data)
        
        return profile

    def delete_profile(self, user_id: str) -> None:
        """
        Delete user profile.
        
        Args:
            user_id: User ID
        """
        profile = self.profile_repo.get_by_user_id(user_id)
        self.profile_repo.delete(profile.id)
        
        self._log_profile_event(user_id, "profile_deleted", {})

    def _validate_profile_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate profile data before update.
        
        Args:
            data: Profile data to validate
            
        Returns:
            Validated data
            
        Raises:
            BusinessRuleViolationError: If validation fails
        """
        validated = {}
        
        # Validate date_of_birth
        if 'date_of_birth' in data:
            dob = data['date_of_birth']
            if isinstance(dob, str):
                try:
                    dob = datetime.fromisoformat(dob).date()
                except ValueError:
                    raise BusinessRuleViolationError("Invalid date_of_birth format")
            
            if isinstance(dob, date):
                # Check age constraints
                today = date.today()
                age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
                
                if age < 13:
                    raise BusinessRuleViolationError("User must be at least 13 years old")
                if age > 120:
                    raise BusinessRuleViolationError("Invalid date of birth")
                
                validated['date_of_birth'] = dob
        
        # Validate gender
        if 'gender' in data:
            gender = data['gender']
            if isinstance(gender, str):
                try:
                    gender = Gender(gender)
                except ValueError:
                    raise BusinessRuleViolationError(f"Invalid gender: {gender}")
            validated['gender'] = gender
        
        # Validate bio length
        if 'bio' in data:
            bio = data['bio']
            if bio and len(bio) > 1000:
                raise BusinessRuleViolationError("Bio must not exceed 1000 characters")
            validated['bio'] = bio
        
        # Validate nationality
        if 'nationality' in data:
            nationality = data['nationality']
            if nationality and len(nationality) > 100:
                raise BusinessRuleViolationError("Nationality too long")
            validated['nationality'] = nationality
        
        # Validate occupation
        if 'occupation' in data:
            occupation = data['occupation']
            if occupation and len(occupation) > 100:
                raise BusinessRuleViolationError("Occupation too long")
            validated['occupation'] = occupation
        
        # Validate organization
        if 'organization' in data:
            organization = data['organization']
            if organization and len(organization) > 255:
                raise BusinessRuleViolationError("Organization name too long")
            validated['organization'] = organization
        
        # Validate URLs
        url_fields = ['profile_image_url', 'cover_image_url']
        for field in url_fields:
            if field in data:
                url = data[field]
                if url:
                    self._validate_url(url)
                validated[field] = url
        
        # Validate language code
        if 'preferred_language' in data:
            lang = data['preferred_language']
            if lang and len(lang) > 10:
                raise BusinessRuleViolationError("Invalid language code")
            validated['preferred_language'] = lang
        
        # Validate timezone
        if 'timezone' in data:
            tz = data['timezone']
            if tz:
                # TODO: Validate against pytz timezones
                pass
            validated['timezone'] = tz
        
        # Copy other fields as-is
        for key, value in data.items():
            if key not in validated:
                validated[key] = value
        
        return validated

    def _validate_url(self, url: str) -> None:
        """Validate URL format."""
        import re
        url_pattern = re.compile(
            r'^https?://'  # http:// or https://
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
            r'localhost|'  # localhost...
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
            r'(?::\d+)?'  # optional port
            r'(?:/?|[/?]\S+)$', re.IGNORECASE
        )
        
        if not url_pattern.match(url):
            raise BusinessRuleViolationError(f"Invalid URL format: {url}")

    # ==================== Profile Completion ====================

    def get_profile_completion(self, user_id: str) -> int:
        """
        Get profile completion percentage.
        
        Args:
            user_id: User ID
            
        Returns:
            Completion percentage (0-100)
        """
        return self.profile_repo.calculate_completion_percentage(user_id)

    def update_profile_completion(self, user_id: str) -> UserProfile:
        """
        Recalculate and update profile completion percentage.
        
        Args:
            user_id: User ID
            
        Returns:
            Updated UserProfile
        """
        return self.profile_repo.update_completion_percentage(user_id)

    def get_completion_suggestions(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Get prioritized suggestions for improving profile completion.
        
        Args:
            user_id: User ID
            
        Returns:
            List of suggestions with priority
        """
        profile = self.profile_repo.get_by_user_id(user_id)
        suggestions = []
        
        # Define fields with their weights and descriptions
        completion_fields = [
            {
                'field': 'gender',
                'weight': 10,
                'title': 'Add Gender',
                'description': 'Help us personalize your experience',
                'category': 'demographics'
            },
            {
                'field': 'date_of_birth',
                'weight': 15,
                'title': 'Add Date of Birth',
                'description': 'Verify your age and get relevant content',
                'category': 'demographics'
            },
            {
                'field': 'nationality',
                'weight': 10,
                'title': 'Add Nationality',
                'description': 'Complete your demographic information',
                'category': 'demographics'
            },
            {
                'field': 'bio',
                'weight': 15,
                'title': 'Write Your Bio',
                'description': 'Tell others about yourself',
                'category': 'personal'
            },
            {
                'field': 'profile_image_url',
                'weight': 15,
                'title': 'Upload Profile Picture',
                'description': 'Make your profile more personable',
                'category': 'media'
            },
            {
                'field': 'occupation',
                'weight': 10,
                'title': 'Add Occupation',
                'description': 'Share what you do',
                'category': 'professional'
            },
            {
                'field': 'organization',
                'weight': 5,
                'title': 'Add Organization',
                'description': 'Share where you work or study',
                'category': 'professional'
            },
            {
                'field': 'social_links',
                'weight': 5,
                'title': 'Add Social Links',
                'description': 'Connect your social media profiles',
                'category': 'social'
            }
        ]
        
        for field_info in completion_fields:
            field = field_info['field']
            value = getattr(profile, field, None)
            
            # Check if field is empty
            is_empty = False
            if value is None:
                is_empty = True
            elif isinstance(value, (dict, list)):
                is_empty = not value
            elif isinstance(value, str):
                is_empty = not value.strip()
            
            if is_empty:
                suggestions.append({
                    'field': field,
                    'weight': field_info['weight'],
                    'title': field_info['title'],
                    'description': field_info['description'],
                    'category': field_info['category'],
                    'priority': 'high' if field_info['weight'] >= 15 else 'medium' if field_info['weight'] >= 10 else 'low'
                })
        
        # Sort by weight (highest first)
        return sorted(suggestions, key=lambda x: x['weight'], reverse=True)

    def get_profile_quality_score(self, user_id: str) -> Dict[str, Any]:
        """
        Get detailed profile quality assessment.
        
        Args:
            user_id: User ID
            
        Returns:
            Profile quality score breakdown
        """
        profile = self.profile_repo.get_by_user_id(user_id)
        user = self.user_repo.get_by_id(user_id)
        
        scores = {
            'completion': profile.profile_completion_percentage if profile else 0,
            'verification': 0,
            'engagement': 0,
            'overall': 0
        }
        
        # Verification score
        verification_points = 0
        if user.is_email_verified:
            verification_points += 50
        if user.is_phone_verified:
            verification_points += 50
        scores['verification'] = verification_points
        
        # Engagement score (based on profile views, last update, etc.)
        engagement_points = 0
        if profile:
            if profile.profile_views > 0:
                engagement_points += min(profile.profile_views * 2, 50)
            
            if profile.last_profile_update:
                days_since_update = (datetime.now(timezone.utc) - profile.last_profile_update).days
                if days_since_update < 30:
                    engagement_points += 30
                elif days_since_update < 90:
                    engagement_points += 20
                else:
                    engagement_points += 10
            
            if profile.social_links:
                engagement_points += min(len(profile.social_links) * 10, 20)
        
        scores['engagement'] = min(engagement_points, 100)
        
        # Calculate overall score (weighted average)
        scores['overall'] = int(
            (scores['completion'] * 0.5) +
            (scores['verification'] * 0.3) +
            (scores['engagement'] * 0.2)
        )
        
        return {
            'scores': scores,
            'quality_level': self._get_quality_level(scores['overall']),
            'suggestions': self.get_completion_suggestions(user_id)[:3]  # Top 3
        }

    def _get_quality_level(self, score: int) -> str:
        """Get quality level from score."""
        if score >= 90:
            return 'excellent'
        elif score >= 75:
            return 'good'
        elif score >= 50:
            return 'fair'
        else:
            return 'needs_improvement'

    # ==================== Demographics ====================

    def update_demographics(
        self,
        user_id: str,
        gender: Optional[Gender] = None,
        date_of_birth: Optional[date] = None,
        nationality: Optional[str] = None
    ) -> UserProfile:
        """
        Update demographic information with validation.
        
        Args:
            user_id: User ID
            gender: Gender
            date_of_birth: Date of birth
            nationality: Nationality
            
        Returns:
            Updated UserProfile
        """
        profile = self.profile_repo.get_by_user_id(user_id)
        
        update_data = {}
        
        if gender is not None:
            update_data['gender'] = gender
        
        if date_of_birth is not None:
            # Validate age
            today = date.today()
            age = today.year - date_of_birth.year - (
                (today.month, today.day) < (date_of_birth.month, date_of_birth.day)
            )
            
            if age < 13:
                raise BusinessRuleViolationError("User must be at least 13 years old")
            if age > 120:
                raise BusinessRuleViolationError("Invalid date of birth")
            
            update_data['date_of_birth'] = date_of_birth
        
        if nationality is not None:
            if len(nationality) > 100:
                raise BusinessRuleViolationError("Nationality too long")
            update_data['nationality'] = nationality
        
        if update_data:
            profile = self.profile_repo.update(profile.id, update_data)
            profile = self.profile_repo.update_completion_percentage(user_id)
            
            self._log_profile_event(user_id, "demographics_updated", {
                "fields": list(update_data.keys())
            })
        
        return profile

    def update_personal_info(
        self,
        user_id: str,
        bio: Optional[str] = None,
        occupation: Optional[str] = None,
        organization: Optional[str] = None
    ) -> UserProfile:
        """
        Update personal information.
        
        Args:
            user_id: User ID
            bio: Biography (max 1000 chars)
            occupation: Occupation
            organization: Organization
            
        Returns:
            Updated UserProfile
        """
        profile = self.profile_repo.get_by_user_id(user_id)
        
        update_data = {}
        
        if bio is not None:
            if len(bio) > 1000:
                raise BusinessRuleViolationError("Bio must not exceed 1000 characters")
            update_data['bio'] = bio.strip()
        
        if occupation is not None:
            if len(occupation) > 100:
                raise BusinessRuleViolationError("Occupation too long")
            update_data['occupation'] = occupation.strip()
        
        if organization is not None:
            if len(organization) > 255:
                raise BusinessRuleViolationError("Organization name too long")
            update_data['organization'] = organization.strip()
        
        if update_data:
            profile = self.profile_repo.update(profile.id, update_data)
            profile = self.profile_repo.update_completion_percentage(user_id)
            
            self._log_profile_event(user_id, "personal_info_updated", {
                "fields": list(update_data.keys())
            })
        
        return profile

    def get_user_age(self, user_id: str) -> Optional[int]:
        """
        Calculate user age from date of birth.
        
        Args:
            user_id: User ID
            
        Returns:
            Age in years or None
        """
        profile = self.profile_repo.get_by_user_id(user_id)
        return profile.age if profile else None

    # ==================== Media Management ====================

    def update_profile_image(
        self,
        user_id: str,
        image_url: str,
        validate_url: bool = True
    ) -> UserProfile:
        """
        Update profile image with validation.
        
        Args:
            user_id: User ID
            image_url: Image URL
            validate_url: Validate URL format
            
        Returns:
            Updated UserProfile
        """
        if validate_url:
            self._validate_url(image_url)
        
        profile = self.profile_repo.update_profile_image(user_id, image_url)
        profile = self.profile_repo.update_completion_percentage(user_id)
        
        self._log_profile_event(user_id, "profile_image_updated", {
            "url": image_url
        })
        
        return profile

    def update_cover_image(
        self,
        user_id: str,
        cover_url: str,
        validate_url: bool = True
    ) -> UserProfile:
        """
        Update cover image with validation.
        
        Args:
            user_id: User ID
            cover_url: Cover image URL
            validate_url: Validate URL format
            
        Returns:
            Updated UserProfile
        """
        if validate_url:
            self._validate_url(cover_url)
        
        profile = self.profile_repo.get_by_user_id(user_id)
        profile = self.profile_repo.update(profile.id, {
            'cover_image_url': cover_url
        })
        
        self._log_profile_event(user_id, "cover_image_updated", {
            "url": cover_url
        })
        
        return profile

    def remove_profile_image(self, user_id: str) -> UserProfile:
        """
        Remove profile image.
        
        Args:
            user_id: User ID
            
        Returns:
            Updated UserProfile
        """
        profile = self.profile_repo.get_by_user_id(user_id)
        profile = self.profile_repo.update(profile.id, {
            'profile_image_url': None
        })
        profile = self.profile_repo.update_completion_percentage(user_id)
        
        self._log_profile_event(user_id, "profile_image_removed", {})
        
        return profile

    def remove_cover_image(self, user_id: str) -> UserProfile:
        """Remove cover image."""
        profile = self.profile_repo.get_by_user_id(user_id)
        profile = self.profile_repo.update(profile.id, {
            'cover_image_url': None
        })
        
        self._log_profile_event(user_id, "cover_image_removed", {})
        
        return profile

    # ==================== Social Links ====================

    def update_social_links(
        self,
        user_id: str,
        social_links: Dict[str, str],
        validate_urls: bool = True
    ) -> UserProfile:
        """
        Update social media links with validation.
        
        Args:
            user_id: User ID
            social_links: Dictionary of platform: url
            validate_urls: Validate URL formats
            
        Returns:
            Updated UserProfile
        """
        if validate_urls:
            for platform, url in social_links.items():
                if url:
                    self._validate_url(url)
        
        profile = self.profile_repo.update_social_links(user_id, social_links)
        profile = self.profile_repo.update_completion_percentage(user_id)
        
        self._log_profile_event(user_id, "social_links_updated", {
            "platforms": list(social_links.keys())
        })
        
        return profile

    def add_social_link(
        self,
        user_id: str,
        platform: str,
        url: str
    ) -> UserProfile:
        """
        Add a single social media link.
        
        Args:
            user_id: User ID
            platform: Social platform name (facebook, twitter, linkedin, etc.)
            url: Profile URL
            
        Returns:
            Updated UserProfile
        """
        self._validate_url(url)
        
        profile = self.profile_repo.get_by_user_id(user_id)
        
        social_links = profile.social_links or {}
        social_links[platform.lower()] = url
        
        return self.update_social_links(user_id, social_links, validate_urls=False)

    def remove_social_link(
        self,
        user_id: str,
        platform: str
    ) -> UserProfile:
        """
        Remove a social media link.
        
        Args:
            user_id: User ID
            platform: Social platform name
            
        Returns:
            Updated UserProfile
        """
        profile = self.profile_repo.get_by_user_id(user_id)
        
        social_links = profile.social_links or {}
        platform_key = platform.lower()
        
        if platform_key in social_links:
            del social_links[platform_key]
            profile = self.profile_repo.update(profile.id, {
                'social_links': social_links
            })
            
            self._log_profile_event(user_id, "social_link_removed", {
                "platform": platform
            })
        
        return profile

    def get_social_links(self, user_id: str) -> Dict[str, str]:
        """
        Get user's social links.
        
        Args:
            user_id: User ID
            
        Returns:
            Dictionary of social links
        """
        profile = self.profile_repo.get_by_user_id(user_id)
        return profile.social_links or {}

    # ==================== Localization ====================

    def update_localization(
        self,
        user_id: str,
        preferred_language: Optional[str] = None,
        timezone: Optional[str] = None
    ) -> UserProfile:
        """
        Update localization settings.
        
        Args:
            user_id: User ID
            preferred_language: ISO 639-1 language code
            timezone: IANA timezone identifier
            
        Returns:
            Updated UserProfile
        """
        profile = self.profile_repo.get_by_user_id(user_id)
        
        update_data = {}
        
        if preferred_language is not None:
            # Validate language code
            valid_languages = ['en', 'es', 'fr', 'de', 'hi', 'mr', 'ta', 'te']
            if preferred_language not in valid_languages:
                raise BusinessRuleViolationError(
                    f"Invalid language code. Supported: {', '.join(valid_languages)}"
                )
            update_data['preferred_language'] = preferred_language
        
        if timezone is not None:
            # TODO: Validate timezone with pytz
            update_data['timezone'] = timezone
        
        if update_data:
            profile = self.profile_repo.update(profile.id, update_data)
            
            self._log_profile_event(user_id, "localization_updated", {
                "fields": list(update_data.keys())
            })
        
        return profile

    # ==================== Profile Views ====================

    def increment_profile_views(self, user_id: str) -> UserProfile:
        """
        Increment profile view count.
        
        Args:
            user_id: User ID
            
        Returns:
            Updated UserProfile
        """
        return self.profile_repo.increment_profile_views(user_id)

    def get_profile_views(self, user_id: str) -> int:
        """
        Get profile view count.
        
        Args:
            user_id: User ID
            
        Returns:
            View count
        """
        profile = self.profile_repo.get_by_user_id(user_id)
        return profile.profile_views or 0

    def reset_profile_views(self, user_id: str) -> UserProfile:
        """Reset profile view count."""
        profile = self.profile_repo.get_by_user_id(user_id)
        return self.profile_repo.update(profile.id, {'profile_views': 0})

    # ==================== Custom Fields ====================

    def update_custom_fields(
        self,
        user_id: str,
        custom_fields: Dict[str, Any]
    ) -> UserProfile:
        """
        Update custom profile fields.
        
        Args:
            user_id: User ID
            custom_fields: Custom fields dictionary
            
        Returns:
            Updated UserProfile
        """
        profile = self.profile_repo.get_by_user_id(user_id)
        
        current_custom = profile.custom_fields or {}
        current_custom.update(custom_fields)
        
        profile = self.profile_repo.update(profile.id, {
            'custom_fields': current_custom
        })
        
        self._log_profile_event(user_id, "custom_fields_updated", {
            "fields": list(custom_fields.keys())
        })
        
        return profile

    def get_custom_field(self, user_id: str, field_name: str) -> Any:
        """Get a specific custom field value."""
        profile = self.profile_repo.get_by_user_id(user_id)
        custom_fields = profile.custom_fields or {}
        return custom_fields.get(field_name)

    def remove_custom_field(self, user_id: str, field_name: str) -> UserProfile:
        """Remove a custom field."""
        profile = self.profile_repo.get_by_user_id(user_id)
        custom_fields = profile.custom_fields or {}
        
        if field_name in custom_fields:
            del custom_fields[field_name]
            profile = self.profile_repo.update(profile.id, {
                'custom_fields': custom_fields
            })
        
        return profile

    # ==================== Analytics ====================

    def get_profile_statistics(self) -> Dict[str, Any]:
        """Get platform-wide profile statistics."""
        return self.profile_repo.get_profile_statistics()

    def get_demographics_statistics(self) -> Dict[str, Any]:
        """Get demographic statistics across all profiles."""
        return self.profile_repo.get_demographics_statistics()

    def get_language_distribution(self) -> Dict[str, int]:
        """Get distribution of preferred languages."""
        return self.profile_repo.get_language_distribution()

    def find_incomplete_profiles(
        self,
        max_completion: int = 50,
        limit: int = 100
    ) -> List[UserProfile]:
        """
        Find profiles with low completion percentage.
        
        Args:
            max_completion: Maximum completion threshold
            limit: Maximum results
            
        Returns:
            List of incomplete profiles
        """
        return self.profile_repo.find_incomplete_profiles(max_completion, limit)

    def get_recently_updated_profiles(
        self,
        days: int = 7,
        limit: int = 50
    ) -> List[UserProfile]:
        """Get recently updated profiles."""
        return self.profile_repo.find_recently_updated(days, limit)

    # ==================== Bulk Operations ====================

    def bulk_update_language(
        self,
        user_ids: List[str],
        language: str
    ) -> int:
        """
        Bulk update preferred language.
        
        Args:
            user_ids: List of user IDs
            language: Language code
            
        Returns:
            Count of updated profiles
        """
        count = 0
        for user_id in user_ids:
            try:
                self.update_localization(user_id, preferred_language=language)
                count += 1
            except Exception:
                continue
        
        return count

    def recalculate_all_completions(self, limit: int = 1000) -> int:
        """
        Recalculate completion percentage for all profiles.
        
        Args:
            limit: Maximum profiles to process
            
        Returns:
            Count of recalculated profiles
        """
        profiles = self.db.query(UserProfile).limit(limit).all()
        
        count = 0
        for profile in profiles:
            try:
                self.profile_repo.update_completion_percentage(profile.user_id)
                count += 1
            except Exception:
                continue
        
        return count

    # ==================== Helper Methods ====================

    def _get_default_notification_preferences(self) -> Dict[str, Any]:
        """Get default notification preferences."""
        return {
            "email_notifications": True,
            "sms_notifications": True,
            "push_notifications": True,
            "booking_notifications": True,
            "payment_notifications": True,
            "complaint_notifications": True,
            "announcement_notifications": True,
            "maintenance_notifications": True,
            "marketing_notifications": False,
            "digest_frequency": "immediate",
            "quiet_hours_start": None,
            "quiet_hours_end": None
        }

    def _get_default_privacy_settings(self) -> Dict[str, Any]:
        """Get default privacy settings."""
        return {
            "profile_visibility": "public",
            "show_email": False,
            "show_phone": False,
            "show_date_of_birth": False,
            "allow_friend_requests": True,
            "show_online_status": True
        }

    def _get_default_communication_preferences(self) -> Dict[str, Any]:
        """Get default communication preferences."""
        return {
            "preferred_contact_method": "email",
            "best_contact_time": "anytime",
            "do_not_disturb": False
        }

    def _log_profile_event(
        self,
        user_id: str,
        event_type: str,
        event_data: Dict[str, Any]
    ) -> None:
        """Log profile event for auditing."""
        # TODO: Implement event logging
        pass

    # ==================== Profile Export ====================

    def export_profile_data(self, user_id: str) -> Dict[str, Any]:
        """
        Export complete profile data.
        
        Args:
            user_id: User ID
            
        Returns:
            Complete profile data
        """
        profile = self.profile_repo.get_by_user_id(user_id)
        
        if not profile:
            return {}
        
        return {
            'demographics': {
                'gender': profile.gender.value if profile.gender else None,
                'date_of_birth': profile.date_of_birth.isoformat() if profile.date_of_birth else None,
                'age': profile.age,
                'nationality': profile.nationality
            },
            'personal': {
                'bio': profile.bio,
                'occupation': profile.occupation,
                'organization': profile.organization
            },
            'media': {
                'profile_image_url': profile.profile_image_url,
                'cover_image_url': profile.cover_image_url
            },
            'localization': {
                'preferred_language': profile.preferred_language,
                'timezone': profile.timezone
            },
            'social': {
                'social_links': profile.social_links
            },
            'preferences': {
                'notification_preferences': profile.notification_preferences,
                'privacy_settings': profile.privacy_settings,
                'communication_preferences': profile.communication_preferences
            },
            'metrics': {
                'profile_completion_percentage': profile.profile_completion_percentage,
                'profile_views': profile.profile_views,
                'last_profile_update': profile.last_profile_update.isoformat() if profile.last_profile_update else None
            },
            'custom_fields': profile.custom_fields,
            'timestamps': {
                'created_at': profile.created_at.isoformat(),
                'updated_at': profile.updated_at.isoformat()
            }
        }


