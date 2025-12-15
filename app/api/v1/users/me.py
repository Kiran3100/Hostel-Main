# app/api/v1/users/me.py

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core import get_session
from app.services import UnitOfWork
from app.services.users import UserService
from app.schemas.user.user_response import UserDetail, UserResponse
from . import CurrentUser, get_current_user

router = APIRouter(tags=["Users - Me"])


def _get_user_service(session: Session) -> UserService:
    """Helper to construct UserService with a UnitOfWork."""
    uow = UnitOfWork(session)
    return UserService(uow)


@router.get("/", response_model=UserDetail)
def get_me(
    current_user: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> UserDetail:
    """
    Return full details of the authenticated user.
    """
    service = _get_user_service(session)
    # Expected service method: get_user_detail(user_id: UUID) -> UserDetail
    return service.get_user_detail(user_id=current_user.id)


@router.get("/summary", response_model=UserResponse)
def get_me_summary(
    current_user: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> UserResponse:
    """
    Lightweight summary of the authenticated user (for headers, etc.).
    """
    service = _get_user_service(session)
    # Expected service method: get_user_summary(user_id: UUID) -> UserResponse
    return service.get_user_summary(user_id=current_user.id)