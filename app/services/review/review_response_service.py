"""
Review Response Service

Manages hostel/admin responses to reviews (owner responses).
"""

from __future__ import annotations

from typing import List
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.review import ReviewResponseRepository
from app.schemas.review import (
    HostelResponseCreate,
    HostelResponseUpdate,
    OwnerResponse,
    ResponseGuidelines,
    ResponseStats,
    ResponseTemplate,
)
from app.core.exceptions import ValidationException, BusinessLogicException


class ReviewResponseService:
    """
    High-level service for owner/hostel responses to reviews.

    Responsibilities:
    - Create/update/delete a response
    - Get guidelines
    - Get response stats per hostel
    - Manage response templates
    """

    def __init__(self, response_repo: ReviewResponseRepository) -> None:
        self.response_repo = response_repo

    # -------------------------------------------------------------------------
    # Responses
    # -------------------------------------------------------------------------

    def create_response(
        self,
        db: Session,
        hostel_id: UUID,
        review_id: UUID,
        created_by: UUID,
        payload: HostelResponseCreate,
    ) -> OwnerResponse:
        """
        Create a response to a review.

        Ensures only one current response per review (if that's your rule),
        with editing handled by update_response.
        """
        obj = self.response_repo.create_response(
            db=db,
            hostel_id=hostel_id,
            review_id=review_id,
            created_by=created_by,
            data=payload.model_dump(exclude_none=True),
        )
        return OwnerResponse.model_validate(obj)

    def update_response(
        self,
        db: Session,
        response_id: UUID,
        updated_by: UUID,
        payload: HostelResponseUpdate,
    ) -> OwnerResponse:
        response = self.response_repo.get_by_id(db, response_id)
        if not response:
            raise ValidationException("Response not found")

        if response.created_by_id != updated_by and not self.response_repo.can_edit_any_response(
            db, updated_by
        ):
            raise BusinessLogicException("Not allowed to edit this response")

        updated = self.response_repo.update_response(
            db=db,
            response=response,
            updated_by=updated_by,
            data=payload.model_dump(exclude_none=True),
        )
        return OwnerResponse.model_validate(updated)

    def delete_response(
        self,
        db: Session,
        response_id: UUID,
        deleted_by: UUID,
    ) -> None:
        response = self.response_repo.get_by_id(db, response_id)
        if not response:
            return

        if response.created_by_id != deleted_by and not self.response_repo.can_edit_any_response(
            db, deleted_by
        ):
            raise BusinessLogicException("Not allowed to delete this response")

        self.response_repo.soft_delete_response(db, response)

    # -------------------------------------------------------------------------
    # Guidelines & stats
    # -------------------------------------------------------------------------

    def get_response_guidelines(
        self,
        db: Session,
        hostel_id: Optional[UUID] = None,
    ) -> ResponseGuidelines:
        data = self.response_repo.get_response_guidelines(db, hostel_id)
        if not data:
            return ResponseGuidelines()
        return ResponseGuidelines.model_validate(data)

    def get_response_stats(
        self,
        db: Session,
        hostel_id: UUID,
    ) -> ResponseStats:
        data = self.response_repo.get_response_stats(db, hostel_id)
        if not data:
            return ResponseStats(
                hostel_id=hostel_id,
                total_responses=0,
                avg_response_time_hours=0.0,
                response_rate=0.0,
                response_rate_by_rating={},
            )
        return ResponseStats.model_validate(data)

    # -------------------------------------------------------------------------
    # Templates
    # -------------------------------------------------------------------------

    def list_templates(
        self,
        db: Session,
        hostel_id: Optional[UUID] = None,
    ) -> List[ResponseTemplate]:
        objs = self.response_repo.get_templates(db, hostel_id)
        return [ResponseTemplate.model_validate(o) for o in objs]

    def create_template(
        self,
        db: Session,
        data: ResponseTemplate,
    ) -> ResponseTemplate:
        obj = self.response_repo.create_template(db, data.model_dump(exclude_none=True))
        return ResponseTemplate.model_validate(obj)

    def update_template(
        self,
        db: Session,
        template_id: UUID,
        data: ResponseTemplate,
    ) -> ResponseTemplate:
        tmpl = self.response_repo.get_template_by_id(db, template_id)
        if not tmpl:
            raise ValidationException("Template not found")

        updated = self.response_repo.update_template(
            db, tmpl, data.model_dump(exclude_none=True)
        )
        return ResponseTemplate.model_validate(updated)

    def delete_template(
        self,
        db: Session,
        template_id: UUID,
    ) -> None:
        tmpl = self.response_repo.get_template_by_id(db, template_id)
        if not tmpl:
            return
        self.response_repo.delete_template(db, tmpl)