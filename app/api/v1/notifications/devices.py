"""
Device Token Management API Endpoints

Handles registration and management of device tokens for push notifications
supporting both FCM (Firebase Cloud Messaging) and APNS (Apple Push Notification Service).
"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.dependencies import AuthenticationDependency
from app.services.notification.device_token_service import DeviceTokenService
from app.schemas.notification import (
    DeviceTokenCreate,
    DeviceTokenResponse,
)
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix="/notifications/devices",
    tags=["Notifications - Devices"],
)


def get_device_service() -> DeviceTokenService:
    """
    Dependency injection for DeviceTokenService.
    
    This should be wired to your DI container in production.
    Override this in your main app configuration.
    
    Raises:
        NotImplementedError: When DI container is not configured
    """
    raise NotImplementedError(
        "DeviceTokenService dependency must be configured in your DI container"
    )


def get_current_user(auth: AuthenticationDependency = Depends()):
    """
    Extract and validate the current authenticated user.
    
    Args:
        auth: Authentication dependency that handles token validation
        
    Returns:
        Current authenticated user object
        
    Raises:
        HTTPException: If authentication fails
    """
    try:
        return auth.get_current_user()
    except Exception as e:
        logger.error(f"Authentication failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials"
        )


@router.post(
    "",
    response_model=DeviceTokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register device token",
    description="Register a device token (FCM/APNS) for push notifications",
    response_description="Successfully registered device token",
)
async def register_device(
    payload: DeviceTokenCreate,
    device_service: DeviceTokenService = Depends(get_device_service),
    current_user = Depends(get_current_user),
) -> DeviceTokenResponse:
    """
    Register a device token for push notifications.
    
    This endpoint allows users to register their device tokens (FCM for Android, 
    APNS for iOS) to receive push notifications. If a device with the same token 
    already exists, it will be updated.
    
    Args:
        payload: Device registration data including token, platform, and device_id
        device_service: Injected device token service
        current_user: Authenticated user from dependency
        
    Returns:
        DeviceTokenResponse: Created or updated device token information
        
    Raises:
        HTTPException: If registration fails
    """
    try:
        logger.info(
            f"Registering device for user_id={current_user.id}, "
            f"platform={payload.platform}, device_id={payload.device_id}"
        )
        
        result = device_service.register_device(
            user_id=current_user.id,
            token=payload.token,
            platform=payload.platform,
            device_id=payload.device_id,
        )
        
        device_token = result.unwrap()
        logger.info(
            f"Device registered successfully: token_id={device_token.id}, "
            f"user_id={current_user.id}"
        )
        
        return device_token
        
    except Exception as e:
        logger.error(
            f"Failed to register device for user_id={current_user.id}: {str(e)}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to register device: {str(e)}"
        )


@router.get(
    "",
    response_model=List[DeviceTokenResponse],
    summary="List my devices",
    description="Retrieve all registered devices for the current user",
    response_description="List of registered device tokens",
)
async def list_devices(
    device_service: DeviceTokenService = Depends(get_device_service),
    current_user = Depends(get_current_user),
) -> List[DeviceTokenResponse]:
    """
    List all registered devices for the authenticated user.
    
    Returns all device tokens that have been registered for receiving 
    push notifications for the current user.
    
    Args:
        device_service: Injected device token service
        current_user: Authenticated user from dependency
        
    Returns:
        List[DeviceTokenResponse]: List of registered device tokens
        
    Raises:
        HTTPException: If retrieval fails
    """
    try:
        logger.debug(f"Fetching devices for user_id={current_user.id}")
        
        result = device_service.list_devices_for_user(user_id=current_user.id)
        devices = result.unwrap()
        
        logger.info(
            f"Retrieved {len(devices)} device(s) for user_id={current_user.id}"
        )
        
        return devices
        
    except Exception as e:
        logger.error(
            f"Failed to list devices for user_id={current_user.id}: {str(e)}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve devices"
        )


@router.delete(
    "/{token}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Unregister device",
    description="Remove a device token from the system",
    response_description="Device successfully unregistered",
)
async def unregister_device(
    token: str,
    device_service: DeviceTokenService = Depends(get_device_service),
    current_user = Depends(get_current_user),
) -> None:
    """
    Unregister a device token.
    
    Removes a device token from the system, preventing future push notifications 
    from being sent to this device. This is typically called when a user logs out 
    or uninstalls the app.
    
    Args:
        token: The device token to unregister
        device_service: Injected device token service
        current_user: Authenticated user from dependency
        
    Raises:
        HTTPException: If unregistration fails or token not found
    """
    try:
        logger.info(
            f"Unregistering device token for user_id={current_user.id}, token={token[:20]}..."
        )
        
        result = device_service.unregister_device(
            user_id=current_user.id, 
            token=token
        )
        result.unwrap()
        
        logger.info(
            f"Device unregistered successfully for user_id={current_user.id}"
        )
        
    except ValueError as e:
        logger.warning(
            f"Device token not found for user_id={current_user.id}, token={token[:20]}..."
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device token not found"
        )
    except Exception as e:
        logger.error(
            f"Failed to unregister device for user_id={current_user.id}: {str(e)}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to unregister device"
        )