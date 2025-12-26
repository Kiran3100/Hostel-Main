"""
Maintenance Assignment Service

Manages assignment of maintenance tasks to internal staff and external vendors.
"""

from __future__ import annotations

from typing import List
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.maintenance import MaintenanceAssignmentRepository
from app.schemas.maintenance import (
    TaskAssignment,
    VendorAssignment as VendorAssignmentSchema,
    AssignmentUpdate,
    BulkAssignment,
    AssignmentEntry,
    AssignmentHistory,
)
from app.core.exceptions import ValidationException, BusinessLogicException


class MaintenanceAssignmentService:
    """
    High-level orchestration for maintenance assignments.

    Responsibilities:
    - Assign maintenance requests to staff
    - Assign to vendors
    - Bulk assignments
    - Retrieve assignment history
    """

    def __init__(self, assignment_repo: MaintenanceAssignmentRepository) -> None:
        self.assignment_repo = assignment_repo

    # -------------------------------------------------------------------------
    # Assignments
    # -------------------------------------------------------------------------

    def assign_to_staff(
        self,
        db: Session,
        data: TaskAssignment,
    ) -> AssignmentEntry:
        """
        Assign a maintenance request to an internal staff member.
        """
        payload = data.model_dump(exclude_none=True)
        obj = self.assignment_repo.assign_to_staff(db, payload)
        return AssignmentEntry.model_validate(obj)

    def assign_to_vendor(
        self,
        db: Session,
        data: VendorAssignmentSchema,
    ) -> AssignmentEntry:
        """
        Assign a maintenance request to an external vendor.
        """
        payload = data.model_dump(exclude_none=True)
        obj = self.assignment_repo.assign_to_vendor(db, payload)
        return AssignmentEntry.model_validate(obj)

    def update_assignment(
        self,
        db: Session,
        assignment_id: UUID,
        update: AssignmentUpdate,
    ) -> AssignmentEntry:
        assignment = self.assignment_repo.get_by_id(db, assignment_id)
        if not assignment:
            raise ValidationException("Assignment not found")

        obj = self.assignment_repo.update_assignment(
            db=db,
            assignment=assignment,
            data=update.model_dump(exclude_none=True),
        )
        return AssignmentEntry.model_validate(obj)

    def bulk_assign(
        self,
        db: Session,
        bulk: BulkAssignment,
    ) -> List[AssignmentEntry]:
        """
        Bulk assign many requests to a single staff member or vendor.
        """
        results: List[AssignmentEntry] = []

        for req_id in bulk.maintenance_request_ids:
            try:
                obj = self.assignment_repo.bulk_assign_single(
                    db=db,
                    maintenance_request_id=req_id,
                    assignee_id=bulk.assignee_id,
                    assignee_type=bulk.assignee_type,
                    priority=bulk.priority,
                    assignment_notes=bulk.assignment_notes,
                )
                results.append(AssignmentEntry.model_validate(obj))
            except Exception:
                if not bulk.skip_failed:
                    raise

        return results

    # -------------------------------------------------------------------------
    # History
    # -------------------------------------------------------------------------

    def get_assignment_history_for_request(
        self,
        db: Session,
        request_id: UUID,
    ) -> AssignmentHistory:
        data = self.assignment_repo.get_history_for_request(db, request_id)
        if not data:
            # Provide empty history object
            return AssignmentHistory(
                maintenance_request_id=request_id,
                assignments=[],
                total_assignments=0,
            )
        return AssignmentHistory.model_validate(data)