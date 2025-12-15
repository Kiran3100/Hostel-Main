# app/api/v1/students/room_history.py
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core import get_session
from app.services import UnitOfWork
from app.services.student import StudentRoomHistoryService
from app.schemas.student.student_room_history import RoomHistoryResponse
from . import CurrentUser, get_current_user, get_current_student

router = APIRouter(tags=["Students - Room History"])


def _get_service(session: Session) -> StudentRoomHistoryService:
    uow = UnitOfWork(session)
    return StudentRoomHistoryService(uow)


@router.get("/", response_model=RoomHistoryResponse)
def get_my_room_history(
    current_user: CurrentUser = Depends(get_current_student),
    session: Session = Depends(get_session),
) -> RoomHistoryResponse:
    """
    Get room/bed history for the authenticated student.

    Expected service method:
        get_history_for_user(user_id: UUID) -> RoomHistoryResponse
    """
    service = _get_service(session)
    return service.get_history_for_user(user_id=current_user.id)


@router.get("/{student_id}", response_model=RoomHistoryResponse)
def get_room_history_for_student(
    student_id: UUID,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> RoomHistoryResponse:
    """
    Admin endpoint: get room/bed history for a specific student.

    Expected service method:
        get_history_for_student(student_id: UUID) -> RoomHistoryResponse
    """
    service = _get_service(session)
    return service.get_history_for_student(student_id=student_id)