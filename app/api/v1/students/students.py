# app/api/v1/students/students.py
from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core import get_session
from app.services import UnitOfWork
from app.services.student import StudentService
from app.schemas.student.student_base import StudentCreate, StudentUpdate
from app.schemas.student.student_response import (
    StudentDetail,
    StudentListItem,
)
from app.schemas.student.student_filters import StudentFilterParams
from . import CurrentUser, get_current_user

router = APIRouter(tags=["Students"])


def _get_service(session: Session) -> StudentService:
    uow = UnitOfWork(session)
    return StudentService(uow)


@router.get("/", response_model=List[StudentListItem])
def list_students(
    filters: StudentFilterParams = Depends(),
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> List[StudentListItem]:
    """
    List students with advanced filters and sorting.

    Expected service method:
        list_students(filters: StudentFilterParams) -> list[StudentListItem]
    """
    service = _get_service(session)
    return service.list_students(filters=filters)


@router.get("/hostels/{hostel_id}", response_model=List[StudentListItem])
def list_students_for_hostel(
    hostel_id: UUID,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> List[StudentListItem]:
    """
    List students for a specific hostel.

    Expected service method:
        list_students_for_hostel(hostel_id: UUID) -> list[StudentListItem]
    """
    service = _get_service(session)
    return service.list_students_for_hostel(hostel_id=hostel_id)


@router.get("/{student_id}", response_model=StudentDetail)
def get_student(
    student_id: UUID,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> StudentDetail:
    """
    Get detailed information for a single student.

    Expected service method:
        get_student_detail(student_id: UUID) -> StudentDetail
    """
    service = _get_service(session)
    return service.get_student_detail(student_id=student_id)


@router.post(
    "/",
    response_model=StudentDetail,
    status_code=status.HTTP_201_CREATED,
)
def create_student(
    payload: StudentCreate,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> StudentDetail:
    """
    Create a new student (admin-only operation).

    Expected service method:
        create_student(data: StudentCreate) -> StudentDetail
    """
    service = _get_service(session)
    return service.create_student(data=payload)


@router.patch("/{student_id}", response_model=StudentDetail)
def update_student(
    student_id: UUID,
    payload: StudentUpdate,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> StudentDetail:
    """
    Update an existing student.

    Expected service method:
        update_student(student_id: UUID, data: StudentUpdate) -> StudentDetail
    """
    service = _get_service(session)
    return service.update_student(
        student_id=student_id,
        data=payload,
    )