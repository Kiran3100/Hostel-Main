"""
Supervisor Assignment Service

Manages supervisor ↔ hostel assignments and related lifecycle with enhanced validation.
"""

from __future__ import annotations

import logging
from typing import List, Optional
from uuid import UUID
from datetime import datetime

from sqlalchemy.orm import Session

from app.repositories.supervisor import SupervisorAssignmentRepository
from app.schemas.supervisor import (
    SupervisorAssignment,
    AssignmentRequest,
    AssignmentUpdate,
    RevokeAssignmentRequest,
)
from app.core1.exceptions import ValidationException

logger = logging.getLogger(__name__)


class SupervisorAssignmentService:
    """
    High-level service for supervisor assignments.

    Responsibilities:
    - Assign supervisor to hostel with validation
    - Update assignment configuration
    - Revoke/transfer assignments with proper handover
    - List assignments per supervisor or hostel
    - Validate assignment conflicts

    Example:
        >>> service = SupervisorAssignmentService(assignment_repo)
        >>> assignment = service.assign_supervisor(db, AssignmentRequest(...))
        >>> assignments = service.list_assignments_for_supervisor(db, supervisor_id)
    """

    def __init__(
        self,
        assignment_repo: SupervisorAssignmentRepository,
    ) -> None:
        """
        Initialize the supervisor assignment service.

        Args:
            assignment_repo: Repository for assignment operations
        """
        if not assignment_repo:
            raise ValueError("assignment_repo cannot be None")
            
        self.assignment_repo = assignment_repo

    # -------------------------------------------------------------------------
    # Assignment Operations
    # -------------------------------------------------------------------------

    def assign_supervisor(
        self,
        db: Session,
        data: AssignmentRequest,
    ) -> SupervisorAssignment:
        """
        Create a new supervisor assignment to a hostel.

        Validates for conflicts and ensures business rules are met.

        Args:
            db: Database session
            data: Assignment request data

        Returns:
            SupervisorAssignment: Created assignment object

        Raises:
            ValidationException: If validation fails or conflicts exist

        Example:
            >>> request = AssignmentRequest(
            ...     supervisor_id=supervisor_id,
            ...     hostel_id=hostel_id,
            ...     employment_type="FULL_TIME"
            ... )
            >>> assignment = service.assign_supervisor(db, request)
        """
        if not db:
            raise ValidationException("Database session is required")
        
        if not data:
            raise ValidationException("Assignment data is required")

        try:
            logger.info(
                f"Creating assignment - supervisor: {data.supervisor_id}, "
                f"hostel: {data.hostel_id}"
            )
            
            # Check for existing active assignments
            existing = self._check_active_assignment(
                db, data.supervisor_id, data.hostel_id
            )
            if existing:
                raise ValidationException(
                    f"Supervisor already has an active assignment to this hostel"
                )
            
            obj = self.assignment_repo.create(
                db,
                data=data.model_dump(exclude_none=True),
            )
            
            logger.info(f"Successfully created assignment with ID: {obj.id}")
            return SupervisorAssignment.model_validate(obj)
            
        except ValidationException:
            raise
        except Exception as e:
            logger.error(f"Failed to create assignment: {str(e)}")
            raise ValidationException(f"Failed to create assignment: {str(e)}")

    def update_assignment(
        self,
        db: Session,
        assignment_id: UUID,
        data: AssignmentUpdate,
    ) -> SupervisorAssignment:
        """
        Update an existing assignment (employment type, permissions, active flag, etc.).

        Args:
            db: Database session
            assignment_id: UUID of the assignment to update
            data: Partial update data

        Returns:
            SupervisorAssignment: Updated assignment object

        Raises:
            ValidationException: If assignment not found or update fails

        Example:
            >>> update = AssignmentUpdate(employment_type="PART_TIME")
            >>> updated = service.update_assignment(db, assignment_id, update)
        """
        if not db:
            raise ValidationException("Database session is required")
        
        if not assignment_id:
            raise ValidationException("Assignment ID is required")
        
        if not data:
            raise ValidationException("Update data is required")

        try:
            logger.info(f"Updating assignment: {assignment_id}")
            
            assignment = self.assignment_repo.get_by_id(db, assignment_id)
            if not assignment:
                logger.warning(f"Assignment not found: {assignment_id}")
                raise ValidationException(
                    f"Assignment not found with ID: {assignment_id}"
                )

            update_dict = data.model_dump(exclude_none=True)
            if not update_dict:
                logger.warning(f"No update data provided for assignment: {assignment_id}")
                raise ValidationException("No update data provided")

            updated = self.assignment_repo.update(db, assignment, update_dict)
            
            logger.info(f"Successfully updated assignment: {assignment_id}")
            return SupervisorAssignment.model_validate(updated)
            
        except ValidationException:
            raise
        except Exception as e:
            logger.error(f"Failed to update assignment {assignment_id}: {str(e)}")
            raise ValidationException(f"Failed to update assignment: {str(e)}")

    def revoke_assignment(
        self,
        db: Session,
        assignment_id: UUID,
        data: RevokeAssignmentRequest,
    ) -> SupervisorAssignment:
        """
        Revoke a supervisor's assignment from a hostel.

        Sets is_active=False, records reason and revoke date, handles handover.

        Args:
            db: Database session
            assignment_id: UUID of the assignment to revoke
            data: Revocation details including reason and handover notes

        Returns:
            SupervisorAssignment: Revoked assignment object

        Raises:
            ValidationException: If assignment not found or already revoked

        Example:
            >>> revoke = RevokeAssignmentRequest(
            ...     reason="Transfer to another hostel",
            ...     handover_notes="All tasks completed"
            ... )
            >>> revoked = service.revoke_assignment(db, assignment_id, revoke)
        """
        if not db:
            raise ValidationException("Database session is required")
        
        if not assignment_id:
            raise ValidationException("Assignment ID is required")
        
        if not data:
            raise ValidationException("Revocation data is required")

        try:
            logger.info(f"Revoking assignment: {assignment_id}")
            
            assignment = self.assignment_repo.get_by_id(db, assignment_id)
            if not assignment:
                logger.warning(f"Assignment not found: {assignment_id}")
                raise ValidationException(
                    f"Assignment not found with ID: {assignment_id}"
                )
            
            if not assignment.is_active:
                logger.warning(f"Assignment already revoked: {assignment_id}")
                raise ValidationException(
                    f"Assignment is already inactive"
                )

            updated = self.assignment_repo.revoke_assignment(
                db,
                assignment,
                revoke_date=data.revoke_date,
                reason=data.reason,
                handover_notes=data.handover_notes,
            )
            
            logger.info(f"Successfully revoked assignment: {assignment_id}")
            return SupervisorAssignment.model_validate(updated)
            
        except ValidationException:
            raise
        except Exception as e:
            logger.error(f"Failed to revoke assignment {assignment_id}: {str(e)}")
            raise ValidationException(f"Failed to revoke assignment: {str(e)}")

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

        Wraps lower-level repository logic with validation.

        Args:
            db: Database session
            assignment_id: UUID of the assignment to transfer
            target_hostel_id: UUID of the destination hostel
            transfer_date: Optional transfer date (defaults to today)
            reason: Optional reason for transfer

        Returns:
            SupervisorAssignment: Transferred assignment object

        Raises:
            ValidationException: If assignment not found or transfer is invalid

        Example:
            >>> transferred = service.transfer_assignment(
            ...     db, assignment_id, new_hostel_id,
            ...     reason="Operational requirement"
            ... )
        """
        if not db:
            raise ValidationException("Database session is required")
        
        if not assignment_id:
            raise ValidationException("Assignment ID is required")
        
        if not target_hostel_id:
            raise ValidationException("Target hostel ID is required")

        try:
            logger.info(
                f"Transferring assignment {assignment_id} to hostel: {target_hostel_id}"
            )
            
            assignment = self.assignment_repo.get_by_id(db, assignment_id)
            if not assignment:
                logger.warning(f"Assignment not found: {assignment_id}")
                raise ValidationException(
                    f"Assignment not found with ID: {assignment_id}"
                )
            
            if assignment.hostel_id == target_hostel_id:
                raise ValidationException(
                    "Target hostel is the same as current hostel"
                )
            
            if not assignment.is_active:
                raise ValidationException(
                    "Cannot transfer an inactive assignment"
                )

            updated = self.assignment_repo.transfer(
                db,
                assignment,
                new_hostel_id=target_hostel_id,
                transfer_date=transfer_date,
                reason=reason,
            )
            
            logger.info(
                f"Successfully transferred assignment {assignment_id} "
                f"to hostel: {target_hostel_id}"
            )
            return SupervisorAssignment.model_validate(updated)
            
        except ValidationException:
            raise
        except Exception as e:
            logger.error(f"Failed to transfer assignment {assignment_id}: {str(e)}")
            raise ValidationException(f"Failed to transfer assignment: {str(e)}")

    # -------------------------------------------------------------------------
    # Listing Operations
    # -------------------------------------------------------------------------

    def list_assignments_for_supervisor(
        self,
        db: Session,
        supervisor_id: UUID,
        include_inactive: bool = False,
    ) -> List[SupervisorAssignment]:
        """
        List all assignments for a supervisor across hostels.

        Args:
            db: Database session
            supervisor_id: UUID of the supervisor
            include_inactive: Whether to include inactive assignments

        Returns:
            List[SupervisorAssignment]: List of assignments

        Raises:
            ValidationException: If parameters are invalid

        Example:
            >>> assignments = service.list_assignments_for_supervisor(
            ...     db, supervisor_id, include_inactive=True
            ... )
        """
        if not db:
            raise ValidationException("Database session is required")
        
        if not supervisor_id:
            raise ValidationException("Supervisor ID is required")

        try:
            logger.debug(
                f"Listing assignments for supervisor: {supervisor_id}, "
                f"include_inactive: {include_inactive}"
            )
            
            objs = self.assignment_repo.get_by_supervisor_id(
                db, supervisor_id, include_inactive=include_inactive
            )
            
            logger.debug(
                f"Found {len(objs)} assignments for supervisor: {supervisor_id}"
            )
            return [SupervisorAssignment.model_validate(o) for o in objs]
            
        except Exception as e:
            logger.error(
                f"Failed to list assignments for supervisor {supervisor_id}: {str(e)}"
            )
            raise ValidationException(
                f"Failed to list supervisor assignments: {str(e)}"
            )

    def list_assignments_for_hostel(
        self,
        db: Session,
        hostel_id: UUID,
        include_inactive: bool = False,
    ) -> List[SupervisorAssignment]:
        """
        List all supervisor assignments for a hostel.

        Args:
            db: Database session
            hostel_id: UUID of the hostel
            include_inactive: Whether to include inactive assignments

        Returns:
            List[SupervisorAssignment]: List of assignments

        Raises:
            ValidationException: If parameters are invalid

        Example:
            >>> assignments = service.list_assignments_for_hostel(
            ...     db, hostel_id, include_inactive=False
            ... )
        """
        if not db:
            raise ValidationException("Database session is required")
        
        if not hostel_id:
            raise ValidationException("Hostel ID is required")

        try:
            logger.debug(
                f"Listing assignments for hostel: {hostel_id}, "
                f"include_inactive: {include_inactive}"
            )
            
            objs = self.assignment_repo.get_by_hostel_id(
                db, hostel_id, include_inactive=include_inactive
            )
            
            logger.debug(f"Found {len(objs)} assignments for hostel: {hostel_id}")
            return [SupervisorAssignment.model_validate(o) for o in objs]
            
        except Exception as e:
            logger.error(
                f"Failed to list assignments for hostel {hostel_id}: {str(e)}"
            )
            raise ValidationException(
                f"Failed to list hostel assignments: {str(e)}"
            )

    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------

    def _check_active_assignment(
        self,
        db: Session,
        supervisor_id: UUID,
        hostel_id: UUID,
    ) -> bool:
        """
        Check if an active assignment already exists for supervisor-hostel pair.

        Args:
            db: Database session
            supervisor_id: UUID of the supervisor
            hostel_id: UUID of the hostel

        Returns:
            bool: True if active assignment exists, False otherwise
        """
        try:
            assignments = self.assignment_repo.get_by_supervisor_id(
                db, supervisor_id, include_inactive=False
            )
            return any(a.hostel_id == hostel_id for a in assignments)
        except Exception:
            return False

    def get_active_assignment(
        self,
        db: Session,
        supervisor_id: UUID,
        hostel_id: UUID,
    ) -> Optional[SupervisorAssignment]:
        """
        Get the active assignment for a supervisor-hostel pair.

        Args:
            db: Database session
            supervisor_id: UUID of the supervisor
            hostel_id: UUID of the hostel

        Returns:
            Optional[SupervisorAssignment]: Active assignment if exists, None otherwise
        """
        if not db or not supervisor_id or not hostel_id:
            return None
        
        try:
            assignments = self.assignment_repo.get_by_supervisor_id(
                db, supervisor_id, include_inactive=False
            )
            for assignment in assignments:
                if assignment.hostel_id == hostel_id:
                    return SupervisorAssignment.model_validate(assignment)
            return None
        except Exception:
            return None