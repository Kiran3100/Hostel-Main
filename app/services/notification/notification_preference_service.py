# app/services/notification/notification_preference_service.py
"""
Enhanced Notification Preference Service

Manages per-user notification preferences and unsubscribe flows with improved:
- Validation and error handling
- Performance optimizations
- Audit logging
- Default preference management
"""

from __future__ import annotations

import logging
from typing import Optional, Dict, Any
from uuid import UUID
from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.repositories.notification import NotificationPreferenceRepository
from app.schemas.notification import (
    UserPreferences,
    PreferenceUpdate,
    UnsubscribeRequest,
)
from app.core1.exceptions import ValidationException, DatabaseException
from app.core1.logging import LoggingContext

logger = logging.getLogger(__name__)


class NotificationPreferenceService:
    """
    Enhanced high-level service for notification preferences.

    Enhanced with:
    - Comprehensive validation
    - Default preference handling
    - Audit logging
    - Performance optimizations
    - Unsubscribe token management
    """

    def __init__(self, pref_repo: NotificationPreferenceRepository) -> None:
        self.pref_repo = pref_repo
        self._default_preferences = {
            "email_notifications": True,
            "sms_notifications": True,
            "push_notifications": True,
            "in_app_notifications": True,
            "marketing_emails": False,
            "security_alerts": True,
            "booking_updates": True,
            "payment_reminders": True,
            "system_maintenance": True,
        }

    def _validate_preferences(self, prefs: UserPreferences) -> None:
        """Validate preference data."""
        if not prefs.user_id:
            raise ValidationException("User ID is required")
        
        # Validate email format if email_address is provided
        if prefs.email_address and '@' not in prefs.email_address:
            raise ValidationException("Invalid email address format")
        
        # Validate phone format if phone_number is provided
        if prefs.phone_number and len(prefs.phone_number.replace('+', '').replace('-', '').replace(' ', '')) < 10:
            raise ValidationException("Invalid phone number format")

    def _validate_preference_update(self, update: PreferenceUpdate) -> None:
        """Validate preference update data."""
        if update.email_address and '@' not in update.email_address:
            raise ValidationException("Invalid email address format")
        
        if update.phone_number and len(update.phone_number.replace('+', '').replace('-', '').replace(' ', '')) < 10:
            raise ValidationException("Invalid phone number format")

    def _validate_unsubscribe_request(self, request: UnsubscribeRequest) -> None:
        """Validate unsubscribe request."""
        if not request.token and not (request.user_id and request.notification_type):
            raise ValidationException(
                "Either unsubscribe token or user_id + notification_type is required"
            )
        
        if request.notification_type and request.notification_type not in [
            "email", "sms", "push", "all", "marketing"
        ]:
            raise ValidationException(
                "Invalid notification type. Must be: email, sms, push, all, or marketing"
            )

    def get_preferences(
        self,
        db: Session,
        user_id: UUID,
        create_if_missing: bool = True,
    ) -> UserPreferences:
        """
        Get user preferences with optional auto-creation of defaults.

        Enhanced with:
        - Auto-creation of default preferences
        - Input validation
        - Performance optimization

        Args:
            db: Database session
            user_id: User identifier
            create_if_missing: Whether to create default preferences if none exist

        Returns:
            UserPreferences: User preference settings

        Raises:
            ValidationException: For invalid user ID
            DatabaseException: For database operation failures
        """
        if not user_id:
            raise ValidationException("User ID is required")

        with LoggingContext(channel="preferences_get", user_id=str(user_id)):
            try:
                logger.debug(f"Retrieving preferences for user {user_id}")
                
                obj = self.pref_repo.get_by_user_id(db, user_id)
                
                if not obj and create_if_missing:
                    logger.debug("No preferences found, creating defaults")
                    return self._create_default_preferences(db, user_id)
                elif not obj:
                    logger.debug("No preferences found and auto-creation disabled")
                    return self._get_empty_preferences(user_id)
                
                preferences = UserPreferences.model_validate(obj)
                logger.debug("Preferences retrieved successfully")
                
                return preferences
                
            except ValidationException:
                raise
            except SQLAlchemyError as e:
                logger.error(f"Database error retrieving preferences: {str(e)}")
                raise DatabaseException("Failed to retrieve user preferences") from e
            except Exception as e:
                logger.error(f"Unexpected error retrieving preferences: {str(e)}")
                raise

    def set_preferences(
        self,
        db: Session,
        user_id: UUID,
        prefs: UserPreferences,
    ) -> UserPreferences:
        """
        Set user preferences with enhanced validation and audit logging.

        Enhanced with:
        - Comprehensive validation
        - Audit logging
        - Transaction management

        Args:
            db: Database session
            user_id: User identifier
            prefs: Complete preference settings

        Returns:
            UserPreferences: Updated preferences

        Raises:
            ValidationException: For invalid preference data
            DatabaseException: For database operation failures
        """
        if not user_id:
            raise ValidationException("User ID is required")
        
        # Ensure user_id matches
        prefs.user_id = user_id
        self._validate_preferences(prefs)

        with LoggingContext(channel="preferences_set", user_id=str(user_id)):
            try:
                logger.info(f"Setting preferences for user {user_id}")
                
                existing = self.pref_repo.get_by_user_id(db, user_id)
                data = prefs.model_dump(exclude_none=True)
                data["user_id"] = user_id
                data["updated_at"] = datetime.utcnow()

                if existing:
                    # Log the changes for audit trail
                    self._log_preference_changes(existing, data)
                    obj = self.pref_repo.update(db, existing, data)
                else:
                    data["created_at"] = datetime.utcnow()
                    obj = self.pref_repo.create(db, data)

                result = UserPreferences.model_validate(obj)
                logger.info("Preferences set successfully")
                
                return result
                
            except ValidationException:
                raise
            except SQLAlchemyError as e:
                logger.error(f"Database error setting preferences: {str(e)}")
                raise DatabaseException("Failed to set user preferences") from e
            except Exception as e:
                logger.error(f"Unexpected error setting preferences: {str(e)}")
                raise

    def update_preferences(
        self,
        db: Session,
        user_id: UUID,
        update: PreferenceUpdate,
    ) -> UserPreferences:
        """
        Update user preferences with enhanced validation and partial updates.

        Enhanced with:
        - Partial update validation
        - Audit logging
        - Performance optimization

        Args:
            db: Database session
            user_id: User identifier
            update: Partial preference updates

        Returns:
            UserPreferences: Updated preferences

        Raises:
            ValidationException: For invalid update data
            DatabaseException: For database operation failures
        """
        if not user_id:
            raise ValidationException("User ID is required")
        
        self._validate_preference_update(update)

        with LoggingContext(channel="preferences_update", user_id=str(user_id)):
            try:
                logger.info(f"Updating preferences for user {user_id}")
                
                existing = self.pref_repo.get_by_user_id(db, user_id)
                update_data = update.model_dump(exclude_none=True)
                update_data["updated_at"] = datetime.utcnow()
                
                if not existing:
                    logger.debug("No existing preferences, creating with defaults")
                    # Create new preferences with defaults + updates
                    default_prefs = UserPreferences(
                        user_id=user_id,
                        **self._default_preferences,
                        **update_data
                    )
                    return self.set_preferences(db, user_id, default_prefs)

                # Log the changes for audit trail
                self._log_preference_changes(existing, update_data)
                
                obj = self.pref_repo.update(db, existing, update_data)
                
                result = UserPreferences.model_validate(obj)
                logger.info("Preferences updated successfully")
                
                return result
                
            except ValidationException:
                raise
            except SQLAlchemyError as e:
                logger.error(f"Database error updating preferences: {str(e)}")
                raise DatabaseException("Failed to update user preferences") from e
            except Exception as e:
                logger.error(f"Unexpected error updating preferences: {str(e)}")
                raise

    def process_unsubscribe(
        self,
        db: Session,
        request: UnsubscribeRequest,
    ) -> Dict[str, Any]:
        """
        Process unsubscribe request with enhanced validation and logging.

        Enhanced with:
        - Comprehensive validation
        - Detailed result reporting
        - Audit logging
        - Security considerations

        Args:
            db: Database session
            request: Unsubscribe request data

        Returns:
            Dict[str, Any]: Processing result with details

        Raises:
            ValidationException: For invalid request data
            DatabaseException: For database operation failures
        """
        self._validate_unsubscribe_request(request)

        with LoggingContext(
            channel="preferences_unsubscribe",
            token_provided=bool(request.token),
            notification_type=request.notification_type
        ):
            try:
                logger.info(
                    f"Processing unsubscribe request, "
                    f"type: {request.notification_type}, "
                    f"has_token: {bool(request.token)}"
                )
                
                # Process the unsubscribe
                result = self.pref_repo.process_unsubscribe(
                    db, request.model_dump(exclude_none=True)
                )
                
                if result.get("success"):
                    logger.info(
                        f"Unsubscribe processed successfully, "
                        f"user_id: {result.get('user_id')}, "
                        f"type: {result.get('notification_type')}"
                    )
                else:
                    logger.warning(
                        f"Unsubscribe processing failed: {result.get('reason')}"
                    )
                
                return result
                
            except ValidationException:
                raise
            except SQLAlchemyError as e:
                logger.error(f"Database error processing unsubscribe: {str(e)}")
                raise DatabaseException("Failed to process unsubscribe request") from e
            except Exception as e:
                logger.error(f"Unexpected error processing unsubscribe: {str(e)}")
                raise

    # -------------------------------------------------------------------------
    # Utility methods
    # -------------------------------------------------------------------------

    def _create_default_preferences(
        self,
        db: Session,
        user_id: UUID,
    ) -> UserPreferences:
        """Create default preferences for a user."""
        default_prefs = UserPreferences(
            user_id=user_id,
            **self._default_preferences
        )
        return self.set_preferences(db, user_id, default_prefs)

    def _get_empty_preferences(self, user_id: UUID) -> UserPreferences:
        """Get empty preferences object."""
        return UserPreferences(
            user_id=user_id,
            **{k: False for k in self._default_preferences.keys()}
        )

    def _log_preference_changes(
        self,
        existing: Any,
        new_data: Dict[str, Any]
    ) -> None:
        """Log preference changes for audit trail."""
        try:
            changes = []
            for key, new_value in new_data.items():
                if hasattr(existing, key):
                    old_value = getattr(existing, key)
                    if old_value != new_value:
                        changes.append(f"{key}: {old_value} -> {new_value}")
            
            if changes:
                logger.info(f"Preference changes: {', '.join(changes)}")
        except Exception as e:
            logger.debug(f"Failed to log preference changes: {str(e)}")

    def generate_unsubscribe_token(
        self,
        db: Session,
        user_id: UUID,
        notification_type: str,
        expires_hours: int = 72,
    ) -> str:
        """
        Generate a secure unsubscribe token.

        Args:
            db: Database session
            user_id: User identifier
            notification_type: Type of notifications to unsubscribe from
            expires_hours: Token expiration in hours

        Returns:
            str: Secure unsubscribe token

        Raises:
            ValidationException: For invalid parameters
            DatabaseException: For database operation failures
        """
        if not user_id:
            raise ValidationException("User ID is required")
        
        if notification_type not in ["email", "sms", "push", "all", "marketing"]:
            raise ValidationException("Invalid notification type")

        with LoggingContext(
            channel="unsubscribe_token_generate",
            user_id=str(user_id),
            notification_type=notification_type
        ):
            try:
                logger.info(f"Generating unsubscribe token for user {user_id}")
                
                token = self.pref_repo.generate_unsubscribe_token(
                    db=db,
                    user_id=user_id,
                    notification_type=notification_type,
                    expires_hours=expires_hours,
                )
                
                logger.info("Unsubscribe token generated successfully")
                return token
                
            except SQLAlchemyError as e:
                logger.error(f"Database error generating token: {str(e)}")
                raise DatabaseException("Failed to generate unsubscribe token") from e
            except Exception as e:
                logger.error(f"Unexpected error generating token: {str(e)}")
                raise

    def get_preference_summary(
        self,
        db: Session,
        user_id: UUID,
    ) -> Dict[str, Any]:
        """
        Get a summary of user's notification preferences.

        Args:
            db: Database session
            user_id: User identifier

        Returns:
            Dict[str, Any]: Preference summary

        Raises:
            ValidationException: For invalid user ID
            DatabaseException: For database operation failures
        """
        if not user_id:
            raise ValidationException("User ID is required")

        with LoggingContext(channel="preferences_summary", user_id=str(user_id)):
            try:
                logger.debug(f"Getting preference summary for user {user_id}")
                
                prefs = self.get_preferences(db, user_id)
                
                summary = {
                    "user_id": str(user_id),
                    "email_enabled": prefs.email_notifications,
                    "sms_enabled": prefs.sms_notifications,
                    "push_enabled": prefs.push_notifications,
                    "in_app_enabled": prefs.in_app_notifications,
                    "marketing_enabled": prefs.marketing_emails,
                    "contact_email": prefs.email_address,
                    "contact_phone": prefs.phone_number,
                    "last_updated": prefs.updated_at.isoformat() if prefs.updated_at else None,
                }
                
                logger.debug("Preference summary generated")
                return summary
                
            except ValidationException:
                raise
            except SQLAlchemyError as e:
                logger.error(f"Database error getting summary: {str(e)}")
                raise DatabaseException("Failed to get preference summary") from e
            except Exception as e:
                logger.error(f"Unexpected error getting summary: {str(e)}")
                raise