# app/services/notification/preference_service.py
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, Protocol
from uuid import UUID, uuid4

from app.schemas.notification.notification_preferences import (
    UserPreferences,
    FrequencySettings,
    PreferenceUpdate,
    UnsubscribeRequest,
)
from app.services.common import errors


class PreferenceStore(Protocol):
    """
    Storage abstraction for per-user notification preferences.
    """

    def get_preferences(self, user_id: UUID) -> Optional[dict]: ...
    def save_preferences(self, user_id: UUID, data: dict) -> None: ...


class PreferenceService:
    """
    Manage per-user notification preferences.

    - Get or create default UserPreferences
    - Update preferences
    - Handle unsubscribe requests
    """

    def __init__(self, store: PreferenceStore) -> None:
        self._store = store

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _default_preferences(self, user_id: UUID) -> UserPreferences:
        now = self._now()
        freq = FrequencySettings(
            id=uuid4(),
            created_at=now,
            updated_at=now,
            immediate_notifications=True,
            batch_notifications=False,
            batch_interval_hours=4,
            daily_digest_time=None,
            weekly_digest_day=None,
        )
        return UserPreferences(
            id=uuid4(),
            created_at=now,
            updated_at=now,
            user_id=user_id,
            notifications_enabled=True,
            email_enabled=True,
            sms_enabled=True,
            push_enabled=True,
            frequency_settings=freq,
            quiet_hours_enabled=False,
            quiet_hours_start=None,
            quiet_hours_end=None,
            payment_notifications=True,
            booking_notifications=True,
            complaint_notifications=True,
            announcement_notifications=True,
            maintenance_notifications=True,
            attendance_notifications=True,
            marketing_notifications=False,
        )

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def get_preferences(self, user_id: UUID) -> UserPreferences:
        record = self._store.get_preferences(user_id)
        if record:
            return UserPreferences.model_validate(record)

        prefs = self._default_preferences(user_id)
        self._store.save_preferences(user_id, prefs.model_dump())
        return prefs

    def update_preferences(
        self,
        user_id: UUID,
        data: PreferenceUpdate,
    ) -> UserPreferences:
        prefs = self.get_preferences(user_id)
        mapping = data.model_dump(exclude_unset=True)
        for field, value in mapping.items():
            if hasattr(prefs, field):
                setattr(prefs, field, value)
        prefs.updated_at = self._now()
        self._store.save_preferences(user_id, prefs.model_dump())
        return prefs

    def unsubscribe(self, req: UnsubscribeRequest) -> UserPreferences:
        """
        Handle unsubscribe requests at various levels.
        """
        prefs = self.get_preferences(req.user_id)

        if req.unsubscribe_type == "all":
            prefs.notifications_enabled = False
            prefs.email_enabled = False
            prefs.sms_enabled = False
            prefs.push_enabled = False
            prefs.marketing_notifications = False
        elif req.unsubscribe_type == "email":
            prefs.email_enabled = False
            prefs.marketing_notifications = False
        elif req.unsubscribe_type == "sms":
            prefs.sms_enabled = False
        elif req.unsubscribe_type == "marketing":
            prefs.marketing_notifications = False
        elif req.unsubscribe_type == "specific_category":
            cat = (req.category or "").lower()
            if cat == "payment":
                prefs.payment_notifications = False
            elif cat == "booking":
                prefs.booking_notifications = False
            elif cat == "complaint":
                prefs.complaint_notifications = False
            elif cat == "announcement":
                prefs.announcement_notifications = False
            elif cat == "maintenance":
                prefs.maintenance_notifications = False
            elif cat == "attendance":
                prefs.attendance_notifications = False
        else:
            raise errors.ValidationError("Unknown unsubscribe_type")

        prefs.updated_at = self._now()
        self._store.save_preferences(req.user_id, prefs.model_dump())
        return prefs