# app/api/v1/students/search.py
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core import get_session
from app.services import UnitOfWork
from app.services.student import StudentSearchService
from app.schemas.student.student_filters import (
    StudentSearchRequest,
    StudentExportRequest,
)
from app.schemas.student.student_response import StudentListItem
from . import CurrentUser, get_current_user

router = APIRouter(tags=["Students - Search"])


def _get_service(session: Session) -> StudentSearchService:
    uow = UnitOfWork(session)
    return StudentSearchService(uow)


@router.post("/", response_model=List[StudentListItem])
def search_students(
    payload: StudentSearchRequest,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> List[StudentListItem]:
    """
    Advanced student search over name, email, phone, room, institution, etc.

    Expected service method:
        search(request: StudentSearchRequest) -> list[StudentListItem]
    """
    service = _get_service(session)
    return service.search(request=payload)


@router.post("/export")
def export_students(
    payload: StudentExportRequest,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> dict:
    """
    Export students matching given criteria.

    This returns a simple metadata dict; you can adapt it to stream files
    or integrate with your generic export service.

    Expected service method:
        export(request: StudentExportRequest) -> dict | ExportResult
    """
    service = _get_service(session)
    result = service.export(request=payload)
    # Assume result is already JSON-serializable (e.g., { "url": "...", "format": "csv" })
    return result