# --- File: C:\Hostel-Main\app\repositories\notification\notification_preferences_repository.py ---
"""
Notification Preferences Repository for user preference management.

Handles user notification settings, channel preferences, quiet hours,
and unsubscribe management with comprehensive analytics.
"""

from datetime import datetime, timedelta, time
from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID

from sqlalchemy import and_, or_, func, desc, asc, case, text
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy.sql import select

from app.models.notification.notification_preferences import (
    NotificationPreference,
    ChannelPreference,
    UnsubscribeToken
)
from app.models.user.user import User
from app.repositories.base.base_repository import BaseRepository
from app.repositories.base.specifications import Specification
from app.repositories.base.pagination import PaginationParams, PaginatedResult


class ActivePreferencesSpec(Specification):
    """Specification for users with notifications enabled."""
    
    def is_satisfied_by(self, query):
        return query.filter(NotificationPreference.notifications_enabled == True)


class QuietHoursEnabledSpec(Specification):
    """Specification for users with quiet hours enabled."""
    
    def is_satisfied_by(self, query):
        return query.filter(NotificationPreference.quiet_hours_enabled == True)


class NotificationPreferencesRepository(BaseRepository[NotificationPreference]):
    """
    Repository for notification preference management with user settings analytics.
    """

    def __init__(self, db_session: Session):
        super().__init__(NotificationPreference, db_session)

    # Core preference operations
    def get_or_create_preferences(self, user_id: UUID) -> NotificationPreference:
        """Get existing preferences or create default ones for user."""
        preferences = self.db_session.query(NotificationPreference).filter(
            NotificationPreference.user_id == user_id
        ).options(
            selectinload(NotificationPreference.channel_preferences)
        ).first()
        
        if not preferences:
            preferences = self._create_default_preferences(user_id)
        
        return preferences

    def update_global_settings(
        self,
        user_id: UUID,
        settings: Dict[str, Any]
    ) -> bool:
        """Update global notification settings for user."""
        preferences = self.get_or_create_preferences(user_id)
        
        # Update allowed fields
        allowed_fields = [
            'notifications_enabled', 'email_enabled', 'sms_enabled', 
            'push_enabled', 'in_app_enabled', 'payment_notifications',
            'booking_notifications', 'complaint_notifications',
            'announcement_notifications', 'maintenance_notifications',
            'attendance_notifications', 'marketing_notifications',
            'immediate_notifications', 'batch_notifications',
            'batch_interval_hours', 'preferred_language', 'timezone'
        ]
        
        updated = False
        for field, value in settings.items():
            if field in allowed_fields and hasattr(preferences, field):
                if getattr(preferences, field) != value:
                    setattr(preferences, field, value)
                    updated = True
        
        if updated:
            self.db_session.commit()
        
        return updated

    def update_quiet_hours(
        self,
        user_id: UUID,
        quiet_hours_config: Dict[str, Any]
    ) -> bool:
        """Update quiet hours configuration."""
        preferences = self.get_or_create_preferences(user_id)
        
        # Update quiet hours settings
        quiet_fields = [
            'quiet_hours_enabled', 'quiet_hours_start', 'quiet_hours_end',
            'quiet_hours_weekdays', 'quiet_hours_weekends', 'quiet_hours_allow_urgent'
        ]
        
        updated = False
        for field, value in quiet_hours_config.items():
            if field in quiet_fields and hasattr(preferences, field):
                # Convert time strings to time objects if needed
                if field in ['quiet_hours_start', 'quiet_hours_end'] and isinstance(value, str):
                    try:
                        value = datetime.strptime(value, '%H:%M').time()
                    except ValueError:
                        continue
                
                if getattr(preferences, field) != value:
                    setattr(preferences, field, value)
                    updated = True
        
        if updated:
            self.db_session.commit()
        
        return updated

    def update_digest_settings(
        self,
        user_id: UUID,
        digest_config: Dict[str, Any]
    ) -> bool:
        """Update digest notification settings."""
        preferences = self.get_or_create_preferences(user_id)
        
        digest_fields = [
            'daily_digest_enabled', 'daily_digest_time',
            'weekly_digest_enabled', 'weekly_digest_day', 'weekly_digest_time'
        ]
        
        updated = False
        for field, value in digest_config.items():
            if field in digest_fields and hasattr(preferences, field):
                # Convert time strings to time objects if needed
                if field in ['daily_digest_time', 'weekly_digest_time'] and isinstance(value, str):
                    try:
                        value = datetime.strptime(value, '%H:%M').time()
                    except ValueError:
                        continue
                
                if getattr(preferences, field) != value:
                    setattr(preferences, field, value)
                    updated = True
        
        if updated:
            self.db_session.commit()
        
        return updated

    # Channel-specific preferences
    def update_channel_preferences(
        self,
        user_id: UUID,
        channel: str,
        settings: Dict[str, Any],
        category_preferences: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Update channel-specific preferences."""
        preferences = self.get_or_create_preferences(user_id)
        
        # Find or create channel preference
        channel_pref = self.db_session.query(ChannelPreference).filter(
            and_(
                ChannelPreference.preference_id == preferences.id,
                ChannelPreference.channel == channel
            )
        ).first()
        
        if not channel_pref:
            channel_pref = ChannelPreference(
                preference_id=preferences.id,
                channel=channel,
                settings={},
                category_preferences={}
            )
            self.db_session.add(channel_pref)
        
        # Update settings
        updated = False
        if settings and settings != channel_pref.settings:
            channel_pref.settings = settings
            updated = True
        
        if category_preferences and category_preferences != channel_pref.category_preferences:
            channel_pref.category_preferences = category_preferences
            updated = True
        
        if updated:
            self.db_session.commit()
        
        return updated

    def get_channel_preferences(
        self,
        user_id: UUID,
        channel: str
    ) -> Optional[ChannelPreference]:
        """Get specific channel preferences for user."""
        preferences = self.get_or_create_preferences(user_id)
        
        return self.db_session.query(ChannelPreference).filter(
            and_(
                ChannelPreference.preference_id == preferences.id,
                ChannelPreference.channel == channel
            )
        ).first()

    # Unsubscribe management
    def create_unsubscribe_token(
        self,
        user_id: UUID,
        unsubscribe_type: str,
        category: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> str:
        """Create secure unsubscribe token."""
        import secrets
        
        token = secrets.token_urlsafe(64)
        
        unsubscribe_token = UnsubscribeToken(
            user_id=user_id,
            token=token,
            unsubscribe_type=unsubscribe_type,
            category=category,
            ip_address=ip_address
        )
        
        self.db_session.add(unsubscribe_token)
        self.db_session.commit()
        
        return token

    def process_unsubscribe(
        self,
        token: str,
        reason: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> Dict[str, Any]:
        """Process unsubscribe request using token."""
        unsubscribe_token = self.db_session.query(UnsubscribeToken).filter(
            and_(
                UnsubscribeToken.token == token,
                UnsubscribeToken.is_used == False
            )
        ).first()
        
        if not unsubscribe_token:
            return {'success': False, 'error': 'Invalid or expired token'}
        
        # Mark token as used
        unsubscribe_token.is_used = True
        unsubscribe_token.used_at = datetime.utcnow()
        unsubscribe_token.reason = reason
        unsubscribe_token.ip_address = ip_address
        
        # Apply unsubscribe settings
        preferences = self.get_or_create_preferences(unsubscribe_token.user_id)
        
        if unsubscribe_token.unsubscribe_type == 'all':
            preferences.notifications_enabled = False
        elif unsubscribe_token.unsubscribe_type == 'email':
            preferences.email_enabled = False
        elif unsubscribe_token.unsubscribe_type == 'sms':
            preferences.sms_enabled = False
        elif unsubscribe_token.unsubscribe_type == 'marketing':
            preferences.marketing_notifications = False
        elif unsubscribe_token.category:
            # Category-specific unsubscribe
            category_field = f"{unsubscribe_token.category}_notifications"
            if hasattr(preferences, category_field):
                setattr(preferences, category_field, False)
        
        self.db_session.commit()
        
        return {
            'success': True,
            'unsubscribe_type': unsubscribe_token.unsubscribe_type,
            'category': unsubscribe_token.category,
            'user_id': str(unsubscribe_token.user_id)
        }

    # Preference analytics and insights
    def get_preference_analytics(self) -> Dict[str, Any]:
        """Get comprehensive preference analytics."""
        # Global settings distribution
        global_stats = self.db_session.query(
            func.count().label('total_users'),
            func.sum(case([(NotificationPreference.notifications_enabled == True, 1)], else_=0)).label('notifications_enabled'),
            func.sum(case([(NotificationPreference.email_enabled == True, 1)], else_=0)).label('email_enabled'),
            func.sum(case([(NotificationPreference.sms_enabled == True, 1)], else_=0)).label('sms_enabled'),
            func.sum(case([(NotificationPreference.push_enabled == True, 1)], else_=0)).label('push_enabled'),
            func.sum(case([(NotificationPreference.marketing_notifications == True, 1)], else_=0)).label('marketing_enabled'),
            func.sum(case([(NotificationPreference.quiet_hours_enabled == True, 1)], else_=0)).label('quiet_hours_enabled')
        ).first()
        
        # Channel preferences
        channel_stats = self.db_session.query(
            ChannelPreference.channel,
            func.count().label('users_count')
        ).group_by(ChannelPreference.channel).all()
        
        # Language distribution
        language_stats = self.db_session.query(
            NotificationPreference.preferred_language,
            func.count().label('user_count')
        ).group_by(NotificationPreference.preferred_language).all()
        
        # Unsubscribe patterns
        unsubscribe_stats = self.db_session.query(
            UnsubscribeToken.unsubscribe_type,
            func.count().label('unsubscribe_count')
        ).filter(
            UnsubscribeToken.is_used == True
        ).group_by(UnsubscribeToken.unsubscribe_type).all()
        
        total_users = global_stats.total_users or 1
        
        return {
            'global_preferences': {
                'total_users': total_users,
                'notifications_enabled_rate': (global_stats.notifications_enabled / total_users * 100),
                'email_enabled_rate': (global_stats.email_enabled / total_users * 100),
                'sms_enabled_rate': (global_stats.sms_enabled / total_users * 100),
                'push_enabled_rate': (global_stats.push_enabled / total_users * 100),
                'marketing_enabled_rate': (global_stats.marketing_enabled / total_users * 100),
                'quiet_hours_usage_rate': (global_stats.quiet_hours_enabled / total_users * 100)
            },
            'channel_adoption': [
                {
                    'channel': stat.channel,
                    'users_count': stat.users_count,
                    'adoption_rate': (stat.users_count / total_users * 100)
                }
                for stat in channel_stats
            ],
            'language_distribution': [
                {
                    'language': stat.preferred_language,
                    'user_count': stat.user_count,
                    'percentage': (stat.user_count / total_users * 100)
                }
                for stat in language_stats
            ],
            'unsubscribe_patterns': [
                {
                    'type': stat.unsubscribe_type,
                    'count': stat.unsubscribe_count
                }
                for stat in unsubscribe_stats
            ]
        }

    def find_users_in_quiet_hours(
        self,
        check_time: Optional[datetime] = None
    ) -> List[UUID]:
        """Find users currently in quiet hours."""
        if check_time is None:
            check_time = datetime.utcnow()
        
        current_time = check_time.time()
        current_weekday = check_time.weekday()  # 0 = Monday, 6 = Sunday
        is_weekend = current_weekday >= 5
        
        # Build query for users in quiet hours
        query = self.db_session.query(NotificationPreference.user_id).filter(
            and_(
                NotificationPreference.quiet_hours_enabled == True,
                or_(
                    and_(is_weekend, NotificationPreference.quiet_hours_weekends == True),
                    and_(not is_weekend, NotificationPreference.quiet_hours_weekdays == True)
                )
            )
        )
        
        # Filter by time range (this is simplified - real implementation would handle timezone conversion)
        users_in_quiet_hours = []
        for result in query.all():
            pref = self.db_session.query(NotificationPreference).filter(
                NotificationPreference.user_id == result.user_id
            ).first()
            
            if pref and pref.quiet_hours_start and pref.quiet_hours_end:
                if self._is_in_quiet_hours(current_time, pref.quiet_hours_start, pref.quiet_hours_end):
                    users_in_quiet_hours.append(result.user_id)
        
        return users_in_quiet_hours

    def get_users_for_digest(
        self,
        digest_type: str,
        target_time: Optional[time] = None
    ) -> List[UUID]:
        """Get users eligible for digest notifications."""
        if target_time is None:
            target_time = datetime.utcnow().time()
        
        if digest_type == 'daily':
            users = self.db_session.query(NotificationPreference.user_id).filter(
                and_(
                    NotificationPreference.daily_digest_enabled == True,
                    NotificationPreference.daily_digest_time == target_time
                )
            ).all()
        elif digest_type == 'weekly':
            current_day = datetime.utcnow().strftime('%A').lower()
            users = self.db_session.query(NotificationPreference.user_id).filter(
                and_(
                    NotificationPreference.weekly_digest_enabled == True,
                    NotificationPreference.weekly_digest_day == current_day,
                    NotificationPreference.weekly_digest_time == target_time
                )
            ).all()
        else:
            return []
        
        return [user.user_id for user in users]

    def get_preference_trends(
        self,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """Get preference change trends over time."""
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        # Daily preference changes
        trends = self.db_session.query(
            func.date(NotificationPreference.updated_at).label('date'),
            func.count().label('total_changes'),
            func.sum(
                case([(NotificationPreference.notifications_enabled == False, 1)], else_=0)
            ).label('disabled_notifications'),
            func.sum(
                case([(NotificationPreference.marketing_notifications == False, 1)], else_=0)
            ).label('disabled_marketing')
        ).filter(
            and_(
                NotificationPreference.updated_at >= start_date,
                NotificationPreference.updated_at <= end_date
            )
        ).group_by(
            func.date(NotificationPreference.updated_at)
        ).order_by(func.date(NotificationPreference.updated_at)).all()
        
        return [
            {
                'date': trend.date.isoformat(),
                'total_changes': trend.total_changes,
                'disabled_notifications': trend.disabled_notifications,
                'disabled_marketing': trend.disabled_marketing
            }
            for trend in trends
        ]

    # Helper methods
    def _create_default_preferences(self, user_id: UUID) -> NotificationPreference:
        """Create default notification preferences for user."""
        preferences = NotificationPreference(
            user_id=user_id,
            notifications_enabled=True,
            email_enabled=True,
            sms_enabled=True,
            push_enabled=True,
            in_app_enabled=True,
            payment_notifications=True,
            booking_notifications=True,
            complaint_notifications=True,
            announcement_notifications=True,
            maintenance_notifications=True,
            attendance_notifications=True,
            marketing_notifications=False,  # Default to opt-out for marketing
            immediate_notifications=True,
            batch_notifications=False,
            daily_digest_enabled=False,
            weekly_digest_enabled=False,
            quiet_hours_enabled=False
        )
        
        return self.create(preferences)

    def _is_in_quiet_hours(
        self,
        current_time: time,
        quiet_start: time,
        quiet_end: time
    ) -> bool:
        """Check if current time is within quiet hours."""
        if quiet_start <= quiet_end:
            # Same day range (e.g., 22:00 - 08:00 next day)
            return quiet_start <= current_time <= quiet_end
        else:
            # Crosses midnight (e.g., 22:00 - 08:00)
            return current_time >= quiet_start or current_time <= quiet_end

    def bulk_update_preferences(
        self,
        user_ids: List[UUID],
        preference_updates: Dict[str, Any]
    ) -> int:
        """Bulk update preferences for multiple users."""
        updated_count = self.db_session.query(NotificationPreference).filter(
            NotificationPreference.user_id.in_(user_ids)
        ).update(preference_updates, synchronize_session=False)
        
        self.db_session.commit()
        return updated_count