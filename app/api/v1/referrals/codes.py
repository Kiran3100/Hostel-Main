"""
Referral Code Management API Endpoints

This module provides endpoints for generating, managing, and tracking referral codes.
Includes code validation, statistics, and lifecycle management (activate/deactivate).
"""

from typing import Any

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import Response

from app.core.dependencies import AuthenticationDependency
from app.services.referral.referral_code_service import ReferralCodeService
from app.schemas.referral import (
    ReferralCodeResponse,
    ReferralCodeStats,
    ReferralCodeListResponse,
    ReferralCodeValidationResponse,
)

router = APIRouter(
    prefix="/referrals/codes",
    tags=["Referrals - Codes"],
)


# ============================================================================
# Dependency Injection
# ============================================================================


def get_code_service() -> ReferralCodeService:
    """
    Dependency injection for ReferralCodeService.
    
    TODO: Wire this to your DI container (e.g., dependency_injector)
    Example:
        from app.core.container import Container
        return Container.referral_code_service()
    """
    raise NotImplementedError(
        "ReferralCodeService dependency must be configured in DI container"
    )


def get_current_user(auth: AuthenticationDependency = Depends()) -> Any:
    """
    Extract and validate current authenticated user from request.
    
    Args:
        auth: Authentication dependency that handles token validation
        
    Returns:
        Current authenticated user object
        
    Raises:
        HTTPException: If authentication fails
    """
    return auth.get_current_user()


# ============================================================================
# Code Generation & Management
# ============================================================================


@router.post(
    "",
    response_model=ReferralCodeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate referral code",
    description="""
    Generate a new referral code for the authenticated user.
    
    The code can be customized with an optional suffix and must be associated
    with an active referral program.
    """,
    responses={
        201: {
            "description": "Referral code successfully created",
            "model": ReferralCodeResponse,
        },
        400: {"description": "Invalid program_id or custom_suffix"},
        401: {"description": "Authentication required"},
        404: {"description": "Referral program not found"},
        409: {"description": "Custom code already exists"},
    },
)
async def generate_code(
    program_id: str = Query(
        ...,
        description="ID of the referral program",
        min_length=1,
        max_length=100,
        example="prog_abc123",
    ),
    custom_suffix: str | None = Query(
        None,
        description="Optional custom code suffix (alphanumeric, 3-20 chars)",
        min_length=3,
        max_length=20,
        regex="^[a-zA-Z0-9]+$",
        example="SUMMER2024",
    ),
    code_service: ReferralCodeService = Depends(get_code_service),
    current_user: Any = Depends(get_current_user),
) -> ReferralCodeResponse:
    """
    Generate a new referral code for the current user.
    
    Args:
        program_id: Unique identifier of the referral program
        custom_suffix: Optional custom suffix for the code
        code_service: Injected referral code service
        current_user: Authenticated user making the request
        
    Returns:
        Newly created referral code details
        
    Raises:
        HTTPException: If generation fails due to validation or business rules
    """
    result = code_service.generate_code(
        user_id=current_user.id,
        program_id=program_id,
        custom_suffix=custom_suffix,
    )
    return result.unwrap()


@router.get(
    "",
    response_model=ReferralCodeListResponse,
    summary="List my referral codes",
    description="""
    Retrieve a paginated list of referral codes owned by the authenticated user.
    
    Supports filtering by status and sorting options.
    """,
    responses={
        200: {
            "description": "List of referral codes with pagination metadata",
            "model": ReferralCodeListResponse,
        },
        401: {"description": "Authentication required"},
    },
)
async def list_my_codes(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(
        20,
        ge=1,
        le=100,
        description="Number of items per page (max 100)",
    ),
    status_filter: str | None = Query(
        None,
        description="Filter by code status",
        regex="^(active|inactive|expired)$",
    ),
    sort_by: str = Query(
        "created_at",
        description="Sort field",
        regex="^(created_at|uses_count|code)$",
    ),
    sort_order: str = Query(
        "desc",
        description="Sort order",
        regex="^(asc|desc)$",
    ),
    code_service: ReferralCodeService = Depends(get_code_service),
    current_user: Any = Depends(get_current_user),
) -> ReferralCodeListResponse:
    """
    List all referral codes belonging to the authenticated user.
    
    Args:
        page: Page number for pagination
        page_size: Number of items per page
        status_filter: Optional status filter
        sort_by: Field to sort by
        sort_order: Sorting direction
        code_service: Injected referral code service
        current_user: Authenticated user making the request
        
    Returns:
        Paginated list of referral codes with metadata
    """
    result = code_service.list_codes_for_user(
        user_id=current_user.id,
        page=page,
        page_size=page_size,
        status_filter=status_filter,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return result.unwrap()


# ============================================================================
# Code Validation (Public Endpoint)
# ============================================================================


@router.get(
    "/validate/{code}",
    response_model=ReferralCodeValidationResponse,
    summary="Validate referral code",
    description="""
    Validate a referral code and retrieve associated program information.
    
    This is a PUBLIC endpoint that does not require authentication,
    allowing potential referees to check code validity before signing up.
    """,
    responses={
        200: {
            "description": "Code validation result with program details",
            "model": ReferralCodeValidationResponse,
        },
        404: {"description": "Code not found or invalid"},
    },
)
async def validate_code(
    code: str = Query(
        ...,
        min_length=3,
        max_length=50,
        description="Referral code to validate",
        example="REF-ABC123",
    ),
    code_service: ReferralCodeService = Depends(get_code_service),
) -> ReferralCodeValidationResponse:
    """
    Check if a referral code is valid and return associated program info.
    
    This endpoint is public (no authentication required) to support
    the referral flow for new users.
    
    Args:
        code: The referral code to validate
        code_service: Injected referral code service
        
    Returns:
        Validation result with program details if valid
        
    Raises:
        HTTPException: If code is not found or invalid
    """
    result = code_service.validate_code(code=code)
    return result.unwrap()


# ============================================================================
# Code Statistics
# ============================================================================


@router.get(
    "/{code_id}/stats",
    response_model=ReferralCodeStats,
    summary="Get stats for specific code",
    description="""
    Retrieve detailed statistics for a specific referral code.
    
    Includes metrics like total uses, conversions, rewards earned, etc.
    """,
    responses={
        200: {
            "description": "Code statistics",
            "model": ReferralCodeStats,
        },
        401: {"description": "Authentication required"},
        403: {"description": "Not authorized to view this code"},
        404: {"description": "Code not found"},
    },
)
async def get_code_stats(
    code_id: str = Query(
        ...,
        description="Unique identifier of the referral code",
        min_length=1,
    ),
    code_service: ReferralCodeService = Depends(get_code_service),
    current_user: Any = Depends(get_current_user),
) -> ReferralCodeStats:
    """
    Get detailed statistics for a specific referral code.
    
    Only the code owner can access these statistics.
    
    Args:
        code_id: Unique identifier of the code
        code_service: Injected referral code service
        current_user: Authenticated user making the request
        
    Returns:
        Detailed code statistics including usage and conversion metrics
        
    Raises:
        HTTPException: If code not found or user not authorized
    """
    result = code_service.get_code_stats(code_id=code_id, user_id=current_user.id)
    return result.unwrap()


# ============================================================================
# Code Lifecycle Management
# ============================================================================


@router.post(
    "/{code_id}/deactivate",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Deactivate code",
    description="""
    Deactivate a referral code, preventing further use.
    
    The code can be reactivated later if needed.
    """,
    responses={
        204: {"description": "Code successfully deactivated"},
        401: {"description": "Authentication required"},
        403: {"description": "Not authorized to modify this code"},
        404: {"description": "Code not found"},
        409: {"description": "Code already inactive"},
    },
)
async def deactivate_code(
    code_id: str = Query(
        ...,
        description="Unique identifier of the referral code",
        min_length=1,
    ),
    code_service: ReferralCodeService = Depends(get_code_service),
    current_user: Any = Depends(get_current_user),
) -> Response:
    """
    Deactivate a referral code owned by the current user.
    
    Args:
        code_id: Unique identifier of the code to deactivate
        code_service: Injected referral code service
        current_user: Authenticated user making the request
        
    Returns:
        Empty response with 204 status
        
    Raises:
        HTTPException: If operation fails
    """
    code_service.deactivate_code(code_id=code_id, user_id=current_user.id).unwrap()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{code_id}/reactivate",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Reactivate code",
    description="""
    Reactivate a previously deactivated referral code.
    
    Cannot reactivate expired codes or codes from inactive programs.
    """,
    responses={
        204: {"description": "Code successfully reactivated"},
        401: {"description": "Authentication required"},
        403: {"description": "Not authorized to modify this code"},
        404: {"description": "Code not found"},
        409: {"description": "Code already active or cannot be reactivated"},
    },
)
async def reactivate_code(
    code_id: str = Query(
        ...,
        description="Unique identifier of the referral code",
        min_length=1,
    ),
    code_service: ReferralCodeService = Depends(get_code_service),
    current_user: Any = Depends(get_current_user),
) -> Response:
    """
    Reactivate a deactivated referral code owned by the current user.
    
    Args:
        code_id: Unique identifier of the code to reactivate
        code_service: Injected referral code service
        current_user: Authenticated user making the request
        
    Returns:
        Empty response with 204 status
        
    Raises:
        HTTPException: If operation fails
    """
    code_service.reactivate_code(code_id=code_id, user_id=current_user.id).unwrap()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete(
    "/{code_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete referral code",
    description="""
    Permanently delete a referral code.
    
    This operation is irreversible. Use deactivate for temporary suspension.
    """,
    responses={
        204: {"description": "Code successfully deleted"},
        401: {"description": "Authentication required"},
        403: {"description": "Not authorized to delete this code"},
        404: {"description": "Code not found"},
        409: {"description": "Cannot delete code with active referrals"},
    },
)
async def delete_code(
    code_id: str = Query(
        ...,
        description="Unique identifier of the referral code",
        min_length=1,
    ),
    code_service: ReferralCodeService = Depends(get_code_service),
    current_user: Any = Depends(get_current_user),
) -> Response:
    """
    Permanently delete a referral code.
    
    Args:
        code_id: Unique identifier of the code to delete
        code_service: Injected referral code service
        current_user: Authenticated user making the request
        
    Returns:
        Empty response with 204 status
        
    Raises:
        HTTPException: If operation fails or code has active referrals
    """
    code_service.delete_code(code_id=code_id, user_id=current_user.id).unwrap()
    return Response(status_code=status.HTTP_204_NO_CONTENT)