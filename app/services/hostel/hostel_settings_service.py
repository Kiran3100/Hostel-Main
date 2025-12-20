# --- File: C:\Hostel-Main\app\services\hostel\hostel_settings_service.py ---
"""
Hostel settings service for operational configuration management.
"""

from datetime import time
from decimal import Decimal
from typing import Dict, List, Optional, Union, Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.hostel.hostel_settings import HostelSettings
from app.repositories.hostel.hostel_settings_repository import HostelSettingsRepository
from app.core.exceptions import (
    SettingsValidationError,
    HostelNotFoundError,
    ValidationError
)
from app.services.base.base_service import BaseService


class HostelSettingsService(BaseService):
    """
    Hostel settings service with configuration management.
    
    Manages hostel operational settings, feature flags,
    payment configurations, and business rules.
    """

    def __init__(self, session: AsyncSession):
        super().__init__(session)
        self.settings_repo = HostelSettingsRepository(session)

    # ===== Settings Retrieval =====

    async def get_hostel_settings(
        self,
        hostel_id: UUID,
        create_if_missing: bool = True
    ) -> HostelSettings:
        """
        Get settings for a hostel.
        
        Args:
            hostel_id: Hostel UUID
            create_if_missing: Create default settings if not found
            
        Returns:
            HostelSettings instance
            
        Raises:
            HostelNotFoundError: If hostel doesn't exist
        """
        settings = await self.settings_repo.get_by_hostel_id(hostel_id)
        
        if not settings and create_if_missing:
            settings = await self.settings_repo.create_default_settings(hostel_id)
        
        if not settings:
            raise HostelNotFoundError(
                f"Settings not found for hostel {hostel_id}"
            )
        
        return settings

    async def get_settings_summary(
        self,
        hostel_ids: List[UUID]
    ) -> Dict[UUID, Dict]:
        """Get settings summary for multiple hostels."""
        return await self.settings_repo.get_settings_summary(hostel_ids)

    # ===== Booking Settings =====

    async def update_booking_settings(
        self,
        hostel_id: UUID,
        auto_approve: Optional[bool] = None,
        advance_percentage: Optional[Decimal] = None,
        max_duration_months: Optional[int] = None,
        min_duration_days: Optional[int] = None,
        same_day_booking: Optional[bool] = None,
        buffer_hours: Optional[int] = None
    ) -> HostelSettings:
        """
        Update booking-related settings.
        
        Args:
            hostel_id: Hostel UUID
            auto_approve: Auto-approve bookings
            advance_percentage: Required advance payment percentage
            max_duration_months: Maximum booking duration
            min_duration_days: Minimum booking duration
            same_day_booking: Allow same-day bookings
            buffer_hours: Booking buffer hours
            
        Returns:
            Updated HostelSettings
        """
        update_data = {}
        
        if auto_approve is not None:
            update_data['auto_approve_bookings'] = auto_approve
        
        if advance_percentage is not None:
            if not (0 <= advance_percentage <= 100):
                raise ValidationError(
                    "Advance percentage must be between 0 and 100"
                )
            update_data['booking_advance_percentage'] = advance_percentage
        
        if max_duration_months is not None:
            if max_duration_months < 1:
                raise ValidationError(
                    "Maximum duration must be at least 1 month"
                )
            update_data['max_booking_duration_months'] = max_duration_months
        
        if min_duration_days is not None:
            if min_duration_days < 1:
                raise ValidationError(
                    "Minimum duration must be at least 1 day"
                )
            update_data['min_booking_duration_days'] = min_duration_days
        
        if same_day_booking is not None:
            update_data['allow_same_day_booking'] = same_day_booking
        
        if buffer_hours is not None:
            if buffer_hours < 0:
                raise ValidationError("Buffer hours cannot be negative")
            update_data['booking_buffer_hours'] = buffer_hours
        
        return await self.settings_repo.update_booking_settings(
            hostel_id,
            update_data
        )

    # ===== Payment Settings =====

    async def update_payment_settings(
        self,
        hostel_id: UUID,
        due_day: Optional[int] = None,
        grace_days: Optional[int] = None,
        penalty_percentage: Optional[Decimal] = None,
        allow_partial: Optional[bool] = None,
        min_partial_percentage: Optional[Decimal] = None,
        security_deposit_months: Optional[int] = None
    ) -> HostelSettings:
        """
        Update payment-related settings.
        
        Args:
            hostel_id: Hostel UUID
            due_day: Monthly payment due day (1-28)
            grace_days: Late payment grace period
            penalty_percentage: Late payment penalty percentage
            allow_partial: Allow partial payments
            min_partial_percentage: Minimum partial payment percentage
            security_deposit_months: Security deposit in months
            
        Returns:
            Updated HostelSettings
        """
        update_data = {}
        
        if due_day is not None:
            if not (1 <= due_day <= 28):
                raise ValidationError("Payment due day must be between 1 and 28")
            update_data['payment_due_day'] = due_day
        
        if grace_days is not None:
            if grace_days < 0:
                raise ValidationError("Grace days cannot be negative")
            update_data['late_payment_grace_days'] = grace_days
        
        if penalty_percentage is not None:
            if not (0 <= penalty_percentage <= 50):
                raise ValidationError(
                    "Penalty percentage must be between 0 and 50"
                )
            update_data['late_payment_penalty_percentage'] = penalty_percentage
        
        if allow_partial is not None:
            update_data['allow_partial_payments'] = allow_partial
        
        if min_partial_percentage is not None:
            if not (0 <= min_partial_percentage <= 100):
                raise ValidationError(
                    "Minimum partial percentage must be between 0 and 100"
                )
            update_data['min_partial_payment_percentage'] = min_partial_percentage
        
        if security_deposit_months is not None:
            if security_deposit_months < 0:
                raise ValidationError(
                    "Security deposit months cannot be negative"
                )
            update_data['security_deposit_months'] = security_deposit_months
        
        return await self.settings_repo.update_payment_settings(
            hostel_id,
            update_data
        )

    async def configure_payment_reminders(
        self,
        hostel_id: UUID,
        reminder_days: List[int]
    ) -> HostelSettings:
        """
        Configure payment reminder schedule.
        
        Args:
            hostel_id: Hostel UUID
            reminder_days: Days before due date to send reminders
            
        Returns:
            Updated HostelSettings
        """
        settings = await self.get_hostel_settings(hostel_id)
        settings.payment_reminder_days = {"days": sorted(reminder_days, reverse=True)}
        
        await self.session.commit()
        return settings

    # ===== Security Settings =====

    async def update_security_settings(
        self,
        hostel_id: UUID,
        visitor_start_time: Optional[time] = None,
        visitor_end_time: Optional[time] = None,
        late_entry_time: Optional[time] = None,
        require_visitor_id: Optional[bool] = None,
        max_visitors: Optional[int] = None,
        advance_approval: Optional[bool] = None
    ) -> HostelSettings:
        """
        Update security-related settings.
        
        Args:
            hostel_id: Hostel UUID
            visitor_start_time: Visitor entry allowed from
            visitor_end_time: Visitor entry allowed until
            late_entry_time: Late entry cutoff time
            require_visitor_id: Require ID proof for visitors
            max_visitors: Maximum simultaneous visitors per student
            advance_approval: Require advance approval for visitors
            
        Returns:
            Updated HostelSettings
        """
        update_data = {}
        
        if visitor_start_time is not None:
            update_data['visitor_entry_time_start'] = visitor_start_time
        
        if visitor_end_time is not None:
            update_data['visitor_entry_time_end'] = visitor_end_time
        
        if visitor_start_time and visitor_end_time:
            if visitor_start_time >= visitor_end_time:
                raise ValidationError(
                    "Visitor start time must be before end time"
                )
        
        if late_entry_time is not None:
            update_data['late_entry_time'] = late_entry_time
        
        if require_visitor_id is not None:
            update_data['require_visitor_id'] = require_visitor_id
        
        if max_visitors is not None:
            if max_visitors < 0:
                raise ValidationError(
                    "Maximum visitors cannot be negative"
                )
            update_data['max_visitors_per_student'] = max_visitors
        
        if advance_approval is not None:
            update_data['visitor_advance_approval_required'] = advance_approval
        
        return await self.settings_repo.update_security_settings(
            hostel_id,
            update_data
        )

    # ===== Feature Management =====

    async def enable_feature(
        self,
        hostel_id: UUID,
        feature_name: str
    ) -> HostelSettings:
        """Enable a specific feature for a hostel."""
        return await self.settings_repo.toggle_feature(
            hostel_id,
            feature_name,
            True
        )

    async def disable_feature(
        self,
        hostel_id: UUID,
        feature_name: str
    ) -> HostelSettings:
        """Disable a specific feature for a hostel."""
        return await self.settings_repo.toggle_feature(
            hostel_id,
            feature_name,
            False
        )

    async def get_enabled_features(
        self,
        hostel_id: UUID
    ) -> Dict[str, bool]:
        """Get all enabled features for a hostel."""
        return await self.settings_repo.get_enabled_features(hostel_id)

    async def is_feature_enabled(
        self,
        hostel_id: UUID,
        feature_name: str
    ) -> bool:
        """Check if a specific feature is enabled."""
        settings = await self.get_hostel_settings(hostel_id)
        return settings.is_feature_enabled(feature_name)

    # ===== Custom Settings =====

    async def set_custom_setting(
        self,
        hostel_id: UUID,
        key: str,
        value: Any
    ) -> HostelSettings:
        """Set a custom setting for a hostel."""
        return await self.settings_repo.update_custom_setting(
            hostel_id,
            key,
            value
        )

    async def get_custom_setting(
        self,
        hostel_id: UUID,
        key: str,
        default: Any = None
    ) -> Any:
        """Get a custom setting value."""
        settings = await self.get_hostel_settings(hostel_id)
        return settings.get_custom_setting(key, default)

    # ===== Settings Templates =====

    async def copy_settings_from_template(
        self,
        hostel_id: UUID,
        template_hostel_id: UUID
    ) -> HostelSettings:
        """
        Copy settings from another hostel.
        
        Args:
            hostel_id: Target hostel UUID
            template_hostel_id: Source hostel UUID
            
        Returns:
            New settings for target hostel
        """
        return await self.settings_repo.copy_settings(
            template_hostel_id,
            hostel_id
        )

    # ===== Validation =====

    async def validate_settings(
        self,
        hostel_id: UUID
    ) -> Dict[str, Any]:
        """
        Validate hostel settings.
        
        Returns:
            Validation result with any errors
        """
        settings = await self.get_hostel_settings(hostel_id)
        errors = await self.settings_repo.validate_settings(settings)
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'hostel_id': hostel_id
        }