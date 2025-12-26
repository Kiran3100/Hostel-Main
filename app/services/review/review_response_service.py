"""
Review Response Service

Enhanced hostel/admin response management with templates,
guidelines, analytics, and compliance tracking.
"""

from __future__ import annotations

import logging
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime, timedelta

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.repositories.review import ReviewResponseRepository
from app.schemas.review import (
    HostelResponseCreate,
    HostelResponseUpdate,
    OwnerResponse,
    ResponseGuidelines,
    ResponseStats,
    ResponseTemplate,
)
from app.core.exceptions import (
    ValidationException,
    BusinessLogicException,
    NotFoundException,
    DatabaseException,
    AuthorizationException,
)
from app.core.cache import cache_result, invalidate_cache
from app.core.metrics import track_performance

logger = logging.getLogger(__name__)


class ReviewResponseService:
    """
    High-level service for owner/hostel responses to reviews.

    Features:
    - Response creation with validation
    - Template management for efficiency
    - Response analytics and compliance
    - Guidelines and best practices
    """

    # Business rules
    MIN_RESPONSE_LENGTH = 20
    MAX_RESPONSE_LENGTH = 2000
    RESPONSE_EDIT_WINDOW_HOURS = 48

    def __init__(self, response_repo: ReviewResponseRepository) -> None:
        """
        Initialize ReviewResponseService.

        Args:
            response_repo: Repository for response operations

        Raises:
            ValueError: If repository is None
        """
        if not response_repo:
            raise ValueError("ResponseRepository cannot be None")

        self.response_repo = response_repo
        logger.info("ReviewResponseService initialized")

    # -------------------------------------------------------------------------
    # Responses
    # -------------------------------------------------------------------------

    @track_performance("response.create")
    @invalidate_cache(patterns=["review_detail:*", "response_stats:*"])
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

        Enforces single active response per review rule with edit capability.

        Args:
            db: Database session
            hostel_id: UUID of hostel
            review_id: UUID of review being responded to
            created_by: UUID of user creating response
            payload: Response data

        Returns:
            OwnerResponse object

        Raises:
            ValidationException: If response data is invalid
            BusinessLogicException: If response already exists or review not found
            AuthorizationException: If user lacks permission
            DatabaseException: If database operation fails
        """
        try:
            logger.info(
                f"Creating response: hostel={hostel_id}, review={review_id}, "
                f"created_by={created_by}"
            )

            # Validate payload
            self._validate_response_create(payload)

            # Verify permissions
            self._verify_response_permission(db, created_by, hostel_id)

            # Check if response already exists
            existing = self.response_repo.get_response_for_review(db, review_id)
            if existing and not existing.is_deleted:
                raise BusinessLogicException(
                    "A response already exists for this review. "
                    "Please update the existing response instead."
                )

            # Create response
            data = payload.model_dump(exclude_none=True)
            data.update({
                "created_by_id": created_by,
                "created_at": datetime.utcnow(),
            })

            obj = self.response_repo.create_response(
                db=db,
                hostel_id=hostel_id,
                review_id=review_id,
                created_by=created_by,
                data=data,
            )

            response = OwnerResponse.model_validate(obj)

            logger.info(f"Response created successfully: id={response.id}")

            return response

        except (ValidationException, BusinessLogicException, AuthorizationException):
            raise
        except SQLAlchemyError as e:
            logger.error(f"Database error creating response: {str(e)}")
            db.rollback()
            raise DatabaseException("Failed to create response") from e

    @track_performance("response.update")
    @invalidate_cache(patterns=["review_detail:*", "response_stats:*"])
    def update_response(
        self,
        db: Session,
        response_id: UUID,
        updated_by: UUID,
        payload: HostelResponseUpdate,
    ) -> OwnerResponse:
        """
        Update an existing response.

        Args:
            db: Database session
            response_id: UUID of response to update
            updated_by: UUID of user updating
            payload: Update data

        Returns:
            Updated OwnerResponse object

        Raises:
            NotFoundException: If response not found
            ValidationException: If update data is invalid
            BusinessLogicException: If edit window expired
            AuthorizationException: If user lacks permission
            DatabaseException: If database operation fails
        """
        try:
            logger.info(f"Updating response {response_id} by user {updated_by}")

            # Fetch response
            response = self.response_repo.get_by_id(db, response_id)
            if not response:
                logger.warning(f"Response not found: {response_id}")
                raise NotFoundException(f"Response {response_id} not found")

            # Verify permissions
            if not self._can_edit_response(db, updated_by, response):
                logger.warning(
                    f"User {updated_by} lacks permission to edit response {response_id}"
                )
                raise AuthorizationException("Not allowed to edit this response")

            # Check edit window
            if not self._within_edit_window(response):
                raise BusinessLogicException(
                    f"Response can no longer be edited. "
                    f"Edit window is {self.RESPONSE_EDIT_WINDOW_HOURS} hours."
                )

            # Validate update
            self._validate_response_update(payload)

            # Perform update
            data = payload.model_dump(exclude_none=True)
            data["updated_at"] = datetime.utcnow()
            data["updated_by_id"] = updated_by

            updated = self.response_repo.update_response(
                db=db,
                response=response,
                updated_by=updated_by,
                data=data,
            )

            result = OwnerResponse.model_validate(updated)

            logger.info(f"Response {response_id} updated successfully")

            return result

        except (NotFoundException, ValidationException, BusinessLogicException, AuthorizationException):
            raise
        except SQLAlchemyError as e:
            logger.error(f"Database error updating response: {str(e)}")
            db.rollback()
            raise DatabaseException("Failed to update response") from e

    @track_performance("response.delete")
    @invalidate_cache(patterns=["review_detail:*", "response_stats:*"])
    def delete_response(
        self,
        db: Session,
        response_id: UUID,
        deleted_by: UUID,
    ) -> None:
        """
        Soft-delete a response.

        Args:
            db: Database session
            response_id: UUID of response to delete
            deleted_by: UUID of user deleting

        Raises:
            NotFoundException: If response not found
            AuthorizationException: If user lacks permission
            DatabaseException: If database operation fails
        """
        try:
            logger.info(f"Deleting response {response_id} by user {deleted_by}")

            response = self.response_repo.get_by_id(db, response_id)
            if not response:
                raise NotFoundException(f"Response {response_id} not found")

            # Verify permissions
            if not self._can_edit_response(db, deleted_by, response):
                logger.warning(
                    f"User {deleted_by} lacks permission to delete response {response_id}"
                )
                raise AuthorizationException("Not allowed to delete this response")

            # Soft delete
            self.response_repo.soft_delete_response(db, response)

            logger.info(f"Response {response_id} deleted successfully")

        except (NotFoundException, AuthorizationException):
            raise
        except SQLAlchemyError as e:
            logger.error(f"Database error deleting response: {str(e)}")
            db.rollback()
            raise DatabaseException("Failed to delete response") from e

    # -------------------------------------------------------------------------
    # Guidelines & stats
    # -------------------------------------------------------------------------

    @cache_result(ttl=3600, key_prefix="response_guidelines")
    def get_response_guidelines(
        self,
        db: Session,
        hostel_id: Optional[UUID] = None,
    ) -> ResponseGuidelines:
        """
        Get response guidelines (global or hostel-specific).

        Args:
            db: Database session
            hostel_id: Optional hostel UUID for specific guidelines

        Returns:
            ResponseGuidelines object

        Raises:
            DatabaseException: If database error occurs
        """
        try:
            logger.debug(f"Fetching response guidelines for hostel: {hostel_id}")

            data = self.response_repo.get_response_guidelines(db, hostel_id)

            if not data:
                logger.info("Using default response guidelines")
                guidelines = ResponseGuidelines()
            else:
                guidelines = ResponseGuidelines.model_validate(data)

            return guidelines

        except SQLAlchemyError as e:
            logger.error(f"Database error fetching guidelines: {str(e)}")
            raise DatabaseException("Failed to fetch response guidelines") from e

    @track_performance("response.get_stats")
    @cache_result(ttl=600, key_prefix="response_stats")
    def get_response_stats(
        self,
        db: Session,
        hostel_id: UUID,
        period_days: Optional[int] = None,
    ) -> ResponseStats:
        """
        Get response statistics for a hostel.

        Args:
            db: Database session
            hostel_id: UUID of hostel
            period_days: Optional number of days for stats period

        Returns:
            ResponseStats object

        Raises:
            DatabaseException: If database error occurs
        """
        try:
            logger.debug(
                f"Fetching response stats for hostel {hostel_id}, "
                f"period_days={period_days}"
            )

            data = self.response_repo.get_response_stats(
                db, hostel_id, period_days=period_days
            )

            if not data:
                logger.info(f"No response data for hostel {hostel_id}, returning empty stats")
                return ResponseStats(
                    hostel_id=hostel_id,
                    total_responses=0,
                    avg_response_time_hours=0.0,
                    response_rate=0.0,
                    response_rate_by_rating={},
                )

            stats = ResponseStats.model_validate(data)

            logger.info(
                f"Stats retrieved: total={stats.total_responses}, "
                f"rate={stats.response_rate:.1f}%, "
                f"avg_time={stats.avg_response_time_hours:.1f}h"
            )

            return stats

        except SQLAlchemyError as e:
            logger.error(f"Database error fetching response stats: {str(e)}")
            raise DatabaseException("Failed to fetch response stats") from e

    # -------------------------------------------------------------------------
    # Templates
    # -------------------------------------------------------------------------

    @cache_result(ttl=1800, key_prefix="response_templates")
    def list_templates(
        self,
        db: Session,
        hostel_id: Optional[UUID] = None,
    ) -> List[ResponseTemplate]:
        """
        List response templates (global or hostel-specific).

        Args:
            db: Database session
            hostel_id: Optional hostel UUID for hostel-specific templates

        Returns:
            List of ResponseTemplate objects

        Raises:
            DatabaseException: If database error occurs
        """
        try:
            logger.debug(f"Listing templates for hostel: {hostel_id}")

            objs = self.response_repo.get_templates(db, hostel_id)
            templates = [ResponseTemplate.model_validate(o) for o in objs]

            logger.info(f"Retrieved {len(templates)} templates")

            return templates

        except SQLAlchemyError as e:
            logger.error(f"Database error listing templates: {str(e)}")
            raise DatabaseException("Failed to list templates") from e

    @track_performance("response.create_template")
    @invalidate_cache(patterns=["response_templates:*"])
    def create_template(
        self,
        db: Session,
        data: ResponseTemplate,
    ) -> ResponseTemplate:
        """
        Create a new response template.

        Args:
            db: Database session
            data: Template data

        Returns:
            Created ResponseTemplate object

        Raises:
            ValidationException: If template data is invalid
            DatabaseException: If database operation fails
        """
        try:
            logger.info(f"Creating template: {data.name}")

            # Validate template
            self._validate_template(data)

            obj = self.response_repo.create_template(
                db, data.model_dump(exclude_none=True)
            )

            template = ResponseTemplate.model_validate(obj)

            logger.info(f"Template created successfully: id={template.id}")

            return template

        except ValidationException:
            raise
        except SQLAlchemyError as e:
            logger.error(f"Database error creating template: {str(e)}")
            db.rollback()
            raise DatabaseException("Failed to create template") from e

    @track_performance("response.update_template")
    @invalidate_cache(patterns=["response_templates:*"])
    def update_template(
        self,
        db: Session,
        template_id: UUID,
        data: ResponseTemplate,
    ) -> ResponseTemplate:
        """
        Update an existing template.

        Args:
            db: Database session
            template_id: UUID of template to update
            data: Update data

        Returns:
            Updated ResponseTemplate object

        Raises:
            NotFoundException: If template not found
            ValidationException: If update data is invalid
            DatabaseException: If database operation fails
        """
        try:
            logger.info(f"Updating template {template_id}")

            tmpl = self.response_repo.get_template_by_id(db, template_id)
            if not tmpl:
                logger.warning(f"Template not found: {template_id}")
                raise NotFoundException(f"Template {template_id} not found")

            # Validate update
            self._validate_template(data)

            updated = self.response_repo.update_template(
                db, tmpl, data.model_dump(exclude_none=True)
            )

            result = ResponseTemplate.model_validate(updated)

            logger.info(f"Template {template_id} updated successfully")

            return result

        except (NotFoundException, ValidationException):
            raise
        except SQLAlchemyError as e:
            logger.error(f"Database error updating template: {str(e)}")
            db.rollback()
            raise DatabaseException("Failed to update template") from e

    @track_performance("response.delete_template")
    @invalidate_cache(patterns=["response_templates:*"])
    def delete_template(
        self,
        db: Session,
        template_id: UUID,
    ) -> None:
        """
        Delete a response template.

        Args:
            db: Database session
            template_id: UUID of template to delete

        Raises:
            NotFoundException: If template not found
            DatabaseException: If database operation fails
        """
        try:
            logger.info(f"Deleting template {template_id}")

            tmpl = self.response_repo.get_template_by_id(db, template_id)
            if not tmpl:
                raise NotFoundException(f"Template {template_id} not found")

            self.response_repo.delete_template(db, tmpl)

            logger.info(f"Template {template_id} deleted successfully")

        except NotFoundException:
            raise
        except SQLAlchemyError as e:
            logger.error(f"Database error deleting template: {str(e)}")
            db.rollback()
            raise DatabaseException("Failed to delete template") from e

    # -------------------------------------------------------------------------
    # Private helper methods
    # -------------------------------------------------------------------------

    def _validate_response_create(self, payload: HostelResponseCreate) -> None:
        """Validate response creation data."""
        if not payload.text or not payload.text.strip():
            raise ValidationException("Response text is required")

        text_length = len(payload.text.strip())
        if text_length < self.MIN_RESPONSE_LENGTH:
            raise ValidationException(
                f"Response must be at least {self.MIN_RESPONSE_LENGTH} characters"
            )

        if text_length > self.MAX_RESPONSE_LENGTH:
            raise ValidationException(
                f"Response cannot exceed {self.MAX_RESPONSE_LENGTH} characters"
            )

    def _validate_response_update(self, payload: HostelResponseUpdate) -> None:
        """Validate response update data."""
        if payload.text is not None:
            if not payload.text.strip():
                raise ValidationException("Response text cannot be empty")

            text_length = len(payload.text.strip())
            if text_length < self.MIN_RESPONSE_LENGTH:
                raise ValidationException(
                    f"Response must be at least {self.MIN_RESPONSE_LENGTH} characters"
                )

            if text_length > self.MAX_RESPONSE_LENGTH:
                raise ValidationException(
                    f"Response cannot exceed {self.MAX_RESPONSE_LENGTH} characters"
                )

    def _validate_template(self, template: ResponseTemplate) -> None:
        """Validate template data."""
        if not template.name or not template.name.strip():
            raise ValidationException("Template name is required")

        if not template.content or not template.content.strip():
            raise ValidationException("Template content is required")

        if len(template.content.strip()) < self.MIN_RESPONSE_LENGTH:
            raise ValidationException(
                f"Template content must be at least {self.MIN_RESPONSE_LENGTH} characters"
            )

    def _verify_response_permission(
        self,
        db: Session,
        user_id: UUID,
        hostel_id: UUID,
    ) -> None:
        """Verify user has permission to respond for hostel."""
        has_permission = self.response_repo.verify_hostel_permission(
            db, user_id, hostel_id
        )

        if not has_permission:
            logger.warning(
                f"User {user_id} lacks permission for hostel {hostel_id}"
            )
            raise AuthorizationException(
                "You do not have permission to respond for this hostel"
            )

    def _can_edit_response(
        self,
        db: Session,
        user_id: UUID,
        response: Any,
    ) -> bool:
        """Check if user can edit response."""
        # Creator can always edit
        if hasattr(response, 'created_by_id') and response.created_by_id == user_id:
            return True

        # Check if user has admin permission
        return self.response_repo.can_edit_any_response(db, user_id)

    def _within_edit_window(self, response: Any) -> bool:
        """Check if response is within edit window."""
        if not hasattr(response, 'created_at') or not response.created_at:
            return False

        cutoff = datetime.utcnow() - timedelta(hours=self.RESPONSE_EDIT_WINDOW_HOURS)
        return response.created_at > cutoff