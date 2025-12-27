"""
Maintenance Completion API Endpoints
Handles task completion, quality checks, and completion certificates.
"""

from typing import Any, List, Optional

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Path,
    Body,
    status,
)
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.maintenance.maintenance_completion import (
    CompletionRequest,
    CompletionResponse,
    QualityCheck,
    CompletionCertificate,
    CompletionVerification,
    WorkSummary,
)
from app.services.maintenance.maintenance_completion_service import (
    MaintenanceCompletionService,
)

# Initialize router with prefix and tags
router = APIRouter(prefix="/completion", tags=["maintenance:completion"])


def get_completion_service(
    db: Session = Depends(deps.get_db),
) -> MaintenanceCompletionService:
    """
    Dependency to get maintenance completion service instance.
    
    Args:
        db: Database session dependency
        
    Returns:
        MaintenanceCompletionService: Service instance for completion operations
    """
    return MaintenanceCompletionService(db=db)


@router.post(
    "/{request_id}",
    response_model=CompletionResponse,
    status_code=status.HTTP_200_OK,
    summary="Record task completion",
    description="Record the completion of a maintenance task with work summary and materials used",
    response_description="Completion confirmation with details",
)
def record_completion(
    request_id: str = Path(..., description="Unique identifier of the maintenance request"),
    payload: CompletionRequest = Body(..., description="Completion details including work summary"),
    supervisor=Depends(deps.get_supervisor_user),
    service: MaintenanceCompletionService = Depends(get_completion_service),
) -> Any:
    """
    Record completion of a maintenance task.
    
    Captures work performed, materials used, actual costs, and completion time.
    Moves the request to pending quality check status.
    
    Args:
        request_id: Unique identifier of the maintenance request
        payload: Completion details including work summary and costs
        supervisor: Authenticated supervisor recording completion
        service: Maintenance completion service instance
        
    Returns:
        CompletionResponse: Completion confirmation with details
        
    Raises:
        HTTPException: If completion recording fails or request not in correct status
    """
    try:
        return service.record_completion(
            request_id=request_id,
            payload=payload,
            actor_id=supervisor.id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except LookupError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to record completion",
        )


@router.post(
    "/{request_id}/quality-check",
    response_model=CompletionResponse,
    summary="Record quality check",
    description="Perform and record quality inspection of completed maintenance work",
    response_description="Quality check results",
)
def record_quality_check(
    request_id: str = Path(..., description="Unique identifier of the maintenance request"),
    payload: QualityCheck = Body(..., description="Quality check details and results"),
    supervisor=Depends(deps.get_supervisor_user),
    service: MaintenanceCompletionService = Depends(get_completion_service),
) -> Any:
    """
    Record quality check for completed maintenance work.
    
    Quality checks verify that work meets standards and specifications.
    Failed checks require rework before final approval.
    
    Args:
        request_id: Unique identifier of the maintenance request
        payload: Quality check details including pass/fail status and notes
        supervisor: Authenticated supervisor performing quality check
        service: Maintenance completion service instance
        
    Returns:
        CompletionResponse: Quality check results
        
    Raises:
        HTTPException: If quality check fails or request not completed
    """
    try:
        return service.record_quality_check(
            request_id=request_id,
            payload=payload,
            actor_id=supervisor.id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except LookupError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to record quality check",
        )


@router.post(
    "/{request_id}/verify",
    response_model=CompletionResponse,
    summary="Verify completion",
    description="Final verification and sign-off on completed maintenance work",
    response_description="Verification confirmation",
)
def verify_completion(
    request_id: str = Path(..., description="Unique identifier of the maintenance request"),
    verification: CompletionVerification = Body(..., description="Verification details"),
    admin=Depends(deps.get_admin_user),
    service: MaintenanceCompletionService = Depends(get_completion_service),
) -> Any:
    """
    Perform final verification and sign-off on completed work.
    
    This is the final step that officially closes the maintenance request
    after quality checks have passed.
    
    Args:
        request_id: Unique identifier of the maintenance request
        verification: Final verification details and sign-off
        admin: Authenticated admin user performing verification
        service: Maintenance completion service instance
        
    Returns:
        CompletionResponse: Verification confirmation
        
    Raises:
        HTTPException: If verification fails or quality checks not passed
    """
    try:
        return service.verify_completion(
            request_id=request_id,
            verification=verification,
            verifier_id=admin.id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except LookupError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to verify completion",
        )


@router.get(
    "/{request_id}/certificate",
    response_model=CompletionCertificate,
    summary="Generate completion certificate",
    description="Generate an official completion certificate for verified maintenance work",
    response_description="Completion certificate with all work details",
)
def get_completion_certificate(
    request_id: str = Path(..., description="Unique identifier of the maintenance request"),
    include_photos: bool = Query(
        False,
        description="Include before/after photos in certificate",
    ),
    admin=Depends(deps.get_admin_user),
    service: MaintenanceCompletionService = Depends(get_completion_service),
) -> Any:
    """
    Generate completion certificate for verified maintenance work.
    
    Certificate includes all work details, costs, timeline, and sign-offs.
    Only available for fully completed and verified requests.
    
    Args:
        request_id: Unique identifier of the maintenance request
        include_photos: Whether to include photos in certificate
        admin: Authenticated admin user
        service: Maintenance completion service instance
        
    Returns:
        CompletionCertificate: Official completion certificate
        
    Raises:
        HTTPException: If certificate generation fails or work not verified
    """
    try:
        return service.generate_completion_certificate(
            request_id,
            include_photos=include_photos,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except LookupError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate completion certificate",
        )


@router.get(
    "/{request_id}/work-summary",
    response_model=WorkSummary,
    summary="Get work summary",
    description="Retrieve detailed summary of work performed and materials used",
    response_description="Comprehensive work summary",
)
def get_work_summary(
    request_id: str = Path(..., description="Unique identifier of the maintenance request"),
    supervisor=Depends(deps.get_supervisor_user),
    service: MaintenanceCompletionService = Depends(get_completion_service),
) -> Any:
    """
    Get detailed summary of work performed.
    
    Includes materials used, labor hours, costs breakdown, and timeline.
    
    Args:
        request_id: Unique identifier of the maintenance request
        supervisor: Authenticated supervisor user
        service: Maintenance completion service instance
        
    Returns:
        WorkSummary: Detailed work summary
        
    Raises:
        HTTPException: If request not found or work not started
    """
    try:
        return service.get_work_summary(request_id)
    except LookupError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve work summary",
        )


@router.post(
    "/{request_id}/reopen",
    response_model=CompletionResponse,
    summary="Reopen completed request",
    description="Reopen a completed request for additional work or corrections",
    response_description="Reopened request details",
)
def reopen_request(
    request_id: str = Path(..., description="Unique identifier of the maintenance request"),
    reason: str = Body(..., embed=True, description="Reason for reopening"),
    admin=Depends(deps.get_admin_user),
    service: MaintenanceCompletionService = Depends(get_completion_service),
) -> Any:
    """
    Reopen a completed maintenance request.
    
    Used when additional work is needed or quality issues are discovered
    after initial completion.
    
    Args:
        request_id: Unique identifier of the maintenance request
        reason: Detailed reason for reopening
        admin: Authenticated admin user
        service: Maintenance completion service instance
        
    Returns:
        CompletionResponse: Reopened request details
        
    Raises:
        HTTPException: If reopening fails or request not completed
    """
    try:
        return service.reopen_request(
            request_id=request_id,
            reason=reason,
            actor_id=admin.id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except LookupError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reopen request",
        )


@router.get(
    "/pending-quality-check",
    response_model=List[CompletionResponse],
    summary="Get tasks pending quality check",
    description="Retrieve all completed tasks awaiting quality inspection",
    response_description="List of tasks pending quality check",
)
def get_pending_quality_checks(
    hostel_id: str = Query(..., description="Hostel ID to filter tasks"),
    pagination=Depends(deps.get_pagination_params),
    supervisor=Depends(deps.get_supervisor_user),
    service: MaintenanceCompletionService = Depends(get_completion_service),
) -> Any:
    """
    Get all tasks pending quality check.
    
    Helps supervisors identify and prioritize quality inspections.
    
    Args:
        hostel_id: Hostel ID to filter tasks
        pagination: Pagination parameters
        supervisor: Authenticated supervisor user
        service: Maintenance completion service instance
        
    Returns:
        List[CompletionResponse]: Tasks awaiting quality check
        
    Raises:
        HTTPException: If retrieval fails
    """
    try:
        return service.get_pending_quality_checks(
            hostel_id=hostel_id,
            pagination=pagination,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve pending quality checks",
        )