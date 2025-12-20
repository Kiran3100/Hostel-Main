# --- File: app/services/attendance/attendance_policy_service.py ---
"""
Attendance policy service with policy management and enforcement.

Provides policy CRUD, violation tracking, exception management,
and policy validation operations.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.attendance.attendance_policy import (
    AttendancePolicy,
    PolicyViolation,
    PolicyException,
)
from app.repositories.attendance.attendance_policy_repository import (
    AttendancePolicyRepository,
)
from app.core.exceptions import ValidationError, NotFoundError, BusinessLogicError
from app.core.logging import get_logger

logger = get_logger(__name__)


class AttendancePolicyService:
    """
    Service for attendance policy management.
    """

    def __init__(self, session: Session):
        """
        Initialize service with database session.

        Args:
            session: SQLAlchemy database session
        """
        self.session = session
        self.policy_repo = AttendancePolicyRepository(session)

    # ==================== Policy Management ====================

    def create_policy(
        self,
        hostel_id: UUID,
        minimum_attendance_percentage: Decimal = Decimal("75.00"),
        late_entry_threshold_minutes: int = 15,
        grace_period_minutes: int = 5,
        grace_days_per_month: int = 3,
        consecutive_absence_alert_days: int = 3,
        total_absence_alert_threshold: int = 10,
        **kwargs: Any,
    ) -> AttendancePolicy:
        """
        Create attendance policy for hostel.

        Args:
            hostel_id: Hostel identifier
            minimum_attendance_percentage: Minimum required percentage
            late_entry_threshold_minutes: Late threshold in minutes
            grace_period_minutes: Grace period for late entries
            grace_days_per_month: Grace days allowed per month
            consecutive_absence_alert_days: Consecutive absence threshold
            total_absence_alert_threshold: Total absence threshold
            **kwargs: Additional policy parameters

        Returns:
            Created policy

        Raises:
            ValidationError: If validation fails
            BusinessLogicError: If policy already exists
        """
        try:
            policy = self.policy_repo.create_policy(
                hostel_id=hostel_id,
                minimum_attendance_percentage=minimum_attendance_percentage,
                late_entry_threshold_minutes=late_entry_threshold_minutes,
                grace_period_minutes=grace_period_minutes,
                grace_days_per_month=grace_days_per_month,
                consecutive_absence_alert_days=consecutive_absence_alert_days,
                total_absence_alert_threshold=total_absence_alert_threshold,
                **kwargs,
            )

            self.session.commit()
            logger.info(f"Attendance policy created for hostel {hostel_id}")

            return policy

        except Exception as e:
            self.session.rollback()
            logger.error(f"Error creating attendance policy: {str(e)}")
            raise

    def update_policy(
        self,
        policy_id: UUID,
        **update_data: Any,
    ) -> AttendancePolicy:
        """
        Update attendance policy.

        Args:
            policy_id: Policy identifier
            **update_data: Fields to update

        Returns:
            Updated policy

        Raises:
            NotFoundError: If policy not found
        """
        try:
            policy = self.policy_repo.update_policy(
                policy_id=policy_id,
                **update_data,
            )

            self.session.commit()
            logger.info(f"Attendance policy {policy_id} updated")

            return policy

        except Exception as e:
            self.session.rollback()
            logger.error(f"Error updating policy: {str(e)}")
            raise

    def get_policy_by_id(
        self,
        policy_id: UUID,
        include_relationships: bool = False,
    ) -> Optional[AttendancePolicy]:
        """
        Get policy by ID.

        Args:
            policy_id: Policy identifier
            include_relationships: Load related entities

        Returns:
            Policy if found
        """
        return self.policy_repo.get_by_id(
            policy_id=policy_id,
            load_relationships=include_relationships,
        )

    def get_hostel_policy(
        self,
        hostel_id: UUID,
        include_inactive: bool = False,
    ) -> Optional[AttendancePolicy]:
        """
        Get active policy for hostel.

        Args:
            hostel_id: Hostel identifier
            include_inactive: Include inactive policies

        Returns:
            Policy if found
        """
        return self.policy_repo.get_by_hostel(
            hostel_id=hostel_id,
            include_inactive=include_inactive,
        )

    def deactivate_policy(
        self,
        policy_id: UUID,
    ) -> AttendancePolicy:
        """
        Deactivate policy.

        Args:
            policy_id: Policy identifier

        Returns:
            Deactivated policy
        """
        try:
            policy = self.policy_repo.deactivate_policy(policy_id)
            self.session.commit()
            logger.info(f"Policy {policy_id} deactivated")
            return policy

        except Exception as e:
            self.session.rollback()
            logger.error(f"Error deactivating policy: {str(e)}")
            raise

    # ==================== Policy Validation ====================

    def validate_attendance_percentage(
        self,
        hostel_id: UUID,
        percentage: Decimal,
    ) -> Dict[str, Any]:
        """
        Validate if attendance percentage meets requirements.

        Args:
            hostel_id: Hostel identifier
            percentage: Attendance percentage to validate

        Returns:
            Validation result dictionary
        """
        return self.policy_repo.validate_attendance_percentage(
            hostel_id=hostel_id,
            percentage=percentage,
        )

    def check_consecutive_absence_violation(
        self,
        hostel_id: UUID,
        consecutive_days: int,
    ) -> Dict[str, Any]:
        """
        Check if consecutive absences violate policy.

        Args:
            hostel_id: Hostel identifier
            consecutive_days: Number of consecutive days

        Returns:
            Violation check result
        """
        return self.policy_repo.check_consecutive_absence_violation(
            hostel_id=hostel_id,
            consecutive_days=consecutive_days,
        )

    def check_late_entry_violation(
        self,
        hostel_id: UUID,
        late_minutes: int,
        late_count_this_month: int,
    ) -> Dict[str, Any]:
        """
        Check if late entry violates policy.

        Args:
            hostel_id: Hostel identifier
            late_minutes: Minutes late
            late_count_this_month: Late count this month

        Returns:
            Violation check result
        """
        return self.policy_repo.check_late_entry_violation(
            hostel_id=hostel_id,
            late_minutes=late_minutes,
            late_count_this_month=late_count_this_month,
        )

    # ==================== Violation Management ====================

    def create_violation(
        self,
        policy_id: UUID,
        student_id: UUID,
        violation_type: str,
        severity: str,
        violation_date: date,
        **kwargs: Any,
    ) -> PolicyViolation:
        """
        Create policy violation record.

        Args:
            policy_id: Policy identifier
            student_id: Student identifier
            violation_type: Type of violation
            severity: Severity level
            violation_date: Date of violation
            **kwargs: Additional violation data

        Returns:
            Created violation
        """
        try:
            violation = self.policy_repo.create_violation(
                policy_id=policy_id,
                student_id=student_id,
                violation_type=violation_type,
                severity=severity,
                violation_date=violation_date,
                **kwargs,
            )

            self.session.commit()
            logger.info(
                f"Policy violation created for student {student_id}: {violation_type}"
            )

            return violation

        except Exception as e:
            self.session.rollback()
            logger.error(f"Error creating violation: {str(e)}")
            raise

    def get_student_violations(
        self,
        student_id: UUID,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        unresolved_only: bool = False,
    ) -> List[PolicyViolation]:
        """
        Get violations for student.

        Args:
            student_id: Student identifier
            start_date: Optional start date
            end_date: Optional end date
            unresolved_only: Only unresolved violations

        Returns:
            List of violations
        """
        return self.policy_repo.get_student_violations(
            student_id=student_id,
            start_date=start_date,
            end_date=end_date,
            unresolved_only=unresolved_only,
        )

    def mark_violation_notified(
        self,
        violation_id: UUID,
        guardian_notified: bool = False,
        admin_notified: bool = False,
        student_notified: bool = False,
        warning_issued: bool = False,
    ) -> PolicyViolation:
        """
        Mark violation as notified.

        Args:
            violation_id: Violation identifier
            guardian_notified: Guardian notified flag
            admin_notified: Admin notified flag
            student_notified: Student notified flag
            warning_issued: Warning issued flag

        Returns:
            Updated violation
        """
        try:
            violation = self.policy_repo.mark_violation_notified(
                violation_id=violation_id,
                guardian_notified=guardian_notified,
                admin_notified=admin_notified,
                student_notified=student_notified,
                warning_issued=warning_issued,
            )

            self.session.commit()
            logger.info(f"Violation {violation_id} marked as notified")

            return violation

        except Exception as e:
            self.session.rollback()
            logger.error(f"Error marking violation notified: {str(e)}")
            raise

    def resolve_violation(
        self,
        violation_id: UUID,
        resolution_notes: str,
    ) -> PolicyViolation:
        """
        Resolve policy violation.

        Args:
            violation_id: Violation identifier
            resolution_notes: Resolution details

        Returns:
            Resolved violation
        """
        try:
            violation = self.policy_repo.resolve_violation(
                violation_id=violation_id,
                resolution_notes=resolution_notes,
            )

            self.session.commit()
            logger.info(f"Violation {violation_id} resolved")

            return violation

        except Exception as e:
            self.session.rollback()
            logger.error(f"Error resolving violation: {str(e)}")
            raise

    def get_unresolved_violations(
        self,
        hostel_id: Optional[UUID] = None,
        severity: Optional[str] = None,
    ) -> List[PolicyViolation]:
        """
        Get unresolved violations.

        Args:
            hostel_id: Optional hostel filter
            severity: Optional severity filter

        Returns:
            List of unresolved violations
        """
        return self.policy_repo.get_unresolved_violations(
            hostel_id=hostel_id,
            severity=severity,
        )

    # ==================== Exception Management ====================

    def create_exception(
        self,
        policy_id: UUID,
        student_id: UUID,
        created_by: UUID,
        exception_type: str,
        reason: str,
        valid_from: date,
        valid_until: date,
        auto_approve: bool = False,
        approved_by: Optional[UUID] = None,
    ) -> PolicyException:
        """
        Create policy exception.

        Args:
            policy_id: Policy identifier
            student_id: Student identifier
            created_by: Creator user ID
            exception_type: Type of exception
            reason: Exception reason
            valid_from: Start date
            valid_until: End date
            auto_approve: Auto-approve flag
            approved_by: Approver user ID

        Returns:
            Created exception
        """
        try:
            is_approved = auto_approve and approved_by is not None

            exception = self.policy_repo.create_exception(
                policy_id=policy_id,
                student_id=student_id,
                created_by=created_by,
                exception_type=exception_type,
                reason=reason,
                valid_from=valid_from,
                valid_until=valid_until,
                is_approved=is_approved,
                approved_by=approved_by if is_approved else None,
            )

            self.session.commit()
            logger.info(
                f"Policy exception created for student {student_id}: {exception_type}"
            )

            return exception

        except Exception as e:
            self.session.rollback()
            logger.error(f"Error creating exception: {str(e)}")
            raise

    def approve_exception(
        self,
        exception_id: UUID,
        approved_by: UUID,
        approval_notes: Optional[str] = None,
    ) -> PolicyException:
        """
        Approve policy exception.

        Args:
            exception_id: Exception identifier
            approved_by: Approver user ID
            approval_notes: Approval notes

        Returns:
            Approved exception
        """
        try:
            exception = self.policy_repo.approve_exception(
                exception_id=exception_id,
                approved_by=approved_by,
                approval_notes=approval_notes,
            )

            self.session.commit()
            logger.info(f"Policy exception {exception_id} approved")

            return exception

        except Exception as e:
            self.session.rollback()
            logger.error(f"Error approving exception: {str(e)}")
            raise

    def revoke_exception(
        self,
        exception_id: UUID,
        revoked_by: UUID,
        revocation_reason: str,
    ) -> PolicyException:
        """
        Revoke policy exception.

        Args:
            exception_id: Exception identifier
            revoked_by: Revoker user ID
            revocation_reason: Revocation reason

        Returns:
            Revoked exception
        """
        try:
            exception = self.policy_repo.revoke_exception(
                exception_id=exception_id,
                revoked_by=revoked_by,
                revocation_reason=revocation_reason,
            )

            self.session.commit()
            logger.info(f"Policy exception {exception_id} revoked")

            return exception

        except Exception as e:
            self.session.rollback()
            logger.error(f"Error revoking exception: {str(e)}")
            raise

    def get_student_exceptions(
        self,
        student_id: UUID,
        active_only: bool = True,
        as_of_date: Optional[date] = None,
    ) -> List[PolicyException]:
        """
        Get exceptions for student.

        Args:
            student_id: Student identifier
            active_only: Only active exceptions
            as_of_date: Check validity as of date

        Returns:
            List of exceptions
        """
        return self.policy_repo.get_student_exceptions(
            student_id=student_id,
            active_only=active_only,
            as_of_date=as_of_date,
        )

    def check_active_exception(
        self,
        student_id: UUID,
        exception_type: str,
        check_date: date,
    ) -> Optional[PolicyException]:
        """
        Check if student has active exception.

        Args:
            student_id: Student identifier
            exception_type: Exception type
            check_date: Date to check

        Returns:
            Active exception if found
        """
        return self.policy_repo.check_active_exception(
            student_id=student_id,
            exception_type=exception_type,
            check_date=check_date,
        )

    def get_expiring_exceptions(
        self,
        days_before_expiry: int = 7,
    ) -> List[PolicyException]:
        """
        Get exceptions expiring soon.

        Args:
            days_before_expiry: Days before expiry

        Returns:
            List of expiring exceptions
        """
        return self.policy_repo.get_expiring_exceptions(
            days_before_expiry=days_before_expiry
        )

    # ==================== Statistics ====================

    def get_violation_statistics(
        self,
        hostel_id: Optional[UUID] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> Dict[str, Any]:
        """
        Get violation statistics.

        Args:
            hostel_id: Optional hostel filter
            start_date: Optional start date
            end_date: Optional end date

        Returns:
            Statistics dictionary
        """
        return self.policy_repo.get_violation_statistics(
            hostel_id=hostel_id,
            start_date=start_date,
            end_date=end_date,
        )

    def get_exception_statistics(
        self,
        hostel_id: Optional[UUID] = None,
    ) -> Dict[str, Any]:
        """
        Get exception statistics.

        Args:
            hostel_id: Optional hostel filter

        Returns:
            Statistics dictionary
        """
        return self.policy_repo.get_exception_statistics(
            hostel_id=hostel_id
        )