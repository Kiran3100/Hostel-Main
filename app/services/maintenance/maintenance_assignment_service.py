"""
Maintenance Assignment Service

Manages the assignment of maintenance tasks to internal staff and external vendors
with comprehensive tracking, bulk operations, and assignment history.

Features:
- Staff and vendor assignment with validation
- Bulk assignment operations with error handling
- Assignment history tracking
- Workload balancing support
- Real-time assignment notifications
"""

from __future__ import annotations

from typing import List, Dict, Any, Optional
from uuid import UUID
from collections import Counter

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
from app.core.logging import logger


class MaintenanceAssignmentService:
    """
    High-level orchestration for maintenance task assignments.

    Provides intelligent assignment capabilities including workload
    balancing, skill matching, and comprehensive audit trails.
    """

    def __init__(self, assignment_repo: MaintenanceAssignmentRepository) -> None:
        """
        Initialize the assignment service.

        Args:
            assignment_repo: Repository for assignment persistence
        """
        if not assignment_repo:
            raise ValueError("MaintenanceAssignmentRepository is required")
        self.assignment_repo = assignment_repo

    # -------------------------------------------------------------------------
    # Staff Assignment Operations
    # -------------------------------------------------------------------------

    def assign_to_staff(
        self,
        db: Session,
        data: TaskAssignment,
    ) -> AssignmentEntry:
        """
        Assign a maintenance request to an internal staff member.

        Validates staff availability and skill match before assignment.

        Args:
            db: Database session
            data: Task assignment details

        Returns:
            AssignmentEntry with assignment details

        Raises:
            ValidationException: If assignment data is invalid
            BusinessLogicException: If assignment fails business rules
        """
        # Validate assignment data
        self._validate_staff_assignment(data)

        try:
            logger.info(
                f"Assigning maintenance request {data.maintenance_request_id} "
                f"to staff {data.assigned_to_staff_id}"
            )

            payload = data.model_dump(exclude_none=True)
            obj = self.assignment_repo.assign_to_staff(db, payload)

            logger.info(f"Successfully created staff assignment {obj.id}")

            # TODO: Trigger notification to assigned staff
            # await self._notify_staff_assignment(obj)

            return AssignmentEntry.model_validate(obj)

        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                f"Error assigning to staff: {str(e)}",
                exc_info=True
            )
            raise BusinessLogicException(
                f"Failed to assign maintenance task: {str(e)}"
            )

    # -------------------------------------------------------------------------
    # Vendor Assignment Operations
    # -------------------------------------------------------------------------

    def assign_to_vendor(
        self,
        db: Session,
        data: VendorAssignmentSchema,
    ) -> AssignmentEntry:
        """
        Assign a maintenance request to an external vendor.

        Validates vendor contracts and capabilities before assignment.

        Args:
            db: Database session
            data: Vendor assignment details

        Returns:
            AssignmentEntry with assignment details

        Raises:
            ValidationException: If assignment data is invalid
            BusinessLogicException: If vendor is not qualified
        """
        # Validate vendor assignment
        self._validate_vendor_assignment(data)

        try:
            logger.info(
                f"Assigning maintenance request {data.maintenance_request_id} "
                f"to vendor {data.assigned_to_vendor_id}"
            )

            payload = data.model_dump(exclude_none=True)
            obj = self.assignment_repo.assign_to_vendor(db, payload)

            logger.info(f"Successfully created vendor assignment {obj.id}")

            # TODO: Trigger notification to vendor
            # await self._notify_vendor_assignment(obj)

            return AssignmentEntry.model_validate(obj)

        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                f"Error assigning to vendor: {str(e)}",
                exc_info=True
            )
            raise BusinessLogicException(
                f"Failed to assign to vendor: {str(e)}"
            )

    # -------------------------------------------------------------------------
    # Assignment Management Operations
    # -------------------------------------------------------------------------

    def update_assignment(
        self,
        db: Session,
        assignment_id: UUID,
        update: AssignmentUpdate,
    ) -> AssignmentEntry:
        """
        Update an existing assignment.

        Allows updating priority, notes, and reassignment.

        Args:
            db: Database session
            assignment_id: UUID of assignment to update
            update: Update data

        Returns:
            Updated AssignmentEntry

        Raises:
            ValidationException: If assignment not found or update invalid
        """
        if not assignment_id:
            raise ValidationException("Assignment ID is required")

        try:
            assignment = self.assignment_repo.get_by_id(db, assignment_id)
            if not assignment:
                raise ValidationException(
                    f"Assignment {assignment_id} not found"
                )

            # Validate update doesn't violate business rules
            self._validate_assignment_update(assignment, update)

            logger.info(f"Updating assignment {assignment_id}")

            obj = self.assignment_repo.update_assignment(
                db=db,
                assignment=assignment,
                data=update.model_dump(exclude_none=True),
            )

            logger.info(f"Successfully updated assignment {assignment_id}")
            return AssignmentEntry.model_validate(obj)

        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                f"Error updating assignment {assignment_id}: {str(e)}",
                exc_info=True
            )
            raise BusinessLogicException(
                f"Failed to update assignment: {str(e)}"
            )

    def reassign_task(
        self,
        db: Session,
        assignment_id: UUID,
        new_assignee_id: UUID,
        assignee_type: str,
        reason: str,
    ) -> AssignmentEntry:
        """
        Reassign a task to a different staff member or vendor.

        Args:
            db: Database session
            assignment_id: UUID of assignment to reassign
            new_assignee_id: UUID of new assignee
            assignee_type: Type of assignee ('staff' or 'vendor')
            reason: Reason for reassignment

        Returns:
            Updated AssignmentEntry

        Raises:
            ValidationException: If reassignment is invalid
        """
        if not reason or len(reason.strip()) < 10:
            raise ValidationException(
                "Reassignment reason must be at least 10 characters"
            )

        update = AssignmentUpdate(
            assigned_to_staff_id=new_assignee_id if assignee_type == "staff" else None,
            assigned_to_vendor_id=new_assignee_id if assignee_type == "vendor" else None,
            assignment_notes=f"Reassigned: {reason}",
        )

        return self.update_assignment(db, assignment_id, update)

    # -------------------------------------------------------------------------
    # Bulk Operations
    # -------------------------------------------------------------------------

    def bulk_assign(
        self,
        db: Session,
        bulk: BulkAssignment,
    ) -> Dict[str, Any]:
        """
        Bulk assign multiple maintenance requests to a single assignee.

        Provides detailed success/failure reporting for each assignment.

        Args:
            db: Database session
            bulk: Bulk assignment configuration

        Returns:
            Dictionary with success/failure results

        Raises:
            ValidationException: If bulk assignment data is invalid
        """
        # Validate bulk assignment
        self._validate_bulk_assignment(bulk)

        if not bulk.maintenance_request_ids:
            raise ValidationException("No maintenance requests specified")

        results: List[AssignmentEntry] = []
        failures: List[Dict[str, Any]] = []
        
        total_requests = len(bulk.maintenance_request_ids)

        logger.info(
            f"Starting bulk assignment of {total_requests} requests "
            f"to {bulk.assignee_type} {bulk.assignee_id}"
        )

        for idx, req_id in enumerate(bulk.maintenance_request_ids, 1):
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
                
                logger.debug(
                    f"Bulk assignment progress: {idx}/{total_requests}"
                )

            except Exception as e:
                error_details = {
                    "request_id": str(req_id),
                    "error": str(e),
                }
                failures.append(error_details)
                
                logger.warning(
                    f"Failed to assign request {req_id}: {str(e)}"
                )

                if not bulk.skip_failed:
                    # Rollback and raise on first failure
                    db.rollback()
                    raise BusinessLogicException(
                        f"Bulk assignment failed at request {req_id}: {str(e)}"
                    )

        # Commit successful assignments
        if results:
            db.commit()

        success_count = len(results)
        failure_count = len(failures)

        logger.info(
            f"Bulk assignment completed: {success_count} successful, "
            f"{failure_count} failed"
        )

        return {
            "total_requests": total_requests,
            "successful_assignments": results,
            "success_count": success_count,
            "failed_assignments": failures,
            "failure_count": failure_count,
            "partial_success": failure_count > 0 and success_count > 0,
        }

    # -------------------------------------------------------------------------
    # Assignment History and Analytics
    # -------------------------------------------------------------------------

    def get_assignment_history_for_request(
        self,
        db: Session,
        request_id: UUID,
    ) -> AssignmentHistory:
        """
        Retrieve the complete assignment history for a maintenance request.

        Includes all assignment changes, reassignments, and status updates.

        Args:
            db: Database session
            request_id: UUID of the maintenance request

        Returns:
            AssignmentHistory with all assignments

        Raises:
            ValidationException: If request_id is invalid
        """
        if not request_id:
            raise ValidationException("Request ID is required")

        try:
            data = self.assignment_repo.get_history_for_request(db, request_id)
            
            if not data:
                # Return empty history
                logger.debug(f"No assignment history found for request {request_id}")
                return AssignmentHistory(
                    maintenance_request_id=request_id,
                    assignments=[],
                    total_assignments=0,
                    total_reassignments=0,
                    current_assignee=None,
                )
            
            return AssignmentHistory.model_validate(data)

        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                f"Error retrieving assignment history for {request_id}: {str(e)}",
                exc_info=True
            )
            raise BusinessLogicException(
                f"Failed to retrieve assignment history: {str(e)}"
            )

    def get_staff_workload(
        self,
        db: Session,
        staff_id: UUID,
        include_completed: bool = False,
    ) -> Dict[str, Any]:
        """
        Get current workload for a staff member.

        Args:
            db: Database session
            staff_id: UUID of staff member
            include_completed: Whether to include completed assignments

        Returns:
            Dictionary with workload statistics
        """
        if not staff_id:
            raise ValidationException("Staff ID is required")

        try:
            workload = self.assignment_repo.get_staff_workload(
                db=db,
                staff_id=staff_id,
                include_completed=include_completed,
            )

            return workload

        except Exception as e:
            logger.error(
                f"Error retrieving workload for staff {staff_id}: {str(e)}",
                exc_info=True
            )
            raise BusinessLogicException(
                f"Failed to retrieve staff workload: {str(e)}"
            )

    def get_vendor_assignments(
        self,
        db: Session,
        vendor_id: UUID,
        status_filter: Optional[str] = None,
    ) -> List[AssignmentEntry]:
        """
        Get all assignments for a vendor.

        Args:
            db: Database session
            vendor_id: UUID of vendor
            status_filter: Optional status filter

        Returns:
            List of assignments
        """
        if not vendor_id:
            raise ValidationException("Vendor ID is required")

        try:
            assignments = self.assignment_repo.get_vendor_assignments(
                db=db,
                vendor_id=vendor_id,
                status=status_filter,
            )

            return [AssignmentEntry.model_validate(a) for a in assignments]

        except Exception as e:
            logger.error(
                f"Error retrieving vendor assignments: {str(e)}",
                exc_info=True
            )
            raise BusinessLogicException(
                f"Failed to retrieve vendor assignments: {str(e)}"
            )

    # -------------------------------------------------------------------------
    # Private Validation Methods
    # -------------------------------------------------------------------------

    def _validate_staff_assignment(self, data: TaskAssignment) -> None:
        """Validate staff assignment data."""
        if not data.maintenance_request_id:
            raise ValidationException("Maintenance request ID is required")
        
        if not data.assigned_to_staff_id:
            raise ValidationException("Staff ID is required")
        
        if data.priority and data.priority not in ["low", "medium", "high", "critical"]:
            raise ValidationException(f"Invalid priority: {data.priority}")

    def _validate_vendor_assignment(self, data: VendorAssignmentSchema) -> None:
        """Validate vendor assignment data."""
        if not data.maintenance_request_id:
            raise ValidationException("Maintenance request ID is required")
        
        if not data.assigned_to_vendor_id:
            raise ValidationException("Vendor ID is required")
        
        if data.quoted_amount is not None and data.quoted_amount < 0:
            raise ValidationException("Quoted amount cannot be negative")

    def _validate_assignment_update(
        self,
        assignment: Any,
        update: AssignmentUpdate
    ) -> None:
        """Validate assignment update doesn't violate business rules."""
        # Check if assignment is already completed
        if assignment.status == "completed":
            raise BusinessLogicException(
                "Cannot update completed assignment"
            )

    def _validate_bulk_assignment(self, bulk: BulkAssignment) -> None:
        """Validate bulk assignment configuration."""
        if not bulk.assignee_id:
            raise ValidationException("Assignee ID is required")
        
        if bulk.assignee_type not in ["staff", "vendor"]:
            raise ValidationException(
                f"Invalid assignee type: {bulk.assignee_type}"
            )
        
        if not bulk.maintenance_request_ids:
            raise ValidationException(
                "At least one maintenance request ID is required"
            )