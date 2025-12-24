"""
Supervisor Assignment Service

Manages supervisor ↔ hostel assignments and related lifecycle.
"""

from __future__ import annotations

from typing import List
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.supervisor import SupervisorAssignmentRepository
from app.schemas.supervisor import (
    SupervisorAssignment,
    AssignmentRequest,
    AssignmentUpdate,
    RevokeAssignmentRequest,
)
from app.core.exceptions import ValidationException


class SupervisorAssignmentService:
    """
    High-level service for supervisor assignments.

    Responsibilities:
    - Assign supervisor to hostel
    - Update assignment configuration
    - Revoke/transfer assignments
    - List assignments per supervisor or hostel
    """

    def __init__(
        self,
        assignment_repo: SupervisorAssignmentRepository,
    ) -> None:
        self.assignment_repo = assignment_repo

    # -------------------------------------------------------------------------
    # Assignment operations
    # -------------------------------------------------------------------------

    def assign_supervisor(
        self,
        db: Session,
        data: AssignmentRequest,
    ) -> SupervisorAssignment:
        """
        Create a new supervisor assignment to a hostel.
        """
        obj = self.assignment_repo.create(
            db,
            data=data.model_dump(exclude_none=True),
        )
        return SupervisorAssignment.model_validate(obj)

    def update_assignment(
        self,
        db: Session,
        assignment_id: UUID,
        data: AssignmentUpdate,
    ) -> SupervisorAssignment:
        """
        Update an existing assignment (employment type, permissions, active flag, etc.).
        """
        assignment = self.assignment_repo.get_by_id(db, assignment_id)
        if not assignment:
            raise ValidationException("Assignment not found")

        updated = self.assignment_repo.update(
            db,
            assignment,
            data.model_dump(exclude_none=True),
        )
        return SupervisorAssignment.model_validate(updated)

    def revoke_assignment(
        self,
        db: Session,
        assignment_id: UUID,
        data: RevokeAssignmentRequest,
    ) -> SupervisorAssignment:
        """
        Revoke a supervisor's assignment from a hostel.

        Typically sets is_active=False, records reason and revoke date.
        """
        assignment = self.assignment_repo.get_by_id(db, assignment_id)
        if not assignment:
            raise ValidationException("Assignment not found")

        updated = self.assignment_repo.revoke_assignment(
            db,
            assignment,
            revoke_date=data.revoke_date,
            reason=data.reason,
            handover_notes=data.handover_notes,
        )
        return SupervisorAssignment.model_validate(updated)

    def transfer_assignment(
        self,
        db: Session,
        assignment_id: UUID,
        target_hostel_id: UUID,
        transfer_date: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> SupervisorAssignment:
        """
        Transfer an assignment to a different hostel.

        Wraps the lower-level repository logic; optionally records reason/notes.
        """
        assignment = self.assignment_repo.get_by_id(db, assignment_id)
        if not assignment:
            raise ValidationException("Assignment not found")

        updated = self.assignment_repo.transfer(
            db,
            assignment,
            new_hostel_id=target_hostel_id,
            transfer_date=transfer_date,
            reason=reason,
        )
        return SupervisorAssignment.model_validate(updated)

    # -------------------------------------------------------------------------
    # Listing
    # -------------------------------------------------------------------------

    def list_assignments_for_supervisor(
        self,
        db: Session,
        supervisor_id: UUID,
    ) -> List[SupervisorAssignment]:
        """
        List all assignments for a supervisor across hostels.
        """
        objs = self.assignment_repo.get_by_supervisor_id(db, supervisor_id)
        return [SupervisorAssignment.model_validate(o) for o in objs]

    def list_assignments_for_hostel(
        self,
        db: Session,
        hostel_id: UUID,
    ) -> List[SupervisorAssignment]:
        """
        List all supervisor assignments for a hostel.
        """
        objs = self.assignment_repo.get_by_hostel_id(db, hostel_id)
        return [SupervisorAssignment.model_validate(o) for o in objs]