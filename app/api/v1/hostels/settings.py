"""
Hostel Settings API Endpoints
Manages hostel configuration and preferences
"""
from typing import Any

from fastapi import APIRouter, Depends, Query, Path, HTTPException, status
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.hostel.hostel_admin import (
    HostelSettings,
    HostelSettingsUpdate,
    NotificationSettings,
    BookingSettings,
    PaymentSettings,
)
from app.services.hostel.hostel_settings_service import HostelSettingsService
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/hostels/settings", tags=["hostels:settings"])


def get_settings_service(
    db: Session = Depends(deps.get_db)
) -> HostelSettingsService:
    """
    Dependency to get hostel settings service instance
    
    Args:
        db: Database session
        
    Returns:
        HostelSettingsService instance
    """
    return HostelSettingsService(db=db)


@router.get(
    "/{hostel_id}",
    response_model=HostelSettings,
    summary="Get hostel settings",
    description="Retrieve all settings and configurations for a hostel",
    responses={
        200: {"description": "Settings retrieved successfully"},
        401: {"description": "Not authenticated"},
        403: {"description": "Not authorized (admin required)"},
        404: {"description": "Hostel not found"},
    },
)
def get_settings(
    hostel_id: str = Path(
        ...,
        description="ID of the hostel",
        example="550e8400-e29b-41d4-a716-446655440000"
    ),
    admin=Depends(deps.get_admin_user),
    service: HostelSettingsService = Depends(get_settings_service),
) -> HostelSettings:
    """
    Get hostel settings.
    
    Returns all configurable settings including:
    - Notification preferences
    - Booking rules
    - Payment configurations
    - Check-in/out times
    - Cancellation policies
    - Guest policies
    
    Args:
        hostel_id: The hostel identifier
        admin: Current admin user
        service: Settings service instance
        
    Returns:
        Complete hostel settings
        
    Raises:
        HTTPException: If hostel not found or access denied
    """
    try:
        # Verify admin has access to this hostel
        if not admin.is_super_admin and admin.hostel_id != hostel_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access these settings"
            )
        
        settings = service.get_settings(hostel_id)
        
        if not settings:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Hostel not found"
            )
        
        logger.info(f"Admin {admin.id} retrieved settings for hostel {hostel_id}")
        return settings
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving settings: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve settings"
        )


@router.put(
    "/{hostel_id}",
    response_model=HostelSettings,
    summary="Update hostel settings",
    description="Update hostel configuration and preferences",
    responses={
        200: {"description": "Settings updated successfully"},
        400: {"description": "Invalid settings data"},
        401: {"description": "Not authenticated"},
        403: {"description": "Not authorized (admin required)"},
        404: {"description": "Hostel not found"},
    },
)
def update_settings(
    hostel_id: str = Path(
        ...,
        description="ID of the hostel",
        example="550e8400-e29b-41d4-a716-446655440000"
    ),
    payload: HostelSettingsUpdate = ...,
    admin=Depends(deps.get_admin_user),
    service: HostelSettingsService = Depends(get_settings_service),
) -> HostelSettings:
    """
    Update hostel settings.
    
    All fields are optional - only provided fields will be updated.
    
    Args:
        hostel_id: The hostel identifier
        payload: Updated settings data
        admin: Current admin user
        service: Settings service instance
        
    Returns:
        Updated settings
        
    Raises:
        HTTPException: If update fails or access denied
    """
    try:
        # Verify admin has access to this hostel
        if not admin.is_super_admin and admin.hostel_id != hostel_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to modify these settings"
            )
        
        logger.info(f"Admin {admin.id} updating settings for hostel {hostel_id}")
        
        updated_settings = service.update_settings(hostel_id, payload)
        
        if not updated_settings:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Hostel not found"
            )
        
        logger.info(f"Settings updated for hostel {hostel_id}")
        return updated_settings
        
    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating settings: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update settings"
        )


@router.patch(
    "/{hostel_id}/notifications",
    response_model=NotificationSettings,
    summary="Update notification settings",
    description="Update notification preferences for a hostel",
    responses={
        200: {"description": "Notification settings updated successfully"},
        400: {"description": "Invalid settings"},
        401: {"description": "Not authenticated"},
        403: {"description": "Not authorized (admin required)"},
        404: {"description": "Hostel not found"},
    },
)
def update_notification_settings(
    hostel_id: str = Path(
        ...,
        description="ID of the hostel",
        example="550e8400-e29b-41d4-a716-446655440000"
    ),
    payload: NotificationSettings = ...,
    admin=Depends(deps.get_admin_user),
    service: HostelSettingsService = Depends(get_settings_service),
) -> NotificationSettings:
    """
    Update notification settings.
    
    Controls:
    - Email notifications
    - SMS notifications
    - Push notifications
    - Notification frequency
    - Event types to notify
    
    Args:
        hostel_id: The hostel identifier
        payload: Notification settings
        admin: Current admin user
        service: Settings service instance
        
    Returns:
        Updated notification settings
    """
    try:
        if not admin.is_super_admin and admin.hostel_id != hostel_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to modify settings"
            )
        
        updated = service.update_notification_settings(hostel_id, payload)
        
        if not updated:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Hostel not found"
            )
        
        logger.info(f"Notification settings updated for hostel {hostel_id}")
        return updated
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating notification settings: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update notification settings"
        )


@router.patch(
    "/{hostel_id}/booking",
    response_model=BookingSettings,
    summary="Update booking settings",
    description="Update booking rules and policies",
    responses={
        200: {"description": "Booking settings updated successfully"},
        400: {"description": "Invalid settings"},
        401: {"description": "Not authenticated"},
        403: {"description": "Not authorized (admin required)"},
        404: {"description": "Hostel not found"},
    },
)
def update_booking_settings(
    hostel_id: str = Path(
        ...,
        description="ID of the hostel",
        example="550e8400-e29b-41d4-a716-446655440000"
    ),
    payload: BookingSettings = ...,
    admin=Depends(deps.get_admin_user),
    service: HostelSettingsService = Depends(get_settings_service),
) -> BookingSettings:
    """
    Update booking settings.
    
    Controls:
    - Advance booking period
    - Minimum stay duration
    - Maximum stay duration
    - Auto-approval settings
    - Cancellation windows
    - Buffer periods
    
    Args:
        hostel_id: The hostel identifier
        payload: Booking settings
        admin: Current admin user
        service: Settings service instance
        
    Returns:
        Updated booking settings
    """
    try:
        if not admin.is_super_admin and admin.hostel_id != hostel_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to modify settings"
            )
        
        updated = service.update_booking_settings(hostel_id, payload)
        
        if not updated:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Hostel not found"
            )
        
        logger.info(f"Booking settings updated for hostel {hostel_id}")
        return updated
        
    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating booking settings: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update booking settings"
        )


@router.patch(
    "/{hostel_id}/payment",
    response_model=PaymentSettings,
    summary="Update payment settings",
    description="Update payment processing configurations",
    responses={
        200: {"description": "Payment settings updated successfully"},
        400: {"description": "Invalid settings"},
        401: {"description": "Not authenticated"},
        403: {"description": "Not authorized (admin required)"},
        404: {"description": "Hostel not found"},
    },
)
def update_payment_settings(
    hostel_id: str = Path(
        ...,
        description="ID of the hostel",
        example="550e8400-e29b-41d4-a716-446655440000"
    ),
    payload: PaymentSettings = ...,
    admin=Depends(deps.get_admin_user),
    service: HostelSettingsService = Depends(get_settings_service),
) -> PaymentSettings:
    """
    Update payment settings.
    
    Controls:
    - Accepted payment methods
    - Payment gateways
    - Security deposit requirements
    - Refund policies
    - Late payment fees
    - Payment schedules
    
    Args:
        hostel_id: The hostel identifier
        payload: Payment settings
        admin: Current admin user
        service: Settings service instance
        
    Returns:
        Updated payment settings
    """
    try:
        if not admin.is_super_admin and admin.hostel_id != hostel_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to modify settings"
            )
        
        updated = service.update_payment_settings(hostel_id, payload)
        
        if not updated:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Hostel not found"
            )
        
        logger.info(f"Payment settings updated for hostel {hostel_id}")
        return updated
        
    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating payment settings: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update payment settings"
        )


@router.post(
    "/{hostel_id}/reset",
    response_model=HostelSettings,
    summary="Reset settings to defaults",
    description="Reset hostel settings to default values",
    responses={
        200: {"description": "Settings reset successfully"},
        401: {"description": "Not authenticated"},
        403: {"description": "Not authorized (super admin required)"},
        404: {"description": "Hostel not found"},
    },
)
def reset_settings(
    hostel_id: str = Path(
        ...,
        description="ID of the hostel",
        example="550e8400-e29b-41d4-a716-446655440000"
    ),
    super_admin=Depends(deps.get_super_admin_user),
    service: HostelSettingsService = Depends(get_settings_service),
) -> HostelSettings:
    """
    Reset all settings to default values.
    
    This is a destructive operation and requires super admin privileges.
    
    Args:
        hostel_id: The hostel identifier
        super_admin: Current super admin user
        service: Settings service instance
        
    Returns:
        Default settings
    """
    try:
        logger.warning(
            f"Super admin {super_admin.id} resetting settings for hostel {hostel_id}"
        )
        
        reset_settings = service.reset_to_defaults(hostel_id)
        
        if not reset_settings:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Hostel not found"
            )
        
        logger.info(f"Settings reset to defaults for hostel {hostel_id}")
        return reset_settings
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resetting settings: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reset settings"
        )