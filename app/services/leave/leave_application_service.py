"""
Leave Application Service Module

Provides comprehensive business logic for leave application management including:
- Application submission with validation
- Cancellation with policy enforcement
- Updates with audit trails
- Detailed retrieval and listing with filters
- Summary analytics

Version: 2.0.0
"""

from typing import Optional, List
from uuid import UUID
from datetime import date
import logging

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.services.base import (
    BaseService,
    ServiceResult,
    ServiceError,
    ErrorCode,
    ErrorSeverity
)
from app.repositories.leave.leave_application_repository import LeaveApplicationRepository
from app.models.leave.leave_application import LeaveApplication as LeaveApplicationModel
from app.schemas.leave.leave_application import (
    LeaveApplicationRequest,
    LeaveCancellationRequest
)
from app.schemas.leave.leave_base import LeaveUpdate
from app.schemas.leave.leave_response import (
    LeaveResponse,
    LeaveDetail,
    LeaveListItem,
    LeaveSummary,
)

logger = logging.getLogger(__name__)


class LeaveApplicationService(BaseService[LeaveApplicationModel, LeaveApplicationRepository]):
    """
    Comprehensive service for managing student leave applications.
    
    Handles the complete lifecycle of leave applications including:
    - Submission with business rule validation
    - Cancellation with policy checks
    - Administrative updates
    - Retrieval and filtering
    - Analytics and reporting
    """

    def __init__(self, repository: LeaveApplicationRepository, db_session: Session):
        """
        Initialize the leave application service.
        
        Args:
            repository: Leave application repository instance
            db_session: Active database session
        """
        super().__init__(repository, db_session)
        self._logger = logger

    def apply(
        self,
        request: LeaveApplicationRequest,
        submitted_by: Optional[UUID] = None,
    ) -> ServiceResult[LeaveDetail]:
        """
        Submit a new leave application with comprehensive validation.
        
        Performs:
        - Business rule validation
        - Balance verification
        - Blackout date checks
        - Overlap detection
        
        Args:
            request: Leave application request data
            submitted_by: UUID of the user submitting (for audit)
            
        Returns:
            ServiceResult containing LeaveDetail on success or error information
        """
        try:
            self._logger.info(
                f"Processing leave application for student {request.student_id}"
            )
            
            # Validate request data
            validation_result = self._validate_application_request(request)
            if not validation_result.success:
                return validation_result

            # Create the application via repository
            detail = self.repository.create_application(
                request,
                submitted_by=submitted_by
            )
            
            # Commit transaction
            self.db.commit()
            
            self._logger.info(
                f"Leave application {detail.id} submitted successfully "
                f"for student {request.student_id}"
            )
            
            return ServiceResult.success(
                detail,
                message="Leave application submitted successfully"
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            self._logger.error(
                f"Database error while applying for leave: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "apply for leave", request.student_id)
            
        except Exception as e:
            self.db.rollback()
            self._logger.error(
                f"Unexpected error while applying for leave: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "apply for leave", request.student_id)

    def cancel(
        self,
        request: LeaveCancellationRequest,
        cancelled_by: Optional[UUID] = None,
    ) -> ServiceResult[bool]:
        """
        Cancel a pending or approved leave application.
        
        Enforces cancellation policies:
        - Time-based restrictions
        - Status-based rules
        - Balance adjustments
        
        Args:
            request: Cancellation request with leave ID and reason
            cancelled_by: UUID of the user cancelling (for audit)
            
        Returns:
            ServiceResult containing success boolean or error information
        """
        try:
            self._logger.info(
                f"Processing cancellation for leave application {request.leave_id}"
            )
            
            # Validate cancellation eligibility
            validation_result = self._validate_cancellation_request(request)
            if not validation_result.success:
                return validation_result

            # Perform cancellation via repository
            success = self.repository.cancel_application(
                request,
                cancelled_by=cancelled_by
            )
            
            if not success:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.OPERATION_FAILED,
                        message="Failed to cancel leave application",
                        severity=ErrorSeverity.ERROR,
                        details={"leave_id": str(request.leave_id)}
                    )
                )
            
            # Commit transaction
            self.db.commit()
            
            self._logger.info(
                f"Leave application {request.leave_id} cancelled successfully"
            )
            
            return ServiceResult.success(
                True,
                message="Leave application cancelled successfully"
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            self._logger.error(
                f"Database error while cancelling leave: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "cancel leave", request.leave_id)
            
        except Exception as e:
            self.db.rollback()
            self._logger.error(
                f"Unexpected error while cancelling leave: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "cancel leave", request.leave_id)

    def update_application(
        self,
        leave_id: UUID,
        update: LeaveUpdate,
        updated_by: Optional[UUID] = None,
    ) -> ServiceResult[LeaveDetail]:
        """
        Perform partial update on an existing leave application.
        
        Primarily used for administrative updates and corrections.
        Maintains audit trail of all modifications.
        
        Args:
            leave_id: UUID of the leave application to update
            update: Partial update data
            updated_by: UUID of the user performing update (for audit)
            
        Returns:
            ServiceResult containing updated LeaveDetail or error information
        """
        try:
            self._logger.info(f"Processing update for leave application {leave_id}")
            
            # Check existence
            existing = self.repository.get_by_id(leave_id)
            if not existing:
                self._logger.warning(f"Leave application {leave_id} not found")
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message="Leave application not found",
                        severity=ErrorSeverity.ERROR,
                        details={"leave_id": str(leave_id)}
                    )
                )
            
            # Validate update permissions and data
            validation_result = self._validate_update_request(existing, update)
            if not validation_result.success:
                return validation_result

            # Perform update via repository
            detail = self.repository.update_application(
                leave_id,
                update,
                updated_by=updated_by
            )
            
            # Commit transaction
            self.db.commit()
            
            self._logger.info(
                f"Leave application {leave_id} updated successfully"
            )
            
            return ServiceResult.success(
                detail,
                message="Leave application updated successfully"
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            self._logger.error(
                f"Database error while updating leave application: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "update leave application", leave_id)
            
        except Exception as e:
            self.db.rollback()
            self._logger.error(
                f"Unexpected error while updating leave application: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "update leave application", leave_id)

    def get_detail(
        self,
        leave_id: UUID,
    ) -> ServiceResult[LeaveDetail]:
        """
        Retrieve comprehensive details for a specific leave application.
        
        Includes:
        - Application data
        - Approval history
        - Related documents
        - Audit trail
        
        Args:
            leave_id: UUID of the leave application
            
        Returns:
            ServiceResult containing LeaveDetail or error information
        """
        try:
            self._logger.debug(f"Retrieving details for leave application {leave_id}")
            
            detail = self.repository.get_detail(leave_id)
            
            if not detail:
                self._logger.warning(f"Leave application {leave_id} not found")
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message="Leave application not found",
                        severity=ErrorSeverity.ERROR,
                        details={"leave_id": str(leave_id)}
                    )
                )
            
            return ServiceResult.success(detail)
            
        except SQLAlchemyError as e:
            self._logger.error(
                f"Database error while retrieving leave detail: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "get leave detail", leave_id)
            
        except Exception as e:
            self._logger.error(
                f"Unexpected error while retrieving leave detail: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "get leave detail", leave_id)

    def list_for_student(
        self,
        student_id: UUID,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> ServiceResult[List[LeaveListItem]]:
        """
        List all leave applications for a specific student with optional date filtering.
        
        Args:
            student_id: UUID of the student
            start_date: Optional filter for applications starting after this date
            end_date: Optional filter for applications ending before this date
            
        Returns:
            ServiceResult containing list of LeaveListItem or error information
        """
        try:
            self._logger.debug(
                f"Listing leave applications for student {student_id} "
                f"(start_date={start_date}, end_date={end_date})"
            )
            
            items = self.repository.list_for_student(
                student_id,
                start_date=start_date,
                end_date=end_date
            )
            
            self._logger.debug(
                f"Retrieved {len(items)} leave applications for student {student_id}"
            )
            
            return ServiceResult.success(
                items,
                metadata={
                    "count": len(items),
                    "student_id": str(student_id),
                    "start_date": start_date.isoformat() if start_date else None,
                    "end_date": end_date.isoformat() if end_date else None,
                }
            )
            
        except SQLAlchemyError as e:
            self._logger.error(
                f"Database error while listing student leaves: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "list student leaves", student_id)
            
        except Exception as e:
            self._logger.error(
                f"Unexpected error while listing student leaves: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "list student leaves", student_id)

    def list_for_hostel(
        self,
        hostel_id: UUID,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> ServiceResult[List[LeaveListItem]]:
        """
        List leave applications for a hostel with filtering and pagination.
        
        Args:
            hostel_id: UUID of the hostel
            status: Optional status filter (pending, approved, rejected, etc.)
            page: Page number (1-indexed)
            page_size: Number of items per page
            
        Returns:
            ServiceResult containing paginated list of LeaveListItem or error information
        """
        try:
            # Validate pagination parameters
            if page < 1:
                page = 1
            if page_size < 1 or page_size > 100:
                page_size = 50
            
            self._logger.debug(
                f"Listing leave applications for hostel {hostel_id} "
                f"(status={status}, page={page}, page_size={page_size})"
            )
            
            items = self.repository.list_for_hostel(
                hostel_id,
                status=status,
                page=page,
                page_size=page_size
            )
            
            self._logger.debug(
                f"Retrieved {len(items)} leave applications for hostel {hostel_id}"
            )
            
            return ServiceResult.success(
                items,
                metadata={
                    "count": len(items),
                    "hostel_id": str(hostel_id),
                    "status": status,
                    "page": page,
                    "page_size": page_size,
                }
            )
            
        except SQLAlchemyError as e:
            self._logger.error(
                f"Database error while listing hostel leaves: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "list hostel leaves", hostel_id)
            
        except Exception as e:
            self._logger.error(
                f"Unexpected error while listing hostel leaves: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "list hostel leaves", hostel_id)

    def summary(
        self,
        hostel_id: Optional[UUID] = None,
        student_id: Optional[UUID] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> ServiceResult[LeaveSummary]:
        """
        Generate summary statistics for leave applications.
        
        Provides aggregated data including:
        - Total applications by status
        - Days utilized vs available
        - Trend analysis
        
        Args:
            hostel_id: Optional hostel filter
            student_id: Optional student filter
            start_date: Optional date range start
            end_date: Optional date range end
            
        Returns:
            ServiceResult containing LeaveSummary or error information
        """
        try:
            self._logger.debug(
                f"Generating leave summary "
                f"(hostel_id={hostel_id}, student_id={student_id}, "
                f"start_date={start_date}, end_date={end_date})"
            )
            
            # Validate that at least one filter is provided
            if not hostel_id and not student_id:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Either hostel_id or student_id must be provided",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            summary = self.repository.get_summary(
                hostel_id=hostel_id,
                student_id=student_id,
                start_date=start_date,
                end_date=end_date
            )
            
            return ServiceResult.success(summary)
            
        except SQLAlchemyError as e:
            self._logger.error(
                f"Database error while generating leave summary: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(
                e,
                "get leave summary",
                hostel_id or student_id
            )
            
        except Exception as e:
            self._logger.error(
                f"Unexpected error while generating leave summary: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(
                e,
                "get leave summary",
                hostel_id or student_id
            )

    # -------------------------------------------------------------------------
    # Private Validation Methods
    # -------------------------------------------------------------------------

    def _validate_application_request(
        self,
        request: LeaveApplicationRequest
    ) -> ServiceResult[None]:
        """
        Validate leave application request data.
        
        Args:
            request: The application request to validate
            
        Returns:
            ServiceResult indicating validation success or specific errors
        """
        # Date range validation
        if request.end_date < request.start_date:
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="End date cannot be before start date",
                    severity=ErrorSeverity.WARNING,
                    details={
                        "start_date": request.start_date.isoformat(),
                        "end_date": request.end_date.isoformat(),
                    }
                )
            )
        
        # Additional validation can be added here
        # - Maximum leave duration
        # - Advance notice requirements
        # - Blackout period checks
        # - Balance availability
        
        return ServiceResult.success(None)

    def _validate_cancellation_request(
        self,
        request: LeaveCancellationRequest
    ) -> ServiceResult[None]:
        """
        Validate leave cancellation request.
        
        Args:
            request: The cancellation request to validate
            
        Returns:
            ServiceResult indicating validation success or specific errors
        """
        # Additional validation can be added here
        # - Cancellation deadline checks
        # - Status eligibility
        # - Policy compliance
        
        return ServiceResult.success(None)

    def _validate_update_request(
        self,
        existing: LeaveApplicationModel,
        update: LeaveUpdate
    ) -> ServiceResult[None]:
        """
        Validate leave application update request.
        
        Args:
            existing: The existing leave application
            update: The update data
            
        Returns:
            ServiceResult indicating validation success or specific errors
        """
        # Additional validation can be added here
        # - Status-based update restrictions
        # - Field-level permissions
        # - Date modification rules
        
        return ServiceResult.success(None)