"""
Leave Balance Service Module

Manages leave balances, quotas, and usage analytics including:
- Balance tracking per leave type
- Quota management and updates
- Manual balance adjustments
- Usage history and analytics
- Academic year rollover

Version: 2.0.0
"""

from typing import Optional, List, Dict, Any
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
from app.repositories.leave.leave_balance_repository import LeaveBalanceRepository
from app.models.leave.leave_balance import LeaveBalance as LeaveBalanceModel
from app.schemas.leave.leave_balance import (
    LeaveBalance as LeaveBalanceSchema,
    LeaveBalanceSummary,
    LeaveQuota,
    LeaveUsageDetail,
)

logger = logging.getLogger(__name__)


class LeaveBalanceService(BaseService[LeaveBalanceModel, LeaveBalanceRepository]):
    """
    Comprehensive service for leave balance and quota management.
    
    Handles:
    - Balance queries and summaries
    - Quota configuration
    - Manual adjustments with audit trails
    - Usage analytics and reporting
    - Academic year transitions
    """

    def __init__(self, repository: LeaveBalanceRepository, db_session: Session):
        """
        Initialize the leave balance service.
        
        Args:
            repository: Leave balance repository instance
            db_session: Active database session
        """
        super().__init__(repository, db_session)
        self._logger = logger

    def get_balance_summary(
        self,
        student_id: UUID,
        academic_year_start: date,
        academic_year_end: date,
    ) -> ServiceResult[LeaveBalanceSummary]:
        """
        Retrieve comprehensive balance summary for a student.
        
        Provides aggregated view across all leave types including:
        - Total allocated days
        - Used days
        - Remaining balance
        - Pending applications
        - Breakdown by leave type
        
        Args:
            student_id: UUID of the student
            academic_year_start: Start date of academic year
            academic_year_end: End date of academic year
            
        Returns:
            ServiceResult containing LeaveBalanceSummary or error information
        """
        try:
            # Validate date range
            if academic_year_end <= academic_year_start:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Academic year end must be after start date",
                        severity=ErrorSeverity.WARNING,
                        details={
                            "start": academic_year_start.isoformat(),
                            "end": academic_year_end.isoformat()
                        }
                    )
                )
            
            self._logger.debug(
                f"Retrieving balance summary for student {student_id} "
                f"for academic year {academic_year_start} to {academic_year_end}"
            )
            
            summary = self.repository.get_balance_summary(
                student_id,
                academic_year_start,
                academic_year_end
            )
            
            if not summary:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message="Balance summary not found for student",
                        severity=ErrorSeverity.WARNING,
                        details={"student_id": str(student_id)}
                    )
                )
            
            return ServiceResult.success(
                summary,
                metadata={
                    "student_id": str(student_id),
                    "academic_year_start": academic_year_start.isoformat(),
                    "academic_year_end": academic_year_end.isoformat(),
                }
            )
            
        except SQLAlchemyError as e:
            self._logger.error(
                f"Database error while retrieving balance summary: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "get leave balance summary", student_id)
            
        except Exception as e:
            self._logger.error(
                f"Unexpected error while retrieving balance summary: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "get leave balance summary", student_id)

    def get_balance_for_type(
        self,
        student_id: UUID,
        leave_type: str,
        academic_year_start: date,
        academic_year_end: date,
    ) -> ServiceResult[LeaveBalanceSchema]:
        """
        Retrieve balance for a specific leave type.
        
        Args:
            student_id: UUID of the student
            leave_type: Type of leave (sick, casual, etc.)
            academic_year_start: Start date of academic year
            academic_year_end: End date of academic year
            
        Returns:
            ServiceResult containing LeaveBalanceSchema or error information
        """
        try:
            # Validate date range
            if academic_year_end <= academic_year_start:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Academic year end must be after start date",
                        severity=ErrorSeverity.WARNING,
                        details={
                            "start": academic_year_start.isoformat(),
                            "end": academic_year_end.isoformat()
                        }
                    )
                )
            
            # Validate leave type
            if not leave_type or not leave_type.strip():
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Leave type is required",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            self._logger.debug(
                f"Retrieving {leave_type} balance for student {student_id}"
            )
            
            balance = self.repository.get_balance_for_type(
                student_id,
                leave_type,
                academic_year_start,
                academic_year_end
            )
            
            if not balance:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message=f"Balance not found for leave type: {leave_type}",
                        severity=ErrorSeverity.WARNING,
                        details={
                            "student_id": str(student_id),
                            "leave_type": leave_type
                        }
                    )
                )
            
            return ServiceResult.success(
                balance,
                metadata={
                    "student_id": str(student_id),
                    "leave_type": leave_type,
                }
            )
            
        except SQLAlchemyError as e:
            self._logger.error(
                f"Database error while retrieving balance for type: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "get leave balance for type", student_id)
            
        except Exception as e:
            self._logger.error(
                f"Unexpected error while retrieving balance for type: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "get leave balance for type", student_id)

    def update_quota(
        self,
        hostel_id: UUID,
        leave_type: str,
        quota: LeaveQuota,
        updated_by: Optional[UUID] = None,
    ) -> ServiceResult[LeaveQuota]:
        """
        Update leave quota configuration for a hostel and leave type.
        
        Args:
            hostel_id: UUID of the hostel
            leave_type: Type of leave
            quota: New quota configuration
            updated_by: UUID of the user making the update (for audit)
            
        Returns:
            ServiceResult containing updated LeaveQuota or error information
        """
        try:
            # Validate quota values
            validation_result = self._validate_quota(quota)
            if not validation_result.success:
                return validation_result
            
            self._logger.info(
                f"Updating quota for {leave_type} in hostel {hostel_id}"
            )
            
            saved = self.repository.update_quota(
                hostel_id,
                leave_type,
                quota,
                updated_by=updated_by
            )
            
            if not saved:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.OPERATION_FAILED,
                        message="Failed to update leave quota",
                        severity=ErrorSeverity.ERROR,
                        details={
                            "hostel_id": str(hostel_id),
                            "leave_type": leave_type
                        }
                    )
                )
            
            # Commit transaction
            self.db.commit()
            
            self._logger.info(
                f"Quota updated successfully for {leave_type} in hostel {hostel_id}"
            )
            
            return ServiceResult.success(
                saved,
                message="Leave quota updated successfully"
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            self._logger.error(
                f"Database error while updating quota: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "update leave quota", hostel_id)
            
        except Exception as e:
            self.db.rollback()
            self._logger.error(
                f"Unexpected error while updating quota: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "update leave quota", hostel_id)

    def adjust_balance(
        self,
        student_id: UUID,
        leave_type: str,
        amount_days: int,
        reason: str,
        adjusted_by: Optional[UUID] = None,
    ) -> ServiceResult[LeaveBalanceSchema]:
        """
        Manually adjust a student's leave balance.
        
        Used for:
        - Corrections and reconciliation
        - Special allowances
        - Compensatory leave grants
        - Administrative adjustments
        
        Args:
            student_id: UUID of the student
            leave_type: Type of leave to adjust
            amount_days: Adjustment amount (positive to add, negative to deduct)
            reason: Explanation for the adjustment (audit trail)
            adjusted_by: UUID of the user making adjustment (for audit)
            
        Returns:
            ServiceResult containing updated LeaveBalanceSchema or error information
        """
        try:
            # Validate adjustment parameters
            if not reason or not reason.strip():
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Reason is required for balance adjustment",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            if amount_days == 0:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Adjustment amount cannot be zero",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            self._logger.info(
                f"Adjusting {leave_type} balance by {amount_days} days "
                f"for student {student_id}. Reason: {reason}"
            )
            
            updated = self.repository.adjust_balance(
                student_id,
                leave_type,
                amount_days,
                reason,
                adjusted_by=adjusted_by
            )
            
            if not updated:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.OPERATION_FAILED,
                        message="Failed to adjust leave balance",
                        severity=ErrorSeverity.ERROR,
                        details={
                            "student_id": str(student_id),
                            "leave_type": leave_type
                        }
                    )
                )
            
            # Commit transaction
            self.db.commit()
            
            self._logger.info(
                f"Balance adjusted successfully for student {student_id}"
            )
            
            return ServiceResult.success(
                updated,
                message="Leave balance adjusted successfully"
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            self._logger.error(
                f"Database error while adjusting balance: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "adjust leave balance", student_id)
            
        except Exception as e:
            self.db.rollback()
            self._logger.error(
                f"Unexpected error while adjusting balance: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "adjust leave balance", student_id)

    def list_usage_details(
        self,
        student_id: UUID,
        start_date: date,
        end_date: date,
    ) -> ServiceResult[List[LeaveUsageDetail]]:
        """
        Retrieve detailed usage history for a student.
        
        Provides transaction-level details of:
        - Leave applications consumed
        - Balance adjustments
        - Refunds and cancellations
        - Timestamps and actors
        
        Args:
            student_id: UUID of the student
            start_date: Start date for usage history
            end_date: End date for usage history
            
        Returns:
            ServiceResult containing list of LeaveUsageDetail or error information
        """
        try:
            # Validate date range
            if end_date < start_date:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="End date cannot be before start date",
                        severity=ErrorSeverity.WARNING,
                        details={
                            "start_date": start_date.isoformat(),
                            "end_date": end_date.isoformat()
                        }
                    )
                )
            
            self._logger.debug(
                f"Retrieving usage details for student {student_id} "
                f"from {start_date} to {end_date}"
            )
            
            usage = self.repository.get_usage_details(
                student_id,
                start_date,
                end_date
            )
            
            if usage is None:
                usage = []
            
            self._logger.debug(
                f"Retrieved {len(usage)} usage detail entries for student {student_id}"
            )
            
            return ServiceResult.success(
                usage,
                metadata={
                    "count": len(usage),
                    "student_id": str(student_id),
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                }
            )
            
        except SQLAlchemyError as e:
            self._logger.error(
                f"Database error while retrieving usage details: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "get leave usage details", student_id)
            
        except Exception as e:
            self._logger.error(
                f"Unexpected error while retrieving usage details: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "get leave usage details", student_id)

    def get_quota_by_hostel(
        self,
        hostel_id: UUID,
    ) -> ServiceResult[List[LeaveQuota]]:
        """
        Retrieve all quota configurations for a hostel.
        
        Args:
            hostel_id: UUID of the hostel
            
        Returns:
            ServiceResult containing list of LeaveQuota or error information
        """
        try:
            self._logger.debug(
                f"Retrieving all quotas for hostel {hostel_id}"
            )
            
            # This would need to be implemented in the repository
            # quotas = self.repository.get_quotas_by_hostel(hostel_id)
            
            # Placeholder implementation
            quotas = []
            
            return ServiceResult.success(
                quotas,
                metadata={
                    "count": len(quotas),
                    "hostel_id": str(hostel_id)
                }
            )
            
        except SQLAlchemyError as e:
            self._logger.error(
                f"Database error while retrieving quotas: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "get hostel quotas", hostel_id)
            
        except Exception as e:
            self._logger.error(
                f"Unexpected error while retrieving quotas: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "get hostel quotas", hostel_id)

    # -------------------------------------------------------------------------
    # Private Validation Methods
    # -------------------------------------------------------------------------

    def _validate_quota(
        self,
        quota: LeaveQuota
    ) -> ServiceResult[None]:
        """
        Validate quota configuration values.
        
        Args:
            quota: The quota configuration to validate
            
        Returns:
            ServiceResult indicating validation success or specific errors
        """
        # Validate that quota values are non-negative
        if hasattr(quota, 'max_days') and quota.max_days < 0:
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Maximum days cannot be negative",
                    severity=ErrorSeverity.WARNING,
                )
            )
        
        # Additional validation logic can be added here
        
        return ServiceResult.success(None)