from typing import Any

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.auth.token import LogoutRequest
from app.services.auth.authentication_service import AuthenticationService

router = APIRouter(prefix="/logout", tags=["auth:logout"])


def get_auth_service(db: Session = Depends(deps.get_db)) -> AuthenticationService:
    return AuthenticationService(db=db)


@router.post(
    "",
    status_code=status.HTTP_200_OK,
    summary="Logout user",
)
def logout(
    payload: LogoutRequest,
    current_user=Depends(deps.get_current_user),
    service: AuthenticationService = Depends(get_auth_service),
) -> Any:
    """
    Log out the current user.
    Can revoke a single session (e.g., current access token) or all sessions based on payload.
    """
    return service.logout(user_id=current_user.id, payload=payload)