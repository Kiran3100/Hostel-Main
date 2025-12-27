"""
Core Referral Management API Endpoints

This module provides endpoints for tracking and managing individual referrals,
including creation, conversion tracking, and user statistics.
"""

from typing import Any

from fastapi import APIRouter, Depends, Path, Query, status
from fastapi.responses import Response

from app.core.dependencies import AuthenticationDependency
from app.services.referral.referral_service import ReferralService
from app.schemas.referral import (
    ReferralResponse,
    ReferralCreate,
    ReferralDetail,
    ReferralStats,
    ReferralLeaderboard,
    ReferralListResponse,
    ReferralConversionRequest,
    ReferralCancellationRequest,
)

router = APIRouter(
    prefix="/referrals",
    tags=["Referrals - Core"],
)


# ============================================================================
# Dependency Injection
# ============================================================================


def get_referral_service() -> ReferralService:
    """
    Dependency injection for ReferralService.
    
    TODO: Wire this to your DI container
    Example:
        from app.core.container import Container
        return Container.referral_service()
    """
    raise NotImplementedError(
        "ReferralService dependency must be configured in DI container"
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


def get_optional_user(auth: AuthenticationDependency = Depends()) -> Any | None:
    """
    Attempt to extract authenticated user, but allow anonymous access.
    
    Args:
        auth: Authentication dependency
        
    Returns:
        Current authenticated user object or None if not authenticated
    """
    try:
        return auth.get_current_user()
    except Exception:
        return None


# ============================================================================
# Referral Creation & Tracking
# ============================================================================


@router.post(
    "",
    response_model=ReferralResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create referral record",
    description="""
    Record a new referral usage when someone signs up using a referral code.
    
    This endpoint can be called with or without authentication depending on
    the signup flow implementation.
    """,
    responses={
        201: {
            "description": "Referral successfully recorded",
            "model": ReferralResponse,
        },
        400: {"description": "Invalid referral data"},
        404: {"description": "Referral code not found or inactive"},
        409: {"description": "User already referred or code usage limit reached"},
    },
)
async def create_referral(
    payload: ReferralCreate,
    referral_service: ReferralService = Depends(get_referral_service),
    current_user: Any | None = Depends(get_optional_user),
) -> ReferralResponse:
    """
    Record a new referral usage (e.g. when someone signs up with a code).
    
    This endpoint supports both authenticated and unauthenticated requests
    to accommodate different signup flows.
    
    Args:
        payload: Referral creation data including code and referee information
        referral_service: Injected referral service
        current_user: Optional authenticated user (if signup after login)
        
    Returns:
        Created referral details
        
    Raises:
        HTTPException: If referral creation fails validation
    """
    result = referral_service.create_referral(
        data=payload,
        referee_user_id=current_user.id if current_user else None,
    )
    return result.unwrap()


@router.get(
    "/{referral_id}",
    response_model=ReferralDetail,
    summary="Get referral detail",
    description="""
    Retrieve detailed information about a specific referral.
    
    Users can only view their own referrals (as referrer or referee).
    """,
    responses={
        200: {
            "description": "Referral details",
            "model": ReferralDetail,
        },
        401: {"description": "Authentication required"},
        403: {"description": "Not authorized to view this referral"},
        404: {"description": "Referral not found"},
    },
)
async def get_referral(
    referral_id: str = Path(
        ...,
        description="Unique identifier of the referral",
        min_length=1,
    ),
    referral_service: ReferralService = Depends(get_referral_service),
    current_user: Any = Depends(get_current_user),
) -> ReferralDetail:
    """
    Get detailed information about a specific referral.
    
    Args:
        referral_id: Unique identifier of the referral
        referral_service: Injected referral service
        current_user: Authenticated user making the request
        
    Returns:
        Detailed referral information
        
    Raises:
        HTTPException: If referral not found or user not authorized
    """
    result = referral_service.get_referral(
        referral_id=referral_id,
        user_id=current_user.id,
    )
    return result.unwrap()


# ============================================================================
# Referral Lifecycle Management
# ============================================================================


@router.post(
    "/{referral_id}/convert",
    response_model=dict[str, Any],
    summary="Record conversion (booking)",
    description="""
    Mark a referral as converted when the referee completes a qualifying action
    (e.g., makes a booking).
    
    This triggers reward calculation and distribution.
    """,
    responses={
        200: {"description": "Conversion successfully recorded"},
        400: {"description": "Invalid conversion data"},
        401: {"description": "Authentication required"},
        404: {"description": "Referral not found"},
        409: {"description": "Referral already converted or expired"},
    },
)
async def record_conversion(
    referral_id: str = Path(
        ...,
        description="Unique identifier of the referral",
        min_length=1,
    ),
    payload: ReferralConversionRequest = ...,
    referral_service: ReferralService = Depends(get_referral_service),
    current_user: Any = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Mark a referral as converted (e.g., booking completed).
    
    This endpoint is typically called by the booking service after successful
    payment or booking confirmation.
    
    Args:
        referral_id: Unique identifier of the referral
        payload: Conversion details including booking_id and amount
        referral_service: Injected referral service
        current_user: Authenticated user making the request
        
    Returns:
        Conversion result with reward information
        
    Raises:
        HTTPException: If conversion fails validation
    """
    result = referral_service.record_conversion(
        referral_id=referral_id,
        booking_id=payload.booking_id,
        conversion_amount=payload.conversion_amount,
        conversion_metadata=payload.metadata,
        processed_by=current_user.id,
    )
    return result.unwrap()


@router.post(
    "/{referral_id}/cancel",
    response_model=dict[str, Any],
    summary="Cancel referral",
    description="""
    Cancel a referral and optionally reverse any rewards.
    
    This is typically used when fraud is detected or terms are violated.
    """,
    responses={
        200: {"description": "Referral successfully cancelled"},
        400: {"description": "Invalid cancellation request"},
        401: {"description": "Authentication required"},
        403: {"description": "Not authorized to cancel this referral"},
        404: {"description": "Referral not found"},
    },
)
async def cancel_referral(
    referral_id: str = Path(
        ...,
        description="Unique identifier of the referral",
        min_length=1,
    ),
    payload: ReferralCancellationRequest = ...,
    referral_service: ReferralService = Depends(get_referral_service),
    current_user: Any = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Cancel a referral with optional reward reversal.
    
    Args:
        referral_id: Unique identifier of the referral
        payload: Cancellation details including reason and reverse_rewards flag
        referral_service: Injected referral service
        current_user: Authenticated user making the request
        
    Returns:
        Cancellation result
        
    Raises:
        HTTPException: If cancellation fails
    """
    result = referral_service.cancel_referral(
        referral_id=referral_id,
        reason=payload.reason,
        reverse_rewards=payload.reverse_rewards,
        cancelled_by=current_user.id,
    )
    return result.unwrap()


# ============================================================================
# User Referral Management
# ============================================================================


@router.get(
    "/my-referrals",
    response_model=ReferralListResponse,
    summary="List my referrals (as referrer)",
    description="""
    Retrieve a paginated list of referrals where the authenticated user
    is the referrer.
    
    Supports filtering by status and date range.
    """,
    responses={
        200: {
            "description": "List of user's referrals",
            "model": ReferralListResponse,
        },
        401: {"description": "Authentication required"},
    },
)
async def list_my_referrals(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    status_filter: str | None = Query(
        None,
        description="Filter by referral status",
        regex="^(pending|converted|cancelled|expired)$",
    ),
    date_from: str | None = Query(
        None,
        description="Filter from date (ISO format)",
        regex=r"^\d{4}-\d{2}-\d{2}$",
    ),
    date_to: str | None = Query(
        None,
        description="Filter to date (ISO format)",
        regex=r"^\d{4}-\d{2}-\d{2}$",
    ),
    sort_by: str = Query(
        "created_at",
        description="Sort field",
        regex="^(created_at|converted_at|status)$",
    ),
    sort_order: str = Query(
        "desc",
        description="Sort order",
        regex="^(asc|desc)$",
    ),
    referral_service: ReferralService = Depends(get_referral_service),
    current_user: Any = Depends(get_current_user),
) -> ReferralListResponse:
    """
    List all referrals where the current user is the referrer.
    
    Args:
        page: Page number for pagination
        page_size: Number of items per page
        status_filter: Optional status filter
        date_from: Optional start date filter
        date_to: Optional end date filter
        sort_by: Field to sort by
        sort_order: Sorting direction
        referral_service: Injected referral service
        current_user: Authenticated user making the request
        
    Returns:
        Paginated list of referrals
    """
    result = referral_service.list_referrals_for_user(
        user_id=current_user.id,
        role="referrer",
        page=page,
        page_size=page_size,
        status_filter=status_filter,
        date_from=date_from,
        date_to=date_to,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return result.unwrap()


@router.get(
    "/referred-by-me",
    response_model=ReferralListResponse,
    summary="List users I referred",
    description="""
    Retrieve a list of all users referred by the authenticated user,
    with their referral status and rewards.
    """,
    responses={
        200: {
            "description": "List of referred users",
            "model": ReferralListResponse,
        },
        401: {"description": "Authentication required"},
    },
)
async def list_referred_users(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    referral_service: ReferralService = Depends(get_referral_service),
    current_user: Any = Depends(get_current_user),
) -> ReferralListResponse:
    """
    List all users referred by the current user.
    
    Args:
        page: Page number for pagination
        page_size: Number of items per page
        referral_service: Injected referral service
        current_user: Authenticated user making the request
        
    Returns:
        Paginated list of referred users
    """
    result = referral_service.list_referred_users(
        referrer_id=current_user.id,
        page=page,
        page_size=page_size,
    )
    return result.unwrap()


# ============================================================================
# Statistics & Leaderboard
# ============================================================================


@router.get(
    "/my-stats",
    response_model=ReferralStats,
    summary="Get my referral stats",
    description="""
    Retrieve comprehensive referral statistics for the authenticated user.
    
    Includes total referrals, conversions, rewards earned, and performance metrics.
    """,
    responses={
        200: {
            "description": "User's referral statistics",
            "model": ReferralStats,
        },
        401: {"description": "Authentication required"},
    },
)
async def get_my_stats(
    period: str = Query(
        "all_time",
        description="Time period for stats",
        regex="^(all_time|month|quarter|year)$",
    ),
    referral_service: ReferralService = Depends(get_referral_service),
    current_user: Any = Depends(get_current_user),
) -> ReferralStats:
    """
    Get comprehensive referral statistics for the current user.
    
    Args:
        period: Time period for statistics calculation
        referral_service: Injected referral service
        current_user: Authenticated user making the request
        
    Returns:
        Detailed referral statistics
    """
    result = referral_service.get_user_stats(
        user_id=current_user.id,
        period=period,
    )
    return result.unwrap()


@router.get(
    "/leaderboard",
    response_model=ReferralLeaderboard,
    summary="Get referral leaderboard",
    description="""
    Retrieve the referral leaderboard showing top performing referrers.
    
    Rankings can be based on different metrics (referrals, conversions, revenue).
    """,
    responses={
        200: {
            "description": "Referral leaderboard",
            "model": ReferralLeaderboard,
        },
        401: {"description": "Authentication required"},
    },
)
async def get_leaderboard(
    limit: int = Query(
        10,
        ge=1,
        le=50,
        description="Number of top referrers to return",
    ),
    metric: str = Query(
        "conversions",
        description="Metric to rank by",
        regex="^(referrals|conversions|revenue)$",
    ),
    period: str = Query(
        "all_time",
        description="Time period for leaderboard",
        regex="^(all_time|month|quarter|year)$",
    ),
    referral_service: ReferralService = Depends(get_referral_service),
    current_user: Any = Depends(get_current_user),
) -> ReferralLeaderboard:
    """
    Get the referral leaderboard with top performers.
    
    Args:
        limit: Number of top referrers to include
        metric: Metric to rank by
        period: Time period for leaderboard calculation
        referral_service: Injected referral service
        current_user: Authenticated user making the request
        
    Returns:
        Leaderboard with top referrers and current user's position
    """
    result = referral_service.get_leaderboard(
        limit=limit,
        metric=metric,
        period=period,
        current_user_id=current_user.id,
    )
    return result.unwrap()


@router.get(
    "/timeline",
    summary="Get referral timeline",
    description="""
    Retrieve a timeline of referral activities for the authenticated user.
    
    Useful for displaying referral progress and milestones.
    """,
    responses={
        200: {"description": "Referral activity timeline"},
        401: {"description": "Authentication required"},
    },
)
async def get_referral_timeline(
    limit: int = Query(20, ge=1, le=100, description="Number of timeline items"),
    referral_service: ReferralService = Depends(get_referral_service),
    current_user: Any = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Get chronological timeline of referral activities.
    
    Args:
        limit: Maximum number of timeline items
        referral_service: Injected referral service
        current_user: Authenticated user making the request
        
    Returns:
        Timeline of referral events
    """
    result = referral_service.get_user_timeline(
        user_id=current_user.id,
        limit=limit,
    )
    return result.unwrap()