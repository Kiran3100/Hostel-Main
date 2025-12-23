"""
Attendance correction workflow service.

Handles:
- Correction request submission
- Approval workflow
- Audit trail maintenance
- Automatic validation
"""

from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime
import logging

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.services.base import (
    BaseService,
    ServiceResult,
    ServiceError,
    ErrorCode,
    ErrorSeverity,
)
from app.repositories.attendance import AttendanceRecordRepository
from app.models.attendance.attendance_record import AttendanceRecord as AttendanceRecordModel
from app.schemas.attendance.attendance_record import AttendanceCorrection
from app.schemas.attendance.attendance_response import AttendanceDetail

logger = logging.getLogger(__name__)


class AttendanceCorrectionService(
    BaseService[AttendanceRecordModel, AttendanceRecordRepository]
):
    """
    Service for submitting and applying attendance corrections.
    
    Responsibilities:
    - Process correction requests with validation
    - Maintain audit trail of all corrections
    - Support approval workflows
    - Ensure data integrity during corrections
    """

    def __init__(self, repository: AttendanceRecordRepository, db_session: Session):
        """
        Initialize correction service.
        
        Args:
            repository: AttendanceRecordRepository instance
            db_session: SQLAlchemy database session
        """
        super().__init__(repository, db_session)
        self._operation_context = "AttendanceCorrectionService"

    def submit_correction(
        self,
        correction: AttendanceCorrection,
        submitted_by: Optional[UUID] = None,
        auto_approve: bool = False,
    ) -> ServiceResult[AttendanceDetail]:
        """
        Submit a correction for an existing attendance record.
        
        Corrections are tracked for audit purposes and may require approval
        based on system configuration.
        
        Args:
            correction: AttendanceCorrection schema with correction details
            submitted_by: UUID of user submitting the correction
            auto_approve: Whether to auto-approve the correction
            
        Returns:
            ServiceResult containing updated AttendanceDetail
        """
        operation = "submit_correction"
        logger.info(
            f"{operation}: record_id={correction.record_id}, "
            f"submitted_by={submitted_by}, "
            f"auto_approve={auto_approve}"
        )
        
        try:
            # Validate correction request
            validation_result = self._validate_correction(correction)
            if not validation_result.success:
                return validation_result
            
            # Check if record exists
            existing_record = self.repository.get_by_id(correction.record_id)
            if not existing_record:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message=f"Attendance record not found: {correction.record_id}",
                        severity=ErrorSeverity.WARNING,
                        details={"record_id": str(correction.record_id)}
                    )
                )
            
            # Apply correction through repository
            detail = self.repository.apply_correction(
                correction,
                submitted_by=submitted_by
            )
            
            self.db.commit()
            
            logger.info(
                f"{operation} successful: record_id={correction.record_id}, "
                f"old_status={existing_record.status}, "
                f"new_status={correction.corrected_status}"
            )
            
            return ServiceResult.success(
                detail,
                message="Attendance correction applied successfully",
                metadata={
                    "record_id": str(correction.record_id),
                    "submitted_by": str(submitted_by) if submitted_by else None,
                    "auto_approved": auto_approve
                }
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(
                f"{operation} database error for record {correction.record_id}: {str(e)}",
                exc_info=True
            )
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.DATABASE_ERROR,
                    message=f"Database error while applying correction: {str(e)}",
                    severity=ErrorSeverity.ERROR,
                    details={"record_id": str(correction.record_id)}
                )
            )
            
        except Exception as e:
            self.db.rollback()
            logger.error(
                f"{operation} unexpected error for record {correction.record_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, operation, correction.record_id)

    def get_correction_history(
        self,
        record_id: UUID,
    ) -> ServiceResult[List[Dict[str, Any]]]:
        """
        Get correction history for a specific attendance record.
        
        Args:
            record_id: UUID of attendance record
            
        Returns:
            ServiceResult containing list of corrections
        """
        operation = "get_correction_history"
        logger.debug(f"{operation}: record_id={record_id}")
        
        try:
            history = self.repository.get_correction_history(record_id)
            
            logger.debug(
                f"{operation} returned {len(history)} corrections for record {record_id}"
            )
            
            return ServiceResult.success(
                history,
                metadata={
                    "record_id": str(record_id),
                    "correction_count": len(history)
                }
            )
            
        except SQLAlchemyError as e:
            logger.error(f"{operation} database error: {str(e)}", exc_info=True)
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.DATABASE_ERROR,
                    message=f"Database error while fetching correction history: {str(e)}",
                    severity=ErrorSeverity.ERROR,
                    details={"record_id": str(record_id)}
                )
            )
            
        except Exception as e:
            logger.error(f"{operation} unexpected error: {str(e)}", exc_info=True)
            return self._handle_exception(e, operation, record_id)

    def approve_correction(
        self,
        correction_id: UUID,
        approved_by: UUID,
        approval_notes: Optional[str] = None,
    ) -> ServiceResult[bool]:
        """
        Approve a pending correction request.
        
        Args:
            correction_id: UUID of correction request
            approved_by: UUID of user approving the correction
            approval_notes: Optional notes for the approval
            
        Returns:
            ServiceResult indicating approval success
        """
        operation = "approve_correction"
        logger.info(
            f"{operation}: correction_id={correction_id}, "
            f"approved_by={approved_by}"
        )
        
        try:
            success = self.repository.approve_correction(
                correction_id=correction_id,
                approved_by=approved_by,
                approval_notes=approval_notes
            )
            
            if not success:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message=f"Correction request not found: {correction_id}",
                        severity=ErrorSeverity.WARNING,
                        details={"correction_id": str(correction_id)}
                    )
                )
            
            self.db.commit()
            
            logger.info(f"{operation} successful: correction_id={correction_id}")
            
            return ServiceResult.success(
                True,
                message="Correction approved successfully",
                metadata={"correction_id": str(correction_id)}
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"{operation} database error: {str(e)}", exc_info=True)
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.DATABASE_ERROR,
                    message=f"Database error while approving correction: {str(e)}",
                    severity=ErrorSeverity.ERROR,
                    details={"correction_id": str(correction_id)}
                )
            )
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"{operation} unexpected error: {str(e)}", exc_info=True)
            return self._handle_exception(e, operation, correction_id)

    def reject_correction(
        self,
        correction_id: UUID,
        rejected_by: UUID,
        rejection_reason: str,
    ) -> ServiceResult[bool]:
        """
        Reject a pending correction request.
        
        Args:
            correction_id: UUID of correction request
            rejected_by: UUID of user rejecting the correction
            rejection_reason: Reason for rejection
            
        Returns:
            ServiceResult indicating rejection success
        """
        operation = "reject_correction"
        logger.info(
            f"{operation}: correction_id={correction_id}, "
            f"rejected_by={rejected_by}"
        )
        
        try:
            if not rejection_reason or not rejection_reason.strip():
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Rejection reason is required",
                        severity=ErrorSeverity.WARNING
                    )
                )
            
            success = self.repository.reject_correction(
                correction_id=correction_id,
                rejected_by=rejected_by,
                rejection_reason=rejection_reason
            )
            
            if not success:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message=f"Correction request not found: {correction_id}",
                        severity=ErrorSeverity.WARNING,
                        details={"correction_id": str(correction_id)}
                    )
                )
            
            self.db.commit()
            
            logger.info(f"{operation} successful: correction_id={correction_id}")
            
            return ServiceResult.success(
                True,
                message="Correction rejected",
                metadata={"correction_id": str(correction_id)}
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"{operation} database error: {str(e)}", exc_info=True)
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.DATABASE_ERROR,
                    message=f"Database error while rejecting correction: {str(e)}",
                    severity=ErrorSeverity.ERROR,
                    details={"correction_id": str(correction_id)}
                )
            )
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"{operation} unexpected error: {str(e)}", exc_info=True)
            return self._handle_exception(e, operation, correction_id)

    # =========================================================================
    # Private Helper Methods
    # =========================================================================

    def _validate_correction(
        self,
        correction: AttendanceCorrection
    ) -> ServiceResult[None]:
        """
        Validate correction request.
        
        Args:
            correction: AttendanceCorrection to validate
            
        Returns:
            ServiceResult indicating validation success/failure
        """
        # Validate reason is provided
        if not correction.reason or not correction.reason.strip():
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Correction reason is required",
                    severity=ErrorSeverity.WARNING,
                    details={"record_id": str(correction.record_id)}
                )
            )
        
        # Validate corrected status is provided if changing status
        if hasattr(correction, 'corrected_status') and correction.corrected_status is None:
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Corrected status must be provided",
                    severity=ErrorSeverity.WARNING,
                    details={"record_id": str(correction.record_id)}
                )
            )
        
        return ServiceResult.success(None)