"""
Visitor Preference Service

Manages visitor preferences and search preferences.
"""

from __future__ import annotations

from typing import Optional
from uuid import UUID

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
    SavedSearch,
)
from app.core.exceptions import ValidationException


class VisitorPreferenceService:
    """
    High-level service for visitor preferences:

    - Get/update visitor preferences
    - Get/update search preferences
    - Get/update notification preferences (visitor-specific)
    """

    def __init__(
        self,
        preferences_repo: VisitorPreferencesRepository,
        search_prefs_repo: SearchPreferencesRepository,
        notification_prefs_repo: NotificationPreferencesRepository,
    ) -> None:
        self.preferences_repo = preferences_repo
        self.search_prefs_repo = search_prefs_repo
        self.notification_prefs_repo = notification_prefs_repo

    # -------------------------------------------------------------------------
    # Visitor preferences
    # -------------------------------------------------------------------------

    def get_preferences(
        self,
        db: Session,
        visitor_id: UUID,
    ) -> Optional[VisitorPreferences]:
        """
        Get visitor preferences, or None if not set.
        """
        prefs = self.preferences_repo.get_by_visitor_id(db, visitor_id)
        if not prefs:
            return None
        return VisitorPreferences.model_validate(prefs)

    def set_preferences(
        self,
        db: Session,
        visitor_id: UUID,
        preferences: VisitorPreferences,
    ) -> VisitorPreferences:
        """
        Create or replace visitor preferences.
        """
        existing = self.preferences_repo.get_by_visitor_id(db, visitor_id)
        data = preferences.model_dump(exclude_none=True)
        data["visitor_id"] = visitor_id

        if existing:
            updated = self.preferences_repo.update(db, existing, data)
        else:
            updated = self.preferences_repo.create(db, data)

        return VisitorPreferences.model_validate(updated)

    def update_preferences(
        self,
        db: Session,
        visitor_id: UUID,
        update: PreferenceUpdate,
    ) -> VisitorPreferences:
        """
        Partially update visitor preferences.
        """
        existing = self.preferences_repo.get_by_visitor_id(db, visitor_id)
        if not existing:
            # If no prefs yet, treat as set
            return self.set_preferences(
                db, visitor_id, VisitorPreferences(**update.model_dump(exclude_none=True))
            )

        data = update.model_dump(exclude_none=True)
        updated = self.preferences_repo.update(db, existing, data)
        return VisitorPreferences.model_validate(updated)

    # -------------------------------------------------------------------------
    # Search preferences
    # -------------------------------------------------------------------------

    def get_search_preferences(
        self,
        db: Session,
        visitor_id: UUID,
    ) -> Optional[SearchPreferences]:
        """
        Get visitor-level search preferences (lightweight saved search template).
        """
        prefs = self.search_prefs_repo.get_by_visitor_id(db, visitor_id)
        if not prefs:
            return None
        return SearchPreferences.model_validate(prefs)

    def save_search_preferences(
        self,
        db: Session,
        visitor_id: UUID,
        search_prefs: SearchPreferences,
    ) -> SearchPreferences:
        """
        Create or update search preferences.
        """
        existing = self.search_prefs_repo.get_by_visitor_id(db, visitor_id)
        data = search_prefs.model_dump(exclude_none=True)
        data["visitor_id"] = visitor_id

        if existing:
            updated = self.search_prefs_repo.update(db, existing, data)
        else:
            updated = self.search_prefs_repo.create(db, data)

        return SearchPreferences.model_validate(updated)