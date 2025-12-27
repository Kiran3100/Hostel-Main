"""
Complaint Escalation API Endpoints
Handles manual and automatic escalation of complaints based on priority and SLA.
"""
from typing import Any, List

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.complaint import (
    EscalationRequest,
    EscalationResponse,
    EscalationHistory,
    AutoEscalationRule,
    AutoEscalationRuleResponse,
)
from app.services.complaint.complaint_escalation_service import ComplaintEscalationService

router = APIRouter(prefix="/complaints/escalation", tags=["complaints:escalation"])


def get_escalation_service(
    db: Session = Depends(deps.get_db),
) -> ComplaintEscalationService:
    """
    Dependency injection for ComplaintEscalationService.
    
    Args:
        db: Database session from dependency injection
        
    Returns:
        ComplaintEscalationService: Initialized service instance
    """
    return ComplaintEscalationService(db=db)


@router.post(
    "/{complaint_id}",
    response_model=EscalationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Escalate complaint",
    description="Manually escalate a complaint to higher authority or change priority level with justification.",
    responses={
        201: {"description": "Complaint escalated successfully"},
        404: {"description": "Complaint not found"},
        400: {"description": "Invalid escalation request or already at max level"},
        403: {"description": "Not authorized to escalate"},
    },
)
def escalate_complaint(
    complaint_id: str,
    payload: EscalationRequest,
    current_user=Depends(deps.get_current_user),
    service: ComplaintEscalationService = Depends(get_escalation_service),
) -> Any:
    """
    Escalate a complaint.
    
    Args:
        complaint_id: Unique identifier of the complaint
        payload: Escalation details (escalation_level, reason, escalate_to)
        current_user: Authenticated user performing escalation
        service: Escalation service instance
        
    Returns:
        EscalationResponse: Escalation details with new level and timestamp
        
    Raises:
        HTTPException: If complaint not found, already escalated, or invalid request
    """
    return service.escalate(
        complaint_id=complaint_id,
        payload=payload,
        user_id=current_user.id
    )


@router.get(
    "/{complaint_id}/history",
    response_model=EscalationHistory,
    summary="Get escalation history",
    description="Retrieve complete escalation history for a complaint including all escalation events.",
    responses={
        200: {"description": "Escalation history retrieved successfully"},
        404: {"description": "Complaint not found"},
    },
)
def get_escalation_history(
    complaint_id: str,
    current_user=Depends(deps.get_current_user),
    service: ComplaintEscalationService = Depends(get_escalation_service),
) -> Any:
    """
    Get escalation history for a complaint.
    
    Args:
        complaint_id: Unique identifier of the complaint
        current_user: Authenticated user requesting history
        service: Escalation service instance
        
    Returns:
        EscalationHistory: Chronological list of escalation events
        
    Raises:
        HTTPException: If complaint not found
    """
    return service.history(complaint_id)


@router.post(
    "/rules",
    response_model=AutoEscalationRuleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create auto-escalation rule",
    description="Define automatic escalation rules based on time thresholds, priority, and category. Admin only.",
    responses={
        201: {"description": "Auto-escalation rule created successfully"},
        400: {"description": "Invalid rule configuration"},
        403: {"description": "Admin access required"},
    },
)
def create_auto_escalation_rule(
    payload: AutoEscalationRule,
    admin=Depends(deps.get_admin_user),
    service: ComplaintEscalationService = Depends(get_escalation_service),
) -> Any:
    """
    Create an auto-escalation rule.
    
    Args:
        payload: Auto-escalation rule configuration
        admin: Admin user creating the rule
        service: Escalation service instance
        
    Returns:
        AutoEscalationRuleResponse: Created rule with ID
        
    Raises:
        HTTPException: If rule configuration invalid
    """
    return service.create_auto_rule(payload, admin_id=admin.id)


@router.get(
    "/rules",
    response_model=List[AutoEscalationRuleResponse],
    summary="List auto-escalation rules",
    description="Get all active auto-escalation rules. Admin only.",
    responses={
        200: {"description": "Auto-escalation rules retrieved successfully"},
        403: {"description": "Admin access required"},
    },
)
def list_auto_escalation_rules(
    admin=Depends(deps.get_admin_user),
    service: ComplaintEscalationService = Depends(get_escalation_service),
) -> Any:
    """
    List all auto-escalation rules.
    
    Args:
        admin: Admin user requesting rules
        service: Escalation service instance
        
    Returns:
        List[AutoEscalationRuleResponse]: All active rules
    """
    return service.list_auto_rules()


@router.put(
    "/rules/{rule_id}",
    response_model=AutoEscalationRuleResponse,
    summary="Update auto-escalation rule",
    description="Update an existing auto-escalation rule. Admin only.",
    responses={
        200: {"description": "Rule updated successfully"},
        404: {"description": "Rule not found"},
        403: {"description": "Admin access required"},
    },
)
def update_auto_escalation_rule(
    rule_id: str,
    payload: AutoEscalationRule,
    admin=Depends(deps.get_admin_user),
    service: ComplaintEscalationService = Depends(get_escalation_service),
) -> Any:
    """
    Update an auto-escalation rule.
    
    Args:
        rule_id: Unique identifier of the rule
        payload: Updated rule configuration
        admin: Admin user updating the rule
        service: Escalation service instance
        
    Returns:
        AutoEscalationRuleResponse: Updated rule
        
    Raises:
        HTTPException: If rule not found
    """
    return service.update_auto_rule(rule_id, payload, admin_id=admin.id)


@router.delete(
    "/rules/{rule_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete auto-escalation rule",
    description="Delete an auto-escalation rule. Admin only.",
    responses={
        200: {"description": "Rule deleted successfully"},
        404: {"description": "Rule not found"},
        403: {"description": "Admin access required"},
    },
)
def delete_auto_escalation_rule(
    rule_id: str,
    admin=Depends(deps.get_admin_user),
    service: ComplaintEscalationService = Depends(get_escalation_service),
) -> Any:
    """
    Delete an auto-escalation rule.
    
    Args:
        rule_id: Unique identifier of the rule
        admin: Admin user deleting the rule
        service: Escalation service instance
        
    Returns:
        dict: Success message
        
    Raises:
        HTTPException: If rule not found
    """
    service.delete_auto_rule(rule_id, admin_id=admin.id)
    return {
        "success": True,
        "message": "Auto-escalation rule deleted successfully",
        "rule_id": rule_id
    }