from typing import Any, Dict

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api import deps
from app.services.auth.mfa_service import MFAService

# You might need specific schemas for MFA enrollment/verification if not already defined.
# Using generic Dict for now; replace with concrete schemas like MFAEnrollResponse, MFAVerifyRequest.

router = APIRouter(prefix="/mfa", tags=["auth:mfa"])


def get_mfa_service(db: Session = Depends(deps.get_db)) -> MFAService:
    return MFAService(db=db)


@router.post(
    "/enroll",
    status_code=status.HTTP_200_OK,
    summary="Initiate MFA enrollment",
)
def enroll_mfa(
    current_user=Depends(deps.get_current_user),
    service: MFAService = Depends(get_mfa_service),
) -> Any:
    """
    Start MFA enrollment (e.g., generate TOTP secret and QR code URI).
    """
    return service.enroll(user_id=current_user.id)


@router.post(
    "/verify",
    status_code=status.HTTP_200_OK,
    summary="Verify MFA enrollment",
)
def verify_mfa_enrollment(
    payload: Dict[str, Any],  # TODO: Replace with MFAVerifyRequest schema
    current_user=Depends(deps.get_current_user),
    service: MFAService = Depends(get_mfa_service),
) -> Any:
    """
    Verify TOTP code to finalize MFA setup and return backup codes.
    """
    return service.verify_enrollment(user_id=current_user.id, payload=payload)


@router.post(
    "/disable",
    status_code=status.HTTP_200_OK,
    summary="Disable MFA",
)
def disable_mfa(
    current_user=Depends(deps.get_current_user),
    service: MFAService = Depends(get_mfa_service),
) -> Any:
    """
    Disable MFA for the current user.
    """
    return service.disable(user_id=current_user.id)


@router.post(
    "/backup-codes",
    status_code=status.HTTP_200_OK,
    summary="Regenerate backup codes",
)
def regenerate_backup_codes(
    current_user=Depends(deps.get_current_user),
    service: MFAService = Depends(get_mfa_service),
) -> Any:
    """
    Generate a new set of backup codes.
    """
    return service.regenerate_backup_codes(user_id=current_user.id)