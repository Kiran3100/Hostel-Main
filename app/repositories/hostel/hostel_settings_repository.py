"""
Hostel settings repository for operational configuration management.
"""

from datetime import datetime, time
from decimal import Decimal
from typing import Dict, List, Optional, Union
from uuid import UUID

from sqlalchemy import and_, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.hostel.hostel_settings import HostelSettings
from app.models.hostel.hostel import Hostel
from app.repositories.base.base_repository import BaseRepository
from app.repositories.base.specifications import Specification
from app.core.exceptions import SettingsValidationError, HostelNotFoundError


class HostelSettingsRepository(BaseRepository[HostelSettings]):
    """
    Hostel settings repository with operational configuration management.
    
    Provides specialized operations for hostel operational settings,
    feature flags, payment configurations, and business rules.
    """

    def __init__(self, session: AsyncSession):
        super().__init__(HostelSettings, session)

    async def get_by_hostel_id(self, hostel_id: UUID) -> Optional[HostelSettings]:
        """
        Get settings by hostel ID.
        
        Args:
            hostel_id: Hostel UUID
            
        Returns:
            HostelSettings if found, None otherwise
        """
        query = select(HostelSettings).where(
            HostelSettings.hostel_id == hostel_id
        ).options(selectinload(HostelSettings.hostel))
        
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def create_default_settings(self, hostel_id: UUID) -> HostelSettings:
        """
        Create default settings for a new hostel.
        
        Args:
            hostel_id: Hostel UUID
            
        Returns:
            Created HostelSettings instance
            
        Raises:
            HostelNotFoundError: If hostel doesn't exist
        """
        # Verify hostel exists
        hostel_query = select(Hostel).where(Hostel.id == hostel_id)
        hostel_result = await self.session.execute(hostel_query)
        hostel = hostel_result.scalar_one_or_none()
        
        if not hostel:
            raise HostelNotFoundError(f"Hostel with ID {hostel_id} not found")

        # Check if settings already exist
        existing = await self.get_by_hostel_id(hostel_id)
        if existing:
            return existing

        # Create default settings
        settings = HostelSettings(
            hostel_id=hostel_id,
            # Default booking settings
            auto_approve_bookings=False,
            booking_advance_percentage=Decimal("20.00"),
            max_booking_duration_months=12,
            min_booking_duration_days=30,
            allow_same_day_booking=False,
            booking_buffer_hours=24,
            
            # Default payment settings
            payment_due_day=5,
            late_payment_grace_days=3,
            late_payment_penalty_percentage=Decimal("5.00"),
            allow_partial_payments=True,
            min_partial_payment_percentage=Decimal("50.00"),
            security_deposit_months=2,
            
            # Default attendance settings
            enable_attendance_tracking=True,
            minimum_attendance_percentage=Decimal("75.00"),
            attendance_grace_period_days=7,
            auto_mark_absent_after_hours=24,
            attendance_alert_threshold=Decimal("70.00"),
            
            # Default notification settings
            notify_on_booking=True,
            notify_on_complaint=True,
            notify_on_payment=True,
            notify_on_maintenance=True,
            notify_on_low_attendance=True,
            payment_reminder_days={"days": [7, 3, 1]},
            
            # Default mess settings
            mess_included=False,
            mess_advance_booking_days=1,
            allow_mess_opt_out=True,
            mess_menu_change_frequency="weekly",
            
            # Default security settings
            visitor_entry_time_start=time(6, 0),
            visitor_entry_time_end=time(22, 0),
            late_entry_time=time(23, 0),
            require_visitor_id=True,
            max_visitors_per_student=2,
            visitor_advance_approval_required=False,
            
            # Default room settings
            allow_room_transfer=True,
            min_stay_before_transfer_days=90,
            auto_assign_beds=False,
            
            # Default maintenance settings
            maintenance_sla_hours=48,
            urgent_maintenance_sla_hours=4,
            allow_student_maintenance_request=True,
            
            # Default leave settings
            max_leave_days_per_month=7,
            leave_advance_notice_days=2,
            emergency_leave_allowed=True,
            
            # Default general settings
            timezone="Asia/Kolkata",
            currency="INR",
            language="en",
            
            # Default features
            features_enabled={
                "advanced_analytics": True,
                "mobile_app": True,
                "visitor_management": True,
                "mess_management": False,
                "attendance_tracking": True,
                "maintenance_requests": True,
                "complaint_management": True,
                "payment_reminders": True,
                "document_verification": True,
                "room_transfer": True
            },
            custom_settings={}
        )

        return await self.create(settings)

    async def update_booking_settings(
        self,
        hostel_id: UUID,
        booking_settings: Dict[str, Union[bool, int, Decimal]]
    ) -> HostelSettings:
        """
        Update booking-related settings.
        
        Args:
            hostel_id: Hostel UUID
            booking_settings: Dictionary of booking settings to update
            
        Returns:
            Updated HostelSettings instance
        """
        settings = await self.get_by_hostel_id(hostel_id)
        if not settings:
            raise SettingsValidationError(f"Settings not found for hostel {hostel_id}")

        # Validate booking settings
        valid_fields = {
            'auto_approve_bookings', 'booking_advance_percentage',
            'max_booking_duration_months', 'min_booking_duration_days',
            'allow_same_day_booking', 'booking_buffer_hours'
        }
        
        invalid_fields = set(booking_settings.keys()) - valid_fields
        if invalid_fields:
            raise SettingsValidationError(f"Invalid booking settings: {invalid_fields}")

        # Apply updates
        for field, value in booking_settings.items():
            setattr(settings, field, value)

        await self.session.commit()
        await self.session.refresh(settings)
        return settings

    async def update_payment_settings(
        self,
        hostel_id: UUID,
        payment_settings: Dict[str, Union[bool, int, Decimal]]
    ) -> HostelSettings:
        """
        Update payment-related settings.
        
        Args:
            hostel_id: Hostel UUID
            payment_settings: Dictionary of payment settings to update
            
        Returns:
            Updated HostelSettings instance
        """
        settings = await self.get_by_hostel_id(hostel_id)
        if not settings:
            raise SettingsValidationError(f"Settings not found for hostel {hostel_id}")

        # Validate payment settings
        valid_fields = {
            'payment_due_day', 'late_payment_grace_days',
            'late_payment_penalty_percentage', 'allow_partial_payments',
            'min_partial_payment_percentage', 'security_deposit_months'
        }
        
        invalid_fields = set(payment_settings.keys()) - valid_fields
        if invalid_fields:
            raise SettingsValidationError(f"Invalid payment settings: {invalid_fields}")

        # Apply updates
        for field, value in payment_settings.items():
            setattr(settings, field, value)

        await self.session.commit()
        await self.session.refresh(settings)
        return settings

    async def toggle_feature(
        self,
        hostel_id: UUID,
        feature_name: str,
        enabled: bool
    ) -> HostelSettings:
        """
        Toggle a specific feature for a hostel.
        
        Args:
            hostel_id: Hostel UUID
            feature_name: Name of the feature to toggle
            enabled: Whether to enable or disable the feature
            
        Returns:
            Updated HostelSettings instance
        """
        settings = await self.get_by_hostel_id(hostel_id)
        if not settings:
            raise SettingsValidationError(f"Settings not found for hostel {hostel_id}")

        if not settings.features_enabled:
            settings.features_enabled = {}

        settings.features_enabled[feature_name] = enabled
        
        # Mark the field as modified for SQLAlchemy
        settings.features_enabled = settings.features_enabled.copy()

        await self.session.commit()
        await self.session.refresh(settings)
        return settings

    async def get_enabled_features(self, hostel_id: UUID) -> Dict[str, bool]:
        """
        Get all enabled features for a hostel.
        
        Args:
            hostel_id: Hostel UUID
            
        Returns:
            Dictionary of features and their enabled status
        """
        settings = await self.get_by_hostel_id(hostel_id)
        if not settings or not settings.features_enabled:
            return {}
        
        return settings.features_enabled

    async def update_custom_setting(
        self,
        hostel_id: UUID,
        key: str,
        value: Union[str, int, float, bool, Dict, List]
    ) -> HostelSettings:
        """
        Update a custom setting for a hostel.
        
        Args:
            hostel_id: Hostel UUID
            key: Setting key
            value: Setting value
            
        Returns:
            Updated HostelSettings instance
        """
        settings = await self.get_by_hostel_id(hostel_id)
        if not settings:
            raise SettingsValidationError(f"Settings not found for hostel {hostel_id}")

        if not settings.custom_settings:
            settings.custom_settings = {}

        settings.custom_settings[key] = value
        
        # Mark the field as modified for SQLAlchemy
        settings.custom_settings = settings.custom_settings.copy()

        await self.session.commit()
        await self.session.refresh(settings)
        return settings

    async def get_payment_reminder_schedule(self, hostel_id: UUID) -> List[int]:
        """
        Get payment reminder schedule for a hostel.
        
        Args:
            hostel_id: Hostel UUID
            
        Returns:
            List of days before due date to send reminders
        """
        settings = await self.get_by_hostel_id(hostel_id)
        if not settings or not settings.payment_reminder_days:
            return [7, 3, 1]  # Default schedule
        
        return settings.payment_reminder_days.get("days", [7, 3, 1])

    async def update_security_settings(
        self,
        hostel_id: UUID,
        security_settings: Dict[str, Union[bool, int, time]]
    ) -> HostelSettings:
        """
        Update security-related settings.
        
        Args:
            hostel_id: Hostel UUID
            security_settings: Dictionary of security settings to update
            
        Returns:
            Updated HostelSettings instance
        """
        settings = await self.get_by_hostel_id(hostel_id)
        if not settings:
            raise SettingsValidationError(f"Settings not found for hostel {hostel_id}")

        # Validate security settings
        valid_fields = {
            'visitor_entry_time_start', 'visitor_entry_time_end',
            'late_entry_time', 'require_visitor_id',
            'max_visitors_per_student', 'visitor_advance_approval_required'
        }
        
        invalid_fields = set(security_settings.keys()) - valid_fields
        if invalid_fields:
            raise SettingsValidationError(f"Invalid security settings: {invalid_fields}")

        # Apply updates
        for field, value in security_settings.items():
            setattr(settings, field, value)

        await self.session.commit()
        await self.session.refresh(settings)
        return settings

    async def get_hostels_with_feature_enabled(self, feature_name: str) -> List[UUID]:
        """
        Get all hostels with a specific feature enabled.
        
        Args:
            feature_name: Name of the feature
            
        Returns:
            List of hostel UUIDs with the feature enabled
        """
        query = select(HostelSettings.hostel_id).where(
            HostelSettings.features_enabled.op('->>')('{}').astext == 'true'.format(feature_name)
        )
        
        result = await self.session.execute(query)
        return [row[0] for row in result.fetchall()]

    async def validate_settings(self, settings: HostelSettings) -> List[str]:
        """
        Validate hostel settings for consistency and business rules.
        
        Args:
            settings: HostelSettings instance to validate
            
        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        # Validate booking settings
        if settings.booking_advance_percentage < 0 or settings.booking_advance_percentage > 100:
            errors.append("Booking advance percentage must be between 0 and 100")

        if settings.max_booking_duration_months < settings.min_booking_duration_days / 30:
            errors.append("Maximum booking duration must be greater than minimum duration")

        # Validate payment settings
        if settings.payment_due_day < 1 or settings.payment_due_day > 28:
            errors.append("Payment due day must be between 1 and 28")

        if settings.late_payment_penalty_percentage < 0 or settings.late_payment_penalty_percentage > 50:
            errors.append("Late payment penalty must be between 0% and 50%")

        # Validate attendance settings
        if settings.minimum_attendance_percentage < 0 or settings.minimum_attendance_percentage > 100:
            errors.append("Minimum attendance percentage must be between 0 and 100")

        # Validate time settings
        if (settings.visitor_entry_time_start and settings.visitor_entry_time_end and 
            settings.visitor_entry_time_start >= settings.visitor_entry_time_end):
            errors.append("Visitor entry start time must be before end time")

        return errors

    async def copy_settings(self, source_hostel_id: UUID, target_hostel_id: UUID) -> HostelSettings:
        """
        Copy settings from one hostel to another.
        
        Args:
            source_hostel_id: Source hostel UUID
            target_hostel_id: Target hostel UUID
            
        Returns:
            New HostelSettings instance for target hostel
        """
        source_settings = await self.get_by_hostel_id(source_hostel_id)
        if not source_settings:
            raise SettingsValidationError(f"Source settings not found for hostel {source_hostel_id}")

        # Create new settings with copied values
        new_settings = HostelSettings(
            hostel_id=target_hostel_id,
            # Copy all settings except IDs and timestamps
            **{
                column.name: getattr(source_settings, column.name)
                for column in HostelSettings.__table__.columns
                if column.name not in ('id', 'hostel_id', 'created_at', 'updated_at')
            }
        )

        return await self.create(new_settings)

    async def get_settings_summary(self, hostel_ids: List[UUID]) -> Dict[UUID, Dict]:
        """
        Get settings summary for multiple hostels.
        
        Args:
            hostel_ids: List of hostel UUIDs
            
        Returns:
            Dictionary mapping hostel ID to settings summary
        """
        query = select(HostelSettings).where(
            HostelSettings.hostel_id.in_(hostel_ids)
        )
        
        result = await self.session.execute(query)
        settings_list = result.scalars().all()

        summary = {}
        for settings in settings_list:
            summary[settings.hostel_id] = {
                'auto_approve_bookings': settings.auto_approve_bookings,
                'payment_due_day': settings.payment_due_day,
                'attendance_tracking_enabled': settings.enable_attendance_tracking,
                'mess_included': settings.mess_included,
                'currency': settings.currency,
                'timezone': settings.timezone,
                'features_enabled': len([f for f in (settings.features_enabled or {}).values() if f]),
                'total_features': len(settings.features_enabled or {}),
                'last_updated': settings.updated_at
            }

        return summary