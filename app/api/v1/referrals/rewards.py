"""
Referral Rewards & Payout Management API Endpoints

This module provides endpoints for tracking rewards, requesting payouts,
and managing the reward distribution lifecycle.
"""

from typing import Any

from fastapi import APIRouter, Depends, Path, Query, status
from fastapi.responses import Response

from app.core.dependencies import AuthenticationDependency
from app.services.referral.referral_reward_service import ReferralRewardService
from app.schemas.referral import (
    RewardSummary,
    RewardTransaction,
    PayoutRequestResponse,
    PayoutHistory,
    PayoutRequestCreate,
    PayoutListResponse,
    PayoutProcessRequest,
)

router = APIRouter(
    prefix="/referrals/rewards",
    tags=["Referrals - Rewards"],
)


# ============================================================================
# Dependency Injection
# ============================================================================


def get_reward_service() -> ReferralRewardService:
    """
    Dependency injection for ReferralRewardService.
    
    TODO: Wire this to your DI container
    Example:
        from app.core.container import Container
        return Container.referral_reward_service()
    """
    raise NotImplementedError(
        "ReferralRewardService dependency must be configured in DI container"
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


def require_admin(auth: AuthenticationDependency = Depends()) -> Any:
    """
    Verify that the current user has admin privileges.
    
    TODO: Implement role-based access control
    """
    return auth.get_current_user()


# ============================================================================
# Reward Summary & Transactions
# ============================================================================


@router.get(
    "/summary",
    response_model=RewardSummary,
    summary="Get reward summary",
    description="""
    Retrieve aggregated reward summary for the authenticated user.
    
    Includes total earned, paid out, pending, and available balance.
    """,
    responses={
        200: {
            "description": "Reward summary with balance breakdown",
            "model": RewardSummary,
        },
        401: {"description": "Authentication required"},
    },
)
async def get_reward_summary(
    reward_service: ReferralRewardService = Depends(get_reward_service),
    current_user: Any = Depends(get_current_user),
) -> RewardSummary:
    """
    Get aggregated reward summary (earned, paid, pending) for current user.
    
    Args:
        reward_service: Injected referral reward service
        current_user: Authenticated user making the request
        
    Returns:
        Comprehensive reward summary with balance breakdown
    """
    result = reward_service.get_reward_summary(user_id=current_user.id)
    return result.unwrap()


@router.get(
    "/transactions",
    response_model=list[RewardTransaction],
    summary="Get reward transaction history",
    description="""
    Retrieve detailed transaction history for all reward activities.
    
    Includes credits (earned) and debits (paid out) with full audit trail.
    """,
    responses={
        200: {
            "description": "List of reward transactions",
            "model": list[RewardTransaction],
        },
        401: {"description": "Authentication required"},
    },
)
async def get_reward_transactions(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    transaction_type: str | None = Query(
        None,
        description="Filter by transaction type",
        regex="^(earned|paid|pending|reversed)$",
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
    reward_service: ReferralRewardService = Depends(get_reward_service),
    current_user: Any = Depends(get_current_user),
) -> list[RewardTransaction]:
    """
    Get detailed reward transaction history.
    
    Args:
        page: Page number for pagination
        page_size: Number of items per page
        transaction_type: Optional filter by transaction type
        date_from: Optional start date filter
        date_to: Optional end date filter
        reward_service: Injected referral reward service
        current_user: Authenticated user making the request
        
    Returns:
        Paginated list of reward transactions
    """
    result = reward_service.get_reward_transactions(
        user_id=current_user.id,
        page=page,
        page_size=page_size,
        transaction_type=transaction_type,
        date_from=date_from,
        date_to=date_to,
    )
    return result.unwrap()


# ============================================================================
# Payout Request Management (User)
# ============================================================================


@router.post(
    "/payouts",
    response_model=PayoutRequestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Request payout",
    description="""
    Create a payout request for accumulated rewards.
    
    The request will be queued for admin approval and processing.
    Minimum payout threshold may apply based on program settings.
    """,
    responses={
        201: {
            "description": "Payout request successfully created",
            "model": PayoutRequestResponse,
        },
        400: {"description": "Invalid payout request (insufficient balance, etc.)"},
        401: {"description": "Authentication required"},
        409: {"description": "Pending payout request already exists"},
    },
)
async def create_payout_request(
    payload: PayoutRequestCreate,
    reward_service: ReferralRewardService = Depends(get_reward_service),
    current_user: Any = Depends(get_current_user),
) -> PayoutRequestResponse:
    """
    Request a payout for accumulated rewards.
    
    Args:
        payload: Payout request details including amount and payment method
        reward_service: Injected referral reward service
        current_user: Authenticated user making the request
        
    Returns:
        Created payout request details
        
    Raises:
        HTTPException: If payout request fails validation
    """
    result = reward_service.create_payout_request(
        user_id=current_user.id,
        data=payload,
    )
    return result.unwrap()


@router.get(
    "/payouts",
    response_model=PayoutListResponse,
    summary="Get payout history",
    description="""
    Retrieve payout request history for the authenticated user.
    
    Includes pending, approved, rejected, and completed payouts.
    """,
    responses={
        200: {
            "description": "List of payout requests",
            "model": PayoutListResponse,
        },
        401: {"description": "Authentication required"},
    },
)
async def get_payout_history(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    status_filter: str | None = Query(
        None,
        description="Filter by payout status",
        regex="^(pending|approved|rejected|completed|cancelled)$",
    ),
    reward_service: ReferralRewardService = Depends(get_reward_service),
    current_user: Any = Depends(get_current_user),
) -> PayoutListResponse:
    """
    Get payout request history for the current user.
    
    Args:
        page: Page number for pagination
        page_size: Number of items per page
        status_filter: Optional filter by payout status
        reward_service: Injected referral reward service
        current_user: Authenticated user making the request
        
    Returns:
        Paginated list of payout requests
    """
    result = reward_service.get_payout_history_for_user(
        user_id=current_user.id,
        page=page,
        page_size=page_size,
        status_filter=status_filter,
    )
    return result.unwrap()


@router.get(
    "/payouts/{payout_id}",
    response_model=PayoutRequestResponse,
    summary="Get payout request details",
    description="""
    Retrieve detailed information about a specific payout request.
    """,
    responses={
        200: {
            "description": "Payout request details",
            "model": PayoutRequestResponse,
        },
        401: {"description": "Authentication required"},
        403: {"description": "Not authorized to view this payout"},
        404: {"description": "Payout request not found"},
    },
)
async def get_payout_request(
    payout_id: str = Path(
        ...,
        description="Unique identifier of the payout request",
        min_length=1,
    ),
    reward_service: ReferralRewardService = Depends(get_reward_service),
    current_user: Any = Depends(get_current_user),
) -> PayoutRequestResponse:
    """
    Get details of a specific payout request.
    
    Args:
        payout_id: Unique identifier of the payout
        reward_service: Injected referral reward service
        current_user: Authenticated user making the request
        
    Returns:
        Detailed payout request information
        
    Raises:
        HTTPException: If payout not found or user not authorized
    """
    result = reward_service.get_payout_request(
        payout_id=payout_id,
        user_id=current_user.id,
    )
    return result.unwrap()


@router.post(
    "/payouts/{payout_id}/cancel",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cancel payout request",
    description="""
    Cancel a pending payout request.
    
    Only pending requests can be cancelled. Approved or completed payouts
    cannot be cancelled by the user.
    """,
    responses={
        204: {"description": "Payout request successfully cancelled"},
        400: {"description": "Cannot cancel payout in current status"},
        401: {"description": "Authentication required"},
        403: {"description": "Not authorized to cancel this payout"},
        404: {"description": "Payout request not found"},
    },
)
async def cancel_payout_request(
    payout_id: str = Path(
        ...,
        description="Unique identifier of the payout request",
        min_length=1,
    ),
    reason: str | None = Query(
        None,
        description="Optional cancellation reason",
        max_length=500,
    ),
    reward_service: ReferralRewardService = Depends(get_reward_service),
    current_user: Any = Depends(get_current_user),
) -> Response:
    """
    Cancel a pending payout request.
    
    Args:
        payout_id: Unique identifier of the payout to cancel
        reason: Optional reason for cancellation
        reward_service: Injected referral reward service
        current_user: Authenticated user making the request
        
    Returns:
        Empty response with 204 status
        
    Raises:
        HTTPException: If cancellation fails
    """
    reward_service.cancel_payout_request(
        payout_id=payout_id,
        user_id=current_user.id,
        reason=reason,
    ).unwrap()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ============================================================================
# Payout Management (Admin)
# ============================================================================


@router.get(
    "/admin/payouts",
    response_model=PayoutListResponse,
    summary="List all payout requests (Admin)",
    description="""
    Retrieve all payout requests across all users for admin review.
    
    **Admin only endpoint**
    """,
    responses={
        200: {
            "description": "List of all payout requests",
            "model": PayoutListResponse,
        },
        401: {"description": "Authentication required"},
        403: {"description": "Admin privileges required"},
    },
)
async def list_all_payouts(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    status_filter: str | None = Query(
        None,
        description="Filter by payout status",
        regex="^(pending|approved|rejected|completed|cancelled)$",
    ),
    sort_by: str = Query(
        "created_at",
        description="Sort field",
        regex="^(created_at|amount|status)$",
    ),
    sort_order: str = Query(
        "desc",
        description="Sort order",
        regex="^(asc|desc)$",
    ),
    reward_service: ReferralRewardService = Depends(get_reward_service),
    current_user: Any = Depends(require_admin),
) -> PayoutListResponse:
    """
    List all payout requests for admin review (Admin only).
    
    Args:
        page: Page number for pagination
        page_size: Number of items per page
        status_filter: Optional filter by status
        sort_by: Field to sort by
        sort_order: Sorting direction
        reward_service: Injected referral reward service
        current_user: Authenticated admin user
        
    Returns:
        Paginated list of all payout requests
    """
    result = reward_service.list_all_payouts(
        page=page,
        page_size=page_size,
        status_filter=status_filter,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return result.unwrap()


@router.post(
    "/admin/payouts/{payout_id}/process",
    response_model=dict[str, Any],
    summary="Process payout request (Admin)",
    description="""
    Approve or reject a payout request.
    
    **Admin only endpoint**
    
    Approval will trigger the payout processing workflow.
    Rejection will return funds to user's available balance.
    """,
    responses={
        200: {"description": "Payout successfully processed"},
        400: {"description": "Invalid action or payout status"},
        401: {"description": "Authentication required"},
        403: {"description": "Admin privileges required"},
        404: {"description": "Payout request not found"},
    },
)
async def process_payout(
    payout_id: str = Path(
        ...,
        description="Unique identifier of the payout request",
        min_length=1,
    ),
    payload: PayoutProcessRequest = ...,
    reward_service: ReferralRewardService = Depends(get_reward_service),
    current_user: Any = Depends(require_admin),
) -> dict[str, Any]:
    """
    Admin endpoint to approve or reject a payout request.
    
    Args:
        payout_id: Unique identifier of the payout
        payload: Processing details including action and reason
        reward_service: Injected referral reward service
        current_user: Authenticated admin user
        
    Returns:
        Processing result with updated payout status
        
    Raises:
        HTTPException: If processing fails
    """
    result = reward_service.process_payout_request(
        payout_id=payout_id,
        action=payload.action,
        reason=payload.reason,
        admin_id=current_user.id,
        payment_reference=payload.payment_reference,
        notes=payload.notes,
    )
    return result.unwrap()


@router.post(
    "/admin/payouts/{payout_id}/complete",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Mark payout as completed (Admin)",
    description="""
    Mark an approved payout as completed after funds transfer.
    
    **Admin only endpoint**
    """,
    responses={
        204: {"description": "Payout marked as completed"},
        400: {"description": "Payout not in approved status"},
        401: {"description": "Authentication required"},
        403: {"description": "Admin privileges required"},
        404: {"description": "Payout request not found"},
    },
)
async def complete_payout(
    payout_id: str = Path(
        ...,
        description="Unique identifier of the payout request",
        min_length=1,
    ),
    payment_reference: str = Query(
        ...,
        description="External payment reference/transaction ID",
        min_length=1,
    ),
    notes: str | None = Query(
        None,
        description="Optional completion notes",
        max_length=1000,
    ),
    reward_service: ReferralRewardService = Depends(get_reward_service),
    current_user: Any = Depends(require_admin),
) -> Response:
    """
    Mark an approved payout as completed (Admin only).
    
    Args:
        payout_id: Unique identifier of the payout
        payment_reference: External payment reference
        notes: Optional completion notes
        reward_service: Injected referral reward service
        current_user: Authenticated admin user
        
    Returns:
        Empty response with 204 status
        
    Raises:
        HTTPException: If operation fails
    """
    reward_service.complete_payout(
        payout_id=payout_id,
        payment_reference=payment_reference,
        notes=notes,
        completed_by=current_user.id,
    ).unwrap()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ============================================================================
# Reward Analytics (Admin)
# ============================================================================


@router.get(
    "/admin/analytics",
    summary="Get reward analytics (Admin)",
    description="""
    Retrieve comprehensive reward and payout analytics.
    
    **Admin only endpoint**
    
    Includes total rewards distributed, pending payouts, top earners, etc.
    """,
    responses={
        200: {"description": "Reward analytics data"},
        401: {"description": "Authentication required"},
        403: {"description": "Admin privileges required"},
    },
)
async def get_reward_analytics(
    date_from: str | None = Query(
        None,
        description="Start date for analytics (ISO format)",
        regex=r"^\d{4}-\d{2}-\d{2}$",
    ),
    date_to: str | None = Query(
        None,
        description="End date for analytics (ISO format)",
        regex=r"^\d{4}-\d{2}-\d{2}$",
    ),
    reward_service: ReferralRewardService = Depends(get_reward_service),
    current_user: Any = Depends(require_admin),
) -> dict[str, Any]:
    """
    Get comprehensive reward analytics (Admin only).
    
    Args:
        date_from: Optional start date for filtering
        date_to: Optional end date for filtering
        reward_service: Injected referral reward service
        current_user: Authenticated admin user
        
    Returns:
        Detailed reward analytics
    """
    result = reward_service.get_reward_analytics(
        date_from=date_from,
        date_to=date_to,
    )
    return result.unwrap()