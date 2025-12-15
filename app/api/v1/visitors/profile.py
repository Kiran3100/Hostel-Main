# app/api/v1/visitors/profile.py

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core import get_session
from app.services import UnitOfWork
from app.services.visitor import VisitorService
from app.schemas.visitor.visitor_base import VisitorUpdate
from app.schemas.visitor.visitor_response import VisitorDetail, VisitorProfile
from . import CurrentUser, get_current_visitor

router = APIRouter(tags=["Visitor - Profile"])


def _get_service(session: Session) -> VisitorService:
    """Helper to construct VisitorService with a UnitOfWork."""
    uow = UnitOfWork(session)
    return VisitorService(uow)


@router.get("/me", response_model=VisitorDetail)
def get_my_profile(
    current_user: CurrentUser = Depends(get_current_visitor),
    session: Session = Depends(get_session),
) -> VisitorDetail:
    """
    Return the detailed visitor profile for the authenticated visitor.
    """
    service = _get_service(session)
    # Expected service method: get_visitor_detail(user_id: UUID) -> VisitorDetail
    return service.get_visitor_detail(user_id=current_user.id)


@router.get("/me/summary", response_model=VisitorProfile)
def get_my_profile_summary(
    current_user: CurrentUser = Depends(get_current_visitor),
    session: Session = Depends(get_session),
) -> VisitorProfile:
    """
    Lightweight summary/profile for dashboard/header usage.
    """
    service = _get_service(session)
    # Expected service method: get_visitor_profile_summary(user_id: UUID) -> VisitorProfile
    return service.get_visitor_profile_summary(user_id=current_user.id)


@router.patch("/me", response_model=VisitorDetail)
def update_my_profile(
    payload: VisitorUpdate,
    current_user: CurrentUser = Depends(get_current_visitor),
    session: Session = Depends(get_session),
) -> VisitorDetail:
    """
    Partially update the visitor profile of the authenticated user.
    """
    service = _get_service(session)
    # Expected service method:
    #   update_visitor_profile(user_id: UUID, data: VisitorUpdate) -> VisitorDetail
    return service.update_visitor_profile(user_id=current_user.id, data=payload)