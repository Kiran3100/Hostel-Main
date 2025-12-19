# --- File: app/repositories/attendance/attendance_policy_repository.py ---
"""
Attendance policy repository with comprehensive policy management.

Provides CRUD operations, violation tracking, exception management,
and policy enforcement for attendance policies.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID

from sqlalchemy import and_, or_, func, case
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.attendance.attendance_policy import (
    AttendancePolicy,
    PolicyViolation,
    PolicyException,
)
from app.repositories.base.base_repository import BaseRepository
from app.core.exceptions import ValidationError, NotFoundError, ConflictError


class AttendancePolicyRepository(BaseRepository[AttendancePolicy]):
    """
    Repository for attendance policy operations with validation.
    """

    def __init__(self, session: Session):
        """
        Initialize repository with database session.

        Args:
            session: SQLAlchemy database session
        """
        super().__init__(AttendancePolicy, session)

    # ==================== Core CRUD Operations ====================

    def create_policy(
        self,
        hostel_id: UUID,
        minimum_attendance_percentage: Decimal = Decimal("75.00"),
        late_entry_threshold_minutes: int = 15,
        grace_period_minutes: int = 5,
        grace_days_per_month: int = 3,
        consecutive_absence_alert_days: int = 3,
        total_absence_alert_threshold: int = 10,
        notify_guardian_on_absence: bool = True,
        notify_admin_on_low_attendance: bool = True,
        notify_student_on_low_attendance: bool = True,
        low_attendance_threshold: Decimal = Decimal("75.00"),
        auto_mark_absent_enabled: bool = False,
        auto_mark_absent_after_time: Optional[datetime] = None,
        track_weekend_attendance: bool = False,
        track_holiday_attendance: bool = False,
        calculation_period: str = "monthly",
        include_weekends: bool = False,
        exclude_holidays: bool = True,
        count_leave_as_absent: bool = False,
        count_leave_as_present: bool = True,
        max_leaves_per_month: int = 3,
        is_active: bool = True,
        effective_from: Optional[date] = None,
        effective_until: Optional[date] = None,
        extended_config: Optional[Dict[str, Any]] = None,
    ) -> AttendancePolicy:
        """
        Create new attendance policy for hostel.

        Args:
            hostel_id: Hostel identifier
            (other parameters match model fields)

        Returns:
            Created attendance policy

        Raises:
            ConflictError: If policy already exists for hostel
            ValidationError: If validation fails
        """
        # Check for existing policy
        existing = self.get_by_hostel(hostel_id)
        if existing:
            raise ConflictError(
                f"Attendance policy already exists for hostel {hostel_id}"
            )

        # Validate percentages
        if not (0 <= minimum_attendance_percentage <= 100):
            raise ValidationError("Minimum attendance percentage must be between 0 and 100")
        
        if not (0 <= low_attendance_threshold <= 100):
            raise ValidationError("Low attendance threshold must be between 0 and 100")

        # Create policy
        policy = AttendancePolicy(
            hostel_id=hostel_id,
            minimum_attendance_percentage=minimum_attendance_percentage,
            late_entry_threshold_minutes=late_entry_threshold_minutes,
            grace_period_minutes=grace_period_minutes,
            grace_days_per_month=grace_days_per_month,
            consecutive_absence_alert_days=consecutive_absence_alert_days,
            total_absence_alert_threshold=total_absence_alert_threshold,
            notify_guardian_on_absence=notify_guardian_on_absence,
            notify_admin_on_low_attendance=notify_admin_on_low_attendance,
            notify_student_on_low_attendance=notify_student_on_low_attendance,
            low_attendance_threshold=low_attendance_threshold,
            auto_mark_absent_enabled=auto_mark_absent_enabled,
            auto_mark_absent_after_time=auto_mark_absent_after_time,
            track_weekend_attendance=track_weekend_attendance,
            track_holiday_attendance=track_holiday_attendance,
            calculation_period=calculation_period,
            include_weekends=include_weekends,
            exclude_holidays=exclude_holidays,
            count_leave_as_absent=count_leave_as_absent,
            count_leave_as_present=count_leave_as_present,
            max_leaves_per_month=max_leaves_per_month,
            is_active=is_active,
            effective_from=effective_from,
            effective_until=effective_until,
            extended_config=extended_config,
        )

        self.session.add(policy)
        self.session.flush()
        return policy

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
            ValidationError: If validation fails
        """
        policy = self.get_by_id(policy_id)
        if not policy:
            raise NotFoundError(f"Attendance policy {policy_id} not found")

        # Validate percentages if being updated
        if 'minimum_attendance_percentage' in update_data:
            value = update_data['minimum_attendance_percentage']
            if not (0 <= value <= 100):
                raise ValidationError("Minimum attendance percentage must be between 0 and 100")

        if 'low_attendance_threshold' in update_data:
            value = update_data['low_attendance_threshold']
            if not (0 <= value <= 100):
                raise ValidationError("Low attendance threshold must be between 0 and 100")

        # Update fields
        for key, value in update_data.items():
            if hasattr(policy, key):
                setattr(policy, key, value)

        self.session.flush()
        return policy

    def get_by_id(
        self,
        policy_id: UUID,
        load_relationships: bool = False,
    ) -> Optional[AttendancePolicy]:
        """
        Get policy by ID.

        Args:
            policy_id: Policy identifier
            load_relationships: Whether to load relationships

        Returns:
            Policy if found
        """
        query = self.session.query(AttendancePolicy).filter(
            AttendancePolicy.id == policy_id
        )

        if load_relationships:
            query = query.options(
                joinedload(AttendancePolicy.hostel),
                selectinload(AttendancePolicy.violations),
                selectinload(AttendancePolicy.exceptions),
            )

        return query.first()

    def get_by_hostel(
        self,
        hostel_id: UUID,
        include_inactive: bool = False,
    ) -> Optional[AttendancePolicy]:
        """
        Get active policy for hostel.

        Args:
            hostel_id: Hostel identifier
            include_inactive: Whether to include inactive policies

        Returns:
            Policy if found
        """
        query = self.session.query(AttendancePolicy).filter(
            AttendancePolicy.hostel_id == hostel_id
        )

        if not include_inactive:
            query = query.filter(AttendancePolicy.is_active == True)

        return query.first()

    def get_all_active_policies(self) -> List[AttendancePolicy]:
        """
        Get all active policies.

        Returns:
            List of active policies
        """
        return self.session.query(AttendancePolicy).filter(
            AttendancePolicy.is_active == True
        ).all()

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

        Raises:
            NotFoundError: If policy not found
        """
        policy = self.get_by_id(policy_id)
        if not policy:
            raise NotFoundError(f"Attendance policy {policy_id} not found")

        policy.is_active = False
        self.session.flush()
        return policy

    # ==================== Policy Validation ====================

    def validate_attendance_percentage(
        self,
        hostel_id: UUID,
        percentage: Decimal,
    ) -> Dict[str, Any]:
        """
        Validate if attendance percentage meets policy requirements.

        Args:
            hostel_id: Hostel identifier
            percentage: Attendance percentage to validate

        Returns:
            Dictionary with validation results
        """
        policy = self.get_by_hostel(hostel_id)
        if not policy:
            return {
                "valid": True,
                "message": "No policy configured",
                "meets_minimum": True,
            }

        meets_minimum = percentage >= policy.minimum_attendance_percentage
        is_low = percentage < policy.low_attendance_threshold

        return {
            "valid": meets_minimum,
            "meets_minimum": meets_minimum,
            "is_low_attendance": is_low,
            "required_percentage": float(policy.minimum_attendance_percentage),
            "low_threshold": float(policy.low_attendance_threshold),
            "current_percentage": float(percentage),
            "message": self._get_validation_message(percentage, policy),
        }

    def check_consecutive_absence_violation(
        self,
        hostel_id: UUID,
        consecutive_days: int,
    ) -> Dict[str, Any]:
        """
        Check if consecutive absences violate policy.

        Args:
            hostel_id: Hostel identifier
            consecutive_days: Number of consecutive absent days

        Returns:
            Dictionary with violation check results
        """
        policy = self.get_by_hostel(hostel_id)
        if not policy:
            return {"violation": False, "message": "No policy configured"}

        violates = consecutive_days >= policy.consecutive_absence_alert_days

        return {
            "violation": violates,
            "consecutive_days": consecutive_days,
            "threshold": policy.consecutive_absence_alert_days,
            "message": f"Consecutive absences: {consecutive_days} (Threshold: {policy.consecutive_absence_alert_days})",
        }

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
            late_count_this_month: Late entries this month

        Returns:
            Dictionary with violation check results
        """
        policy = self.get_by_hostel(hostel_id)
        if not policy:
            return {"violation": False, "message": "No policy configured"}

        # Check if within grace period
        within_grace = late_minutes <= policy.grace_period_minutes
        
        # Check if within grace days
        within_grace_days = late_count_this_month < policy.grace_days_per_month

        is_late = late_minutes > policy.grace_period_minutes
        violates_threshold = late_minutes >= policy.late_entry_threshold_minutes

        return {
            "is_late": is_late,
            "violation": violates_threshold and not (within_grace and within_grace_days),
            "within_grace_period": within_grace,
            "within_grace_days": within_grace_days,
            "late_minutes": late_minutes,
            "threshold_minutes": policy.late_entry_threshold_minutes,
            "grace_period_minutes": policy.grace_period_minutes,
            "late_count_this_month": late_count_this_month,
            "grace_days_per_month": policy.grace_days_per_month,
        }

    # ==================== Policy Violation Management ====================

    def create_violation(
        self,
        policy_id: UUID,
        student_id: UUID,
        violation_type: str,
        severity: str,
        violation_date: date,
        current_attendance_percentage: Optional[Decimal] = None,
        required_attendance_percentage: Optional[Decimal] = None,
        consecutive_absences: Optional[int] = None,
        late_entries_this_month: Optional[int] = None,
        total_absences_this_month: Optional[int] = None,
        first_violation_date: Optional[date] = None,
        notes: Optional[str] = None,
        action_plan: Optional[str] = None,
    ) -> PolicyViolation:
        """
        Create policy violation record.

        Args:
            policy_id: Policy identifier
            student_id: Student identifier
            violation_type: Type of violation
            severity: Severity level
            violation_date: Date of violation
            (other parameters match model fields)

        Returns:
            Created violation record

        Raises:
            NotFoundError: If policy not found
        """
        policy = self.get_by_id(policy_id)
        if not policy:
            raise NotFoundError(f"Attendance policy {policy_id} not found")

        violation = PolicyViolation(
            policy_id=policy_id,
            student_id=student_id,
            violation_type=violation_type,
            severity=severity,
            violation_date=violation_date,
            current_attendance_percentage=current_attendance_percentage,
            required_attendance_percentage=required_attendance_percentage,
            consecutive_absences=consecutive_absences,
            late_entries_this_month=late_entries_this_month,
            total_absences_this_month=total_absences_this_month,
            first_violation_date=first_violation_date or violation_date,
            notes=notes,
            action_plan=action_plan,
        )

        self.session.add(violation)
        self.session.flush()
        return violation

    def get_violation_by_id(
        self,
        violation_id: UUID,
    ) -> Optional[PolicyViolation]:
        """
        Get violation by ID.

        Args:
            violation_id: Violation identifier

        Returns:
            Violation if found
        """
        return self.session.query(PolicyViolation).filter(
            PolicyViolation.id == violation_id
        ).options(
            joinedload(PolicyViolation.policy),
            joinedload(PolicyViolation.student),
        ).first()

    def get_student_violations(
        self,
        student_id: UUID,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        violation_type: Optional[str] = None,
        resolved_only: bool = False,
        unresolved_only: bool = False,
    ) -> List[PolicyViolation]:
        """
        Get violations for student with optional filters.

        Args:
            student_id: Student identifier
            start_date: Start date filter
            end_date: End date filter
            violation_type: Type filter
            resolved_only: Only resolved violations
            unresolved_only: Only unresolved violations

        Returns:
            List of violations
        """
        query = self.session.query(PolicyViolation).filter(
            PolicyViolation.student_id == student_id
        )

        if start_date:
            query = query.filter(PolicyViolation.violation_date >= start_date)
        if end_date:
            query = query.filter(PolicyViolation.violation_date <= end_date)
        if violation_type:
            query = query.filter(PolicyViolation.violation_type == violation_type)
        if resolved_only:
            query = query.filter(PolicyViolation.resolved == True)
        if unresolved_only:
            query = query.filter(PolicyViolation.resolved == False)

        return query.order_by(PolicyViolation.violation_date.desc()).all()

    def get_policy_violations(
        self,
        policy_id: UUID,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        severity: Optional[str] = None,
    ) -> List[PolicyViolation]:
        """
        Get violations for policy.

        Args:
            policy_id: Policy identifier
            start_date: Start date filter
            end_date: End date filter
            severity: Severity filter

        Returns:
            List of violations
        """
        query = self.session.query(PolicyViolation).filter(
            PolicyViolation.policy_id == policy_id
        )

        if start_date:
            query = query.filter(PolicyViolation.violation_date >= start_date)
        if end_date:
            query = query.filter(PolicyViolation.violation_date <= end_date)
        if severity:
            query = query.filter(PolicyViolation.severity == severity)

        return query.order_by(PolicyViolation.violation_date.desc()).all()

    def update_violation(
        self,
        violation_id: UUID,
        **update_data: Any,
    ) -> PolicyViolation:
        """
        Update violation record.

        Args:
            violation_id: Violation identifier
            **update_data: Fields to update

        Returns:
            Updated violation

        Raises:
            NotFoundError: If violation not found
        """
        violation = self.get_violation_by_id(violation_id)
        if not violation:
            raise NotFoundError(f"Policy violation {violation_id} not found")

        for key, value in update_data.items():
            if hasattr(violation, key):
                setattr(violation, key, value)

        self.session.flush()
        return violation

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
            guardian_notified: Guardian notification flag
            admin_notified: Admin notification flag
            student_notified: Student notification flag
            warning_issued: Warning issued flag

        Returns:
            Updated violation
        """
        violation = self.get_violation_by_id(violation_id)
        if not violation:
            raise NotFoundError(f"Policy violation {violation_id} not found")

        now = datetime.utcnow()

        if guardian_notified:
            violation.guardian_notified = True
            violation.guardian_notified_at = now
        if admin_notified:
            violation.admin_notified = True
            violation.admin_notified_at = now
        if student_notified:
            violation.student_notified = True
        if warning_issued:
            violation.warning_issued = True
            violation.warning_issued_at = now

        self.session.flush()
        return violation

    def resolve_violation(
        self,
        violation_id: UUID,
        resolution_notes: str,
    ) -> PolicyViolation:
        """
        Resolve violation.

        Args:
            violation_id: Violation identifier
            resolution_notes: Resolution details

        Returns:
            Resolved violation

        Raises:
            NotFoundError: If violation not found
        """
        violation = self.get_violation_by_id(violation_id)
        if not violation:
            raise NotFoundError(f"Policy violation {violation_id} not found")

        violation.resolved = True
        violation.resolved_at = datetime.utcnow()
        violation.resolution_notes = resolution_notes

        self.session.flush()
        return violation

    def get_unresolved_violations(
        self,
        hostel_id: Optional[UUID] = None,
        severity: Optional[str] = None,
    ) -> List[PolicyViolation]:
        """
        Get all unresolved violations.

        Args:
            hostel_id: Optional hostel filter
            severity: Optional severity filter

        Returns:
            List of unresolved violations
        """
        query = self.session.query(PolicyViolation).filter(
            PolicyViolation.resolved == False
        )

        if hostel_id:
            query = query.join(AttendancePolicy).filter(
                AttendancePolicy.hostel_id == hostel_id
            )

        if severity:
            query = query.filter(PolicyViolation.severity == severity)

        return query.order_by(PolicyViolation.violation_date.asc()).all()

    # ==================== Policy Exception Management ====================

    def create_exception(
        self,
        policy_id: UUID,
        student_id: UUID,
        created_by: UUID,
        exception_type: str,
        reason: str,
        valid_from: date,
        valid_until: date,
        is_approved: bool = False,
        approved_by: Optional[UUID] = None,
        approval_notes: Optional[str] = None,
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
            is_approved: Approval status
            approved_by: Approver user ID
            approval_notes: Approval notes

        Returns:
            Created exception

        Raises:
            NotFoundError: If policy not found
            ValidationError: If dates invalid
        """
        policy = self.get_by_id(policy_id)
        if not policy:
            raise NotFoundError(f"Attendance policy {policy_id} not found")

        if valid_until < valid_from:
            raise ValidationError("valid_until must be >= valid_from")

        exception = PolicyException(
            policy_id=policy_id,
            student_id=student_id,
            created_by=created_by,
            exception_type=exception_type,
            reason=reason,
            valid_from=valid_from,
            valid_until=valid_until,
            is_approved=is_approved,
            approved_by=approved_by,
            approved_at=datetime.utcnow() if is_approved and approved_by else None,
            approval_notes=approval_notes,
        )

        self.session.add(exception)
        self.session.flush()
        return exception

    def get_exception_by_id(
        self,
        exception_id: UUID,
    ) -> Optional[PolicyException]:
        """
        Get exception by ID.

        Args:
            exception_id: Exception identifier

        Returns:
            Exception if found
        """
        return self.session.query(PolicyException).filter(
            PolicyException.id == exception_id
        ).options(
            joinedload(PolicyException.policy),
            joinedload(PolicyException.student),
        ).first()

    def get_student_exceptions(
        self,
        student_id: UUID,
        active_only: bool = True,
        approved_only: bool = True,
        as_of_date: Optional[date] = None,
    ) -> List[PolicyException]:
        """
        Get exceptions for student.

        Args:
            student_id: Student identifier
            active_only: Only active exceptions
            approved_only: Only approved exceptions
            as_of_date: Check validity as of date

        Returns:
            List of exceptions
        """
        query = self.session.query(PolicyException).filter(
            PolicyException.student_id == student_id
        )

        if active_only:
            query = query.filter(
                and_(
                    PolicyException.is_active == True,
                    PolicyException.revoked == False,
                )
            )

        if approved_only:
            query = query.filter(PolicyException.is_approved == True)

        if as_of_date:
            query = query.filter(
                and_(
                    PolicyException.valid_from <= as_of_date,
                    PolicyException.valid_until >= as_of_date,
                )
            )

        return query.order_by(PolicyException.valid_from.desc()).all()

    def check_active_exception(
        self,
        student_id: UUID,
        exception_type: str,
        check_date: date,
    ) -> Optional[PolicyException]:
        """
        Check if student has active exception of type on date.

        Args:
            student_id: Student identifier
            exception_type: Exception type
            check_date: Date to check

        Returns:
            Active exception if found
        """
        return self.session.query(PolicyException).filter(
            and_(
                PolicyException.student_id == student_id,
                PolicyException.exception_type == exception_type,
                PolicyException.is_active == True,
                PolicyException.is_approved == True,
                PolicyException.revoked == False,
                PolicyException.valid_from <= check_date,
                PolicyException.valid_until >= check_date,
            )
        ).first()

    def approve_exception(
        self,
        exception_id: UUID,
        approved_by: UUID,
        approval_notes: Optional[str] = None,
    ) -> PolicyException:
        """
        Approve exception.

        Args:
            exception_id: Exception identifier
            approved_by: Approver user ID
            approval_notes: Approval notes

        Returns:
            Approved exception

        Raises:
            NotFoundError: If exception not found
        """
        exception = self.get_exception_by_id(exception_id)
        if not exception:
            raise NotFoundError(f"Policy exception {exception_id} not found")

        exception.is_approved = True
        exception.approved_by = approved_by
        exception.approved_at = datetime.utcnow()
        exception.approval_notes = approval_notes

        self.session.flush()
        return exception

    def revoke_exception(
        self,
        exception_id: UUID,
        revoked_by: UUID,
        revocation_reason: str,
    ) -> PolicyException:
        """
        Revoke exception.

        Args:
            exception_id: Exception identifier
            revoked_by: Revoker user ID
            revocation_reason: Revocation reason

        Returns:
            Revoked exception

        Raises:
            NotFoundError: If exception not found
        """
        exception = self.get_exception_by_id(exception_id)
        if not exception:
            raise NotFoundError(f"Policy exception {exception_id} not found")

        exception.revoked = True
        exception.revoked_at = datetime.utcnow()
        exception.revoked_by = revoked_by
        exception.revocation_reason = revocation_reason
        exception.is_active = False

        self.session.flush()
        return exception

    def get_expiring_exceptions(
        self,
        days_before_expiry: int = 7,
    ) -> List[PolicyException]:
        """
        Get exceptions expiring within specified days.

        Args:
            days_before_expiry: Days before expiry to check

        Returns:
            List of expiring exceptions
        """
        expiry_date = date.today() + timedelta(days=days_before_expiry)

        return self.session.query(PolicyException).filter(
            and_(
                PolicyException.is_active == True,
                PolicyException.is_approved == True,
                PolicyException.revoked == False,
                PolicyException.valid_until <= expiry_date,
                PolicyException.valid_until >= date.today(),
            )
        ).order_by(PolicyException.valid_until.asc()).all()

    # ==================== Statistics and Analytics ====================

    def get_violation_statistics(
        self,
        policy_id: Optional[UUID] = None,
        hostel_id: Optional[UUID] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> Dict[str, Any]:
        """
        Get violation statistics.

        Args:
            policy_id: Optional policy filter
            hostel_id: Optional hostel filter
            start_date: Optional start date
            end_date: Optional end date

        Returns:
            Dictionary with statistics
        """
        query = self.session.query(PolicyViolation)

        if policy_id:
            query = query.filter(PolicyViolation.policy_id == policy_id)
        elif hostel_id:
            query = query.join(AttendancePolicy).filter(
                AttendancePolicy.hostel_id == hostel_id
            )

        if start_date:
            query = query.filter(PolicyViolation.violation_date >= start_date)
        if end_date:
            query = query.filter(PolicyViolation.violation_date <= end_date)

        total_violations = query.count()
        resolved_violations = query.filter(PolicyViolation.resolved == True).count()
        unresolved_violations = total_violations - resolved_violations

        # Count by severity
        severity_counts = dict(
            self.session.query(
                PolicyViolation.severity,
                func.count(PolicyViolation.id),
            ).filter(
                PolicyViolation.id.in_([v.id for v in query.all()])
            ).group_by(PolicyViolation.severity).all()
        )

        # Count by type
        type_counts = dict(
            self.session.query(
                PolicyViolation.violation_type,
                func.count(PolicyViolation.id),
            ).filter(
                PolicyViolation.id.in_([v.id for v in query.all()])
            ).group_by(PolicyViolation.violation_type).all()
        )

        return {
            "total_violations": total_violations,
            "resolved_violations": resolved_violations,
            "unresolved_violations": unresolved_violations,
            "resolution_rate": round(
                (resolved_violations / total_violations * 100) if total_violations > 0 else 0,
                2,
            ),
            "by_severity": severity_counts,
            "by_type": type_counts,
        }

    def get_exception_statistics(
        self,
        policy_id: Optional[UUID] = None,
        hostel_id: Optional[UUID] = None,
    ) -> Dict[str, Any]:
        """
        Get exception statistics.

        Args:
            policy_id: Optional policy filter
            hostel_id: Optional hostel filter

        Returns:
            Dictionary with statistics
        """
        query = self.session.query(PolicyException)

        if policy_id:
            query = query.filter(PolicyException.policy_id == policy_id)
        elif hostel_id:
            query = query.join(AttendancePolicy).filter(
                AttendancePolicy.hostel_id == hostel_id
            )

        total_exceptions = query.count()
        active_exceptions = query.filter(
            and_(
                PolicyException.is_active == True,
                PolicyException.revoked == False,
            )
        ).count()
        approved_exceptions = query.filter(
            PolicyException.is_approved == True
        ).count()
        pending_approval = query.filter(
            PolicyException.is_approved == False
        ).count()
        revoked_exceptions = query.filter(
            PolicyException.revoked == True
        ).count()

        return {
            "total_exceptions": total_exceptions,
            "active_exceptions": active_exceptions,
            "approved_exceptions": approved_exceptions,
            "pending_approval": pending_approval,
            "revoked_exceptions": revoked_exceptions,
            "approval_rate": round(
                (approved_exceptions / total_exceptions * 100) if total_exceptions > 0 else 0,
                2,
            ),
        }

    # ==================== Helper Methods ====================

    def _get_validation_message(
        self,
        percentage: Decimal,
        policy: AttendancePolicy,
    ) -> str:
        """Generate validation message based on percentage and policy."""
        if percentage >= policy.minimum_attendance_percentage:
            if percentage < policy.low_attendance_threshold:
                return f"Attendance is low ({percentage}%). Minimum required: {policy.minimum_attendance_percentage}%"
            return f"Attendance meets requirements ({percentage}%)"
        else:
            return f"Attendance below minimum ({percentage}%). Required: {policy.minimum_attendance_percentage}%"


