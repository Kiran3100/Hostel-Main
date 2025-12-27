"""
Notification Preferences API Endpoints

Manages user notification preferences including channel preferences,
notification types, quiet hours, and unsubscribe functionality.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.dependencies import AuthenticationDependency
from app.services.notification.notification_preference_service import NotificationPreferenceService
from app.schemas.notification import (
    NotificationPreferences,
    NotificationPreferencesUpdate,
)
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix="/notifications/preferences",
    tags=["Notifications - Preferences"],
)


def get_preference_service() -> NotificationPreferenceService:
    """
    Dependency injection for NotificationPreferenceService.
    
    Raises:
        NotImplementedError: When DI container is not configured
    """
    raise NotImplementedError(
        "NotificationPreferenceService dependency must be configured in your DI container"
    )


def get_current_user(auth: AuthenticationDependency = Depends()):
    """
    Extract and validate the current authenticated user.
    
    Returns:
        Current authenticated user object
    """
    try:
        return auth.get_current_user()
    except Exception as e:
        logger.error(f"Authentication failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials"
        )


@router.get(
    "",
    response_model=NotificationPreferences,
    summary="Get notification preferences",
    description="Retrieve current notification preferences for the authenticated user",
    response_description="User notification preferences",
)
async def get_preferences(
    preference_service: NotificationPreferenceService = Depends(get_preference_service),
    current_user = Depends(get_current_user),
) -> NotificationPreferences:
    """
    Get notification preferences for the current user.
    
    Returns the user's current notification settings including:
    - Channel preferences (email, SMS, push, in-app)
    - Notification type preferences
    - Quiet hours settings
    - Frequency settings
    
    Args:
        preference_service: Injected preference service
        current_user: Authenticated user from dependency
        
    Returns:
        NotificationPreferences: Current user preferences
        
    Raises:
        HTTPException: If retrieval fails
    """
    try:
        logger.debug(f"Fetching preferences for user_id={current_user.id}")
        
        result = preference_service.get_preferences(user_id=current_user.id)
        preferences = result.unwrap()
        
        logger.info(f"Preferences retrieved for user_id={current_user.id}")
        
        return preferences
        
    except Exception as e:
        logger.error(
            f"Failed to get preferences for user_id={current_user.id}: {str(e)}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve notification preferences"
        )


@router.put(
    "",
    response_model=NotificationPreferences,
    summary="Set notification preferences",
    description="Set/replace all notification preferences for the authenticated user",
    response_description="Updated notification preferences",
)
async def set_preferences(
    payload: NotificationPreferences,
    preference_service: NotificationPreferenceService = Depends(get_preference_service),
    current_user = Depends(get_current_user),
) -> NotificationPreferences:
    """
    Set notification preferences for the current user.
    
    This endpoint performs a full replacement of user preferences.
    Use PATCH endpoint for partial updates.
    
    Args:
        payload: Complete notification preferences
        preference_service: Injected preference service
        current_user: Authenticated user from dependency
        
    Returns:
        NotificationPreferences: Updated preferences
        
    Raises:
        HTTPException: If update fails
    """
    try:
        logger.info(
            f"Setting preferences for user_id={current_user.id}: {payload.dict()}"
        )
        
        result = preference_service.set_preferences(
            user_id=current_user.id,
            data=payload,
        )
        
        preferences = result.unwrap()
        
        logger.info(f"Preferences updated successfully for user_id={current_user.id}")
        
        return preferences
        
    except ValueError as e:
        logger.warning(
            f"Invalid preference data for user_id={current_user.id}: {str(e)}"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid preference data: {str(e)}"
        )
    except Exception as e:
        logger.error(
            f"Failed to set preferences for user_id={current_user.id}: {str(e)}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update notification preferences"
        )


@router.patch(
    "",
    response_model=NotificationPreferences,
    summary="Update notification preferences",
    description="Partially update notification preferences for the authenticated user",
    response_description="Updated notification preferences",
)
async def update_preferences(
    payload: NotificationPreferencesUpdate,
    preference_service: NotificationPreferenceService = Depends(get_preference_service),
    current_user = Depends(get_current_user),
) -> NotificationPreferences:
    """
    Partially update notification preferences.
    
    Only the fields provided in the payload will be updated.
    Other preferences will remain unchanged.
    
    Args:
        payload: Partial notification preferences update
        preference_service: Injected preference service
        current_user: Authenticated user from dependency
        
    Returns:
        NotificationPreferences: Updated complete preferences
        
    Raises:
        HTTPException: If update fails
    """
    try:
        logger.info(
            f"Updating preferences for user_id={current_user.id}: "
            f"{payload.dict(exclude_unset=True)}"
        )
        
        result = preference_service.update_preferences(
            user_id=current_user.id,
            data=payload,
        )
        
        preferences = result.unwrap()
        
        logger.info(
            f"Preferences partially updated for user_id={current_user.id}"
        )
        
        return preferences
        
    except ValueError as e:
        logger.warning(
            f"Invalid preference update data for user_id={current_user.id}: {str(e)}"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid preference data: {str(e)}"
        )
    except Exception as e:
        logger.error(
            f"Failed to update preferences for user_id={current_user.id}: {str(e)}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update notification preferences"
        )


@router.post(
    "/unsubscribe",
    summary="Unsubscribe via token",
    description="Public endpoint to handle one-click unsubscribe from emails",
    response_description="Unsubscribe confirmation",
)
async def unsubscribe(
    token: str = Query(..., description="Unsubscribe token from email"),
    preference_service: NotificationPreferenceService = Depends(get_preference_service),
) -> dict:
    """
    Handle one-click unsubscribe from email notifications.
    
    This is a public endpoint that doesn't require authentication.
    It uses a secure token that is generated when emails are sent.
    
    Typically linked from email footers to comply with email regulations
    (CAN-SPAM, GDPR, etc.).
    
    Args:
        token: Secure unsubscribe token from email
        preference_service: Injected preference service
        
    Returns:
        dict: Confirmation message and updated preferences
        
    Raises:
        HTTPException: If token is invalid or operation fails
    """
    try:
        logger.info(f"Processing unsubscribe request with token: {token[:20]}...")
        
        if not token or len(token) < 10:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid unsubscribe token"
            )
        
        result = preference_service.process_unsubscribe(token=token)
        response = result.unwrap()
        
        logger.info(
            f"Unsubscribe processed successfully for token: {token[:20]}..."
        )
        
        return {
            "message": "You have been successfully unsubscribed from email notifications",
            **response
        }
        
    except ValueError as e:
        logger.warning(f"Invalid unsubscribe token: {token[:20]}...")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired unsubscribe token"
        )
    except Exception as e:
        logger.error(
            f"Failed to process unsubscribe: {str(e)}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process unsubscribe request"
        )