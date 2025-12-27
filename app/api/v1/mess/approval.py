"""
Mess Menu Approval API Endpoints

This module handles the approval workflow for mess menus including submission,
approval, rejection, and history tracking.
"""

from typing import Any, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.dependencies import AuthenticationDependency
from app.services.mess.menu_approval_service import MenuApprovalService
from app.schemas.mess import (
    MenuApprovalResponse,
    ApprovalHistory,
    MenuApprovalRequest,
    MenuRejectionRequest,
)
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix="/mess/approval",
    tags=["Mess - Approval"],
)


async def get_approval_service() -> MenuApprovalService:
    """
    Dependency injection for MenuApprovalService.
    
    This should be implemented in your DI container.
    Replace NotImplementedError with actual service instantiation.
    
    Raises:
        NotImplementedError: When DI container is not configured
    """
    raise NotImplementedError(
        "MenuApprovalService dependency injection not configured. "
        "Please implement this in your DI container."
    )


async def get_current_user(auth: AuthenticationDependency = Depends()) -> Any:
    """
    Get the currently authenticated user.
    
    Args:
        auth: Authentication dependency
        
    Returns:
        Current authenticated user object
    """
    return auth.get_current_user()


@router.post(
    "/{menu_id}/submit",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Submit menu for approval",
    description="Submit a menu for approval workflow. Only draft menus can be submitted.",
    responses={
        200: {"description": "Menu successfully submitted for approval"},
        400: {"description": "Menu cannot be submitted (invalid state)"},
        404: {"description": "Menu not found"},
        403: {"description": "User not authorized to submit this menu"},
    },
)
async def submit_menu(
    menu_id: str,
    approval_service: MenuApprovalService = Depends(get_approval_service),
    current_user: Any = Depends(get_current_user),
) -> dict:
    """
    Submit a menu for approval.
    
    Args:
        menu_id: Unique identifier of the menu to submit
        approval_service: Menu approval service instance
        current_user: Currently authenticated user
        
    Returns:
        dict: Submission confirmation with menu and approval details
        
    Raises:
        HTTPException: If submission fails or user lacks permission
    """
    logger.info(
        f"User {current_user.id} submitting menu {menu_id} for approval"
    )
    
    result = approval_service.submit_for_approval(
        menu_id=menu_id,
        submitted_by=current_user.id,
    )
    
    if result.is_err():
        error = result.unwrap_err()
        logger.error(f"Failed to submit menu {menu_id}: {error}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        )
    
    logger.info(f"Menu {menu_id} successfully submitted for approval")
    return result.unwrap()


@router.post(
    "/{menu_id}/approve",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Approve menu",
    description="Approve a pending menu. Requires appropriate approval permissions.",
    responses={
        200: {"description": "Menu successfully approved"},
        400: {"description": "Menu cannot be approved (invalid state)"},
        404: {"description": "Menu not found"},
        403: {"description": "User not authorized to approve menus"},
    },
)
async def approve_menu(
    menu_id: str,
    approval_service: MenuApprovalService = Depends(get_approval_service),
    current_user: Any = Depends(get_current_user),
) -> dict:
    """
    Approve a submitted menu.
    
    Args:
        menu_id: Unique identifier of the menu to approve
        approval_service: Menu approval service instance
        current_user: Currently authenticated user (must have approval rights)
        
    Returns:
        dict: Approval confirmation with updated menu status
        
    Raises:
        HTTPException: If approval fails or user lacks permission
    """
    logger.info(
        f"User {current_user.id} approving menu {menu_id}"
    )
    
    result = approval_service.approve_menu(
        menu_id=menu_id,
        approved_by=current_user.id,
    )
    
    if result.is_err():
        error = result.unwrap_err()
        logger.error(f"Failed to approve menu {menu_id}: {error}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        )
    
    logger.info(f"Menu {menu_id} successfully approved")
    return result.unwrap()


@router.post(
    "/{menu_id}/reject",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Reject menu",
    description="Reject a pending menu with a reason. Requires appropriate approval permissions.",
    responses={
        200: {"description": "Menu successfully rejected"},
        400: {"description": "Menu cannot be rejected (invalid state) or missing reason"},
        404: {"description": "Menu not found"},
        403: {"description": "User not authorized to reject menus"},
    },
)
async def reject_menu(
    menu_id: str,
    reason: str = Query(
        ...,
        min_length=10,
        max_length=500,
        description="Reason for rejection (10-500 characters)",
    ),
    approval_service: MenuApprovalService = Depends(get_approval_service),
    current_user: Any = Depends(get_current_user),
) -> dict:
    """
    Reject a submitted menu with a reason.
    
    Args:
        menu_id: Unique identifier of the menu to reject
        reason: Detailed reason for rejection (required, 10-500 chars)
        approval_service: Menu approval service instance
        current_user: Currently authenticated user (must have approval rights)
        
    Returns:
        dict: Rejection confirmation with reason
        
    Raises:
        HTTPException: If rejection fails or user lacks permission
    """
    logger.info(
        f"User {current_user.id} rejecting menu {menu_id} with reason: {reason[:50]}..."
    )
    
    result = approval_service.reject_menu(
        menu_id=menu_id,
        reason=reason.strip(),
        rejected_by=current_user.id,
    )
    
    if result.is_err():
        error = result.unwrap_err()
        logger.error(f"Failed to reject menu {menu_id}: {error}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        )
    
    logger.info(f"Menu {menu_id} successfully rejected")
    return result.unwrap()


@router.get(
    "/{menu_id}/history",
    response_model=List[ApprovalHistory],
    status_code=status.HTTP_200_OK,
    summary="Get approval history",
    description="Retrieve complete approval history for a specific menu.",
    responses={
        200: {"description": "Approval history retrieved successfully"},
        404: {"description": "Menu not found"},
    },
)
async def get_approval_history(
    menu_id: str,
    approval_service: MenuApprovalService = Depends(get_approval_service),
    current_user: Any = Depends(get_current_user),
) -> List[ApprovalHistory]:
    """
    Get approval history for a menu.
    
    Args:
        menu_id: Unique identifier of the menu
        approval_service: Menu approval service instance
        current_user: Currently authenticated user
        
    Returns:
        List[ApprovalHistory]: Chronological list of approval events
        
    Raises:
        HTTPException: If menu not found
    """
    logger.debug(f"Fetching approval history for menu {menu_id}")
    
    result = approval_service.get_approval_history_for_menu(menu_id=menu_id)
    
    if result.is_err():
        error = result.unwrap_err()
        logger.error(f"Failed to fetch approval history for menu {menu_id}: {error}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Menu with ID {menu_id} not found",
        )
    
    history = result.unwrap()
    logger.debug(f"Retrieved {len(history)} approval history records for menu {menu_id}")
    return history


@router.get(
    "/pending",
    response_model=List[MenuApprovalResponse],
    status_code=status.HTTP_200_OK,
    summary="Get pending approvals",
    description="Get all menus pending approval for the current user.",
    responses={
        200: {"description": "Pending approvals retrieved successfully"},
        403: {"description": "User not authorized to view pending approvals"},
    },
)
async def get_pending_approvals(
    approval_service: MenuApprovalService = Depends(get_approval_service),
    current_user: Any = Depends(get_current_user),
) -> List[MenuApprovalResponse]:
    """
    Get pending approval requests for the current user.
    
    Args:
        approval_service: Menu approval service instance
        current_user: Currently authenticated user
        
    Returns:
        List[MenuApprovalResponse]: List of menus pending approval
        
    Raises:
        HTTPException: If user lacks approval permissions
    """
    logger.debug(f"Fetching pending approvals for user {current_user.id}")
    
    result = approval_service.get_pending_approvals_for_user(user_id=current_user.id)
    
    if result.is_err():
        error = result.unwrap_err()
        logger.error(f"Failed to fetch pending approvals: {error}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User not authorized to view pending approvals",
        )
    
    pending = result.unwrap()
    logger.debug(f"Retrieved {len(pending)} pending approvals for user {current_user.id}")
    return pending