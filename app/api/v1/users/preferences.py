"""
User preference management endpoints.

Handles notification preferences, quiet hours,
and other user-configurable settings.
"""
from typing import Any

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import Response

from app.core.dependencies import AuthenticationDependency
from app.services.user.user_preference_service import UserPreferenceService
from app.schemas.user.user_preferences import (
    UserNotificationPreferences,
    UserNotificationPreferencesUpdate,
)

router = APIRouter(
    prefix="/users/me/preferences",
    tags=["Users - Preferences"],
)


# ==================== Dependencies ====================


def get_preference_service() -> UserPreferenceService:
    """
    Dependency injection for UserPreferenceService.
    
    Returns:
        UserPreferenceService: Configured preference service instance
        
    Raises:
        NotImplementedError: When service factory is not configured
    """
    # TODO: Wire to ServiceFactory / DI container
    raise NotImplementedError("UserPreferenceService dependency must be configured")


def get_current_user(auth: AuthenticationDependency = Depends()) -> Any:
    """
    Extract current authenticated user from auth dependency.
    
    Args:
        auth: Authentication dependency instance
        
    Returns:
        User object for the authenticated user
    """
    return auth.get_current_user()


# ==================== Notification Preferences ====================


@router.get(
    "/notifications",
    response_model=UserNotificationPreferences,
    summary="Get notification preferences",
    description="Retrieve current notification preferences for authenticated user",
    response_description="Current notification preferences",
)
async def get_notification_preferences(
    preference_service: UserPreferenceService = Depends(get_preference_service),
    current_user: Any = Depends(get_current_user),
) -> UserNotificationPreferences:
    """
    Get user's notification preferences.
    
    Returns all notification settings including:
    - Email notification toggles
    - Push notification settings
    - SMS preferences
    - Notification categories (messages, updates, marketing)
    - Quiet hours configuration
    
    Returns:
        Complete notification preference configuration
    """
    result = preference_service.get_notification_preferences(user_id=current_user.id)
    return result.unwrap()


@router.put(
    "/notifications",
    response_model=UserNotificationPreferences,
    summary="Replace notification preferences",
    description="Replace all notification preferences with new configuration",
    response_description="Updated notification preferences",
    responses={
        200: {"description": "Preferences updated successfully"},
        400: {"description": "Invalid preference data"},
    },
)
async def replace_notification_preferences(
    payload: UserNotificationPreferences,
    preference_service: UserPreferenceService = Depends(get_preference_service),
    current_user: Any = Depends(get_current_user),
) -> UserNotificationPreferences:
    """
    Replace all notification preferences.
    
    **PUT semantics** - replaces entire preference object.
    All fields must be provided or will revert to defaults.
    
    Use PATCH endpoint for partial updates.
    
    Args:
        payload: Complete notification preference configuration
        
    Returns:
        Updated notification preferences
        
    Raises:
        HTTPException: 400 if validation fails
    """
    result = preference_service.update_notification_preferences(
        user_id=current_user.id,
        data=payload,
    )
    return result.unwrap()


@router.patch(
    "/notifications",
    response_model=UserNotificationPreferences,
    summary="Partially update notification preferences",
    description="Update specific notification preferences without affecting others",
    response_description="Updated notification preferences",
    responses={
        200: {"description": "Preferences updated successfully"},
        400: {"description": "Invalid preference data"},
    },
)
async def update_notification_preferences(
    payload: UserNotificationPreferencesUpdate,
    preference_service: UserPreferenceService = Depends(get_preference_service),
    current_user: Any = Depends(get_current_user),
) -> UserNotificationPreferences:
    """
    Partially update notification preferences.
    
    **PATCH semantics** - only provided fields are updated.
    Other preferences remain unchanged.
    
    Recommended for most use cases as it's safer than PUT.
    
    Args:
        payload: Partial notification preference updates
        
    Returns:
        Complete updated notification preferences
    """
    result = preference_service.update_notification_preferences(
        user_id=current_user.id,
        data=payload,
    )
    return result.unwrap()


@router.post(
    "/notifications/reset",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Reset notification preferences to defaults",
    description="Restore all notification preferences to system defaults",
    responses={
        204: {"description": "Preferences reset successfully"},
    },
)
async def reset_notification_preferences(
    preference_service: UserPreferenceService = Depends(get_preference_service),
    current_user: Any = Depends(get_current_user),
) -> Response:
    """
    Reset notification preferences to defaults.
    
    Reverts all custom preference settings and restores
    system-defined default notification configuration.
    
    Useful for troubleshooting or starting fresh.
    
    Returns:
        204 No Content on success
    """
    preference_service.reset_to_defaults(user_id=current_user.id).unwrap()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ==================== Quiet Hours Management ====================


@router.post(
    "/notifications/quiet-hours",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Set quiet hours",
    description="Configure time period during which notifications are suppressed",
    responses={
        204: {"description": "Quiet hours configured successfully"},
        400: {"description": "Invalid time format"},
    },
)
async def set_quiet_hours(
    start_time: str = Query(
        ...,
        description="Start time in HH:MM format (24-hour)",
        regex=r"^([01]\d|2[0-3]):([0-5]\d)$",
        example="22:00",
    ),
    end_time: str = Query(
        ...,
        description="End time in HH:MM format (24-hour)",
        regex=r"^([01]\d|2[0-3]):([0-5]\d)$",
        example="07:00",
    ),
    preference_service: UserPreferenceService = Depends(get_preference_service),
    current_user: Any = Depends(get_current_user),
) -> Response:
    """
    Set quiet hours for notification suppression.
    
    During quiet hours, non-critical notifications will be:
    - Suppressed entirely, OR
    - Queued for delivery after quiet hours end
    
    **Time Format:** HH:MM in 24-hour format
    **Timezone:** Uses user's configured timezone
    
    Can span midnight (e.g., 22:00 to 07:00).
    
    Args:
        start_time: When quiet hours begin (HH:MM)
        end_time: When quiet hours end (HH:MM)
        
    Returns:
        204 No Content on success
        
    Raises:
        HTTPException: 400 if time format invalid
    """
    preference_service.set_quiet_hours(
        user_id=current_user.id,
        start_time=start_time,
        end_time=end_time,
    ).unwrap()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete(
    "/notifications/quiet-hours",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Disable quiet hours",
    description="Remove quiet hours configuration",
    responses={
        204: {"description": "Quiet hours disabled successfully"},
    },
)
async def disable_quiet_hours(
    preference_service: UserPreferenceService = Depends(get_preference_service),
    current_user: Any = Depends(get_current_user),
) -> Response:
    """
    Disable quiet hours.
    
    Removes quiet hours configuration, allowing notifications
    at all times according to other preference settings.
    
    Returns:
        204 No Content on success
    """
    preference_service.disable_quiet_hours(user_id=current_user.id).unwrap()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/notifications/quiet-hours/status",
    summary="Check quiet hours status",
    description="Determine if current time falls within quiet hours",
    response_description="Quiet hours status",
)
async def check_quiet_hours_status(
    preference_service: UserPreferenceService = Depends(get_preference_service),
    current_user: Any = Depends(get_current_user),
) -> dict[str, bool]:
    """
    Check if currently in quiet hours.
    
    Evaluates current time against user's configured
    quiet hours (if any) and timezone.
    
    Useful for:
    - UI indicators
    - Client-side notification logic
    - Testing quiet hours configuration
    
    Returns:
        Dictionary with 'in_quiet_hours' boolean field
    """
    result = preference_service.is_in_quiet_hours(user_id=current_user.id)
    return {"in_quiet_hours": result.unwrap()}