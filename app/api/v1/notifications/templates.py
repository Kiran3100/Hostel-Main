# app/api/v1/notifications/templates.py
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, status, Response
from sqlalchemy.orm import Session

from app.core import get_session
from app.services import UnitOfWork
from app.services.notification import TemplateService
from app.schemas.notification.notification_template import (
    TemplateCreate,
    TemplateUpdate,
    TemplateResponse,
    TemplatePreview,
    TemplatePreviewResponse,
    TemplateList,
    TemplateCategory,
)
from . import CurrentUser, get_current_admin

router = APIRouter(tags=["Notifications - Templates"])


def _get_service(session: Session) -> TemplateService:
    uow = UnitOfWork(session)
    return TemplateService(uow)


@router.get("/", response_model=TemplateList)
def list_templates(
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_admin),
) -> TemplateList:
    """
    List all notification templates.
    """
    service = _get_service(session)
    # Expected: list_templates() -> TemplateList
    return service.list_templates()


@router.get("/categories", response_model=List[TemplateCategory])
def list_template_categories(
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_admin),
) -> List[TemplateCategory]:
    """
    List template categories.
    """
    service = _get_service(session)
    # Expected: list_categories() -> list[TemplateCategory]
    return service.list_categories()


@router.get("/{template_id}", response_model=TemplateResponse)
def get_template(
    template_id: UUID,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_admin),
) -> TemplateResponse:
    """
    Get a single template.
    """
    service = _get_service(session)
    # Expected: get_template(template_id: UUID) -> TemplateResponse
    return service.get_template(template_id=template_id)


@router.post(
    "/",
    response_model=TemplateResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_template(
    payload: TemplateCreate,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_admin),
) -> TemplateResponse:
    """
    Create a new template.
    """
    service = _get_service(session)
    # Expected: create_template(data: TemplateCreate, created_by: UUID) -> TemplateResponse
    return service.create_template(
        data=payload,
        created_by=current_user.id,
    )


@router.patch("/{template_id}", response_model=TemplateResponse)
def update_template(
    template_id: UUID,
    payload: TemplateUpdate,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_admin),
) -> TemplateResponse:
    """
    Update an existing template.
    """
    service = _get_service(session)
    # Expected: update_template(template_id: UUID, data: TemplateUpdate, updated_by: UUID) -> TemplateResponse
    return service.update_template(
        template_id=template_id,
        data=payload,
        updated_by=current_user.id,
    )


@router.delete("/{template_id}")
def delete_template(
    template_id: UUID,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_admin),
) -> Response:
    """
    Delete a template.
    """
    service = _get_service(session)
    # Expected: delete_template(template_id: UUID) -> None
    service.delete_template(template_id=template_id)
    return Response(status_code=204)


@router.post("/{template_id}/preview", response_model=TemplatePreviewResponse)
def preview_template(
    template_id: UUID,
    payload: TemplatePreview,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_admin),
) -> TemplatePreviewResponse:
    """
    Render a preview of a template with given variables.
    """
    service = _get_service(session)
    # Expected: preview_template(template_id: UUID, data: TemplatePreview) -> TemplatePreviewResponse
    return service.preview_template(
        template_id=template_id,
        data=payload,
    )