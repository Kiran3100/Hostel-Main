"""
Maintenance Completion Service

Handles the completion workflow for maintenance tasks including work verification,
quality checks, documentation, and certificate generation.

Features:
- Comprehensive completion documentation
- Multi-level quality checks
- Photo/evidence upload support
- Material and time tracking
- Completion certificate generation
- Warranty tracking
"""

from __future__ import annotations

from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime

from sqlalchemy.orm import Session

from app.repositories.maintenance import MaintenanceCompletionRepository
from app.schemas.maintenance import (
    CompletionRequest,
    CompletionResponse,
    CompletionCertificate,
    ChecklistItem,
    QualityCheck,
)
from app.core.exceptions import ValidationException, BusinessLogicException
from app.core.logging import logger


class MaintenanceCompletionService:
    """
    High-level orchestration for maintenance completion and quality control.

    Ensures proper documentation and verification of completed maintenance work.
    """

    def __init__(self, completion_repo: MaintenanceCompletionRepository) -> None:
        """
        Initialize the completion service.

        Args:
            completion_repo: Repository for completion data persistence
        """
        if not completion_repo:
            raise ValueError("MaintenanceCompletionRepository is required")
        self.completion_repo = completion_repo

    # -------------------------------------------------------------------------
    # Completion Recording
    # -------------------------------------------------------------------------

    def record_completion(
        self,
        db: Session,
        request: CompletionRequest,
    ) -> CompletionResponse:
        """
        Record completion of a maintenance request.

        Documents work performed, materials used, time spent, and any
        additional notes or photos.

        Args:
            db: Database session
            request: Completion details

        Returns:
            CompletionResponse with completion record

        Raises:
            ValidationException: If completion data is invalid
            BusinessLogicException: If request cannot be completed
        """
        # Validate completion data
        self._validate_completion_request(request)

        try:
            logger.info(
                f"Recording completion for maintenance request "
                f"{request.maintenance_request_id}"
            )

            payload = request.model_dump(exclude_none=True)
            
            # Ensure completion timestamp
            if "completed_at" not in payload or not payload["completed_at"]:
                payload["completed_at"] = datetime.utcnow()

            obj = self.completion_repo.create_completion(db, payload)

            logger.info(
                f"Successfully recorded completion {obj.id} for "
                f"request {request.maintenance_request_id}"
            )

            # TODO: Trigger notifications
            # await self._notify_completion(obj)
            # await self._request_quality_check(obj)

            return CompletionResponse.model_validate(obj)

        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                f"Error recording completion: {str(e)}",
                exc_info=True
            )
            raise BusinessLogicException(
                f"Failed to record maintenance completion: {str(e)}"
            )

    def update_completion(
        self,
        db: Session,
        completion_id: UUID,
        updates: Dict[str, Any],
    ) -> CompletionResponse:
        """
        Update completion record with additional information.

        Args:
            db: Database session
            completion_id: UUID of completion record
            updates: Fields to update

        Returns:
            Updated CompletionResponse

        Raises:
            ValidationException: If completion not found
        """
        if not completion_id:
            raise ValidationException("Completion ID is required")

        try:
            completion = self.completion_repo.get_by_id(db, completion_id)
            if not completion:
                raise ValidationException(
                    f"Completion record {completion_id} not found"
                )

            updated = self.completion_repo.update_completion(
                db=db,
                completion=completion,
                data=updates,
            )

            logger.info(f"Updated completion record {completion_id}")
            return CompletionResponse.model_validate(updated)

        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                f"Error updating completion {completion_id}: {str(e)}",
                exc_info=True
            )
            raise BusinessLogicException(
                f"Failed to update completion: {str(e)}"
            )

    # -------------------------------------------------------------------------
    # Quality Check Operations
    # -------------------------------------------------------------------------

    def record_quality_check(
        self,
        db: Session,
        request_id: UUID,
        qc: QualityCheck,
    ) -> QualityCheck:
        """
        Record a quality check for a completed maintenance request.

        Quality checks verify that work was completed to standards and
        can trigger rework if issues are found.

        Args:
            db: Database session
            request_id: UUID of maintenance request
            qc: Quality check details

        Returns:
            QualityCheck record

        Raises:
            ValidationException: If quality check data is invalid
            BusinessLogicException: If request is not completed
        """
        # Validate quality check data
        self._validate_quality_check(qc)

        try:
            logger.info(
                f"Recording quality check for maintenance request {request_id}"
            )

            payload = qc.model_dump(exclude_none=True)
            payload["maintenance_request_id"] = request_id

            # Ensure inspection timestamp
            if "inspected_at" not in payload or not payload["inspected_at"]:
                payload["inspected_at"] = datetime.utcnow()

            obj = self.completion_repo.create_quality_check(db, payload)

            logger.info(
                f"Quality check recorded with status: {qc.inspection_status}"
            )

            # If QC failed, trigger rework workflow
            if qc.inspection_status == "failed":
                logger.warning(
                    f"Quality check failed for request {request_id}, "
                    f"rework required"
                )
                # TODO: Trigger rework workflow
                # await self._initiate_rework(obj)

            # If QC passed, finalize completion
            elif qc.inspection_status == "passed":
                logger.info(f"Quality check passed for request {request_id}")
                # TODO: Finalize completion and close request
                # await self._finalize_completion(request_id)

            return QualityCheck.model_validate(obj)

        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                f"Error recording quality check: {str(e)}",
                exc_info=True
            )
            raise BusinessLogicException(
                f"Failed to record quality check: {str(e)}"
            )

    def get_quality_checks_for_request(
        self,
        db: Session,
        request_id: UUID,
    ) -> List[QualityCheck]:
        """
        Retrieve all quality checks for a maintenance request.

        Args:
            db: Database session
            request_id: UUID of maintenance request

        Returns:
            List of QualityCheck records
        """
        if not request_id:
            raise ValidationException("Request ID is required")

        try:
            checks = self.completion_repo.get_quality_checks_for_request(
                db,
                request_id
            )

            return [QualityCheck.model_validate(c) for c in checks]

        except Exception as e:
            logger.error(
                f"Error retrieving quality checks: {str(e)}",
                exc_info=True
            )
            raise BusinessLogicException(
                f"Failed to retrieve quality checks: {str(e)}"
            )

    # -------------------------------------------------------------------------
    # Certificate Generation
    # -------------------------------------------------------------------------

    def generate_completion_certificate(
        self,
        db: Session,
        completion_id: UUID,
    ) -> CompletionCertificate:
        """
        Generate a completion certificate for a finished maintenance task.

        The certificate includes all work details, quality check results,
        and warranty information.

        Args:
            db: Database session
            completion_id: UUID of completion record

        Returns:
            CompletionCertificate with complete documentation

        Raises:
            ValidationException: If completion not found or not ready
        """
        if not completion_id:
            raise ValidationException("Completion ID is required")

        try:
            logger.info(f"Generating completion certificate for {completion_id}")

            data = self.completion_repo.get_certificate_data(db, completion_id)
            if not data:
                raise ValidationException(
                    f"Completion certificate data not found for {completion_id}"
                )

            # Verify completion is ready for certificate
            self._verify_certificate_ready(data)

            certificate = CompletionCertificate.model_validate(data)

            logger.info(
                f"Successfully generated completion certificate {completion_id}"
            )

            # TODO: Generate PDF and store
            # pdf_path = await self._generate_certificate_pdf(certificate)
            # certificate.pdf_url = pdf_path

            return certificate

        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                f"Error generating certificate: {str(e)}",
                exc_info=True
            )
            raise BusinessLogicException(
                f"Failed to generate completion certificate: {str(e)}"
            )

    def get_completion_for_request(
        self,
        db: Session,
        request_id: UUID,
    ) -> Optional[CompletionResponse]:
        """
        Retrieve completion record for a maintenance request.

        Args:
            db: Database session
            request_id: UUID of maintenance request

        Returns:
            CompletionResponse if found, None otherwise
        """
        if not request_id:
            raise ValidationException("Request ID is required")

        try:
            completion = self.completion_repo.get_by_request_id(db, request_id)
            if not completion:
                return None

            return CompletionResponse.model_validate(completion)

        except Exception as e:
            logger.error(
                f"Error retrieving completion for request {request_id}: {str(e)}",
                exc_info=True
            )
            raise BusinessLogicException(
                f"Failed to retrieve completion record: {str(e)}"
            )

    # -------------------------------------------------------------------------
    # Checklist Management
    # -------------------------------------------------------------------------

    def create_completion_checklist(
        self,
        db: Session,
        request_id: UUID,
        items: List[ChecklistItem],
    ) -> List[ChecklistItem]:
        """
        Create a completion checklist for a maintenance request.

        Args:
            db: Database session
            request_id: UUID of maintenance request
            items: Checklist items

        Returns:
            List of created ChecklistItem records
        """
        if not request_id:
            raise ValidationException("Request ID is required")

        if not items:
            raise ValidationException("At least one checklist item is required")

        try:
            created_items = []
            for item in items:
                payload = item.model_dump(exclude_none=True)
                payload["maintenance_request_id"] = request_id

                obj = self.completion_repo.create_checklist_item(db, payload)
                created_items.append(ChecklistItem.model_validate(obj))

            logger.info(
                f"Created {len(created_items)} checklist items "
                f"for request {request_id}"
            )

            return created_items

        except Exception as e:
            logger.error(
                f"Error creating checklist: {str(e)}",
                exc_info=True
            )
            raise BusinessLogicException(
                f"Failed to create completion checklist: {str(e)}"
            )

    def update_checklist_item(
        self,
        db: Session,
        item_id: UUID,
        completed: bool,
        notes: Optional[str] = None,
    ) -> ChecklistItem:
        """
        Update a checklist item completion status.

        Args:
            db: Database session
            item_id: UUID of checklist item
            completed: Whether item is completed
            notes: Optional notes

        Returns:
            Updated ChecklistItem
        """
        if not item_id:
            raise ValidationException("Checklist item ID is required")

        try:
            item = self.completion_repo.get_checklist_item(db, item_id)
            if not item:
                raise ValidationException(f"Checklist item {item_id} not found")

            updates = {
                "completed": completed,
                "completed_at": datetime.utcnow() if completed else None,
            }
            if notes:
                updates["notes"] = notes

            updated = self.completion_repo.update_checklist_item(
                db=db,
                item=item,
                data=updates,
            )

            return ChecklistItem.model_validate(updated)

        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                f"Error updating checklist item: {str(e)}",
                exc_info=True
            )
            raise BusinessLogicException(
                f"Failed to update checklist item: {str(e)}"
            )

    # -------------------------------------------------------------------------
    # Private Validation Methods
    # -------------------------------------------------------------------------

    def _validate_completion_request(self, request: CompletionRequest) -> None:
        """Validate completion request data."""
        if not request.maintenance_request_id:
            raise ValidationException("Maintenance request ID is required")

        if not request.completed_by:
            raise ValidationException("Completed by field is required")

        if request.actual_cost is not None and request.actual_cost < 0:
            raise ValidationException("Actual cost cannot be negative")

        if request.labor_hours is not None and request.labor_hours < 0:
            raise ValidationException("Labor hours cannot be negative")

    def _validate_quality_check(self, qc: QualityCheck) -> None:
        """Validate quality check data."""
        if not qc.inspected_by:
            raise ValidationException("Inspector ID is required")

        valid_statuses = ["passed", "failed", "conditional"]
        if qc.inspection_status not in valid_statuses:
            raise ValidationException(
                f"Invalid inspection status. Must be one of: {valid_statuses}"
            )

        if qc.inspection_status == "failed" and not qc.issues_found:
            raise ValidationException(
                "Issues found must be specified for failed inspection"
            )

        if qc.quality_rating is not None:
            if not 1 <= qc.quality_rating <= 5:
                raise ValidationException("Quality rating must be between 1 and 5")

    def _verify_certificate_ready(self, data: Dict[str, Any]) -> None:
        """Verify completion is ready for certificate generation."""
        # Check if quality check passed
        qc_status = data.get("quality_check_status")
        if qc_status != "passed":
            raise BusinessLogicException(
                "Cannot generate certificate: Quality check must pass"
            )

        # Verify completion data is complete
        required_fields = ["completed_by", "completed_at", "work_performed"]
        missing = [f for f in required_fields if not data.get(f)]
        if missing:
            raise ValidationException(
                f"Cannot generate certificate: Missing required fields: {missing}"
            )