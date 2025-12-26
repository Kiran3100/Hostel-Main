"""
Visitor Preference Service

Manages visitor preferences, search preferences, and notification settings.
Provides centralized preference management for personalization.
"""

from __future__ import annotations

import logging
from typing import Optional, Dict, Any
from uuid import UUID
from datetime import datetime

from sqlalchemy.orm import Session

from app.repositories.visitor import (
    VisitorPreferencesRepository,
    SearchPreferencesRepository,
    NotificationPreferencesRepository,
)
from app.schemas.visitor import (
    VisitorPreferences,
    PreferenceUpdate,
    SearchPreferences,
    NotificationPreferences,
)
from app.core.exceptions import (
    ValidationException,
    NotFoundException,
    ServiceException,
)
from app.core.caching import cache_result, invalidate_cache

logger = logging.getLogger(__name__)


class VisitorPreferenceService:
    """
    High-level service for visitor preference management.

    Manages three types of preferences:
    1. General visitor preferences (UI, language, currency, etc.)
    2. Search preferences (default filters, saved criteria)
    3. Notification preferences (channels, frequency, opt-ins)

    Features:
    - Get/set/update preferences with validation
    - Default preference initialization
    - Preference inheritance and merging
    - Cache management for performance
    """

    # Cache TTL for preferences (in seconds)
    CACHE_TTL = 600  # 10 minutes

    def __init__(
        self,
        preferences_repo: VisitorPreferencesRepository,
        search_prefs_repo: SearchPreferencesRepository,
        notification_prefs_repo: NotificationPreferencesRepository,
    ) -> None:
        """
        Initialize the preference service.

        Args:
            preferences_repo: Repository for general visitor preferences
            search_prefs_repo: Repository for search preferences
            notification_prefs_repo: Repository for notification preferences
        """
        self.preferences_repo = preferences_repo
        self.search_prefs_repo = search_prefs_repo
        self.notification_prefs_repo = notification_prefs_repo

    # -------------------------------------------------------------------------
    # General Visitor Preferences
    # -------------------------------------------------------------------------

    @cache_result(ttl=CACHE_TTL, key_prefix="visitor_prefs")
    def get_preferences(
        self,
        db: Session,
        visitor_id: UUID,
        create_if_missing: bool = True,
    ) -> Optional[VisitorPreferences]:
        """
        Get visitor preferences.

        Args:
            db: Database session
            visitor_id: UUID of the visitor
            create_if_missing: If True, create default preferences if none exist

        Returns:
            VisitorPreferences or None if not set and create_if_missing is False

        Raises:
            ServiceException: If retrieval fails
        """
        try:
            prefs = self.preferences_repo.get_by_visitor_id(db, visitor_id)

            if not prefs and create_if_missing:
                logger.info(f"Creating default preferences for visitor {visitor_id}")
                prefs = self._create_default_preferences(db, visitor_id)

            if not prefs:
                return None

            return VisitorPreferences.model_validate(prefs)

        except Exception as e:
            logger.error(
                f"Failed to get preferences for visitor {visitor_id}: {str(e)}",
                exc_info=True
            )
            raise ServiceException(f"Failed to retrieve preferences: {str(e)}")

    @invalidate_cache(key_prefix="visitor_prefs")
    def set_preferences(
        self,
        db: Session,
        visitor_id: UUID,
        preferences: VisitorPreferences,
    ) -> VisitorPreferences:
        """
        Create or completely replace visitor preferences.

        Args:
            db: Database session
            visitor_id: UUID of the visitor
            preferences: Complete preference object

        Returns:
            VisitorPreferences: The created/updated preferences

        Raises:
            ValidationException: If preferences are invalid
            ServiceException: If operation fails
        """
        try:
            # Validate preferences
            self._validate_preferences(preferences)

            existing = self.preferences_repo.get_by_visitor_id(db, visitor_id)

            # Prepare data
            data = preferences.model_dump(exclude_none=True)
            data["visitor_id"] = visitor_id
            data["updated_at"] = datetime.utcnow()

            if existing:
                updated = self.preferences_repo.update(db, existing, data)
                logger.info(f"Updated preferences for visitor {visitor_id}")
            else:
                data["created_at"] = datetime.utcnow()
                updated = self.preferences_repo.create(db, data)
                logger.info(f"Created preferences for visitor {visitor_id}")

            return VisitorPreferences.model_validate(updated)

        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                f"Failed to set preferences for visitor {visitor_id}: {str(e)}",
                exc_info=True
            )
            raise ServiceException(f"Failed to set preferences: {str(e)}")

    @invalidate_cache(key_prefix="visitor_prefs")
    def update_preferences(
        self,
        db: Session,
        visitor_id: UUID,
        update: PreferenceUpdate,
    ) -> VisitorPreferences:
        """
        Partially update visitor preferences.

        Only updates the fields provided in the update object.

        Args:
            db: Database session
            visitor_id: UUID of the visitor
            update: Partial preference updates

        Returns:
            VisitorPreferences: Updated preferences

        Raises:
            ValidationException: If update data is invalid
            ServiceException: If update fails
        """
        try:
            existing = self.preferences_repo.get_by_visitor_id(db, visitor_id)

            if not existing:
                # If no preferences exist, create with the update data
                logger.info(
                    f"No existing preferences for visitor {visitor_id}, creating new"
                )
                full_prefs = VisitorPreferences(**update.model_dump(exclude_none=True))
                return self.set_preferences(db, visitor_id, full_prefs)

            # Validate update data
            update_data = update.model_dump(exclude_none=True)
            if update_data:
                self._validate_preference_update(update_data)

            # Apply updates
            update_data["updated_at"] = datetime.utcnow()
            updated = self.preferences_repo.update(db, existing, update_data)

            logger.info(f"Partially updated preferences for visitor {visitor_id}")

            return VisitorPreferences.model_validate(updated)

        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                f"Failed to update preferences for visitor {visitor_id}: {str(e)}",
                exc_info=True
            )
            raise ServiceException(f"Failed to update preferences: {str(e)}")

    def reset_preferences(
        self,
        db: Session,
        visitor_id: UUID,
    ) -> VisitorPreferences:
        """
        Reset preferences to default values.

        Args:
            db: Database session
            visitor_id: UUID of the visitor

        Returns:
            VisitorPreferences: Reset preferences

        Raises:
            ServiceException: If reset fails
        """
        try:
            existing = self.preferences_repo.get_by_visitor_id(db, visitor_id)

            if existing:
                # Delete existing and recreate defaults
                self.preferences_repo.delete(db, existing)
                logger.info(f"Deleted existing preferences for visitor {visitor_id}")

            default_prefs = self._create_default_preferences(db, visitor_id)

            logger.info(f"Reset preferences to defaults for visitor {visitor_id}")

            return VisitorPreferences.model_validate(default_prefs)

        except Exception as e:
            logger.error(
                f"Failed to reset preferences for visitor {visitor_id}: {str(e)}",
                exc_info=True
            )
            raise ServiceException(f"Failed to reset preferences: {str(e)}")

    # -------------------------------------------------------------------------
    # Search Preferences
    # -------------------------------------------------------------------------

    @cache_result(ttl=CACHE_TTL, key_prefix="search_prefs")
    def get_search_preferences(
        self,
        db: Session,
        visitor_id: UUID,
        create_if_missing: bool = False,
    ) -> Optional[SearchPreferences]:
        """
        Get visitor-level search preferences.

        These serve as default search criteria templates.

        Args:
            db: Database session
            visitor_id: UUID of the visitor
            create_if_missing: If True, create empty preferences if none exist

        Returns:
            SearchPreferences or None

        Raises:
            ServiceException: If retrieval fails
        """
        try:
            prefs = self.search_prefs_repo.get_by_visitor_id(db, visitor_id)

            if not prefs and create_if_missing:
                logger.info(f"Creating default search preferences for visitor {visitor_id}")
                prefs = self._create_default_search_preferences(db, visitor_id)

            if not prefs:
                return None

            return SearchPreferences.model_validate(prefs)

        except Exception as e:
            logger.error(
                f"Failed to get search preferences for visitor {visitor_id}: {str(e)}",
                exc_info=True
            )
            raise ServiceException(f"Failed to retrieve search preferences: {str(e)}")

    @invalidate_cache(key_prefix="search_prefs")
    def save_search_preferences(
        self,
        db: Session,
        visitor_id: UUID,
        search_prefs: SearchPreferences,
    ) -> SearchPreferences:
        """
        Create or update search preferences.

        Args:
            db: Database session
            visitor_id: UUID of the visitor
            search_prefs: Search preference data

        Returns:
            SearchPreferences: Created/updated preferences

        Raises:
            ValidationException: If preferences are invalid
            ServiceException: If operation fails
        """
        try:
            # Validate search preferences
            self._validate_search_preferences(search_prefs)

            existing = self.search_prefs_repo.get_by_visitor_id(db, visitor_id)

            # Prepare data
            data = search_prefs.model_dump(exclude_none=True)
            data["visitor_id"] = visitor_id
            data["updated_at"] = datetime.utcnow()

            if existing:
                updated = self.search_prefs_repo.update(db, existing, data)
                logger.info(f"Updated search preferences for visitor {visitor_id}")
            else:
                data["created_at"] = datetime.utcnow()
                updated = self.search_prefs_repo.create(db, data)
                logger.info(f"Created search preferences for visitor {visitor_id}")

            return SearchPreferences.model_validate(updated)

        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                f"Failed to save search preferences for visitor {visitor_id}: {str(e)}",
                exc_info=True
            )
            raise ServiceException(f"Failed to save search preferences: {str(e)}")

    @invalidate_cache(key_prefix="search_prefs")
    def clear_search_preferences(
        self,
        db: Session,
        visitor_id: UUID,
    ) -> None:
        """
        Clear search preferences for a visitor.

        Args:
            db: Database session
            visitor_id: UUID of the visitor

        Raises:
            ServiceException: If deletion fails
        """
        try:
            existing = self.search_prefs_repo.get_by_visitor_id(db, visitor_id)

            if existing:
                self.search_prefs_repo.delete(db, existing)
                logger.info(f"Cleared search preferences for visitor {visitor_id}")

        except Exception as e:
            logger.error(
                f"Failed to clear search preferences for visitor {visitor_id}: {str(e)}",
                exc_info=True
            )
            raise ServiceException(f"Failed to clear search preferences: {str(e)}")

    # -------------------------------------------------------------------------
    # Notification Preferences
    # -------------------------------------------------------------------------

    @cache_result(ttl=CACHE_TTL, key_prefix="notification_prefs")
    def get_notification_preferences(
        self,
        db: Session,
        visitor_id: UUID,
        create_if_missing: bool = True,
    ) -> Optional[NotificationPreferences]:
        """
        Get notification preferences for a visitor.

        Args:
            db: Database session
            visitor_id: UUID of the visitor
            create_if_missing: If True, create defaults if none exist

        Returns:
            NotificationPreferences or None

        Raises:
            ServiceException: If retrieval fails
        """
        try:
            prefs = self.notification_prefs_repo.get_by_visitor_id(db, visitor_id)

            if not prefs and create_if_missing:
                logger.info(
                    f"Creating default notification preferences for visitor {visitor_id}"
                )
                prefs = self._create_default_notification_preferences(db, visitor_id)

            if not prefs:
                return None

            return NotificationPreferences.model_validate(prefs)

        except Exception as e:
            logger.error(
                f"Failed to get notification preferences for visitor {visitor_id}: {str(e)}",
                exc_info=True
            )
            raise ServiceException(
                f"Failed to retrieve notification preferences: {str(e)}"
            )

    @invalidate_cache(key_prefix="notification_prefs")
    def update_notification_preferences(
        self,
        db: Session,
        visitor_id: UUID,
        preferences: NotificationPreferences,
    ) -> NotificationPreferences:
        """
        Update notification preferences for a visitor.

        Args:
            db: Database session
            visitor_id: UUID of the visitor
            preferences: Notification preference data

        Returns:
            NotificationPreferences: Updated preferences

        Raises:
            ValidationException: If preferences are invalid
            ServiceException: If update fails
        """
        try:
            # Validate notification preferences
            self._validate_notification_preferences(preferences)

            existing = self.notification_prefs_repo.get_by_visitor_id(db, visitor_id)

            # Prepare data
            data = preferences.model_dump(exclude_none=True)
            data["visitor_id"] = visitor_id
            data["updated_at"] = datetime.utcnow()

            if existing:
                updated = self.notification_prefs_repo.update(db, existing, data)
                logger.info(f"Updated notification preferences for visitor {visitor_id}")
            else:
                data["created_at"] = datetime.utcnow()
                updated = self.notification_prefs_repo.create(db, data)
                logger.info(f"Created notification preferences for visitor {visitor_id}")

            return NotificationPreferences.model_validate(updated)

        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                f"Failed to update notification preferences for visitor {visitor_id}: {str(e)}",
                exc_info=True
            )
            raise ServiceException(
                f"Failed to update notification preferences: {str(e)}"
            )

    def opt_out_all_notifications(
        self,
        db: Session,
        visitor_id: UUID,
    ) -> NotificationPreferences:
        """
        Opt out of all notifications.

        Args:
            db: Database session
            visitor_id: UUID of the visitor

        Returns:
            NotificationPreferences: Updated preferences with all disabled

        Raises:
            ServiceException: If operation fails
        """
        try:
            opt_out_prefs = NotificationPreferences(
                email_enabled=False,
                sms_enabled=False,
                push_enabled=False,
                marketing_enabled=False,
                transactional_enabled=True,  # Keep transactional for legal reasons
            )

            result = self.update_notification_preferences(db, visitor_id, opt_out_prefs)

            logger.info(f"Visitor {visitor_id} opted out of all notifications")

            return result

        except Exception as e:
            logger.error(
                f"Failed to opt out notifications for visitor {visitor_id}: {str(e)}",
                exc_info=True
            )
            raise ServiceException(f"Failed to opt out of notifications: {str(e)}")

    # -------------------------------------------------------------------------
    # Bulk Operations
    # -------------------------------------------------------------------------

    def get_all_preferences(
        self,
        db: Session,
        visitor_id: UUID,
    ) -> Dict[str, Any]:
        """
        Get all preference types for a visitor in one call.

        Args:
            db: Database session
            visitor_id: UUID of the visitor

        Returns:
            Dictionary with all preference types

        Raises:
            ServiceException: If retrieval fails
        """
        try:
            return {
                "visitor_preferences": self.get_preferences(db, visitor_id),
                "search_preferences": self.get_search_preferences(db, visitor_id),
                "notification_preferences": self.get_notification_preferences(
                    db, visitor_id
                ),
                "visitor_id": str(visitor_id),
                "retrieved_at": datetime.utcnow(),
            }

        except Exception as e:
            logger.error(
                f"Failed to get all preferences for visitor {visitor_id}: {str(e)}",
                exc_info=True
            )
            raise ServiceException(f"Failed to retrieve all preferences: {str(e)}")

    # -------------------------------------------------------------------------
    # Validation Helpers
    # -------------------------------------------------------------------------

    def _validate_preferences(self, preferences: VisitorPreferences) -> None:
        """
        Validate general visitor preferences.

        Args:
            preferences: Preferences to validate

        Raises:
            ValidationException: If validation fails
        """
        # Validate language code
        if preferences.language:
            valid_languages = ["en", "es", "fr", "de", "it", "pt", "zh", "ja", "ko"]
            if preferences.language not in valid_languages:
                raise ValidationException(
                    f"Invalid language code. Must be one of: {valid_languages}"
                )

        # Validate currency code
        if preferences.currency:
            valid_currencies = ["USD", "EUR", "GBP", "JPY", "CNY", "INR", "AUD", "CAD"]
            if preferences.currency not in valid_currencies:
                raise ValidationException(
                    f"Invalid currency code. Must be one of: {valid_currencies}"
                )

        # Validate timezone
        if preferences.timezone:
            # Basic timezone validation
            if not preferences.timezone.startswith(("UTC", "America/", "Europe/", "Asia/", "Africa/", "Australia/")):
                raise ValidationException("Invalid timezone format")

    def _validate_preference_update(self, update_data: Dict[str, Any]) -> None:
        """
        Validate preference update data.

        Args:
            update_data: Update data dictionary

        Raises:
            ValidationException: If validation fails
        """
        # Add specific validation for partial updates
        if "language" in update_data:
            valid_languages = ["en", "es", "fr", "de", "it", "pt", "zh", "ja", "ko"]
            if update_data["language"] not in valid_languages:
                raise ValidationException(f"Invalid language code")

        if "currency" in update_data:
            valid_currencies = ["USD", "EUR", "GBP", "JPY", "CNY", "INR", "AUD", "CAD"]
            if update_data["currency"] not in valid_currencies:
                raise ValidationException(f"Invalid currency code")

    def _validate_search_preferences(self, search_prefs: SearchPreferences) -> None:
        """
        Validate search preferences.

        Args:
            search_prefs: Search preferences to validate

        Raises:
            ValidationException: If validation fails
        """
        # Validate price range
        if search_prefs.min_price is not None and search_prefs.max_price is not None:
            if search_prefs.min_price > search_prefs.max_price:
                raise ValidationException("min_price cannot be greater than max_price")

            if search_prefs.min_price < 0:
                raise ValidationException("min_price cannot be negative")

        # Validate guest count
        if search_prefs.guests is not None:
            if search_prefs.guests < 1 or search_prefs.guests > 20:
                raise ValidationException("guests must be between 1 and 20")

        # Validate date range
        if search_prefs.check_in and search_prefs.check_out:
            if search_prefs.check_in >= search_prefs.check_out:
                raise ValidationException("check_in must be before check_out")

    def _validate_notification_preferences(
        self, preferences: NotificationPreferences
    ) -> None:
        """
        Validate notification preferences.

        Args:
            preferences: Notification preferences to validate

        Raises:
            ValidationException: If validation fails
        """
        # Ensure at least transactional notifications are enabled
        if not preferences.transactional_enabled:
            logger.warning("Transactional notifications should remain enabled")
            # Don't raise error, just warn

        # Validate frequency if provided
        if hasattr(preferences, 'notification_frequency'):
            valid_frequencies = ["instant", "daily", "weekly", "monthly"]
            if preferences.notification_frequency not in valid_frequencies:
                raise ValidationException(
                    f"Invalid notification frequency. Must be one of: {valid_frequencies}"
                )

    # -------------------------------------------------------------------------
    # Default Creation Helpers
    # -------------------------------------------------------------------------

    def _create_default_preferences(
        self,
        db: Session,
        visitor_id: UUID,
    ) -> Any:
        """
        Create default visitor preferences.

        Args:
            db: Database session
            visitor_id: UUID of the visitor

        Returns:
            Created preference object
        """
        default_data = {
            "visitor_id": visitor_id,
            "language": "en",
            "currency": "USD",
            "timezone": "UTC",
            "theme": "light",
            "email_notifications": True,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }

        return self.preferences_repo.create(db, default_data)

    def _create_default_search_preferences(
        self,
        db: Session,
        visitor_id: UUID,
    ) -> Any:
        """
        Create default search preferences.

        Args:
            db: Database session
            visitor_id: UUID of the visitor

        Returns:
            Created search preference object
        """
        default_data = {
            "visitor_id": visitor_id,
            "search_name": "Default Search",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }

        return self.search_prefs_repo.create(db, default_data)

    def _create_default_notification_preferences(
        self,
        db: Session,
        visitor_id: UUID,
    ) -> Any:
        """
        Create default notification preferences.

        Args:
            db: Database session
            visitor_id: UUID of the visitor

        Returns:
            Created notification preference object
        """
        default_data = {
            "visitor_id": visitor_id,
            "email_enabled": True,
            "sms_enabled": False,
            "push_enabled": True,
            "marketing_enabled": True,
            "transactional_enabled": True,
            "notification_frequency": "instant",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }

        return self.notification_prefs_repo.create(db, default_data)