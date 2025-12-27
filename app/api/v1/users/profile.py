"""
User profile management endpoints.

Handles profile information, images, contact details,
and profile completeness tracking.
"""
from typing import Any

from fastapi import APIRouter, Depends, status
from fastapi.responses import Response

from app.core.dependencies import AuthenticationDependency
from app.services.user.user_profile_service import UserProfileService
from app.schemas.user import UserDetail
from app.schemas.user_profile import (
    ProfileUpdate,
    ProfileImageUpdate,
    ContactInfoUpdate,
    ProfileCompletenessResponse,
)

router = APIRouter(
    prefix="/users/me/profile",
    tags=["Users - Profile"],
)


# ==================== Dependencies ====================


def get_profile_service() -> UserProfileService:
    """
    Dependency injection for UserProfileService.
    
    Returns:
        UserProfileService: Configured profile service instance
        
    Raises:
        NotImplementedError: When service factory is not configured
    """
    # TODO: Wire to ServiceFactory / DI container
    raise NotImplementedError("UserProfileService dependency must be configured")


def get_current_user(auth: AuthenticationDependency = Depends()) -> Any:
    """
    Extract current authenticated user from auth dependency.
    
    Args:
        auth: Authentication dependency instance
        
    Returns:
        User object for the authenticated user
    """
    return auth.get_current_user()


# ==================== Profile Endpoints ====================


@router.get(
    "",
    response_model=UserDetail,
    summary="Get current user profile",
    description="Retrieve complete profile information for authenticated user",
    response_description="Current user's profile details",
)
async def get_user_profile(
    profile_service: UserProfileService = Depends(get_profile_service),
    current_user: Any = Depends(get_current_user),
) -> UserDetail:
    """
    Get current user's complete profile.
    
    Returns all profile fields including:
    - Basic information (name, username)
    - Contact details (email, phone)
    - Profile image
    - Preferences
    - Metadata (created_at, updated_at)
    
    Returns:
        Complete user profile details
    """
    result = profile_service.get_profile(user_id=current_user.id)
    return result.unwrap()


@router.patch(
    "",
    response_model=UserDetail,
    summary="Update profile",
    description="Partially update user profile information",
    response_description="Updated user profile",
    responses={
        200: {"description": "Profile updated successfully"},
        400: {"description": "Invalid profile data"},
    },
)
async def update_user_profile(
    payload: ProfileUpdate,
    profile_service: UserProfileService = Depends(get_profile_service),
    current_user: Any = Depends(get_current_user),
) -> UserDetail:
    """
    Partially update current user's profile.
    
    Only provided fields will be updated (PATCH semantics).
    Supports updating:
    - Display name
    - Bio/description
    - Location
    - Social media links
    - Other profile metadata
    
    Args:
        payload: Partial profile data to update
        
    Returns:
        Updated user profile
        
    Raises:
        HTTPException: 400 if validation fails
    """
    result = profile_service.update_profile(
        user_id=current_user.id,
        data=payload,
    )
    return result.unwrap()


# ==================== Profile Image Management ====================


@router.put(
    "/image",
    response_model=UserDetail,
    status_code=status.HTTP_200_OK,
    summary="Update profile image",
    description="Set or replace user's profile image",
    response_description="Updated user profile with new image",
    responses={
        200: {"description": "Profile image updated successfully"},
        400: {"description": "Invalid image data or format"},
        413: {"description": "Image file too large"},
    },
)
async def update_profile_image(
    payload: ProfileImageUpdate,
    profile_service: UserProfileService = Depends(get_profile_service),
    current_user: Any = Depends(get_current_user),
) -> UserDetail:
    """
    Update user's profile image.
    
    Accepts image URL or base64-encoded image data.
    Old image will be replaced (and potentially deleted from storage).
    
    **Constraints:**
    - Supported formats: JPEG, PNG, WebP
    - Maximum size: typically 5MB (configurable)
    - Recommended dimensions: 400x400 pixels
    
    Args:
        payload: Image update data (URL or base64)
        
    Returns:
        Updated user profile with new image URL
        
    Raises:
        HTTPException: 400 if image format invalid
        HTTPException: 413 if image too large
    """
    result = profile_service.update_profile_image(
        user_id=current_user.id,
        data=payload,
    )
    return result.unwrap()


@router.delete(
    "/image",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove profile image",
    description="Delete current user's profile image",
    responses={
        204: {"description": "Profile image removed successfully"},
        404: {"description": "No profile image to remove"},
    },
)
async def remove_profile_image(
    profile_service: UserProfileService = Depends(get_profile_service),
    current_user: Any = Depends(get_current_user),
) -> Response:
    """
    Remove user's profile image.
    
    Sets profile image to null/default and deletes
    associated image file from storage if applicable.
    
    Returns:
        204 No Content on success
    """
    profile_service.remove_profile_image(user_id=current_user.id).unwrap()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ==================== Contact Information ====================


@router.patch(
    "/contact",
    response_model=UserDetail,
    summary="Update contact information",
    description="Update user's contact details",
    response_description="Updated user profile",
    responses={
        200: {"description": "Contact information updated successfully"},
        400: {"description": "Invalid contact data"},
        409: {"description": "Email or phone already in use"},
    },
)
async def update_contact_information(
    payload: ContactInfoUpdate,
    profile_service: UserProfileService = Depends(get_profile_service),
    current_user: Any = Depends(get_current_user),
) -> UserDetail:
    """
    Update contact information.
    
    Supports updating:
    - Email address (may require verification)
    - Phone number (may require verification)
    - Alternative contact methods
    
    **Security Note:**
    Email/phone changes may trigger verification workflows
    and require confirmation before taking effect.
    
    Args:
        payload: Contact information to update
        
    Returns:
        Updated user profile
        
    Raises:
        HTTPException: 400 if validation fails
        HTTPException: 409 if email/phone already taken
    """
    result = profile_service.update_contact_info(
        user_id=current_user.id,
        data=payload,
    )
    return result.unwrap()


# ==================== Profile Analytics ====================


@router.get(
    "/completeness",
    response_model=ProfileCompletenessResponse,
    summary="Get profile completeness",
    description="Calculate profile completion percentage and missing fields",
    response_description="Profile completeness metrics",
)
async def get_profile_completeness(
    profile_service: UserProfileService = Depends(get_profile_service),
    current_user: Any = Depends(get_current_user),
) -> ProfileCompletenessResponse:
    """
    Get profile completeness metrics.
    
    Analyzes the user's profile and returns:
    - Completion percentage (0-100)
    - List of missing/incomplete fields
    - Suggestions for improving profile
    
    Useful for:
    - Onboarding flows
    - Profile completion prompts
    - User engagement metrics
    
    Returns:
        Profile completeness analysis with percentage and missing fields
    """
    result = profile_service.get_profile_completeness(user_id=current_user.id)
    return result.unwrap()