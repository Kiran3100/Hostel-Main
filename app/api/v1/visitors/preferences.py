"""
Visitor preferences management endpoints.

This module provides endpoints for managing visitor preferences:
- General preferences (language, currency, etc.)
- Notification preferences
- Privacy settings
- Display preferences
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Body, status

from app.core.dependencies import get_current_user, get_visitor_preference_service
from app.schemas.visitor import (
    VisitorPreferences,
    NotificationPreferences,
    PrivacyPreferences,
    DisplayPreferences,
    PreferencesUpdate,
)
from app.services.visitor.visitor_preference_service import VisitorPreferenceService

# Type aliases for cleaner dependency injection
CurrentUser = Annotated[dict, Depends(get_current_user)]
PreferenceServiceDep = Annotated[VisitorPreferenceService, Depends(get_visitor_preference_service)]

router = APIRouter(
    prefix="/visitors/me/preferences",
    tags=["Visitors - Preferences"],
)


@router.get(
    "",
    response_model=VisitorPreferences,
    summary="Get visitor preferences",
    description="Retrieve all preferences for the current visitor.",
    responses={
        200: {
            "description": "Preferences retrieved successfully",
            "model": VisitorPreferences,
        },
        401: {"description": "Authentication required"},
        404: {"description": "Preferences not found"},
    },
)
async def get_preferences(
    current_user: CurrentUser,
    preference_service: PreferenceServiceDep,
) -> VisitorPreferences:
    """
    Retrieve all preferences for the current visitor.

    Includes:
    - Language and locale settings
    - Currency preferences
    - Notification settings
    - Privacy settings
    - Display preferences
    - Search defaults

    Args:
        current_user: Authenticated user from dependency injection
        preference_service: Preference service instance

    Returns:
        VisitorPreferences: Complete preference settings

    Raises:
        HTTPException: If preferences cannot be retrieved
    """
    result = await preference_service.get_preferences(visitor_user_id=current_user.id)
    return result.unwrap()


@router.put(
    "",
    response_model=VisitorPreferences,
    summary="Replace all visitor preferences",
    description="Completely replace all visitor preferences with new values.",
    responses={
        200: {
            "description": "Preferences replaced successfully",
            "model": VisitorPreferences,
        },
        400: {"description": "Invalid preference data"},
        401: {"description": "Authentication required"},
    },
)
async def set_preferences(
    current_user: CurrentUser,
    preference_service: PreferenceServiceDep,
    payload: VisitorPreferences = Body(
        ...,
        description="Complete preference settings",
        examples=[{
            "language": "en",
            "currency": "USD",
            "timezone": "America/New_York",
            "notifications": {
                "email_enabled": True,
                "push_enabled": True,
                "sms_enabled": False
            }
        }]
    ),
) -> VisitorPreferences:
    """
    Replace all visitor preferences.

    Warning: This replaces ALL preferences. Use PATCH for partial updates.

    Args:
        current_user: Authenticated user from dependency injection
        preference_service: Preference service instance
        payload: Complete new preference set

    Returns:
        VisitorPreferences: Updated preferences

    Raises:
        HTTPException: If update fails or data is invalid
    """
    result = await preference_service.set_preferences(
        visitor_user_id=current_user.id,
        data=payload
    )
    return result.unwrap()


@router.patch(
    "",
    response_model=VisitorPreferences,
    summary="Partially update preferences",
    description="Update specific preference fields without affecting others.",
    responses={
        200: {
            "description": "Preferences updated successfully",
            "model": VisitorPreferences,
        },
        400: {"description": "Invalid preference data"},
        401: {"description": "Authentication required"},
    },
)
async def update_preferences(
    current_user: CurrentUser,
    preference_service: PreferenceServiceDep,
    payload: PreferencesUpdate = Body(
        ...,
        description="Preference fields to update",
        examples=[{
            "language": "es",
            "currency": "EUR"
        }]
    ),
) -> VisitorPreferences:
    """
    Partially update visitor preferences.

    Only provided fields are updated; others remain unchanged.

    Args:
        current_user: Authenticated user from dependency injection
        preference_service: Preference service instance
        payload: Fields to update

    Returns:
        VisitorPreferences: Updated complete preferences

    Raises:
        HTTPException: If update fails
    """
    result = await preference_service.update_preferences(
        visitor_user_id=current_user.id,
        data=payload
    )
    return result.unwrap()


@router.delete(
    "",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Reset preferences to defaults",
    description="Reset all preferences to system defaults.",
    responses={
        204: {"description": "Preferences reset successfully"},
        401: {"description": "Authentication required"},
    },
)
async def reset_preferences(
    current_user: CurrentUser,
    preference_service: PreferenceServiceDep,
) -> None:
    """
    Reset all preferences to default values.

    This action:
    - Resets all custom preferences
    - Applies system defaults
    - Cannot be undone

    Args:
        current_user: Authenticated user from dependency injection
        preference_service: Preference service instance

    Raises:
        HTTPException: If reset fails
    """
    result = await preference_service.reset_preferences(visitor_user_id=current_user.id)
    result.unwrap()


# Notification Preferences Sub-routes

@router.get(
    "/notifications",
    response_model=NotificationPreferences,
    summary="Get notification preferences",
    description="Retrieve notification preferences for the current visitor.",
    responses={
        200: {
            "description": "Notification preferences retrieved successfully",
            "model": NotificationPreferences,
        },
        401: {"description": "Authentication required"},
    },
)
async def get_notification_preferences(
    current_user: CurrentUser,
    preference_service: PreferenceServiceDep,
) -> NotificationPreferences:
    """
    Retrieve notification preferences.

    Includes settings for:
    - Email notifications
    - Push notifications
    - SMS notifications
    - Notification frequency
    - Quiet hours
    - Notification types

    Args:
        current_user: Authenticated user from dependency injection
        preference_service: Preference service instance

    Returns:
        NotificationPreferences: Notification settings

    Raises:
        HTTPException: If preferences cannot be retrieved
    """
    result = await preference_service.get_notification_preferences(
        visitor_user_id=current_user.id
    )
    return result.unwrap()


@router.patch(
    "/notifications",
    response_model=NotificationPreferences,
    summary="Update notification preferences",
    description="Update specific notification preference settings.",
    responses={
        200: {
            "description": "Notification preferences updated successfully",
            "model": NotificationPreferences,
        },
        400: {"description": "Invalid preference data"},
        401: {"description": "Authentication required"},
    },
)
async def update_notification_preferences(
    current_user: CurrentUser,
    preference_service: PreferenceServiceDep,
    payload: NotificationPreferences = Body(
        ...,
        description="Notification settings to update",
        examples=[{
            "email_enabled": True,
            "push_enabled": True,
            "sms_enabled": False,
            "booking_updates": True,
            "promotional": False
        }]
    ),
) -> NotificationPreferences:
    """
    Update notification preferences.

    Granular control over:
    - Channel preferences (email, push, SMS)
    - Notification categories
    - Frequency settings
    - Quiet hours

    Args:
        current_user: Authenticated user from dependency injection
        preference_service: Preference service instance
        payload: Notification settings to update

    Returns:
        NotificationPreferences: Updated notification settings

    Raises:
        HTTPException: If update fails
    """
    result = await preference_service.update_notification_preferences(
        visitor_user_id=current_user.id,
        data=payload
    )
    return result.unwrap()


@router.post(
    "/notifications/opt-out-all",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Opt out from all notifications",
    description="Disable all notification channels and types.",
    responses={
        204: {"description": "Opted out from all notifications successfully"},
        401: {"description": "Authentication required"},
    },
)
async def opt_out_all_notifications(
    current_user: CurrentUser,
    preference_service: PreferenceServiceDep,
) -> None:
    """
    Disable all notifications.

    This action:
    - Disables all notification channels
    - Disables all notification types
    - Can be reversed by updating preferences

    Note: Critical account security notifications may still be sent.

    Args:
        current_user: Authenticated user from dependency injection
        preference_service: Preference service instance

    Raises:
        HTTPException: If operation fails
    """
    result = await preference_service.opt_out_all_notifications(
        visitor_user_id=current_user.id
    )
    result.unwrap()


@router.post(
    "/notifications/opt-in-all",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Opt in to all notifications",
    description="Enable all notification channels and types.",
    responses={
        204: {"description": "Opted in to all notifications successfully"},
        401: {"description": "Authentication required"},
    },
)
async def opt_in_all_notifications(
    current_user: CurrentUser,
    preference_service: PreferenceServiceDep,
) -> None:
    """
    Enable all notifications.

    This action enables:
    - All notification channels (email, push, SMS)
    - All notification types
    - Default frequency settings

    Args:
        current_user: Authenticated user from dependency injection
        preference_service: Preference service instance

    Raises:
        HTTPException: If operation fails
    """
    result = await preference_service.opt_in_all_notifications(
        visitor_user_id=current_user.id
    )
    result.unwrap()


# Privacy Preferences Sub-routes

@router.get(
    "/privacy",
    response_model=PrivacyPreferences,
    summary="Get privacy preferences",
    description="Retrieve privacy and data sharing preferences.",
    responses={
        200: {
            "description": "Privacy preferences retrieved successfully",
            "model": PrivacyPreferences,
        },
        401: {"description": "Authentication required"},
    },
)
async def get_privacy_preferences(
    current_user: CurrentUser,
    preference_service: PreferenceServiceDep,
) -> PrivacyPreferences:
    """
    Retrieve privacy preferences.

    Controls:
    - Profile visibility
    - Data sharing settings
    - Analytics opt-in/out
    - Third-party sharing

    Args:
        current_user: Authenticated user from dependency injection
        preference_service: Preference service instance

    Returns:
        PrivacyPreferences: Privacy settings

    Raises:
        HTTPException: If preferences cannot be retrieved
    """
    result = await preference_service.get_privacy_preferences(
        visitor_user_id=current_user.id
    )
    return result.unwrap()


@router.patch(
    "/privacy",
    response_model=PrivacyPreferences,
    summary="Update privacy preferences",
    description="Update privacy and data sharing settings.",
    responses={
        200: {
            "description": "Privacy preferences updated successfully",
            "model": PrivacyPreferences,
        },
        400: {"description": "Invalid preference data"},
        401: {"description": "Authentication required"},
    },
)
async def update_privacy_preferences(
    current_user: CurrentUser,
    preference_service: PreferenceServiceDep,
    payload: PrivacyPreferences = Body(..., description="Privacy settings to update"),
) -> PrivacyPreferences:
    """
    Update privacy preferences.

    Args:
        current_user: Authenticated user from dependency injection
        preference_service: Preference service instance
        payload: Privacy settings to update

    Returns:
        PrivacyPreferences: Updated privacy settings

    Raises:
        HTTPException: If update fails
    """
    result = await preference_service.update_privacy_preferences(
        visitor_user_id=current_user.id,
        data=payload
    )
    return result.unwrap()


# Display Preferences Sub-routes

@router.get(
    "/display",
    response_model=DisplayPreferences,
    summary="Get display preferences",
    description="Retrieve UI and display preferences.",
    responses={
        200: {
            "description": "Display preferences retrieved successfully",
            "model": DisplayPreferences,
        },
        401: {"description": "Authentication required"},
    },
)
async def get_display_preferences(
    current_user: CurrentUser,
    preference_service: PreferenceServiceDep,
) -> DisplayPreferences:
    """
    Retrieve display preferences.

    Controls:
    - Theme (light/dark/auto)
    - List vs grid view
    - Items per page
    - Map default zoom
    - Accessibility settings

    Args:
        current_user: Authenticated user from dependency injection
        preference_service: Preference service instance

    Returns:
        DisplayPreferences: Display settings

    Raises:
        HTTPException: If preferences cannot be retrieved
    """
    result = await preference_service.get_display_preferences(
        visitor_user_id=current_user.id
    )
    return result.unwrap()


@router.patch(
    "/display",
    response_model=DisplayPreferences,
    summary="Update display preferences",
    description="Update UI and display settings.",
    responses={
        200: {
            "description": "Display preferences updated successfully",
            "model": DisplayPreferences,
        },
        400: {"description": "Invalid preference data"},
        401: {"description": "Authentication required"},
    },
)
async def update_display_preferences(
    current_user: CurrentUser,
    preference_service: PreferenceServiceDep,
    payload: DisplayPreferences = Body(..., description="Display settings to update"),
) -> DisplayPreferences:
    """
    Update display preferences.

    Args:
        current_user: Authenticated user from dependency injection
        preference_service: Preference service instance
        payload: Display settings to update

    Returns:
        DisplayPreferences: Updated display settings

    Raises:
        HTTPException: If update fails
    """
    result = await preference_service.update_display_preferences(
        visitor_user_id=current_user.id,
        data=payload
    )
    return result.unwrap()