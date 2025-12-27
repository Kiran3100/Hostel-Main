"""
Authentication logout endpoints.

This module provides endpoints for user session termination including:
- Single session logout
- All sessions logout
"""

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.auth.token import LogoutRequest
from app.services.auth.authentication_service import AuthenticationService

# Router configuration
router = APIRouter(
    prefix="/logout",
    tags=["auth:logout"],
    responses={
        401: {"description": "Unauthorized - Invalid or missing token"},
        404: {"description": "Session not found"},
    },
)


def get_auth_service(db: Session = Depends(deps.get_db)) -> AuthenticationService:
    """
    Dependency injection for AuthenticationService.
    
    Args:
        db: Database session from dependency injection
        
    Returns:
        AuthenticationService instance
    """
    return AuthenticationService(db=db)


@router.post(
    "",
    status_code=status.HTTP_200_OK,
    summary="Logout user",
    description="Terminate user session(s). Can revoke current session or all sessions.",
    response_description="Successfully logged out",
)
async def logout(
    payload: LogoutRequest,
    current_user=Depends(deps.get_current_user),
    service: AuthenticationService = Depends(get_auth_service),
) -> Dict[str, Any]:
    """
    Log out the current user.
    
    Can revoke a single session (current access token) or all sessions
    based on the payload configuration.
    
    Args:
        payload: Logout configuration (e.g., logout_all_sessions flag)
        current_user: Currently authenticated user from dependency injection
        service: Authentication service instance
        
    Returns:
        Success message with logout details
        
    Raises:
        HTTPException: If logout operation fails
    """
    try:
        result = service.logout(user_id=current_user.id, payload=payload)
        return {
            "message": "Successfully logged out",
            "detail": result,
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during logout",
        ) from e