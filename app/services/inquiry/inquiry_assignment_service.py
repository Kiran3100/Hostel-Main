"""
Inquiry assignment service: assign/transfer/unassign ownership.

Enhanced with:
- Assignment history tracking
- Workload balancing hints
- Assignment validation
- Comprehensive audit logging
"""

from typing import Optional, Dict, Any, List
from uuid import UUID
import logging
from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.services.base import (
    BaseService,
    ServiceResult,
    ServiceError,
    ErrorCode,
    ErrorSeverity,
)
from app.repositories.inquiry.inquiry_repository import InquiryRepository
from app.models.inquiry.inquiry import Inquiry as InquiryModel
from app.schemas.inquiry.inquiry_status import InquiryAssignment

logger = logging.getLogger(__name__)


class InquiryAssignmentService(BaseService[InquiryModel, InquiryRepository]):
    """
    Manage inquiry assignment lifecycle.
    
    Handles:
    - Assignment to staff/admins
    - Transfer between users
    - Unassignment and reassignment
    - Assignment validation and history
    """

    def __init__(self, repository: InquiryRepository, db_session: Session):
        """
        Initialize assignment service.
        
        Args:
            repository: InquiryRepository for data access
            db_session: SQLAlchemy database session
        """
        super().__init__(repository, db_session)
        self._logger = logger

    # =========================================================================
    # ASSIGNMENT OPERATIONS
    # =========================================================================

    def assign(
        self,
        request: InquiryAssignment,
        assigned_by: Optional[UUID] = None,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Assign an inquiry to a staff member or admin.
        
        Args:
            request: InquiryAssignment with inquiry_id and assignee_id
            assigned_by: UUID of user performing the assignment
            
        Returns:
            ServiceResult with assignment details and metadata
        """
        try:
            self._logger.info(
                f"Assigning inquiry {request.inquiry_id} to user {request.assignee_id}"
            )
            
            # Validate assignment request
            validation_error = self._validate_assignment(request)
            if validation_error:
                return ServiceResult.failure(validation_error)
            
            # Check if inquiry exists
            inquiry = self.repository.get_by_id(request.inquiry_id)
            if not inquiry:
                self._logger.warning(f"Inquiry {request.inquiry_id} not found for assignment")
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message=f"Inquiry with ID {request.inquiry_id} not found",
                        severity=ErrorSeverity.ERROR,
                    )
                )
            
            # Check if already assigned
            previous_assignee = None
            if hasattr(inquiry, 'assigned_to') and inquiry.assigned_to:
                previous_assignee = inquiry.assigned_to
                self._logger.info(
                    f"Inquiry {request.inquiry_id} already assigned to {previous_assignee}, "
                    f"reassigning to {request.assignee_id}"
                )
            
            # Perform assignment
            success = self.repository.assign(request, assigned_by=assigned_by)
            
            if not success:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.OPERATION_FAILED,
                        message="Assignment operation failed",
                        severity=ErrorSeverity.ERROR,
                    )
                )
            
            # Commit transaction
            self.db.commit()
            
            self._logger.info(f"Successfully assigned inquiry {request.inquiry_id}")
            
            return ServiceResult.success(
                {
                    "inquiry_id": str(request.inquiry_id),
                    "assignee_id": str(request.assignee_id),
                    "assigned_by": str(assigned_by) if assigned_by else None,
                    "assigned_at": datetime.utcnow().isoformat(),
                    "previous_assignee": str(previous_assignee) if previous_assignee else None,
                    "is_reassignment": previous_assignee is not None,
                },
                message="Inquiry assigned successfully",
                metadata={
                    "action": "reassignment" if previous_assignee else "assignment",
                }
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            self._logger.error(f"Database error assigning inquiry {request.inquiry_id}: {str(e)}")
            return self._handle_exception(e, "assign inquiry", request.inquiry_id)
        except Exception as e:
            self.db.rollback()
            self._logger.exception(f"Unexpected error assigning inquiry {request.inquiry_id}: {str(e)}")
            return self._handle_exception(e, "assign inquiry", request.inquiry_id)

    def unassign(
        self,
        inquiry_id: UUID,
        reason: Optional[str] = None,
        unassigned_by: Optional[UUID] = None,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Unassign an inquiry (clear ownership).
        
        Args:
            inquiry_id: UUID of inquiry to unassign
            reason: Optional reason for unassignment
            unassigned_by: UUID of user performing unassignment
            
        Returns:
            ServiceResult with unassignment details
        """
        try:
            self._logger.info(f"Unassigning inquiry {inquiry_id}, reason: {reason or 'N/A'}")
            
            # Check if inquiry exists and is assigned
            inquiry = self.repository.get_by_id(inquiry_id)
            if not inquiry:
                self._logger.warning(f"Inquiry {inquiry_id} not found for unassignment")
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message=f"Inquiry with ID {inquiry_id} not found",
                        severity=ErrorSeverity.ERROR,
                    )
                )
            
            previous_assignee = None
            if hasattr(inquiry, 'assigned_to'):
                previous_assignee = inquiry.assigned_to
                
            if not previous_assignee:
                self._logger.warning(f"Inquiry {inquiry_id} is not currently assigned")
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Inquiry is not currently assigned",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            # Perform unassignment
            success = self.repository.unassign(
                inquiry_id,
                reason=reason,
                unassigned_by=unassigned_by
            )
            
            if not success:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.OPERATION_FAILED,
                        message="Unassignment operation failed",
                        severity=ErrorSeverity.ERROR,
                    )
                )
            
            # Commit transaction
            self.db.commit()
            
            self._logger.info(f"Successfully unassigned inquiry {inquiry_id}")
            
            return ServiceResult.success(
                {
                    "inquiry_id": str(inquiry_id),
                    "previous_assignee": str(previous_assignee),
                    "unassigned_by": str(unassigned_by) if unassigned_by else None,
                    "unassigned_at": datetime.utcnow().isoformat(),
                    "reason": reason,
                },
                message="Inquiry unassigned successfully"
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            self._logger.error(f"Database error unassigning inquiry {inquiry_id}: {str(e)}")
            return self._handle_exception(e, "unassign inquiry", inquiry_id)
        except Exception as e:
            self.db.rollback()
            self._logger.exception(f"Unexpected error unassigning inquiry {inquiry_id}: {str(e)}")
            return self._handle_exception(e, "unassign inquiry", inquiry_id)

    def transfer(
        self,
        inquiry_id: UUID,
        from_user: UUID,
        to_user: UUID,
        reason: Optional[str] = None,
        transferred_by: Optional[UUID] = None,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Transfer an inquiry from one user to another.
        
        Args:
            inquiry_id: UUID of inquiry to transfer
            from_user: UUID of current assignee
            to_user: UUID of new assignee
            reason: Optional reason for transfer
            transferred_by: UUID of user performing transfer
            
        Returns:
            ServiceResult with transfer details
        """
        try:
            self._logger.info(
                f"Transferring inquiry {inquiry_id} from {from_user} to {to_user}"
            )
            
            # Validate transfer
            if from_user == to_user:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Cannot transfer inquiry to the same user",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            # Verify current assignment
            inquiry = self.repository.get_by_id(inquiry_id)
            if not inquiry:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message=f"Inquiry with ID {inquiry_id} not found",
                        severity=ErrorSeverity.ERROR,
                    )
                )
            
            current_assignee = getattr(inquiry, 'assigned_to', None)
            if current_assignee != from_user:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message=f"Inquiry is not currently assigned to user {from_user}",
                        severity=ErrorSeverity.ERROR,
                    )
                )
            
            # Perform transfer via reassignment
            assignment_request = InquiryAssignment(
                inquiry_id=inquiry_id,
                assignee_id=to_user,
            )
            
            success = self.repository.assign(assignment_request, assigned_by=transferred_by)
            
            if not success:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.OPERATION_FAILED,
                        message="Transfer operation failed",
                        severity=ErrorSeverity.ERROR,
                    )
                )
            
            # Commit transaction
            self.db.commit()
            
            self._logger.info(f"Successfully transferred inquiry {inquiry_id}")
            
            return ServiceResult.success(
                {
                    "inquiry_id": str(inquiry_id),
                    "from_user": str(from_user),
                    "to_user": str(to_user),
                    "transferred_by": str(transferred_by) if transferred_by else None,
                    "transferred_at": datetime.utcnow().isoformat(),
                    "reason": reason,
                },
                message="Inquiry transferred successfully",
                metadata={"action": "transfer"}
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            self._logger.error(f"Database error transferring inquiry {inquiry_id}: {str(e)}")
            return self._handle_exception(e, "transfer inquiry", inquiry_id)
        except Exception as e:
            self.db.rollback()
            self._logger.exception(f"Unexpected error transferring inquiry {inquiry_id}: {str(e)}")
            return self._handle_exception(e, "transfer inquiry", inquiry_id)

    # =========================================================================
    # QUERY OPERATIONS
    # =========================================================================

    def get_assigned_inquiries(
        self,
        assignee_id: UUID,
        status_filter: Optional[List[str]] = None,
        limit: int = 50,
    ) -> ServiceResult[List[Dict[str, Any]]]:
        """
        Get all inquiries assigned to a specific user.
        
        Args:
            assignee_id: UUID of assignee
            status_filter: Optional list of statuses to filter by
            limit: Maximum number of results (default 50, max 100)
            
        Returns:
            ServiceResult containing list of assigned inquiries
        """
        try:
            limit = min(max(1, limit), 100)  # Cap between 1-100
            
            self._logger.debug(f"Fetching assigned inquiries for user {assignee_id}")
            
            # Use repository method if available, otherwise query directly
            if hasattr(self.repository, 'get_assigned_inquiries'):
                inquiries = self.repository.get_assigned_inquiries(
                    assignee_id,
                    status_filter=status_filter,
                    limit=limit
                )
            else:
                # Fallback implementation
                query = self.db.query(InquiryModel).filter(
                    InquiryModel.assigned_to == assignee_id
                )
                if status_filter:
                    query = query.filter(InquiryModel.status.in_(status_filter))
                inquiries = query.limit(limit).all()
            
            result = [
                {
                    "inquiry_id": str(inq.id),
                    "status": getattr(inq, 'status', None),
                    "assigned_at": getattr(inq, 'assigned_at', None),
                    "guest_name": getattr(inq, 'guest_name', None),
                }
                for inq in inquiries
            ]
            
            return ServiceResult.success(
                result,
                metadata={
                    "assignee_id": str(assignee_id),
                    "count": len(result),
                    "status_filter": status_filter,
                }
            )
            
        except SQLAlchemyError as e:
            self._logger.error(f"Database error fetching assigned inquiries: {str(e)}")
            return self._handle_exception(e, "get assigned inquiries")
        except Exception as e:
            self._logger.exception(f"Unexpected error fetching assigned inquiries: {str(e)}")
            return self._handle_exception(e, "get assigned inquiries")

    def get_assignment_history(
        self,
        inquiry_id: UUID,
        limit: int = 20,
    ) -> ServiceResult[List[Dict[str, Any]]]:
        """
        Get assignment history for an inquiry.
        
        Args:
            inquiry_id: UUID of inquiry
            limit: Maximum number of history entries
            
        Returns:
            ServiceResult containing assignment history timeline
        """
        try:
            self._logger.debug(f"Fetching assignment history for inquiry {inquiry_id}")
            
            # Check if repository has dedicated method
            if hasattr(self.repository, 'get_assignment_history'):
                history = self.repository.get_assignment_history(inquiry_id, limit=limit)
            else:
                # Return empty history if not implemented
                history = []
            
            return ServiceResult.success(
                history,
                metadata={
                    "inquiry_id": str(inquiry_id),
                    "count": len(history),
                }
            )
            
        except SQLAlchemyError as e:
            self._logger.error(f"Database error fetching assignment history: {str(e)}")
            return self._handle_exception(e, "get assignment history", inquiry_id)
        except Exception as e:
            self._logger.exception(f"Unexpected error fetching assignment history: {str(e)}")
            return self._handle_exception(e, "get assignment history", inquiry_id)

    # =========================================================================
    # VALIDATION & UTILITIES
    # =========================================================================

    def _validate_assignment(self, request: InquiryAssignment) -> Optional[ServiceError]:
        """
        Validate assignment request.
        
        Args:
            request: Assignment request to validate
            
        Returns:
            ServiceError if invalid, None if valid
        """
        if not request.inquiry_id:
            return ServiceError(
                code=ErrorCode.VALIDATION_ERROR,
                message="Inquiry ID is required for assignment",
                severity=ErrorSeverity.ERROR,
            )
        
        if not request.assignee_id:
            return ServiceError(
                code=ErrorCode.VALIDATION_ERROR,
                message="Assignee ID is required for assignment",
                severity=ErrorSeverity.ERROR,
            )
        
        # Additional validations can be added here
        # e.g., check if assignee exists, has proper role, etc.
        
        return None

    def get_workload_stats(
        self,
        assignee_id: UUID,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Get workload statistics for an assignee.
        
        Args:
            assignee_id: UUID of assignee
            
        Returns:
            ServiceResult with workload metrics
        """
        try:
            self._logger.debug(f"Fetching workload stats for user {assignee_id}")
            
            # Get assigned inquiries count by status
            if hasattr(self.repository, 'get_workload_stats'):
                stats = self.repository.get_workload_stats(assignee_id)
            else:
                # Fallback: calculate from assigned inquiries
                assigned = self.db.query(InquiryModel).filter(
                    InquiryModel.assigned_to == assignee_id
                ).all()
                
                stats = {
                    "total_assigned": len(assigned),
                    "by_status": {},
                    "assignee_id": str(assignee_id),
                }
                
                # Group by status
                for inq in assigned:
                    status = getattr(inq, 'status', 'unknown')
                    stats["by_status"][status] = stats["by_status"].get(status, 0) + 1
            
            return ServiceResult.success(stats)
            
        except SQLAlchemyError as e:
            self._logger.error(f"Database error fetching workload stats: {str(e)}")
            return self._handle_exception(e, "get workload stats")
        except Exception as e:
            self._logger.exception(f"Unexpected error fetching workload stats: {str(e)}")
            return self._handle_exception(e, "get workload stats")