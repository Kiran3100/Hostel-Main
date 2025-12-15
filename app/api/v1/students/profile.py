# app/api/v1/students/profile.py
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core import get_session
from app.services import UnitOfWork
from app.services.student import StudentProfileService
from app.schemas.student.student_profile import (
    StudentProfileUpdate,
    StudentDocuments,
    DocumentInfo,
    DocumentUploadRequest,
    DocumentVerificationRequest,
    StudentPreferences,
)
from app.schemas.student.student_response import StudentDetail
from . import CurrentUser, get_current_student

router = APIRouter(tags=["Students - Profile"])


def _get_service(session: Session) -> StudentProfileService:
    uow = UnitOfWork(session)
    return StudentProfileService(uow)


@router.get("/", response_model=StudentDetail)
def get_my_student_profile(
    current_user: CurrentUser = Depends(get_current_student),
    session: Session = Depends(get_session),
) -> StudentDetail:
    """
    Get the student profile for the authenticated student user.

    Expected service method:
        get_profile_for_user(user_id: UUID) -> StudentDetail
    """
    service = _get_service(session)
    return service.get_profile_for_user(user_id=current_user.id)


@router.patch("", response_model=StudentDetail)
def update_my_student_profile(
    payload: StudentProfileUpdate,
    current_user: CurrentUser = Depends(get_current_student),
    session: Session = Depends(get_session),
) -> StudentDetail:
    """
    Update profile fields (guardian, institution, employment, preferences) for the current student.

    Expected service method:
        update_profile_for_user(user_id: UUID, data: StudentProfileUpdate) -> StudentDetail
    """
    service = _get_service(session)
    return service.update_profile_for_user(
        user_id=current_user.id,
        data=payload,
    )


@router.get("/preferences", response_model=StudentPreferences)
def get_my_preferences(
    current_user: CurrentUser = Depends(get_current_student),
    session: Session = Depends(get_session),
) -> StudentPreferences:
    """
    Get preferences for the authenticated student.

    Expected service method:
        get_preferences_for_user(user_id: UUID) -> StudentPreferences
    """
    service = _get_service(session)
    return service.get_preferences_for_user(user_id=current_user.id)


@router.patch("/preferences", response_model=StudentPreferences)
def update_my_preferences(
    payload: StudentPreferences,
    current_user: CurrentUser = Depends(get_current_student),
    session: Session = Depends(get_session),
) -> StudentPreferences:
    """
    Update preferences for the authenticated student.

    Expected service method:
        update_preferences_for_user(user_id: UUID, data: StudentPreferences) -> StudentPreferences
    """
    service = _get_service(session)
    return service.update_preferences_for_user(
        user_id=current_user.id,
        data=payload,
    )


@router.get("/documents", response_model=StudentDocuments)
def list_my_documents(
    current_user: CurrentUser = Depends(get_current_student),
    session: Session = Depends(get_session),
) -> StudentDocuments:
    """
    List all documents for the authenticated student.

    Expected service method:
        list_documents_for_user(user_id: UUID) -> StudentDocuments
    """
    service = _get_service(session)
    return service.list_documents_for_user(user_id=current_user.id)


@router.post("/documents/upload", response_model=DocumentInfo)
def init_document_upload(
    payload: DocumentUploadRequest,
    current_user: CurrentUser = Depends(get_current_student),
    session: Session = Depends(get_session),
) -> DocumentInfo:
    """
    Initialize a document upload for the student (returns metadata / upload target).

    Expected service method:
        init_document_upload(user_id: UUID, data: DocumentUploadRequest) -> DocumentInfo
    """
    service = _get_service(session)
    return service.init_document_upload(
        user_id=current_user.id,
        data=payload,
    )


@router.post("/documents/{document_id}/verify", response_model=DocumentInfo)
def verify_document(
    document_id: UUID,
    payload: DocumentVerificationRequest,
    current_user: CurrentUser = Depends(get_current_student),
    session: Session = Depends(get_session),
) -> DocumentInfo:
    """
    Submit verification info for an uploaded document.

    Expected service method:
        verify_document(user_id: UUID, document_id: UUID, data: DocumentVerificationRequest) -> DocumentInfo
    """
    service = _get_service(session)
    return service.verify_document(
        user_id=current_user.id,
        document_id=document_id,
        data=payload,
    )