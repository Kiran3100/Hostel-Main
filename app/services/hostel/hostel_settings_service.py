# --- File: C:\Hostel-Main\app\services\hostel\hostel_settings_service.py ---
"""
Hostel settings service.

Manages operational settings for hostels including booking configurations,
payment settings, notification preferences, and security options.
"""

from typing import Optional, Dict, Any
from uuid import UUID
import logging

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.services.base import (
    BaseService, 
    ServiceResult, 
    ServiceError, 
    ErrorCode, 
    ErrorSeverity
)
from app.repositories.hostel import HostelSettingsRepository
from app.models.hostel.hostel_settings import HostelSettings as HostelSettingsModel
from app.schemas.hostel.hostel_admin import HostelSettings as HostelSettingsSchema
from app.services.hostel.constants import (
    ERROR_HOSTEL_NOT_FOUND,
    SUCCESS_SETTINGS_UPDATED
)

logger = logging.getLogger(__name__)


class HostelSettingsService(BaseService[HostelSettingsModel, HostelSettingsRepository]):
    """
    Manage operational settings for a hostel.
    
    Handles configuration for:
    - Booking policies and rules
    - Payment gateway settings
    - Notification preferences
    - Security settings
    - Integration configurations
    """

    def __init__(self, repository: HostelSettingsRepository, db_session: Session):
        """
        Initialize hostel settings service.
        
        Args:
            repository: Hostel settings repository instance
            db_session: Database session
        """
        super().__init__(repository, db_session)
        self._settings_cache: Dict[UUID, HostelSettingsSchema] = {}

    def get_settings(
        self,
        hostel_id: UUID,
        use_cache: bool = True,
    ) -> ServiceResult[HostelSettingsSchema]:
        """
        Retrieve hostel settings with optional caching.
        
        Args:
            hostel_id: UUID of the hostel
            use_cache: Whether to use cached settings if available
            
        Returns:
            ServiceResult containing hostel settings or error
        """
        try:
            # Check cache first
            if use_cache and hostel_id in self._settings_cache:
                logger.debug(f"Cache hit for hostel settings: {hostel_id}")
                return ServiceResult.success(self._settings_cache[hostel_id])
            
            logger.info(f"Retrieving settings for hostel: {hostel_id}")
            
            # Fetch from repository
            settings = self.repository.get_settings(hostel_id)
            
            if not settings:
                logger.warning(f"Settings not found for hostel: {hostel_id}")
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message=ERROR_HOSTEL_NOT_FOUND,
                        severity=ErrorSeverity.ERROR,
                        details={"hostel_id": str(hostel_id)}
                    )
                )
            
            # Cache the settings
            if use_cache:
                self._settings_cache[hostel_id] = settings
            
            return ServiceResult.success(settings)
            
        except SQLAlchemyError as e:
            logger.error(f"Database error retrieving settings for {hostel_id}: {str(e)}")
            return self._handle_exception(e, "get hostel settings", hostel_id)
        except Exception as e:
            logger.error(f"Unexpected error retrieving settings for {hostel_id}: {str(e)}")
            return self._handle_exception(e, "get hostel settings", hostel_id)

    def update_settings(
        self,
        hostel_id: UUID,
        update: HostelSettingsSchema,
        updated_by: Optional[UUID] = None,
        validate_changes: bool = True,
    ) -> ServiceResult[HostelSettingsSchema]:
        """
        Update hostel settings with validation and audit trail.
        
        Args:
            hostel_id: UUID of the hostel
            update: Settings update schema
            updated_by: UUID of the user performing the update
            validate_changes: Whether to validate setting changes
            
        Returns:
            ServiceResult containing updated settings or error
        """
        try:
            logger.info(f"Updating settings for hostel: {hostel_id}")
            
            # Validate settings if requested
            if validate_changes:
                validation_error = self._validate_settings(update, hostel_id)
                if validation_error:
                    return validation_error
            
            # Perform update
            saved = self.repository.update_settings(
                hostel_id, 
                update, 
                updated_by=updated_by
            )
            
            self.db.flush()
            
            # Verify update succeeded
            if not saved:
                self.db.rollback()
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.DATABASE_ERROR,
                        message="Failed to update hostel settings",
                        severity=ErrorSeverity.ERROR,
                        details={"hostel_id": str(hostel_id)}
                    )
                )
            
            self.db.commit()
            
            # Invalidate cache
            self._invalidate_cache(hostel_id)
            
            logger.info(f"Settings updated successfully for hostel: {hostel_id}")
            return ServiceResult.success(saved, message=SUCCESS_SETTINGS_UPDATED)
            
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Database error updating settings for {hostel_id}: {str(e)}")
            return self._handle_exception(e, "update hostel settings", hostel_id)
        except Exception as e:
            self.db.rollback()
            logger.error(f"Unexpected error updating settings for {hostel_id}: {str(e)}")
            return self._handle_exception(e, "update hostel settings", hostel_id)

    def reset_to_defaults(
        self,
        hostel_id: UUID,
        updated_by: Optional[UUID] = None,
    ) -> ServiceResult[HostelSettingsSchema]:
        """
        Reset hostel settings to default values.
        
        Args:
            hostel_id: UUID of the hostel
            updated_by: UUID of the user performing the reset
            
        Returns:
            ServiceResult containing reset settings or error
        """
        try:
            logger.info(f"Resetting settings to defaults for hostel: {hostel_id}")
            
            # Create default settings schema
            default_settings = self._get_default_settings()
            
            # Update with defaults
            result = self.update_settings(
                hostel_id,
                default_settings,
                updated_by=updated_by,
                validate_changes=False
            )
            
            if result.success:
                logger.info(f"Settings reset to defaults for hostel: {hostel_id}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error resetting settings for {hostel_id}: {str(e)}")
            return self._handle_exception(e, "reset hostel settings", hostel_id)

    def bulk_update_settings(
        self,
        settings_map: Dict[UUID, HostelSettingsSchema],
        updated_by: Optional[UUID] = None,
    ) -> ServiceResult[Dict[UUID, bool]]:
        """
        Update settings for multiple hostels in a single transaction.
        
        Args:
            settings_map: Dictionary mapping hostel IDs to their settings
            updated_by: UUID of the user performing the updates
            
        Returns:
            ServiceResult containing success status for each hostel
        """
        try:
            logger.info(f"Bulk updating settings for {len(settings_map)} hostels")
            
            results: Dict[UUID, bool] = {}
            
            for hostel_id, settings in settings_map.items():
                try:
                    self.repository.update_settings(
                        hostel_id,
                        settings,
                        updated_by=updated_by
                    )
                    results[hostel_id] = True
                except Exception as e:
                    logger.error(f"Failed to update settings for {hostel_id}: {str(e)}")
                    results[hostel_id] = False
            
            # Commit all changes
            self.db.commit()
            
            # Clear cache for all updated hostels
            for hostel_id in settings_map.keys():
                self._invalidate_cache(hostel_id)
            
            success_count = sum(1 for v in results.values() if v)
            logger.info(
                f"Bulk update completed: {success_count}/{len(settings_map)} successful"
            )
            
            return ServiceResult.success(
                results,
                message=f"Updated {success_count} of {len(settings_map)} hostel settings"
            )
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error in bulk settings update: {str(e)}")
            return self._handle_exception(e, "bulk update hostel settings")

    # =========================================================================
    # Private Helper Methods
    # =========================================================================

    def _validate_settings(
        self,
        settings: HostelSettingsSchema,
        hostel_id: UUID,
    ) -> Optional[ServiceResult[HostelSettingsSchema]]:
        """
        Validate settings before update.
        
        Args:
            settings: Settings schema to validate
            hostel_id: UUID of the hostel
            
        Returns:
            ServiceResult with error if validation fails, None otherwise
        """
        # Add custom validation logic
        # For example: validate booking windows, payment thresholds, etc.
        
        # Example validation
        if hasattr(settings, 'booking_settings'):
            booking = settings.booking_settings
            if booking and hasattr(booking, 'advance_booking_days'):
                if booking.advance_booking_days and booking.advance_booking_days < 0:
                    return ServiceResult.failure(
                        ServiceError(
                            code=ErrorCode.VALIDATION_ERROR,
                            message="Advance booking days cannot be negative",
                            severity=ErrorSeverity.WARNING
                        )
                    )
        
        return None

    def _get_default_settings(self) -> HostelSettingsSchema:
        """
        Get default settings configuration.
        
        Returns:
            HostelSettingsSchema with default values
        """
        # Return default settings schema
        # This should be customized based on your application's defaults
        return HostelSettingsSchema()

    def _invalidate_cache(self, hostel_id: UUID) -> None:
        """
        Remove cached settings for a hostel.
        
        Args:
            hostel_id: UUID of the hostel
        """
        if hostel_id in self._settings_cache:
            del self._settings_cache[hostel_id]
            logger.debug(f"Settings cache invalidated for hostel: {hostel_id}")

    def clear_cache(self) -> None:
        """Clear all cached settings."""
        self._settings_cache.clear()
        logger.info("All hostel settings cache cleared")