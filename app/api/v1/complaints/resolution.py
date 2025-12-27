"""
Complaint Resolution API Endpoints
Handles resolution, closure, and reopening of complaints.
"""
from typing import Any

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.complaint import (
    ResolutionRequest,
    ResolutionResponse,
    ResolutionUpdate,
    ReopenRequest,
    ReopenResponse,
    CloseRequest,
    CloseResponse,
)
from app.services.complaint.complaint_resolution_service import ComplaintResolutionService

router = APIRouter(prefix="/complaints/resolution", tags=["complaints:resolution"])


def get_resolution_service(
    db: Session = Depends(deps.get_db),
) -> ComplaintResolutionService:
    """
    Dependency injection for ComplaintResolutionService.
    
    Args:
        db: Database session from dependency injection
        
    Returns:
        ComplaintResolutionService: Initialized service instance
    """
    return ComplaintResolutionService(db=db)


@router.post(
    "/{complaint_id}/resolve",
    response_model=ResolutionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Resolve complaint",
    description="Mark a complaint as resolved with resolution details and supporting documentation. Supervisor only.",
    responses={
        201: {"description": "Complaint resolved successfully"},
        404: {"description": "Complaint not found"},
        400: {"description": "Complaint already resolved or invalid state"},
        403: {"description": "Supervisor access required"},
    },
)
def resolve_complaint(
    complaint_id: str,
    payload: ResolutionRequest,
    supervisor=Depends(deps.get_supervisor_user),
    service: ComplaintResolutionService = Depends(get_resolution_service),
) -> Any:
    """
    Resolve a complaint.
    
    Args:
        complaint_id: Unique identifier of the complaint
        payload: Resolution details (description, actions_taken, attachments)
        supervisor: Supervisor user resolving the complaint
        service: Resolution service instance
        
    Returns:
        ResolutionResponse: Resolution details with timestamp
        
    Raises:
        HTTPException: If complaint not found, already resolved, or invalid state
    """
    return service.resolve(
        complaint_id=complaint_id,
        payload=payload,
        resolver_id=supervisor.id
    )


@router.put(
    "/{complaint_id}/resolve",
    response_model=ResolutionResponse,
    summary="Update resolution details",
    description="Update the resolution information for a complaint. Supervisor only.",
    responses={
        200: {"description": "Resolution updated successfully"},
        404: {"description": "Complaint or resolution not found"},
        400: {"description": "Complaint not in resolved state"},
        403: {"description": "Supervisor access required"},
    },
)
def update_resolution(
    complaint_id: str,
    payload: ResolutionUpdate,
    supervisor=Depends(deps.get_supervisor_user),
    service: ComplaintResolutionService = Depends(get_resolution_service),
) -> Any:
    """
    Update resolution details.
    
    Args:
        complaint_id: Unique identifier of the complaint
        payload: Updated resolution information
        supervisor: Supervisor user updating the resolution
        service: Resolution service instance
        
    Returns:
        ResolutionResponse: Updated resolution details
        
    Raises:
        HTTPException: If complaint not resolved or not found
    """
    return service.update_resolution(
        complaint_id=complaint_id,
        payload=payload,
        user_id=supervisor.id
    )


@router.post(
    "/{complaint_id}/reopen",
    response_model=ReopenResponse,
    summary="Reopen resolved complaint",
    description="Reopen a resolved complaint if the issue persists or resolution was inadequate.",
    responses={
        200: {"description": "Complaint reopened successfully"},
        404: {"description": "Complaint not found"},
        400: {"description": "Complaint not in resolved state or cannot be reopened"},
    },
)
def reopen_complaint(
    complaint_id: str,
    payload: ReopenRequest,
    current_user=Depends(deps.get_current_user),
    service: ComplaintResolutionService = Depends(get_resolution_service),
) -> Any:
    """
    Reopen a resolved complaint.
    
    Args:
        complaint_id: Unique identifier of the complaint
        payload: Reopen details (reason, additional_info)
        current_user: User requesting to reopen
        service: Resolution service instance
        
    Returns:
        ReopenResponse: Updated complaint status
        
    Raises:
        HTTPException: If complaint not resolved or cannot be reopened
    """
    return service.reopen(
        complaint_id=complaint_id,
        payload=payload,
        user_id=current_user.id
    )


@router.post(
    "/{complaint_id}/close",
    response_model=CloseResponse,
    summary="Close complaint permanently",
    description="Permanently close a complaint after verification. This is final and prevents reopening.",
    responses={
        200: {"description": "Complaint closed successfully"},
        404: {"description": "Complaint not found"},
        400: {"description": "Complaint not in resolved state or already closed"},
        403: {"description": "Supervisor access required"},
    },
)
def close_complaint(
    complaint_id: str,
    payload: CloseRequest,
    supervisor=Depends(deps.get_supervisor_user),
    service: ComplaintResolutionService = Depends(get_resolution_service),
) -> Any:
    """
    Permanently close a complaint.
    
    Args:
        complaint_id: Unique identifier of the complaint
        payload: Closure details (verification_notes, closure_reason)
        supervisor: Supervisor user closing the complaint
        service: Resolution service instance
        
    Returns:
        CloseResponse: Final closure confirmation
        
    Raises:
        HTTPException: If complaint not resolved or already closed
    """
    return service.close(
        complaint_id=complaint_id,
        payload=payload,
        user_id=supervisor.id
    )


@router.get(
    "/{complaint_id}/resolution",
    response_model=ResolutionResponse,
    summary="Get resolution details",
    description="Retrieve resolution information for a complaint.",
    responses={
        200: {"description": "Resolution details retrieved successfully"},
        404: {"description": "Complaint or resolution not found"},
    },
)
def get_resolution(
    complaint_id: str,
    current_user=Depends(deps.get_current_user),
    service: ComplaintResolutionService = Depends(get_resolution_service),
) -> Any:
    """
    Get resolution details for a complaint.
    
    Args:
        complaint_id: Unique identifier of the complaint
        current_user: Authenticated user requesting resolution
        service: Resolution service instance
        
    Returns:
        ResolutionResponse: Resolution details
        
    Raises:
        HTTPException: If complaint or resolution not found
    """
    return service.get_resolution(complaint_id, user_id=current_user.id)