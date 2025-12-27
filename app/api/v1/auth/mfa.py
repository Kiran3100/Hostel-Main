"""
Multi-Factor Authentication (MFA) endpoints.

This module provides endpoints for MFA management including:
- MFA enrollment with TOTP
- Verification of TOTP codes
- MFA disable functionality
- Backup codes generation and regeneration
"""

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api import deps
from app.services.auth.mfa_service import MFAService

# TODO: Replace Dict with concrete schemas
# from app.schemas.auth.mfa import (
#     MFAEnrollResponse,
#     MFAVerifyRequest,
#     MFAVerifyResponse,
#     MFADisableResponse,
#     BackupCodesResponse,
# )

# Router configuration
router = APIRouter(
    prefix="/mfa",
    tags=["auth:mfa"],
    responses={
        401: {"description": "Unauthorized"},
        403: {"description": "MFA operation not allowed"},
        409: {"description": "MFA already enabled/disabled"},
    },
)


def get_mfa_service(db: Session = Depends(deps.get_db)) -> MFAService:
    """
    Dependency injection for MFAService.
    
    Args:
        db: Database session from dependency injection
        
    Returns:
        MFAService instance
    """
    return MFAService(db=db)


@router.post(
    "/enroll",
    status_code=status.HTTP_200_OK,
    summary="Initiate MFA enrollment",
    description="Generate TOTP secret and QR code URI for MFA setup.",
    response_description="MFA enrollment data including secret and QR code",
)
async def enroll_mfa(
    current_user=Depends(deps.get_current_user),
    service: MFAService = Depends(get_mfa_service),
) -> Dict[str, Any]:
    """
    Start MFA enrollment process.
    
    Generates a TOTP secret and provides QR code URI for authenticator apps.
    
    Args:
        current_user: Currently authenticated user from dependency injection
        service: MFA service instance
        
    Returns:
        Dictionary containing TOTP secret, QR code URI, and enrollment instructions
        
    Raises:
        HTTPException: If MFA is already enabled or enrollment fails
    """
    try:
        result = service.enroll(user_id=current_user.id)
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during MFA enrollment",
        ) from e


@router.post(
    "/verify",
    status_code=status.HTTP_200_OK,
    summary="Verify MFA enrollment",
    description="Verify TOTP code to complete MFA setup and receive backup codes.",
    response_description="MFA verification result with backup codes",
)
async def verify_mfa_enrollment(
    payload: Dict[str, Any],  # TODO: Replace with MFAVerifyRequest schema
    current_user=Depends(deps.get_current_user),
    service: MFAService = Depends(get_mfa_service),
) -> Dict[str, Any]:
    """
    Verify TOTP code to finalize MFA setup.
    
    Args:
        payload: Verification data containing TOTP code
        current_user: Currently authenticated user from dependency injection
        service: MFA service instance
        
    Returns:
        Dictionary containing verification status and backup codes
        
    Raises:
        HTTPException: If verification fails or code is invalid
    """
    try:
        result = service.verify_enrollment(user_id=current_user.id, payload=payload)
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during MFA verification",
        ) from e


@router.post(
    "/disable",
    status_code=status.HTTP_200_OK,
    summary="Disable MFA",
    description="Disable multi-factor authentication for the current user.",
    response_description="MFA disabled successfully",
)
async def disable_mfa(
    current_user=Depends(deps.get_current_user),
    service: MFAService = Depends(get_mfa_service),
) -> Dict[str, str]:
    """
    Disable MFA for the current user.
    
    Args:
        current_user: Currently authenticated user from dependency injection
        service: MFA service instance
        
    Returns:
        Success message confirming MFA has been disabled
        
    Raises:
        HTTPException: If MFA is not enabled or disable operation fails
    """
    try:
        service.disable(user_id=current_user.id)
        return {"message": "MFA has been successfully disabled"}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while disabling MFA",
        ) from e


@router.post(
    "/backup-codes",
    status_code=status.HTTP_200_OK,
    summary="Regenerate backup codes",
    description="Generate a new set of backup codes for MFA recovery.",
    response_description="New backup codes",
)
async def regenerate_backup_codes(
    current_user=Depends(deps.get_current_user),
    service: MFAService = Depends(get_mfa_service),
) -> Dict[str, Any]:
    """
    Generate a new set of backup codes.
    
    Previous backup codes will be invalidated.
    
    Args:
        current_user: Currently authenticated user from dependency injection
        service: MFA service instance
        
    Returns:
        Dictionary containing new backup codes
        
    Raises:
        HTTPException: If MFA is not enabled or regeneration fails
    """
    try:
        result = service.regenerate_backup_codes(user_id=current_user.id)
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while regenerating backup codes",
        ) from e