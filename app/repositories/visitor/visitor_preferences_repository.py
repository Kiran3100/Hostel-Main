# --- File: app/repositories/visitor/visitor_preferences_repository.py ---
"""
Visitor preferences repository for detailed preference management.

This module provides repository operations for visitor preferences including
search criteria, notification settings, and personalization.
"""

from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.models.visitor.visitor_preferences import (
    NotificationPreferences,
    SearchPreferences,
    VisitorPreferences,
)
from app.repositories.base.base_repository import BaseRepository


class VisitorPreferencesRepository(BaseRepository[VisitorPreferences]):
    """
    Repository for VisitorPreferences entity.
    
    Provides comprehensive preference management for personalization
    and search optimization.
    """

    def __init__(self, session: Session):
        super().__init__(VisitorPreferences, session)

    def create_preferences(
        self,
        visitor_id: UUID,
        **preferences_data,
    ) -> VisitorPreferences:
        """
        Create visitor preferences.
        
        Args:
            visitor_id: Visitor ID
            **preferences_data: Preference fields
            
        Returns:
            Created VisitorPreferences instance
        """
        preferences = VisitorPreferences(
            visitor_id=visitor_id,
            **preferences_data
        )
        
        self.session.add(preferences)
        self.session.flush()
        
        return preferences

    def find_by_visitor_id(self, visitor_id: UUID) -> Optional[VisitorPreferences]:
        """
        Find preferences by visitor ID.
        
        Args:
            visitor_id: Visitor ID
            
        Returns:
            VisitorPreferences instance if found
        """
        query = select(VisitorPreferences).where(
            and_(
                VisitorPreferences.visitor_id == visitor_id,
                VisitorPreferences.is_deleted == False,
            )
        )
        
        result = self.session.execute(query)
        return result.scalar_one_or_none()

    def update_budget_preferences(
        self,
        visitor_id: UUID,
        budget_min: Optional[Decimal] = None,
        budget_max: Optional[Decimal] = None,
    ) -> VisitorPreferences:
        """
        Update budget preferences.
        
        Args:
            visitor_id: Visitor ID
            budget_min: Minimum budget
            budget_max: Maximum budget
            
        Returns:
            Updated VisitorPreferences instance
        """
        preferences = self.find_by_visitor_id(visitor_id)
        if not preferences:
            raise ValueError(f"Preferences not found for visitor: {visitor_id}")
        
        if budget_min is not None:
            preferences.budget_min = budget_min
        if budget_max is not None:
            preferences.budget_max = budget_max
        
        self._track_preference_update(preferences, ["budget_min", "budget_max"])
        
        self.session.flush()
        return preferences

    def update_location_preferences(
        self,
        visitor_id: UUID,
        preferred_cities: Optional[List[str]] = None,
        preferred_areas: Optional[List[str]] = None,
        max_distance_from_work_km: Optional[Decimal] = None,
    ) -> VisitorPreferences:
        """
        Update location preferences.
        
        Args:
            visitor_id: Visitor ID
            preferred_cities: Preferred cities list
            preferred_areas: Preferred areas list
            max_distance_from_work_km: Maximum distance from work
            
        Returns:
            Updated VisitorPreferences instance
        """
        preferences = self.find_by_visitor_id(visitor_id)
        if not preferences:
            raise ValueError(f"Preferences not found for visitor: {visitor_id}")
        
        updated_fields = []
        
        if preferred_cities is not None:
            preferences.preferred_cities = preferred_cities
            updated_fields.append("preferred_cities")
        
        if preferred_areas is not None:
            preferences.preferred_areas = preferred_areas
            updated_fields.append("preferred_areas")
        
        if max_distance_from_work_km is not None:
            preferences.max_distance_from_work_km = max_distance_from_work_km
            updated_fields.append("max_distance_from_work_km")
        
        self._track_preference_update(preferences, updated_fields)
        
        self.session.flush()
        return preferences

    def update_amenity_preferences(
        self,
        visitor_id: UUID,
        required_amenities: Optional[List[str]] = None,
        preferred_amenities: Optional[List[str]] = None,
    ) -> VisitorPreferences:
        """
        Update amenity preferences.
        
        Args:
            visitor_id: Visitor ID
            required_amenities: Required amenities
            preferred_amenities: Preferred amenities
            
        Returns:
            Updated VisitorPreferences instance
        """
        preferences = self.find_by_visitor_id(visitor_id)
        if not preferences:
            raise ValueError(f"Preferences not found for visitor: {visitor_id}")
        
        updated_fields = []
        
        if required_amenities is not None:
            preferences.required_amenities = required_amenities
            updated_fields.append("required_amenities")
        
        if preferred_amenities is not None:
            preferences.preferred_amenities = preferred_amenities
            updated_fields.append("preferred_amenities")
        
        self._track_preference_update(preferences, updated_fields)
        
        self.session.flush()
        return preferences

    def update_facility_requirements(
        self,
        visitor_id: UUID,
        need_parking: Optional[bool] = None,
        need_gym: Optional[bool] = None,
        need_laundry: Optional[bool] = None,
        need_mess: Optional[bool] = None,
    ) -> VisitorPreferences:
        """
        Update facility requirements.
        
        Args:
            visitor_id: Visitor ID
            need_parking: Parking requirement
            need_gym: Gym requirement
            need_laundry: Laundry requirement
            need_mess: Mess requirement
            
        Returns:
            Updated VisitorPreferences instance
        """
        preferences = self.find_by_visitor_id(visitor_id)
        if not preferences:
            raise ValueError(f"Preferences not found for visitor: {visitor_id}")
        
        updated_fields = []
        
        if need_parking is not None:
            preferences.need_parking = need_parking
            updated_fields.append("need_parking")
        
        if need_gym is not None:
            preferences.need_gym = need_gym
            updated_fields.append("need_gym")
        
        if need_laundry is not None:
            preferences.need_laundry = need_laundry
            updated_fields.append("need_laundry")
        
        if need_mess is not None:
            preferences.need_mess = need_mess
            updated_fields.append("need_mess")
        
        self._track_preference_update(preferences, updated_fields)
        
        self.session.flush()
        return preferences

    def update_notification_preferences(
        self,
        visitor_id: UUID,
        email_notifications: Optional[bool] = None,
        sms_notifications: Optional[bool] = None,
        push_notifications: Optional[bool] = None,
        notify_on_price_drop: Optional[bool] = None,
        notify_on_availability: Optional[bool] = None,
        notify_on_new_listings: Optional[bool] = None,
    ) -> VisitorPreferences:
        """
        Update notification preferences.
        
        Args:
            visitor_id: Visitor ID
            email_notifications: Email notifications enabled
            sms_notifications: SMS notifications enabled
            push_notifications: Push notifications enabled
            notify_on_price_drop: Notify on price drops
            notify_on_availability: Notify on availability
            notify_on_new_listings: Notify on new listings
            
        Returns:
            Updated VisitorPreferences instance
        """
        preferences = self.find_by_visitor_id(visitor_id)
        if not preferences:
            raise ValueError(f"Preferences not found for visitor: {visitor_id}")
        
        updated_fields = []
        
        if email_notifications is not None:
            preferences.email_notifications = email_notifications
            updated_fields.append("email_notifications")
        
        if sms_notifications is not None:
            preferences.sms_notifications = sms_notifications
            updated_fields.append("sms_notifications")
        
        if push_notifications is not None:
            preferences.push_notifications = push_notifications
            updated_fields.append("push_notifications")
        
        if notify_on_price_drop is not None:
            preferences.notify_on_price_drop = notify_on_price_drop
            updated_fields.append("notify_on_price_drop")
        
        if notify_on_availability is not None:
            preferences.notify_on_availability = notify_on_availability
            updated_fields.append("notify_on_availability")
        
        if notify_on_new_listings is not None:
            preferences.notify_on_new_listings = notify_on_new_listings
            updated_fields.append("notify_on_new_listings")
        
        self._track_preference_update(preferences, updated_fields)
        
        self.session.flush()
        return preferences

    def _track_preference_update(
        self,
        preferences: VisitorPreferences,
        updated_fields: List[str],
    ) -> None:
        """
        Track preference field updates.
        
        Args:
            preferences: VisitorPreferences instance
            updated_fields: List of updated field names
        """
        if updated_fields:
            # Add to last updated fields (keep last 10)
            current_fields = list(preferences.last_updated_fields or [])
            current_fields.extend(updated_fields)
            preferences.last_updated_fields = current_fields[-10:]


class SearchPreferencesRepository(BaseRepository[SearchPreferences]):
    """Repository for SearchPreferences entity."""

    def __init__(self, session: Session):
        super().__init__(SearchPreferences, session)

    def create_search_preference(
        self,
        visitor_id: UUID,
        search_name: str,
        search_criteria: Dict,
        **kwargs,
    ) -> SearchPreferences:
        """
        Create a saved search preference.
        
        Args:
            visitor_id: Visitor ID
            search_name: Name for the search
            search_criteria: Search criteria dictionary
            **kwargs: Additional search preference fields
            
        Returns:
            Created SearchPreferences instance
        """
        search_pref = SearchPreferences(
            visitor_id=visitor_id,
            search_name=search_name,
            search_criteria=search_criteria,
            **kwargs
        )
        
        self.session.add(search_pref)
        self.session.flush()
        
        return search_pref

    def find_active_searches(
        self,
        visitor_id: UUID,
    ) -> List[SearchPreferences]:
        """
        Find active search preferences for visitor.
        
        Args:
            visitor_id: Visitor ID
            
        Returns:
            List of active SearchPreferences
        """
        query = select(SearchPreferences).where(
            and_(
                SearchPreferences.visitor_id == visitor_id,
                SearchPreferences.is_active == True,
                SearchPreferences.is_deleted == False,
            )
        )
        
        result = self.session.execute(query)
        return list(result.scalars().all())

    def update_search_results(
        self,
        search_id: UUID,
        total_matches: int,
        new_matches: int,
    ) -> SearchPreferences:
        """
        Update search preference with new results.
        
        Args:
            search_id: Search preference ID
            total_matches: Total current matches
            new_matches: New matches since last check
            
        Returns:
            Updated SearchPreferences instance
        """
        search_pref = self.find_by_id(search_id)
        if not search_pref:
            raise ValueError(f"Search preference not found: {search_id}")
        
        search_pref.total_matches = total_matches
        search_pref.new_matches_since_last_check = new_matches
        search_pref.last_checked_at = datetime.utcnow()
        
        self.session.flush()
        return search_pref

    def mark_notification_sent(
        self,
        search_id: UUID,
    ) -> SearchPreferences:
        """
        Mark that notification was sent for search.
        
        Args:
            search_id: Search preference ID
            
        Returns:
            Updated SearchPreferences instance
        """
        search_pref = self.find_by_id(search_id)
        if not search_pref:
            raise ValueError(f"Search preference not found: {search_id}")
        
        search_pref.last_notification_sent_at = datetime.utcnow()
        search_pref.new_matches_since_last_check = 0
        
        self.session.flush()
        return search_pref


class NotificationPreferencesRepository(BaseRepository[NotificationPreferences]):
    """Repository for NotificationPreferences entity."""

    def __init__(self, session: Session):
        super().__init__(NotificationPreferences, session)

    def create_notification_preferences(
        self,
        visitor_id: UUID,
        **kwargs,
    ) -> NotificationPreferences:
        """
        Create notification preferences with defaults.
        
        Args:
            visitor_id: Visitor ID
            **kwargs: Override default preference values
            
        Returns:
            Created NotificationPreferences instance
        """
        notif_prefs = NotificationPreferences(
            visitor_id=visitor_id,
            **kwargs
        )
        
        self.session.add(notif_prefs)
        self.session.flush()
        
        return notif_prefs

    def find_by_visitor_id(
        self,
        visitor_id: UUID,
    ) -> Optional[NotificationPreferences]:
        """
        Find notification preferences by visitor ID.
        
        Args:
            visitor_id: Visitor ID
            
        Returns:
            NotificationPreferences instance if found
        """
        query = select(NotificationPreferences).where(
            NotificationPreferences.visitor_id == visitor_id
        )
        
        result = self.session.execute(query)
        return result.scalar_one_or_none()

    def update_channel_preferences(
        self,
        visitor_id: UUID,
        email_enabled: Optional[bool] = None,
        sms_enabled: Optional[bool] = None,
        push_enabled: Optional[bool] = None,
        in_app_enabled: Optional[bool] = None,
    ) -> NotificationPreferences:
        """
        Update notification channel preferences.
        
        Args:
            visitor_id: Visitor ID
            email_enabled: Email notifications enabled
            sms_enabled: SMS notifications enabled
            push_enabled: Push notifications enabled
            in_app_enabled: In-app notifications enabled
            
        Returns:
            Updated NotificationPreferences instance
        """
        prefs = self.find_by_visitor_id(visitor_id)
        if not prefs:
            raise ValueError(f"Notification preferences not found for visitor: {visitor_id}")
        
        if email_enabled is not None:
            prefs.email_enabled = email_enabled
        if sms_enabled is not None:
            prefs.sms_enabled = sms_enabled
        if push_enabled is not None:
            prefs.push_enabled = push_enabled
        if in_app_enabled is not None:
            prefs.in_app_enabled = in_app_enabled
        
        self.session.flush()
        return prefs

    def update_quiet_hours(
        self,
        visitor_id: UUID,
        enabled: bool,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> NotificationPreferences:
        """
        Update quiet hours settings.
        
        Args:
            visitor_id: Visitor ID
            enabled: Quiet hours enabled
            start_time: Start time (HH:MM format)
            end_time: End time (HH:MM format)
            
        Returns:
            Updated NotificationPreferences instance
        """
        prefs = self.find_by_visitor_id(visitor_id)
        if not prefs:
            raise ValueError(f"Notification preferences not found for visitor: {visitor_id}")
        
        prefs.quiet_hours_enabled = enabled
        if start_time is not None:
            prefs.quiet_hours_start = start_time
        if end_time is not None:
            prefs.quiet_hours_end = end_time
        
        self.session.flush()
        return prefs