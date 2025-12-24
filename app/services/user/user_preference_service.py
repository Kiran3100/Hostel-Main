"""
User Preference Service

Manages user-level preferences (notification settings, quiet hours, etc.).
"""

from __future__ import annotations

from uuid import UUID
from typing import Optional

from sqlalchemy.orm import Session

from app.repositories.notification import NotificationPreferenceRepository
from app.schemas.user import NotificationPreferencesUpdate
from app.models.notification.notification_preferences import NotificationPreference
from app.core.exceptions import ValidationException


class UserPreferenceService:
    """
    High-level service for user preferences.

    Currently focuses on notification preferences stored in notification.NotificationPreference.
    """

    def __init__(
        self,
        notification_pref_repo: NotificationPreferenceRepository,
    ) -> None:
        self.notification_pref_repo = notification_pref_repo

    def get_notification_preferences(
        self,
        db: Session,
        user_id: UUID,
    ) -> Optional[NotificationPreference]:
        """
        Get user notification preferences, or None if not configured.
        """
        return self.notification_pref_repo.get_by_user_id(db, user_id)

    def update_notification_preferences(
        self,
        db: Session,
        user_id: UUID,
        update: NotificationPreferencesUpdate,
    ) -> NotificationPreference:
        """
        Create or update notification preferences for a user.
        """
        existing = self.notification_pref_repo.get_by_user_id(db, user_id)
        data = update.model_dump(exclude_none=True)
        data["user_id"] = user_id

        if existing:
            pref = self.notification_pref_repo.update(db, existing, data)
        else:
            pref = self.notification_pref_repo.create(db, data)

        return pref