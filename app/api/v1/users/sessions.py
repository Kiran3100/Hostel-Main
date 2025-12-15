# app/api/v1/users/sessions.py

from typing import Any, Union

from fastapi import APIRouter, Depends, Response, status
from app.services.auth import SessionService
from app.schemas.user.user_session import (
    ActiveSessionsList,
    RevokeSessionRequest,
    RevokeAllSessionsRequest,
)
from . import CurrentUser, get_current_user

router = APIRouter(tags=["Users - Sessions"])


def get_session_service() -> SessionService:
    """
    Construct a SessionService.

    Adjust this to inject a concrete SessionStore or config if needed.
    """
    return SessionService()


@router.get("/", response_model=ActiveSessionsList)
def list_my_sessions(
    current_user: CurrentUser = Depends(get_current_user),
    session_service: SessionService = Depends(get_session_service),
) -> ActiveSessionsList:
    """
    List all active sessions for the authenticated user.
    """
    # Expected service method:
    #   list_active_sessions(user_id: UUID) -> ActiveSessionsList
    return session_service.list_active_sessions(user_id=current_user.id)


@router.post("/revoke", status_code=status.HTTP_204_NO_CONTENT)
def revoke_session(
    payload: RevokeSessionRequest,
    current_user: CurrentUser = Depends(get_current_user),
    session_service: SessionService = Depends(get_session_service),
) -> Response:
    """
    Revoke a single session for the authenticated user.
    """
    # Expected payload field: session_id (str or UUID-like)
    # Expected service method:
    #   revoke_session(user_id: UUID, session_id: str) -> None
    session_service.revoke_session(
        user_id=current_user.id,
        session_id=str(payload.session_id),
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/revoke-all", status_code=status.HTTP_204_NO_CONTENT)
def revoke_all_sessions(
    payload: Union[RevokeAllSessionsRequest, None] = None,
    current_user: CurrentUser = Depends(get_current_user),
    session_service: SessionService = Depends(get_session_service),
) -> Response:
    """
    Revoke all sessions for the authenticated user.

    The payload is optional; included only to match your schema.
    """
    # Expected service method:
    #   revoke_all_sessions(user_id: UUID) -> None
    session_service.revoke_all_sessions(user_id=current_user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)