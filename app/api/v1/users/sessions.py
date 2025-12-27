"""
User session management endpoints.

Handles active session listing, session revocation,
and session analytics for security and auditing.
"""
from typing import Any

from fastapi import APIRouter, Depends, Path, Query, status
from fastapi.responses import Response

from app.core.dependencies import AuthenticationDependency
from app.services.user.user_session_service import UserSessionService
from app.schemas.user_session import (
    SessionInfo,
    SessionAnalytics,
)

router = APIRouter(
    prefix="/users/me/sessions",
    tags=["Users - Sessions"],
)


# ==================== Dependencies ====================


def get_session_service() -> UserSessionService:
    """
    Dependency injection for UserSessionService.
    
    Returns:
        UserSessionService: Configured session service instance
        
    Raises:
        NotImplementedError: When service factory is not configured
    """
    # TODO: Wire to ServiceFactory / DI container
    raise NotImplementedError("UserSessionService dependency must be configured")


def get_current_user(auth: AuthenticationDependency = Depends()) -> Any:
    """
    Extract current authenticated user from auth dependency.
    
    Args:
        auth: Authentication dependency instance
        
    Returns:
        User object for the authenticated user
    """
    return auth.get_current_user()


# ==================== Session Listing & Details ====================


@router.get(
    "",
    response_model=list[SessionInfo],
    summary="List active sessions",
    description="Retrieve all active sessions for the authenticated user",
    response_description="List of active sessions",
)
async def list_active_sessions(
    session_service: UserSessionService = Depends(get_session_service),
    current_user: Any = Depends(get_current_user),
) -> list[SessionInfo]:
    """
    List all active sessions for current user.
    
    Returns information about each session including:
    - Session ID
    - Device information (type, OS, browser)
    - Location (IP address, geolocation)
    - Creation and last activity timestamps
    - Current session indicator
    
    Useful for:
    - Security auditing
    - Device management
    - Suspicious activity detection
    
    Returns:
        List of active session details
    """
    result = session_service.list_active_sessions(user_id=current_user.id)
    return result.unwrap()


@router.get(
    "/{session_id}",
    response_model=SessionInfo,
    summary="Get session details",
    description="Retrieve detailed information about a specific session",
    response_description="Session details",
    responses={
        200: {"description": "Session found"},
        404: {"description": "Session not found"},
        403: {"description": "Session belongs to another user"},
    },
)
async def get_session_details(
    session_id: str = Path(
        ...,
        description="Unique session identifier",
        example="sess_abc123xyz789",
    ),
    session_service: UserSessionService = Depends(get_session_service),
    current_user: Any = Depends(get_current_user),
) -> SessionInfo:
    """
    Get detailed information about a specific session.
    
    Provides comprehensive session data including:
    - Full device fingerprint
    - Complete activity history
    - Security events
    - Geographic details
    
    Args:
        session_id: Unique identifier for the session
        
    Returns:
        Detailed session information
        
    Raises:
        HTTPException: 404 if session not found
        HTTPException: 403 if session doesn't belong to user
    """
    result = session_service.get_session(
        user_id=current_user.id,
        session_id=session_id,
    )
    return result.unwrap()


# ==================== Session Analytics ====================


@router.get(
    "/analytics",
    response_model=SessionAnalytics,
    summary="Get session analytics",
    description="Retrieve analytics and statistics about user sessions",
    response_description="Session analytics data",
)
async def get_session_analytics(
    session_service: UserSessionService = Depends(get_session_service),
    current_user: Any = Depends(get_current_user),
) -> SessionAnalytics:
    """
    Get session analytics for current user.
    
    Provides aggregated metrics including:
    - Total active sessions
    - Session distribution by device type
    - Geographic distribution
    - Login frequency patterns
    - Security events summary
    
    Useful for:
    - Security monitoring
    - Usage pattern analysis
    - Anomaly detection
    
    Returns:
        Comprehensive session analytics
    """
    result = session_service.get_session_analytics(user_id=current_user.id)
    return result.unwrap()


# ==================== Session Revocation ====================


@router.delete(
    "/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke session",
    description="Terminate a specific session",
    responses={
        204: {"description": "Session revoked successfully"},
        404: {"description": "Session not found"},
        403: {"description": "Cannot revoke this session"},
    },
)
async def revoke_session(
    session_id: str = Path(
        ...,
        description="Unique session identifier to revoke",
    ),
    session_service: UserSessionService = Depends(get_session_service),
    current_user: Any = Depends(get_current_user),
) -> Response:
    """
    Revoke a specific session.
    
    Immediately terminates the specified session, logging out
    the associated device/browser. The user will need to
    re-authenticate to create a new session.
    
    **Can revoke current session** - use with caution as it will
    log out the current request.
    
    Args:
        session_id: ID of session to revoke
        
    Returns:
        204 No Content on success
        
    Raises:
        HTTPException: 404 if session not found
        HTTPException: 403 if session doesn't belong to user
    """
    session_service.revoke_session(
        user_id=current_user.id,
        session_id=session_id,
    ).unwrap()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete(
    "",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke all sessions",
    description="Terminate all sessions for the user",
    responses={
        204: {"description": "Sessions revoked successfully"},
    },
)
async def revoke_all_sessions(
    keep_current: bool = Query(
        True,
        description="Whether to preserve the current session",
    ),
    session_service: UserSessionService = Depends(get_session_service),
    current_user: Any = Depends(get_current_user),
) -> Response:
    """
    Revoke all user sessions.
    
    Terminates all active sessions for the user, effectively
    logging out all devices.
    
    **Security Use Cases:**
    - Password change
    - Suspected account compromise
    - Lost/stolen device
    - Privacy concerns
    
    Args:
        keep_current: If True, preserves the current session.
                     If False, logs out everywhere including current device.
                     
    Returns:
        204 No Content on success
        
    **Warning:** Setting keep_current=False will log out the current
    session, requiring re-authentication.
    """
    session_service.revoke_all_sessions(
        user_id=current_user.id,
        keep_current=keep_current,
    ).unwrap()
    return Response(status_code=status.HTTP_204_NO_CONTENT)