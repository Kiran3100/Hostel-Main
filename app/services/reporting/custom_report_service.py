# app/services/reporting/custom_report_service.py
"""
Custom Report Service

Handles definition, execution, caching, and history for custom reports.
"""

from __future__ import annotations

from typing import List, Optional
from uuid import UUID
from datetime import datetime

from sqlalchemy.orm import Session

from app.schemas.analytics import (
    CustomReportRequest,
    CustomReportDefinition,
    CustomReportResult,
)
from app.repositories.analytics import CustomReportsRepository
from app.core.exceptions import ValidationException


class CustomReportService:
    """
    High-level orchestration for the custom reporting system.

    Responsibilities:
    - Create/update/delete saved report definitions
    - Execute ad-hoc or saved reports
    - Manage cached results & execution history
    """

    def __init__(self, custom_reports_repo: CustomReportsRepository) -> None:
        self.custom_reports_repo = custom_reports_repo

    # -------------------------------------------------------------------------
    # Definitions
    # -------------------------------------------------------------------------

    def create_definition(
        self,
        db: Session,
        owner_id: UUID,
        request: CustomReportRequest,
    ) -> CustomReportDefinition:
        """
        Create a new custom report definition.
        """
        payload = request.model_dump(exclude_none=True)
        payload["owner_id"] = owner_id

        obj = self.custom_reports_repo.create_definition(db, payload)
        return CustomReportDefinition.model_validate(obj)

    def update_definition(
        self,
        db: Session,
        definition_id: UUID,
        request: CustomReportRequest,
    ) -> CustomReportDefinition:
        """
        Update an existing custom report definition.
        """
        definition = self.custom_reports_repo.get_definition_by_id(db, definition_id)
        if not definition:
            raise ValidationException("Report definition not found")

        updated = self.custom_reports_repo.update_definition(
            db=db,
            definition=definition,
            data=request.model_dump(exclude_none=True),
        )
        return CustomReportDefinition.model_validate(updated)

    def delete_definition(
        self,
        db: Session,
        definition_id: UUID,
        owner_id: UUID,
    ) -> None:
        """
        Delete a custom report definition (soft delete).
        """
        definition = self.custom_reports_repo.get_definition_by_id(db, definition_id)
        if not definition or definition.owner_id != owner_id:
            return
        self.custom_reports_repo.delete_definition(db, definition)

    def list_definitions_for_owner(
        self,
        db: Session,
        owner_id: UUID,
    ) -> List[CustomReportDefinition]:
        objs = self.custom_reports_repo.get_definitions_by_owner(db, owner_id)
        return [CustomReportDefinition.model_validate(o) for o in objs]

    # -------------------------------------------------------------------------
    # Execution
    # -------------------------------------------------------------------------

    def run_report(
        self,
        db: Session,
        request: CustomReportRequest,
        owner_id: Optional[UUID] = None,
        use_cache: bool = True,
    ) -> CustomReportResult:
        """
        Execute a custom report from a request (without saving definition).

        Args:
            db: DB session
            request: CustomReportRequest
            owner_id: Optional owner id to attribute execution
            use_cache: Use cached results if available

        Returns:
            CustomReportResult
        """
        payload = request.model_dump(exclude_none=True)

        result_data = self.custom_reports_repo.execute_report_from_request(
            db=db,
            request_data=payload,
            owner_id=owner_id,
            use_cache=use_cache,
        )
        return CustomReportResult.model_validate(result_data)

    def run_saved_report(
        self,
        db: Session,
        definition_id: UUID,
        parameters: Optional[dict] = None,
        use_cache: bool = True,
    ) -> CustomReportResult:
        """
        Execute a saved report definition.
        """
        definition = self.custom_reports_repo.get_definition_by_id(db, definition_id)
        if not definition:
            raise ValidationException("Report definition not found")

        result_data = self.custom_reports_repo.execute_saved_report(
            db=db,
            definition=definition,
            parameters=parameters or {},
            use_cache=use_cache,
        )
        return CustomReportResult.model_validate(result_data)

    def get_cached_result(
        self,
        db: Session,
        result_id: UUID,
    ) -> Optional[CustomReportResult]:
        """
        Retrieve a cached report result by id.
        """
        cached = self.custom_reports_repo.get_cached_result_by_id(db, result_id)
        if not cached:
            return None
        return CustomReportResult.model_validate(cached)