"""
Attendance policy service for configuration and violations.

Handles:
- Policy configuration per hostel
- Violation detection algorithms
- Policy enforcement rules
- Threshold management
"""

from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import date, datetime, timedelta
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
from app.repositories.attendance import AttendancePolicyRepository
from app.models.attendance.attendance_policy import AttendancePolicy as AttendancePolicyModel
from app.schemas.attendance.attendance_policy import (
    AttendancePolicy as AttendancePolicySchema,
    PolicyConfig,
    PolicyUpdate,
    PolicyViolation,
)

logger = logging.getLogger(__name__)


class AttendancePolicyService(
    BaseService[AttendancePolicyModel, AttendancePolicyRepository]
):
    """
    Service for managing attendance policy and detecting violations.
    
    Responsibilities:
    - Configure attendance policies per hostel
    - Detect policy violations based on rules
    - Manage thresholds and grace periods
    - Generate violation reports
    """

    def __init__(self, repository: AttendancePolicyRepository, db_session: Session):
        """
        Initialize policy service.
        
        Args:
            repository: AttendancePolicyRepository instance
            db_session: SQLAlchemy database session
        """
        super().__init__(repository, db_session)
        self._operation_context = "AttendancePolicyService"

    def get_policy(
        self,
        hostel_id: UUID,
    ) -> ServiceResult[AttendancePolicySchema]:
        """
        Fetch current attendance policy for hostel.
        
        Returns default policy if none configured.
        
        Args:
            hostel_id: UUID of hostel
            
        Returns:
            ServiceResult containing AttendancePolicySchema
        """
        operation = "get_policy"
        logger.debug(f"{operation}: hostel_id={hostel_id}")
        
        try:
            policy = self.repository.get_policy(hostel_id)
            
            if not policy:
                logger.warning(f"No policy found for hostel {hostel_id}")
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message="Attendance policy not found for this hostel",
                        severity=ErrorSeverity.WARNING,
                        details={
                            "hostel_id": str(hostel_id),
                            "suggestion": "Create a policy or use system defaults"
                        }
                    )
                )
            
            logger.debug(f"{operation} successful for hostel {hostel_id}")
            
            return ServiceResult.success(
                policy,
                metadata={"hostel_id": str(hostel_id)}
            )
            
        except SQLAlchemyError as e:
            logger.error(f"{operation} database error: {str(e)}", exc_info=True)
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.DATABASE_ERROR,
                    message=f"Database error while fetching policy: {str(e)}",
                    severity=ErrorSeverity.ERROR,
                    details={"hostel_id": str(hostel_id)}
                )
            )
            
        except Exception as e:
            logger.error(f"{operation} unexpected error: {str(e)}", exc_info=True)
            return self._handle_exception(e, operation, hostel_id)

    def create_policy(
        self,
        hostel_id: UUID,
        config: PolicyConfig,
        created_by: Optional[UUID] = None,
    ) -> ServiceResult[AttendancePolicySchema]:
        """
        Create a new attendance policy for hostel.
        
        Args:
            hostel_id: UUID of hostel
            config: PolicyConfig with policy settings
            created_by: UUID of user creating the policy
            
        Returns:
            ServiceResult containing created AttendancePolicySchema
        """
        operation = "create_policy"
        logger.info(f"{operation}: hostel_id={hostel_id}, created_by={created_by}")
        
        try:
            # Validate configuration
            validation_result = self._validate_policy_config(config)
            if not validation_result.success:
                return validation_result
            
            # Check if policy already exists
            existing = self.repository.get_policy(hostel_id)
            if existing:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.ALREADY_EXISTS,
                        message="Policy already exists for this hostel",
                        severity=ErrorSeverity.WARNING,
                        details={
                            "hostel_id": str(hostel_id),
                            "suggestion": "Use update_policy instead"
                        }
                    )
                )
            
            # Create policy
            policy = self.repository.create_policy(
                hostel_id=hostel_id,
                config=config,
                created_by=created_by
            )
            
            self.db.commit()
            
            logger.info(f"{operation} successful for hostel {hostel_id}")
            
            return ServiceResult.success(
                policy,
                message="Attendance policy created successfully",
                metadata={"hostel_id": str(hostel_id)}
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"{operation} database error: {str(e)}", exc_info=True)
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.DATABASE_ERROR,
                    message=f"Database error while creating policy: {str(e)}",
                    severity=ErrorSeverity.ERROR,
                    details={"hostel_id": str(hostel_id)}
                )
            )
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"{operation} unexpected error: {str(e)}", exc_info=True)
            return self._handle_exception(e, operation, hostel_id)

    def update_policy(
        self,
        hostel_id: UUID,
        update: PolicyUpdate,
        updated_by: Optional[UUID] = None,
    ) -> ServiceResult[AttendancePolicySchema]:
        """
        Update partial policy configuration.
        
        Args:
            hostel_id: UUID of hostel
            update: PolicyUpdate with fields to update
            updated_by: UUID of user updating the policy
            
        Returns:
            ServiceResult containing updated AttendancePolicySchema
        """
        operation = "update_policy"
        logger.info(f"{operation}: hostel_id={hostel_id}, updated_by={updated_by}")
        
        try:
            # Validate update data
            validation_result = self._validate_policy_update(update)
            if not validation_result.success:
                return validation_result
            
            # Update policy
            policy = self.repository.update_policy(
                hostel_id=hostel_id,
                update=update,
                updated_by=updated_by
            )
            
            if not policy:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message="Policy not found for this hostel",
                        severity=ErrorSeverity.WARNING,
                        details={
                            "hostel_id": str(hostel_id),
                            "suggestion": "Create a policy first"
                        }
                    )
                )
            
            self.db.commit()
            
            logger.info(f"{operation} successful for hostel {hostel_id}")
            
            return ServiceResult.success(
                policy,
                message="Attendance policy updated successfully",
                metadata={"hostel_id": str(hostel_id)}
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"{operation} database error: {str(e)}", exc_info=True)
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.DATABASE_ERROR,
                    message=f"Database error while updating policy: {str(e)}",
                    severity=ErrorSeverity.ERROR,
                    details={"hostel_id": str(hostel_id)}
                )
            )
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"{operation} unexpected error: {str(e)}", exc_info=True)
            return self._handle_exception(e, operation, hostel_id)

    def detect_violations(
        self,
        hostel_id: UUID,
        start_date: date,
        end_date: date,
        student_id: Optional[UUID] = None,
    ) -> ServiceResult[List[PolicyViolation]]:
        """
        Detect policy violations for a period.
        
        Checks attendance records against configured policy rules.
        
        Args:
            hostel_id: UUID of hostel
            start_date: Start of date range
            end_date: End of date range
            student_id: Optional UUID to check specific student
            
        Returns:
            ServiceResult containing list of PolicyViolation
        """
        operation = "detect_violations"
        logger.info(
            f"{operation}: hostel_id={hostel_id}, "
            f"date_range={start_date} to {end_date}, "
            f"student_id={student_id}"
        )
        
        try:
            # Validate date range
            if start_date > end_date:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Start date must be before or equal to end date",
                        severity=ErrorSeverity.WARNING,
                        details={
                            "start_date": str(start_date),
                            "end_date": str(end_date)
                        }
                    )
                )
            
            # Check date range is not too large
            max_range_days = 90
            if (end_date - start_date).days > max_range_days:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message=f"Date range cannot exceed {max_range_days} days",
                        severity=ErrorSeverity.WARNING,
                        details={
                            "start_date": str(start_date),
                            "end_date": str(end_date),
                            "days": (end_date - start_date).days
                        }
                    )
                )
            
            # Detect violations
            violations = self.repository.detect_violations(
                hostel_id=hostel_id,
                start_date=start_date,
                end_date=end_date,
                student_id=student_id
            )
            
            logger.info(
                f"{operation} found {len(violations)} violations for hostel {hostel_id}"
            )
            
            return ServiceResult.success(
                violations,
                metadata={
                    "count": len(violations),
                    "hostel_id": str(hostel_id),
                    "date_range": f"{start_date} to {end_date}",
                    "student_id": str(student_id) if student_id else None
                }
            )
            
        except SQLAlchemyError as e:
            logger.error(f"{operation} database error: {str(e)}", exc_info=True)
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.DATABASE_ERROR,
                    message=f"Database error while detecting violations: {str(e)}",
                    severity=ErrorSeverity.ERROR,
                    details={"hostel_id": str(hostel_id)}
                )
            )
            
        except Exception as e:
            logger.error(f"{operation} unexpected error: {str(e)}", exc_info=True)
            return self._handle_exception(e, operation, hostel_id)

    def get_violation_summary(
        self,
        hostel_id: UUID,
        start_date: date,
        end_date: date,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Get summary of violations by type and severity.
        
        Args:
            hostel_id: UUID of hostel
            start_date: Start of date range
            end_date: End of date range
            
        Returns:
            ServiceResult containing violation summary statistics
        """
        operation = "get_violation_summary"
        logger.debug(
            f"{operation}: hostel_id={hostel_id}, "
            f"date_range={start_date} to {end_date}"
        )
        
        try:
            summary = self.repository.get_violation_summary(
                hostel_id=hostel_id,
                start_date=start_date,
                end_date=end_date
            )
            
            return ServiceResult.success(
                summary,
                metadata={
                    "hostel_id": str(hostel_id),
                    "date_range": f"{start_date} to {end_date}"
                }
            )
            
        except Exception as e:
            logger.error(f"{operation} error: {str(e)}", exc_info=True)
            return self._handle_exception(e, operation, hostel_id)

    # =========================================================================
    # Private Helper Methods
    # =========================================================================

    def _validate_policy_config(self, config: PolicyConfig) -> ServiceResult[None]:
        """
        Validate policy configuration.
        
        Args:
            config: PolicyConfig to validate
            
        Returns:
            ServiceResult indicating validation success/failure
        """
        errors = []
        
        # Validate minimum attendance percentage
        if hasattr(config, 'minimum_attendance_percentage'):
            if config.minimum_attendance_percentage < 0 or config.minimum_attendance_percentage > 100:
                errors.append("Minimum attendance percentage must be between 0 and 100")
        
        # Validate consecutive absences threshold
        if hasattr(config, 'consecutive_absences_threshold'):
            if config.consecutive_absences_threshold < 1:
                errors.append("Consecutive absences threshold must be at least 1")
        
        # Validate late threshold minutes
        if hasattr(config, 'late_threshold_minutes'):
            if config.late_threshold_minutes < 0:
                errors.append("Late threshold minutes cannot be negative")
        
        if errors:
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Policy configuration validation failed",
                    severity=ErrorSeverity.WARNING,
                    details={"errors": errors}
                )
            )
        
        return ServiceResult.success(None)

    def _validate_policy_update(self, update: PolicyUpdate) -> ServiceResult[None]:
        """
        Validate policy update data.
        
        Args:
            update: PolicyUpdate to validate
            
        Returns:
            ServiceResult indicating validation success/failure
        """
        # Similar validation as config, but only for provided fields
        errors = []
        
        update_dict = update.dict(exclude_none=True)
        
        if 'minimum_attendance_percentage' in update_dict:
            value = update_dict['minimum_attendance_percentage']
            if value < 0 or value > 100:
                errors.append("Minimum attendance percentage must be between 0 and 100")
        
        if 'consecutive_absences_threshold' in update_dict:
            value = update_dict['consecutive_absences_threshold']
            if value < 1:
                errors.append("Consecutive absences threshold must be at least 1")
        
        if 'late_threshold_minutes' in update_dict:
            value = update_dict['late_threshold_minutes']
            if value < 0:
                errors.append("Late threshold minutes cannot be negative")
        
        if errors:
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Policy update validation failed",
                    severity=ErrorSeverity.WARNING,
                    details={"errors": errors}
                )
            )
        
        return ServiceResult.success(None)