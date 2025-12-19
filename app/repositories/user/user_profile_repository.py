"""
User Profile Repository - Extended user profile and personalization management.
"""
from datetime import datetime, timezone, date
from typing import List, Optional, Dict, Any
from sqlalchemy import func, and_, or_
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert

from app.models.user import UserProfile
from app.repositories.base.base_repository import BaseRepository
from app.schemas.common.enums import Gender


class UserProfileRepository(BaseRepository[UserProfile]):
    """
    Repository for UserProfile entity with profile management,
    personalization, and completion tracking.
    """

    def __init__(self, db: Session):
        super().__init__(UserProfile, db)

    # ==================== Profile Management ====================

    def find_by_user_id(self, user_id: str) -> Optional[UserProfile]:
        """
        Find profile by user ID.
        
        Args:
            user_id: User ID
            
        Returns:
            UserProfile or None
        """
        return self.db.query(UserProfile).filter(
            UserProfile.user_id == user_id
        ).first()

    def get_by_user_id(self, user_id: str) -> UserProfile:
        """
        Get profile by user ID (raises exception if not found).
        
        Args:
            user_id: User ID
            
        Returns:
            UserProfile
            
        Raises:
            EntityNotFoundError: If profile not found
        """
        profile = self.find_by_user_id(user_id)
        if not profile:
            raise EntityNotFoundError(f"Profile not found for user {user_id}")
        return profile

    def create_or_update(self, user_id: str, profile_data: Dict[str, Any]) -> UserProfile:
        """
        Create new profile or update existing one (upsert).
        
        Args:
            user_id: User ID
            profile_data: Profile data dictionary
            
        Returns:
            Created or updated UserProfile
        """
        existing = self.find_by_user_id(user_id)
        
        if existing:
            return self.update(existing.id, profile_data)
        else:
            profile_data['user_id'] = user_id
            return self.create(profile_data)

    # ==================== Profile Completion ====================

    def calculate_completion_percentage(self, user_id: str) -> int:
        """
        Calculate profile completion percentage.
        
        Args:
            user_id: User ID
            
        Returns:
            Completion percentage (0-100)
        """
        profile = self.find_by_user_id(user_id)
        if not profile:
            return 0
        
        # Define required fields and their weights
        fields = {
            'gender': 10,
            'date_of_birth': 15,
            'nationality': 10,
            'bio': 15,
            'occupation': 10,
            'profile_image_url': 15,
            'preferred_language': 5,
            'timezone': 5,
            'notification_preferences': 5,
            'privacy_settings': 5,
            'social_links': 5
        }
        
        total_weight = sum(fields.values())
        earned_weight = 0
        
        for field, weight in fields.items():
            value = getattr(profile, field, None)
            if value is not None:
                if isinstance(value, (dict, list)):
                    if value:  # Non-empty dict or list
                        earned_weight += weight
                else:
                    earned_weight += weight
        
        return int((earned_weight / total_weight) * 100)

    def update_completion_percentage(self, user_id: str) -> UserProfile:
        """
        Recalculate and update profile completion percentage.
        
        Args:
            user_id: User ID
            
        Returns:
            Updated UserProfile
        """
        profile = self.get_by_user_id(user_id)
        completion = self.calculate_completion_percentage(user_id)
        
        profile.profile_completion_percentage = completion
        profile.last_profile_update = datetime.now(timezone.utc)
        
        self.db.commit()
        self.db.refresh(profile)
        
        return profile

    def find_incomplete_profiles(
        self, 
        max_completion: int = 50,
        limit: int = 100
    ) -> List[UserProfile]:
        """
        Find profiles with low completion percentage.
        
        Args:
            max_completion: Maximum completion percentage threshold
            limit: Maximum results
            
        Returns:
            List of incomplete profiles
        """
        return self.db.query(UserProfile).filter(
            UserProfile.profile_completion_percentage <= max_completion
        ).order_by(
            UserProfile.profile_completion_percentage.asc()
        ).limit(limit).all()

    # ==================== Demographics ====================

    def find_by_gender(self, gender: Gender, limit: int = 100) -> List[UserProfile]:
        """
        Find profiles by gender.
        
        Args:
            gender: Gender filter
            limit: Maximum results
            
        Returns:
            List of profiles
        """
        return self.db.query(UserProfile).filter(
            UserProfile.gender == gender
        ).limit(limit).all()

    def find_by_age_range(
        self, 
        min_age: Optional[int] = None,
        max_age: Optional[int] = None
    ) -> List[UserProfile]:
        """
        Find profiles by age range.
        
        Args:
            min_age: Minimum age
            max_age: Maximum age
            
        Returns:
            List of profiles
        """
        today = date.today()
        
        query = self.db.query(UserProfile).filter(
            UserProfile.date_of_birth.isnot(None)
        )
        
        if min_age is not None:
            max_birth_date = date(today.year - min_age, today.month, today.day)
            query = query.filter(UserProfile.date_of_birth <= max_birth_date)
        
        if max_age is not None:
            min_birth_date = date(today.year - max_age - 1, today.month, today.day)
            query = query.filter(UserProfile.date_of_birth > min_birth_date)
        
        return query.all()

    def find_by_nationality(self, nationality: str) -> List[UserProfile]:
        """
        Find profiles by nationality.
        
        Args:
            nationality: Nationality filter
            
        Returns:
            List of profiles
        """
        return self.db.query(UserProfile).filter(
            UserProfile.nationality == nationality
        ).all()

    def get_demographics_statistics(self) -> Dict[str, Any]:
        """
        Get demographic statistics across all profiles.
        
        Returns:
            Dictionary with demographic breakdowns
        """
        # Gender distribution
        gender_dist = self.db.query(
            UserProfile.gender,
            func.count(UserProfile.id).label('count')
        ).filter(
            UserProfile.gender.isnot(None)
        ).group_by(UserProfile.gender).all()
        
        # Nationality distribution
        nationality_dist = self.db.query(
            UserProfile.nationality,
            func.count(UserProfile.id).label('count')
        ).filter(
            UserProfile.nationality.isnot(None)
        ).group_by(UserProfile.nationality).order_by(
            func.count(UserProfile.id).desc()
        ).limit(10).all()
        
        # Average age
        avg_age_result = self.db.query(
            func.avg(
                func.extract('year', func.age(UserProfile.date_of_birth))
            )
        ).filter(
            UserProfile.date_of_birth.isnot(None)
        ).scalar()
        
        return {
            "gender_distribution": {
                gender.value if gender else "unknown": count 
                for gender, count in gender_dist
            },
            "top_nationalities": [
                {"nationality": nat, "count": count} 
                for nat, count in nationality_dist
            ],
            "average_age": float(avg_age_result) if avg_age_result else None
        }

    # ==================== Preferences Management ====================

    def update_notification_preferences(
        self, 
        user_id: str, 
        preferences: Dict[str, Any]
    ) -> UserProfile:
        """
        Update notification preferences.
        
        Args:
            user_id: User ID
            preferences: Notification preferences dictionary
            
        Returns:
            Updated UserProfile
        """
        profile = self.get_by_user_id(user_id)
        
        current_prefs = profile.notification_preferences or {}
        current_prefs.update(preferences)
        
        profile.notification_preferences = current_prefs
        profile.last_profile_update = datetime.now(timezone.utc)
        
        self.db.commit()
        self.db.refresh(profile)
        
        return profile

    def update_privacy_settings(
        self, 
        user_id: str, 
        settings: Dict[str, Any]
    ) -> UserProfile:
        """
        Update privacy settings.
        
        Args:
            user_id: User ID
            settings: Privacy settings dictionary
            
        Returns:
            Updated UserProfile
        """
        profile = self.get_by_user_id(user_id)
        
        current_settings = profile.privacy_settings or {}
        current_settings.update(settings)
        
        profile.privacy_settings = current_settings
        profile.last_profile_update = datetime.now(timezone.utc)
        
        self.db.commit()
        self.db.refresh(profile)
        
        return profile

    def update_communication_preferences(
        self, 
        user_id: str, 
        preferences: Dict[str, Any]
    ) -> UserProfile:
        """
        Update communication preferences.
        
        Args:
            user_id: User ID
            preferences: Communication preferences dictionary
            
        Returns:
            Updated UserProfile
        """
        profile = self.get_by_user_id(user_id)
        
        current_prefs = profile.communication_preferences or {}
        current_prefs.update(preferences)
        
        profile.communication_preferences = current_prefs
        profile.last_profile_update = datetime.now(timezone.utc)
        
        self.db.commit()
        self.db.refresh(profile)
        
        return profile

    # ==================== Social & Media ====================

    def update_profile_image(self, user_id: str, image_url: str) -> UserProfile:
        """
        Update profile image URL.
        
        Args:
            user_id: User ID
            image_url: New image URL
            
        Returns:
            Updated UserProfile
        """
        profile = self.get_by_user_id(user_id)
        
        profile.profile_image_url = image_url
        profile.last_profile_update = datetime.now(timezone.utc)
        
        self.db.commit()
        self.db.refresh(profile)
        
        return profile

    def update_social_links(
        self, 
        user_id: str, 
        social_links: Dict[str, str]
    ) -> UserProfile:
        """
        Update social media links.
        
        Args:
            user_id: User ID
            social_links: Dictionary of social platform URLs
            
        Returns:
            Updated UserProfile
        """
        profile = self.get_by_user_id(user_id)
        
        current_links = profile.social_links or {}
        current_links.update(social_links)
        
        profile.social_links = current_links
        profile.last_profile_update = datetime.now(timezone.utc)
        
        self.db.commit()
        self.db.refresh(profile)
        
        return profile

    def increment_profile_views(self, user_id: str) -> UserProfile:
        """
        Increment profile view count.
        
        Args:
            user_id: User ID
            
        Returns:
            Updated UserProfile
        """
        profile = self.get_by_user_id(user_id)
        
        profile.profile_views = (profile.profile_views or 0) + 1
        
        self.db.commit()
        self.db.refresh(profile)
        
        return profile

    # ==================== Localization ====================

    def find_by_timezone(self, timezone: str) -> List[UserProfile]:
        """
        Find profiles by timezone.
        
        Args:
            timezone: IANA timezone identifier
            
        Returns:
            List of profiles
        """
        return self.db.query(UserProfile).filter(
            UserProfile.timezone == timezone
        ).all()

    def find_by_language(self, language_code: str) -> List[UserProfile]:
        """
        Find profiles by preferred language.
        
        Args:
            language_code: ISO 639-1 language code
            
        Returns:
            List of profiles
        """
        return self.db.query(UserProfile).filter(
            UserProfile.preferred_language == language_code
        ).all()

    def get_language_distribution(self) -> Dict[str, int]:
        """
        Get distribution of preferred languages.
        
        Returns:
            Dictionary mapping language to count
        """
        results = self.db.query(
            UserProfile.preferred_language,
            func.count(UserProfile.id).label('count')
        ).group_by(UserProfile.preferred_language).all()
        
        return {lang: count for lang, count in results}

    # ==================== Analytics ====================

    def get_profile_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive profile statistics.
        
        Returns:
            Dictionary with profile metrics
        """
        total = self.db.query(func.count(UserProfile.id)).scalar()
        
        with_image = self.db.query(func.count(UserProfile.id)).filter(
            UserProfile.profile_image_url.isnot(None)
        ).scalar()
        
        with_bio = self.db.query(func.count(UserProfile.id)).filter(
            UserProfile.bio.isnot(None)
        ).scalar()
        
        avg_completion = self.db.query(
            func.avg(UserProfile.profile_completion_percentage)
        ).scalar()
        
        return {
            "total_profiles": total,
            "with_profile_image": with_image,
            "with_bio": with_bio,
            "average_completion": float(avg_completion) if avg_completion else 0,
            "image_rate": (with_image / total * 100) if total > 0 else 0,
            "bio_rate": (with_bio / total * 100) if total > 0 else 0
        }

    def find_recently_updated(
        self, 
        days: int = 7,
        limit: int = 50
    ) -> List[UserProfile]:
        """
        Find recently updated profiles.
        
        Args:
            days: Number of days to look back
            limit: Maximum results
            
        Returns:
            List of recently updated profiles
        """
        from datetime import timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        
        return self.db.query(UserProfile).filter(
            UserProfile.last_profile_update >= cutoff
        ).order_by(
            UserProfile.last_profile_update.desc()
        ).limit(limit).all()