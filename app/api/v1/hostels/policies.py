"""
Hostel Policies API Endpoints
Manages hostel rules, policies, and student acknowledgments
"""
from typing import Any, List
from enum import Enum

from fastapi import APIRouter, Depends, status, Query, Path, HTTPException
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.hostel.hostel_policy import (
    PolicyCreate,
    PolicyUpdate,
    PolicyResponse,
    PolicyAcknowledgment,
    PolicyType,
)
from app.services.hostel.hostel_policy_service import HostelPolicyService
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/hostels/policies", tags=["hostels:policies"])


def get_policy_service(db: Session = Depends(deps.get_db)) -> HostelPolicyService:
    """
    Dependency to get hostel policy service instance
    
    Args:
        db: Database session
        
    Returns:
        HostelPolicyService instance
    """
    return HostelPolicyService(db=db)


@router.post(
    "",
    response_model=PolicyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create policy",
    description="Create a new policy or rule for a hostel",
    responses={
        201: {"description": "Policy created successfully"},
        400: {"description": "Invalid policy data"},
        401: {"description": "Not authenticated"},
        403: {"description": "Not authorized (admin required)"},
    },
)
def create_policy(
    payload: PolicyCreate,
    admin=Depends(deps.get_admin_user),
    service: HostelPolicyService = Depends(get_policy_service),
) -> PolicyResponse:
    """
    Create a new hostel policy.
    
    Policy types:
    - general: General hostel rules
    - safety: Safety regulations
    - visitor: Visitor policies
    - noise: Noise restrictions
    - cleanliness: Cleaning requirements
    - payment: Payment terms
    - cancellation: Cancellation policy
    
    Args:
        payload: Policy creation data
        admin: Current admin user
        service: Policy service instance
        
    Returns:
        Created policy details
        
    Raises:
        HTTPException: If creation fails
    """
    try:
        logger.info(
            f"Admin {admin.id} creating {payload.policy_type} policy "
            f"for hostel {payload.hostel_id}"
        )
        
        policy = service.create_policy(payload)
        
        logger.info(f"Policy {policy.id} created successfully")
        return policy
        
    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error creating policy: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create policy"
        )


@router.get(
    "",
    response_model=List[PolicyResponse],
    summary="List policies for hostel",
    description="Retrieve all policies for a specific hostel",
    responses={
        200: {"description": "Policies retrieved successfully"},
        404: {"description": "Hostel not found"},
    },
)
def list_policies(
    hostel_id: str = Query(
        ...,
        description="ID of the hostel",
        example="550e8400-e29b-41d4-a716-446655440000"
    ),
    policy_type: PolicyType | None = Query(
        None,
        description="Filter by policy type"
    ),
    is_mandatory: bool | None = Query(
        None,
        description="Filter by mandatory status"
    ),
    is_active: bool = Query(
        True,
        description="Filter by active status"
    ),
    service: HostelPolicyService = Depends(get_policy_service),
) -> List[PolicyResponse]:
    """
    List all policies for a hostel.
    
    Args:
        hostel_id: The hostel identifier
        policy_type: Optional type filter
        is_mandatory: Optional mandatory filter
        is_active: Filter active/inactive policies
        service: Policy service instance
        
    Returns:
        List of policies
        
    Raises:
        HTTPException: If retrieval fails
    """
    try:
        policies = service.list_policies(
            hostel_id=hostel_id,
            policy_type=policy_type,
            is_mandatory=is_mandatory,
            is_active=is_active
        )
        
        logger.info(f"Retrieved {len(policies)} policies for hostel {hostel_id}")
        return policies
        
    except Exception as e:
        logger.error(f"Error listing policies: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve policies"
        )


@router.get(
    "/{policy_id}",
    response_model=PolicyResponse,
    summary="Get policy details",
    description="Retrieve detailed information about a specific policy",
    responses={
        200: {"description": "Policy details retrieved successfully"},
        404: {"description": "Policy not found"},
    },
)
def get_policy(
    policy_id: str = Path(
        ...,
        description="ID of the policy",
        example="550e8400-e29b-41d4-a716-446655440000"
    ),
    service: HostelPolicyService = Depends(get_policy_service),
) -> PolicyResponse:
    """
    Get policy details.
    
    Args:
        policy_id: The policy identifier
        service: Policy service instance
        
    Returns:
        Policy details
        
    Raises:
        HTTPException: If policy not found
    """
    policy = service.get_policy(policy_id)
    
    if not policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Policy not found"
        )
    
    return policy


@router.patch(
    "/{policy_id}",
    response_model=PolicyResponse,
    summary="Update policy",
    description="Update an existing policy",
    responses={
        200: {"description": "Policy updated successfully"},
        400: {"description": "Invalid update data"},
        401: {"description": "Not authenticated"},
        403: {"description": "Not authorized (admin required)"},
        404: {"description": "Policy not found"},
    },
)
def update_policy(
    policy_id: str = Path(
        ...,
        description="ID of the policy",
        example="550e8400-e29b-41d4-a716-446655440000"
    ),
    payload: PolicyUpdate = ...,
    admin=Depends(deps.get_admin_user),
    service: HostelPolicyService = Depends(get_policy_service),
) -> PolicyResponse:
    """
    Update a policy.
    
    Args:
        policy_id: The policy identifier
        payload: Updated policy data
        admin: Current admin user
        service: Policy service instance
        
    Returns:
        Updated policy details
    """
    try:
        logger.info(f"Admin {admin.id} updating policy {policy_id}")
        
        updated_policy = service.update_policy(policy_id, payload)
        
        if not updated_policy:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Policy not found"
            )
        
        logger.info(f"Policy {policy_id} updated successfully")
        return updated_policy
        
    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error updating policy: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update policy"
        )


@router.delete(
    "/{policy_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete policy",
    description="Delete a policy (soft delete by default)",
    responses={
        204: {"description": "Policy deleted successfully"},
        401: {"description": "Not authenticated"},
        403: {"description": "Not authorized (admin required)"},
        404: {"description": "Policy not found"},
    },
)
def delete_policy(
    policy_id: str = Path(
        ...,
        description="ID of the policy",
        example="550e8400-e29b-41d4-a716-446655440000"
    ),
    admin=Depends(deps.get_admin_user),
    service: HostelPolicyService = Depends(get_policy_service),
) -> None:
    """
    Delete a policy.
    
    Args:
        policy_id: The policy identifier
        admin: Current admin user
        service: Policy service instance
        
    Raises:
        HTTPException: If policy not found
    """
    try:
        logger.info(f"Admin {admin.id} deleting policy {policy_id}")
        
        success = service.delete_policy(policy_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Policy not found"
            )
        
        logger.info(f"Policy {policy_id} deleted successfully")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting policy: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete policy"
        )


@router.post(
    "/{policy_id}/acknowledge",
    response_model=PolicyAcknowledgment,
    status_code=status.HTTP_201_CREATED,
    summary="Acknowledge policy (student)",
    description="Student acknowledges reading and accepting a policy",
    responses={
        201: {"description": "Policy acknowledged successfully"},
        400: {"description": "Policy already acknowledged"},
        401: {"description": "Not authenticated"},
        404: {"description": "Policy not found"},
    },
)
def acknowledge_policy(
    policy_id: str = Path(
        ...,
        description="ID of the policy to acknowledge",
        example="550e8400-e29b-41d4-a716-446655440000"
    ),
    current_user=Depends(deps.get_student_user),
    service: HostelPolicyService = Depends(get_policy_service),
) -> PolicyAcknowledgment:
    """
    Acknowledge a policy.
    
    Students must acknowledge mandatory policies before booking.
    
    Args:
        policy_id: The policy identifier
        current_user: Current student user
        service: Policy service instance
        
    Returns:
        Acknowledgment confirmation
        
    Raises:
        HTTPException: If policy not found or already acknowledged
    """
    try:
        logger.info(f"User {current_user.id} acknowledging policy {policy_id}")
        
        acknowledgment = service.acknowledge(
            policy_id=policy_id,
            user_id=current_user.id
        )
        
        logger.info(
            f"Policy {policy_id} acknowledged by user {current_user.id}"
        )
        return acknowledgment
        
    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except LookupError as e:
        logger.error(f"Policy not found: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error acknowledging policy: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to acknowledge policy"
        )


@router.get(
    "/{policy_id}/acknowledgments",
    response_model=List[PolicyAcknowledgment],
    summary="List policy acknowledgments",
    description="Get all acknowledgments for a policy (admin only)",
    responses={
        200: {"description": "Acknowledgments retrieved successfully"},
        401: {"description": "Not authenticated"},
        403: {"description": "Not authorized (admin required)"},
        404: {"description": "Policy not found"},
    },
)
def list_acknowledgments(
    policy_id: str = Path(
        ...,
        description="ID of the policy",
        example="550e8400-e29b-41d4-a716-446655440000"
    ),
    admin=Depends(deps.get_admin_user),
    service: HostelPolicyService = Depends(get_policy_service),
) -> List[PolicyAcknowledgment]:
    """
    List all acknowledgments for a policy.
    
    Args:
        policy_id: The policy identifier
        admin: Current admin user
        service: Policy service instance
        
    Returns:
        List of acknowledgments
    """
    try:
        acknowledgments = service.list_acknowledgments(policy_id)
        
        logger.info(
            f"Retrieved {len(acknowledgments)} acknowledgments for policy {policy_id}"
        )
        return acknowledgments
        
    except Exception as e:
        logger.error(f"Error listing acknowledgments: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve acknowledgments"
        )


@router.get(
    "/user/{user_id}/acknowledgments",
    response_model=List[PolicyAcknowledgment],
    summary="Get user's policy acknowledgments",
    description="Get all policies acknowledged by a user",
    responses={
        200: {"description": "Acknowledgments retrieved successfully"},
        401: {"description": "Not authenticated"},
    },
)
def get_user_acknowledgments(
    user_id: str = Path(
        ...,
        description="ID of the user",
        example="550e8400-e29b-41d4-a716-446655440000"
    ),
    hostel_id: str | None = Query(
        None,
        description="Filter by hostel"
    ),
    current_user=Depends(deps.get_current_user),
    service: HostelPolicyService = Depends(get_policy_service),
) -> List[PolicyAcknowledgment]:
    """
    Get user's policy acknowledgments.
    
    Users can only view their own acknowledgments unless they're admin.
    
    Args:
        user_id: The user identifier
        hostel_id: Optional hostel filter
        current_user: Current authenticated user
        service: Policy service instance
        
    Returns:
        List of acknowledgments
    """
    # Verify user can access this data
    if current_user.id != user_id and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view these acknowledgments"
        )
    
    try:
        acknowledgments = service.get_user_acknowledgments(
            user_id=user_id,
            hostel_id=hostel_id
        )
        
        return acknowledgments
        
    except Exception as e:
        logger.error(f"Error retrieving acknowledgments: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve acknowledgments"
        )