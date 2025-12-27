"""
Core user management endpoints.

Provides CRUD operations and user administration functionality
for both admin and self-service use cases.
"""
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query, Path, status, HTTPException
from fastapi.responses import Response

from app.core.dependencies import AuthenticationDependency
from app.services.user.user_service import UserService
from app.schemas.user import (
    UserResponse,
    UserDetail,
    UserListItem,
    UserStats,
    UserCreate,
    UserUpdate,
)
from app.schemas.common import PaginatedResponse

router = APIRouter(
    prefix="/users",
    tags=["Users"],
)


# ==================== Dependencies ====================


def get_user_service() -> UserService:
    """
    Dependency injection for UserService.
    
    Returns:
        UserService: Configured user service instance
        
    Raises:
        NotImplementedError: When service factory is not configured
    """
    # TODO: Wire to ServiceFactory / DI container
    raise NotImplementedError("UserService dependency must be configured")


def get_current_user(auth: AuthenticationDependency = Depends()) -> Any:
    """
    Extract current authenticated user from auth dependency.
    
    Args:
        auth: Authentication dependency instance
        
    Returns:
        User object for the authenticated user
    """
    return auth.get_current_user()


# ==================== Self-Service Endpoints ====================


@router.get(
    "/me",
    response_model=UserDetail,
    summary="Get current user profile",
    description="Retrieve complete profile information for the authenticated user",
    response_description="Current user's detailed profile",
)
async def get_current_user_profile(
    user_service: UserService = Depends(get_user_service),
    current_user: Any = Depends(get_current_user),
) -> UserDetail:
    """
    Get authenticated user's complete profile.
    
    This endpoint provides self-service access to user profile data
    without requiring admin privileges.
    """
    result = user_service.get_user(user_id=current_user.id)
    return result.unwrap()


# ==================== Admin User Management ====================


@router.post(
    "",
    response_model=UserDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Create new user",
    description="Create a new user account (admin only)",
    response_description="Created user details",
    responses={
        201: {"description": "User created successfully"},
        400: {"description": "Invalid user data"},
        409: {"description": "User already exists"},
    },
)
async def create_user(
    payload: UserCreate,
    user_service: UserService = Depends(get_user_service),
    current_user: Any = Depends(get_current_user),
) -> UserDetail:
    """
    Create a new user account.
    
    **Admin-only endpoint**
    
    Args:
        payload: User creation data including email, password, role, etc.
        
    Returns:
        Newly created user with full details
        
    Raises:
        HTTPException: 409 if user already exists
        HTTPException: 400 if validation fails
    """
    # TODO: Enforce admin-only access via AuthorizationDependency
    result = user_service.create_user(data=payload)
    return result.unwrap()


@router.get(
    "",
    response_model=PaginatedResponse[UserListItem],
    summary="List users with filtering",
    description="Retrieve paginated list of users with optional filters (admin only)",
    response_description="Paginated user list",
)
async def list_users(
    user_service: UserService = Depends(get_user_service),
    current_user: Any = Depends(get_current_user),
    # Filter parameters
    role: Optional[str] = Query(
        None,
        description="Filter by user role",
        example="admin",
    ),
    active: Optional[bool] = Query(
        None,
        description="Filter by account status",
    ),
    search: Optional[str] = Query(
        None,
        min_length=2,
        max_length=100,
        description="Search in name, email, or username",
        example="john@example.com",
    ),
    # Pagination parameters
    page: int = Query(
        1,
        ge=1,
        description="Page number (1-indexed)",
    ),
    page_size: int = Query(
        20,
        ge=1,
        le=100,
        description="Number of items per page",
    ),
) -> PaginatedResponse[UserListItem]:
    """
    List users with filtering and pagination.
    
    **Admin-only endpoint**
    
    Supports filtering by:
    - Role (exact match)
    - Active status (boolean)
    - Full-text search across name, email, username
    
    Returns:
        Paginated response containing user list items
    """
    # TODO: Enforce admin-only access
    
    filters = {
        "role": role,
        "active": active,
        "search": search,
        "page": page,
        "page_size": page_size,
    }
    
    # Remove None values to avoid passing unnecessary filters
    filters = {k: v for k, v in filters.items() if v is not None}
    
    result = user_service.list_users(filters=filters)
    return result.unwrap()


@router.get(
    "/{user_id}",
    response_model=UserDetail,
    summary="Get user by ID",
    description="Retrieve detailed information for a specific user",
    response_description="User details",
    responses={
        200: {"description": "User found"},
        404: {"description": "User not found"},
    },
)
async def get_user_by_id(
    user_id: str = Path(
        ...,
        description="Unique user identifier",
        example="usr_1234567890",
    ),
    user_service: UserService = Depends(get_user_service),
    current_user: Any = Depends(get_current_user),
) -> UserDetail:
    """
    Get detailed user information by ID.
    
    **Access Control:**
    - Users can access their own profile
    - Admins can access any user profile
    
    Args:
        user_id: Unique identifier for the target user
        
    Returns:
        Complete user profile details
        
    Raises:
        HTTPException: 404 if user not found
        HTTPException: 403 if unauthorized to view user
    """
    # TODO: Implement authorization check
    # if user_id != current_user.id and not current_user.is_admin:
    #     raise HTTPException(status_code=403, detail="Forbidden")
    
    result = user_service.get_user(user_id=user_id)
    return result.unwrap()


@router.patch(
    "/{user_id}",
    response_model=UserDetail,
    summary="Update user",
    description="Partially update user information",
    response_description="Updated user details",
    responses={
        200: {"description": "User updated successfully"},
        404: {"description": "User not found"},
        400: {"description": "Invalid update data"},
    },
)
async def update_user(
    payload: UserUpdate,
    user_id: str = Path(
        ...,
        description="Unique user identifier",
    ),
    user_service: UserService = Depends(get_user_service),
    current_user: Any = Depends(get_current_user),
) -> UserDetail:
    """
    Partially update user information.
    
    **Access Control:**
    - Users can update their own profile (limited fields)
    - Admins can update any user (all fields)
    
    Only provided fields will be updated (PATCH semantics).
    
    Args:
        user_id: ID of user to update
        payload: Partial user data to update
        
    Returns:
        Updated user details
        
    Raises:
        HTTPException: 404 if user not found
        HTTPException: 403 if unauthorized
    """
    # TODO: Implement field-level authorization
    result = user_service.update_user(user_id=user_id, data=payload)
    return result.unwrap()


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete user",
    description="Soft delete or deactivate user account",
    responses={
        204: {"description": "User deleted successfully"},
        404: {"description": "User not found"},
        403: {"description": "Cannot delete this user"},
    },
)
async def delete_user(
    user_id: str = Path(
        ...,
        description="Unique user identifier",
    ),
    user_service: UserService = Depends(get_user_service),
    current_user: Any = Depends(get_current_user),
) -> Response:
    """
    Delete or deactivate user account.
    
    **Admin-only endpoint**
    
    Implementation may use soft delete or account deactivation
    based on business requirements and data retention policies.
    
    Args:
        user_id: ID of user to delete
        
    Returns:
        204 No Content on success
        
    Raises:
        HTTPException: 404 if user not found
        HTTPException: 403 if trying to delete self or protected user
    """
    # TODO: Prevent self-deletion
    # if user_id == current_user.id:
    #     raise HTTPException(status_code=400, detail="Cannot delete own account")
    
    user_service.delete_user(user_id=user_id).unwrap()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ==================== User Activation Management ====================


@router.post(
    "/{user_id}/activate",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Activate user account",
    description="Enable a deactivated user account",
    responses={
        204: {"description": "User activated successfully"},
        404: {"description": "User not found"},
        400: {"description": "User already active"},
    },
)
async def activate_user(
    user_id: str = Path(
        ...,
        description="Unique user identifier",
    ),
    user_service: UserService = Depends(get_user_service),
    current_user: Any = Depends(get_current_user),
) -> Response:
    """
    Activate a user account.
    
    **Admin-only endpoint**
    
    Restores access to a previously deactivated account.
    
    Args:
        user_id: ID of user to activate
        
    Returns:
        204 No Content on success
    """
    # TODO: Enforce admin-only access
    user_service.activate_user(user_id=user_id).unwrap()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{user_id}/deactivate",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Deactivate user account",
    description="Disable a user account without deletion",
    responses={
        204: {"description": "User deactivated successfully"},
        404: {"description": "User not found"},
        400: {"description": "User already inactive"},
    },
)
async def deactivate_user(
    user_id: str = Path(
        ...,
        description="Unique user identifier",
    ),
    user_service: UserService = Depends(get_user_service),
    current_user: Any = Depends(get_current_user),
) -> Response:
    """
    Deactivate a user account.
    
    **Admin-only endpoint**
    
    Prevents user login without deleting data.
    Deactivated accounts can be reactivated later.
    
    Args:
        user_id: ID of user to deactivate
        
    Returns:
        204 No Content on success
    """
    # TODO: Prevent self-deactivation
    # if user_id == current_user.id:
    #     raise HTTPException(status_code=400, detail="Cannot deactivate own account")
    
    user_service.deactivate_user(user_id=user_id).unwrap()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ==================== Statistics ====================


@router.get(
    "/stats/overview",
    response_model=UserStats,
    summary="Get user statistics",
    description="Retrieve global user statistics and metrics (admin only)",
    response_description="Aggregated user statistics",
)
async def get_user_statistics(
    user_service: UserService = Depends(get_user_service),
    current_user: Any = Depends(get_current_user),
) -> UserStats:
    """
    Get global user statistics.
    
    **Admin-only endpoint**
    
    Provides aggregated metrics such as:
    - Total user count
    - Active vs inactive users
    - User role distribution
    - Recent registration trends
    
    Returns:
        Comprehensive user statistics
    """
    # TODO: Enforce admin-only access
    result = user_service.get_user_stats()
    return result.unwrap()