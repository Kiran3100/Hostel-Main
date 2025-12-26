"""
Maintenance Completion Service

Handles completion of maintenance tasks and quality checks:
- Record completion (work done, materials, time, photos)
- Record quality check
- Generate completion certificate
"""

from __future__ import annotations

from typing import List
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.maintenance import MaintenanceCompletionRepository
from app.schemas.maintenance import (
    CompletionRequest,
    CompletionResponse,
    CompletionCertificate,
    ChecklistItem,
    QualityCheck,
)
from app.core.exceptions import ValidationException


class MaintenanceCompletionService:
    """
    High-level orchestration for maintenance completion and QC.
    """

    def __init__(self, completion_repo: MaintenanceCompletionRepository) -> None:
        self.completion_repo = completion_repo

    def record_completion(
        self,
        db: Session,
        request: CompletionRequest,
    ) -> CompletionResponse:
        """
        Record that a maintenance request has been completed.
        """
        payload = request.model_dump(exclude_none=True)
        obj = self.completion_repo.create_completion(db, payload)
        return CompletionResponse.model_validate(obj)

    def record_quality_check(
        self,
        db: Session,
        request_id: UUID,
        qc: QualityCheck,
    ) -> QualityCheck:
        """
        Record a quality check for a completed maintenance request.
        """
        payload = qc.model_dump(exclude_none=True)
        payload["maintenance_request_id"] = request_id

        obj = self.completion_repo.create_quality_check(db, payload)
        return QualityCheck.model_validate(obj)

    def generate_completion_certificate(
        self,
        db: Session,
        completion_id: UUID,
    ) -> CompletionCertificate:
        """
        Generate a completion certificate (data only; PDF/etc handled elsewhere).
        """
        data = self.completion_repo.get_certificate_data(db, completion_id)
        if not data:
            raise ValidationException("Completion certificate data not found")
        return CompletionCertificate.model_validate(data)