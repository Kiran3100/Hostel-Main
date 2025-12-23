"""
Complaint assignment service: assign/reassign/unassign/bulk operations and history.

Manages the assignment lifecycle of complaints to staff members including
bulk operations and comprehensive audit history.
"""

from typing import Optional, Dict, Any, List
from uuid import UUID
import logging

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.services.base import BaseService, ServiceResult, ServiceError, ErrorCode, ErrorSeverity
from app.repositories.complaint.complaint_assignment_repository import ComplaintAssignmentRepository
from app.models.complaint.complaint_assignment import ComplaintAssignment as ComplaintAssignmentModel
from app.schemas.complaint.complaint_assignment import (
    AssignmentRequest,
    AssignmentResponse,
    ReassignmentRequest,
    BulkAssignment,
    UnassignRequest,
    AssignmentHistory,
)

logger = logging.getLogger(__name__)


class ComplaintAssignmentService(BaseService[ComplaintAssignmentModel, ComplaintAssignmentRepository]):
    """
    Business logic for complaint assignments and history tracking.
    
    Handles single and bulk assignment operations with comprehensive
    validation and audit trails.
    """

    def __init__(self, repository: ComplaintAssignmentRepository, db_session: Session):
        """
        Initialize assignment service.
        
        Args:
            repository: Complaint assignment repository instance
            db_session: Active database session
        """
        super().__init__(repository, db_session)
        self._logger = logger

    # -------------------------------------------------------------------------
    # Assignment Operations
    # -------------------------------------------------------------------------

    def assign(
        self,
        request: AssignmentRequest,
        assigned_by: Optional[UUID] = None,
    ) -> ServiceResult[AssignmentResponse]:
        """
        Assign a complaint to a staff member.
        
        Args:
            request: Assignment request data
            assigned_by: UUID of user performing the assignment
            
        Returns:
            ServiceResult containing AssignmentResponse or error
        """
        try:
            self._logger.info(
                f"Assigning complaint {request.complaint_id} to {request.assigned_to}, "
                f"assigned_by: {assigned_by}"
            )
            
            # Validate assignment request
            validation_result = self._validate_assignment(request)
            if not validation_result.success:
                return validation_result
            
            # Perform assignment
            response = self.repository.assign(request, assigned_by=assigned_by)
            
            # Commit transaction
            self.db.commit()
            
            self._logger.info(
                f"Complaint {request.complaint_id} assigned successfully to {request.assigned_to}"
            )
            
            return ServiceResult.success(
                response,
                message="Complaint assigned successfully",
                metadata={
                    "complaint_id": str(request.complaint_id),
                    "assigned_to": str(request.assigned_to),
                }
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            self._logger.error(
                f"Database error assigning complaint {request.complaint_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "assign complaint", request.complaint_id)
            
        except Exception as e:
            self.db.rollback()
            self._logger.error(
                f"Unexpected error assigning complaint {request.complaint_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "assign complaint", request.complaint_id)

    def reassign(
        self,
        request: ReassignmentRequest,
    ) -> ServiceResult[AssignmentResponse]:
        """
        Reassign a complaint from one staff member to another.
        
        Args:
            request: Reassignment request data
            
        Returns:
            ServiceResult containing AssignmentResponse or error
        """
        try:
            self._logger.info(
                f"Reassigning complaint {request.complaint_id} to {request.new_assigned_to}"
            )
            
            # Validate reassignment request
            validation_result = self._validate_reassignment(request)
            if not validation_result.success:
                return validation_result
            
            # Perform reassignment
            response = self.repository.reassign(request)
            
            # Commit transaction
            self.db.commit()
            
            self._logger.info(
                f"Complaint {request.complaint_id} reassigned successfully to {request.new_assigned_to}"
            )
            
            return ServiceResult.success(
                response,
                message="Complaint reassigned successfully",
                metadata={
                    "complaint_id": str(request.complaint_id),
                    "new_assigned_to": str(request.new_assigned_to),
                }
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            self._logger.error(
                f"Database error reassigning complaint {request.complaint_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "reassign complaint", request.complaint_id)
            
        except Exception as e:
            self.db.rollback()
            self._logger.error(
                f"Unexpected error reassigning complaint {request.complaint_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "reassign complaint", request.complaint_id)

    def unassign(
        self,
        request: UnassignRequest,
    ) -> ServiceResult[bool]:
        """
        Unassign a complaint from its current assignee.
        
        Args:
            request: Unassignment request data
            
        Returns:
            ServiceResult containing success boolean or error
        """
        try:
            self._logger.info(f"Unassigning complaint {request.complaint_id}")
            
            # Validate unassignment request
            validation_result = self._validate_unassignment(request)
            if not validation_result.success:
                return validation_result
            
            # Perform unassignment
            success = self.repository.unassign(request)
            
            # Commit transaction
            self.db.commit()
            
            if success:
                self._logger.info(f"Complaint {request.complaint_id} unassigned successfully")
                return ServiceResult.success(
                    True,
                    message="Complaint unassigned successfully",
                    metadata={"complaint_id": str(request.complaint_id)}
                )
            else:
                self._logger.warning(f"Failed to unassign complaint {request.complaint_id}")
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.OPERATION_FAILED,
                        message="Failed to unassign complaint",
                        severity=ErrorSeverity.ERROR,
                    )
                )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            self._logger.error(
                f"Database error unassigning complaint {request.complaint_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "unassign complaint", request.complaint_id)
            
        except Exception as e:
            self.db.rollback()
            self._logger.error(
                f"Unexpected error unassigning complaint {request.complaint_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "unassign complaint", request.complaint_id)

    def bulk_assign(
        self,
        request: BulkAssignment,
        assigned_by: Optional[UUID] = None,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Assign multiple complaints in a single operation.
        
        Args:
            request: Bulk assignment request data
            assigned_by: UUID of user performing the bulk assignment
            
        Returns:
            ServiceResult containing summary dictionary or error
        """
        try:
            complaint_count = len(request.complaint_ids)
            self._logger.info(
                f"Bulk assigning {complaint_count} complaints to {request.assigned_to}, "
                f"assigned_by: {assigned_by}"
            )
            
            # Validate bulk assignment
            validation_result = self._validate_bulk_assignment(request)
            if not validation_result.success:
                return validation_result
            
            # Perform bulk assignment
            summary = self.repository.bulk_assign(request, assigned_by=assigned_by)
            
            # Commit transaction
            self.db.commit()
            
            success_count = summary.get("success_count", 0)
            failed_count = summary.get("failed_count", 0)
            
            self._logger.info(
                f"Bulk assignment completed: {success_count} successful, {failed_count} failed"
            )
            
            return ServiceResult.success(
                summary,
                message=f"Bulk assignment completed: {success_count} successful, {failed_count} failed",
                metadata={
                    "total_requested": complaint_count,
                    "success_count": success_count,
                    "failed_count": failed_count,
                }
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            self._logger.error(f"Database error in bulk assignment: {str(e)}", exc_info=True)
            return self._handle_exception(e, "bulk assign complaints")
            
        except Exception as e:
            self.db.rollback()
            self._logger.error(f"Unexpected error in bulk assignment: {str(e)}", exc_info=True)
            return self._handle_exception(e, "bulk assign complaints")

    # -------------------------------------------------------------------------
    # History Operations
    # -------------------------------------------------------------------------

    def history(
        self,
        complaint_id: UUID,
        limit: int = 50,
    ) -> ServiceResult[List[AssignmentHistory]]:
        """
        Retrieve assignment history for a complaint.
        
        Args:
            complaint_id: UUID of complaint
            limit: Maximum number of history entries to return
            
        Returns:
            ServiceResult containing list of AssignmentHistory or error
        """
        try:
            # Validate limit
            if limit < 1 or limit > 500:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Limit must be between 1 and 500",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            self._logger.debug(
                f"Fetching assignment history for complaint {complaint_id}, limit: {limit}"
            )
            
            items = self.repository.get_history(complaint_id, limit=limit)
            
            self._logger.debug(f"Retrieved {len(items)} assignment history entries")
            
            return ServiceResult.success(
                items,
                metadata={
                    "count": len(items),
                    "complaint_id": str(complaint_id),
                    "limit": limit,
                }
            )
            
        except SQLAlchemyError as e:
            self._logger.error(
                f"Database error fetching assignment history for {complaint_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "get assignment history", complaint_id)
            
        except Exception as e:
            self._logger.error(
                f"Unexpected error fetching assignment history for {complaint_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "get assignment history", complaint_id)

    # -------------------------------------------------------------------------
    # Validation Helpers
    # -------------------------------------------------------------------------

    def _validate_assignment(
        self,
        request: AssignmentRequest
    ) -> ServiceResult[None]:
        """
        Validate assignment request.
        
        Args:
            request: Assignment request to validate
            
        Returns:
            ServiceResult indicating validation success or failure
        """
        # Add custom validation logic
        # For example: check if assignee is valid staff member, check complaint status, etc.
        
        if not request.complaint_id:
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Complaint ID is required",
                    severity=ErrorSeverity.WARNING,
                )
            )
        
        if not request.assigned_to:
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Assignee ID is required",
                    severity=ErrorSeverity.WARNING,
                )
            )
        
        return ServiceResult.success(None)

    def _validate_reassignment(
        self,
        request: ReassignmentRequest
    ) -> ServiceResult[None]:
        """
        Validate reassignment request.
        
        Args:
            request: Reassignment request to validate
            
        Returns:
            ServiceResult indicating validation success or failure
        """
        if not request.new_assigned_to:
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="New assignee ID is required",
                    severity=ErrorSeverity.WARNING,
                )
            )
        
        return ServiceResult.success(None)

    def _validate_unassignment(
        self,
        request: UnassignRequest
    ) -> ServiceResult[None]:
        """
        Validate unassignment request.
        
        Args:
            request: Unassignment request to validate
            
        Returns:
            ServiceResult indicating validation success or failure
        """
        if not request.complaint_id:
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Complaint ID is required",
                    severity=ErrorSeverity.WARNING,
                )
            )
        
        return ServiceResult.success(None)

    def _validate_bulk_assignment(
        self,
        request: BulkAssignment
    ) -> ServiceResult[None]:
        """
        Validate bulk assignment request.
        
        Args:
            request: Bulk assignment request to validate
            
        Returns:
            ServiceResult indicating validation success or failure
        """
        if not request.complaint_ids or len(request.complaint_ids) == 0:
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="At least one complaint ID is required",
                    severity=ErrorSeverity.WARNING,
                )
            )
        
        if len(request.complaint_ids) > 100:
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Cannot bulk assign more than 100 complaints at once",
                    severity=ErrorSeverity.WARNING,
                )
            )
        
        if not request.assigned_to:
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Assignee ID is required",
                    severity=ErrorSeverity.WARNING,
                )
            )
        
        return ServiceResult.success(None)