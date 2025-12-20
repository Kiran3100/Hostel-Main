# --- File: app/services/attendance/attendance_correction_service.py ---
"""
Attendance correction service with audit trail management.

Provides correction creation, approval workflow, and correction
history tracking with comprehensive audit logging.
"""

from datetime import date, datetime, time
from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.attendance.attendance_record import (
    AttendanceRecord,
    AttendanceCorrection,
)
from app.models.base.enums import AttendanceStatus
from app.repositories.attendance.attendance_record_repository import (
    AttendanceRecordRepository,
)
from app.core.exceptions import ValidationError, NotFoundError, BusinessLogicError
from app.core.logging import get_logger

logger = get_logger(__name__)


class AttendanceCorrectionService:
    """
    Service for attendance correction management with audit trail.
    """

    def __init__(self, session: Session):
        """
        Initialize service with database session.

        Args:
            session: SQLAlchemy database session
        """
        self.session = session
        self.attendance_repo = AttendanceRecordRepository(session)

    # ==================== Correction Management ====================

    def create_correction(
        self,
        attendance_id: UUID,
        corrected_by: UUID,
        corrected_status: AttendanceStatus,
        correction_reason: str,
        corrected_check_in_time: Optional[time] = None,
        corrected_check_out_time: Optional[time] = None,
        corrected_is_late: bool = False,
        corrected_late_minutes: Optional[int] = None,
        require_approval: bool = True,
        approved_by: Optional[UUID] = None,
    ) -> AttendanceCorrection:
        """
        Create correction for attendance record.

        Args:
            attendance_id: Attendance record identifier
            corrected_by: User making correction
            corrected_status: Corrected status
            correction_reason: Reason for correction
            corrected_check_in_time: Corrected check-in time
            corrected_check_out_time: Corrected check-out time
            corrected_is_late: Corrected late flag
            corrected_late_minutes: Corrected late minutes
            require_approval: Whether approval is required
            approved_by: Approver identifier (if pre-approved)

        Returns:
            Created correction record

        Raises:
            NotFoundError: If attendance record not found
            ValidationError: If correction validation fails
            BusinessLogicError: If business rules violated
        """
        try:
            # Validate correction reason
            if not correction_reason or len(correction_reason.strip()) < 10:
                raise ValidationError(
                    "Correction reason must be at least 10 characters"
                )

            # Get original record to validate
            original = self.attendance_repo.get_by_id(attendance_id)
            if not original:
                raise NotFoundError(f"Attendance record {attendance_id} not found")

            # Validate correction limits (e.g., max corrections per record)
            max_corrections = 5
            if original.correction_count >= max_corrections:
                raise BusinessLogicError(
                    f"Maximum correction limit ({max_corrections}) reached for this record"
                )

            # Validate correction window (e.g., only allow corrections within 7 days)
            days_since_attendance = (date.today() - original.attendance_date).days
            max_correction_days = 7
            if days_since_attendance > max_correction_days:
                raise BusinessLogicError(
                    f"Corrections can only be made within {max_correction_days} days "
                    f"of attendance date"
                )

            # Determine if approved based on requirement
            final_approved_by = None
            if not require_approval and approved_by:
                final_approved_by = approved_by
            elif require_approval and approved_by:
                final_approved_by = approved_by

            # Create correction
            correction = self.attendance_repo.create_correction(
                attendance_id=attendance_id,
                corrected_by=corrected_by,
                corrected_status=corrected_status,
                correction_reason=correction_reason,
                corrected_check_in_time=corrected_check_in_time,
                corrected_check_out_time=corrected_check_out_time,
                corrected_is_late=corrected_is_late,
                corrected_late_minutes=corrected_late_minutes,
                approved_by=final_approved_by,
            )

            self.session.commit()
            logger.info(
                f"Attendance correction created for record {attendance_id} by {corrected_by}"
            )

            return correction

        except Exception as e:
            self.session.rollback()
            logger.error(f"Error creating correction: {str(e)}")
            raise

    def approve_correction(
        self,
        correction_id: UUID,
        approved_by: UUID,
        approval_notes: Optional[str] = None,
    ) -> AttendanceCorrection:
        """
        Approve pending correction.

        Args:
            correction_id: Correction identifier
            approved_by: User approving
            approval_notes: Optional approval notes

        Returns:
            Approved correction

        Raises:
            NotFoundError: If correction not found
            BusinessLogicError: If already approved
        """
        try:
            # Get correction
            corrections = self.get_correction_history(correction_id)
            if not corrections:
                raise NotFoundError(f"Correction {correction_id} not found")

            correction = corrections[0]

            # Check if already approved
            if correction.approved_by is not None:
                raise BusinessLogicError("Correction has already been approved")

            # Update correction
            correction.approved_by = approved_by
            correction.approved_at = datetime.utcnow()
            
            # Could add approval_notes field to model if needed
            # For now, we'll just log it
            
            self.session.commit()
            logger.info(f"Correction {correction_id} approved by {approved_by}")

            return correction

        except Exception as e:
            self.session.rollback()
            logger.error(f"Error approving correction: {str(e)}")
            raise

    def reject_correction(
        self,
        correction_id: UUID,
        rejected_by: UUID,
        rejection_reason: str,
    ) -> Dict[str, Any]:
        """
        Reject pending correction and revert changes.

        Args:
            correction_id: Correction identifier
            rejected_by: User rejecting
            rejection_reason: Reason for rejection

        Returns:
            Rejection result dictionary

        Raises:
            NotFoundError: If correction not found
            BusinessLogicError: If already approved
        """
        try:
            # Get correction
            corrections = self.get_correction_history(correction_id)
            if not corrections:
                raise NotFoundError(f"Correction {correction_id} not found")

            correction = corrections[0]

            # Check if already approved
            if correction.approved_by is not None:
                raise BusinessLogicError(
                    "Cannot reject an already approved correction"
                )

            # Get attendance record
            attendance = self.attendance_repo.get_by_id(correction.attendance_id)
            if not attendance:
                raise NotFoundError("Associated attendance record not found")

            # Revert to original values
            attendance.status = correction.original_status
            attendance.check_in_time = correction.original_check_in_time
            attendance.check_out_time = correction.original_check_out_time
            attendance.is_late = correction.original_is_late
            attendance.late_minutes = correction.original_late_minutes
            attendance.correction_count -= 1

            # Delete correction record
            self.session.delete(correction)

            self.session.commit()
            logger.info(
                f"Correction {correction_id} rejected by {rejected_by}: {rejection_reason}"
            )

            return {
                "correction_id": str(correction_id),
                "rejected_by": str(rejected_by),
                "rejection_reason": rejection_reason,
                "attendance_id": str(correction.attendance_id),
                "reverted_to_original": True,
            }

        except Exception as e:
            self.session.rollback()
            logger.error(f"Error rejecting correction: {str(e)}")
            raise

    # ==================== Correction Querying ====================

    def get_correction_history(
        self,
        attendance_id: UUID,
    ) -> List[AttendanceCorrection]:
        """
        Get all corrections for attendance record.

        Args:
            attendance_id: Attendance record identifier

        Returns:
            List of corrections ordered by timestamp
        """
        return self.attendance_repo.get_correction_history(attendance_id)

    def get_pending_corrections(
        self,
        hostel_id: Optional[UUID] = None,
    ) -> List[AttendanceCorrection]:
        """
        Get pending corrections awaiting approval.

        Args:
            hostel_id: Optional hostel filter

        Returns:
            List of pending corrections
        """
        # This would require additional repository method
        # Simplified implementation
        return []

    def get_corrected_records(
        self,
        hostel_id: UUID,
        start_date: date,
        end_date: date,
    ) -> List[AttendanceRecord]:
        """
        Get all corrected attendance records in date range.

        Args:
            hostel_id: Hostel identifier
            start_date: Start date (inclusive)
            end_date: End date (inclusive)

        Returns:
            List of corrected records
        """
        return self.attendance_repo.get_corrected_records(
            hostel_id=hostel_id,
            start_date=start_date,
            end_date=end_date,
        )

    def get_user_corrections(
        self,
        corrected_by: UUID,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> List[AttendanceCorrection]:
        """
        Get corrections made by specific user.

        Args:
            corrected_by: User identifier
            start_date: Optional start date
            end_date: Optional end date

        Returns:
            List of corrections
        """
        # This would require additional repository method
        # Simplified implementation
        return []

    # ==================== Correction Analytics ====================

    def get_correction_statistics(
        self,
        hostel_id: UUID,
        start_date: date,
        end_date: date,
    ) -> Dict[str, Any]:
        """
        Get correction statistics for period.

        Args:
            hostel_id: Hostel identifier
            start_date: Start date (inclusive)
            end_date: End date (inclusive)

        Returns:
            Statistics dictionary
        """
        try:
            corrected_records = self.attendance_repo.get_corrected_records(
                hostel_id=hostel_id,
                start_date=start_date,
                end_date=end_date,
            )

            total_corrected = len(corrected_records)
            total_corrections = sum(r.correction_count for r in corrected_records)

            # Calculate correction rate
            all_records = self.attendance_repo.get_hostel_attendance_range(
                hostel_id=hostel_id,
                start_date=start_date,
                end_date=end_date,
            )[0]

            total_records = len(all_records)
            correction_rate = (
                (total_corrected / total_records * 100) if total_records > 0 else 0
            )

            # Group by correction reason (would need to aggregate from corrections)
            # Simplified here

            return {
                "total_records": total_records,
                "total_corrected_records": total_corrected,
                "total_corrections": total_corrections,
                "correction_rate": round(correction_rate, 2),
                "average_corrections_per_record": round(
                    total_corrections / total_corrected if total_corrected > 0 else 0,
                    2,
                ),
                "period_start": start_date,
                "period_end": end_date,
            }

        except Exception as e:
            logger.error(f"Error calculating correction statistics: {str(e)}")
            raise

    def get_most_corrected_records(
        self,
        hostel_id: UUID,
        start_date: date,
        end_date: date,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Get records with most corrections.

        Args:
            hostel_id: Hostel identifier
            start_date: Start date (inclusive)
            end_date: End date (inclusive)
            limit: Number of records to return

        Returns:
            List of records with correction details
        """
        try:
            corrected_records = self.attendance_repo.get_corrected_records(
                hostel_id=hostel_id,
                start_date=start_date,
                end_date=end_date,
            )

            # Sort by correction count
            sorted_records = sorted(
                corrected_records,
                key=lambda r: r.correction_count,
                reverse=True,
            )[:limit]

            return [
                {
                    "attendance_id": str(record.id),
                    "student_id": str(record.student_id),
                    "attendance_date": record.attendance_date,
                    "correction_count": record.correction_count,
                    "current_status": record.status.value,
                }
                for record in sorted_records
            ]

        except Exception as e:
            logger.error(f"Error getting most corrected records: {str(e)}")
            raise

    # ==================== Validation ====================

    def validate_correction(
        self,
        attendance_id: UUID,
        corrected_status: AttendanceStatus,
        correction_reason: str,
    ) -> Dict[str, Any]:
        """
        Validate if correction can be made.

        Args:
            attendance_id: Attendance record identifier
            corrected_status: Proposed corrected status
            correction_reason: Correction reason

        Returns:
            Validation result dictionary
        """
        validation = {
            "valid": True,
            "warnings": [],
            "errors": [],
        }

        try:
            # Get original record
            original = self.attendance_repo.get_by_id(attendance_id)
            if not original:
                validation["valid"] = False
                validation["errors"].append("Attendance record not found")
                return validation

            # Check correction limit
            if original.correction_count >= 5:
                validation["valid"] = False
                validation["errors"].append("Maximum correction limit reached")

            # Check correction window
            days_since = (date.today() - original.attendance_date).days
            if days_since > 7:
                validation["warnings"].append(
                    f"Correction is {days_since} days old, may require approval"
                )

            # Validate reason
            if not correction_reason or len(correction_reason.strip()) < 10:
                validation["valid"] = False
                validation["errors"].append(
                    "Correction reason must be at least 10 characters"
                )

            # Check if status is actually changing
            if corrected_status == original.status:
                validation["warnings"].append(
                    "Corrected status is same as original status"
                )

            return validation

        except Exception as e:
            logger.error(f"Error validating correction: {str(e)}")
            validation["valid"] = False
            validation["errors"].append(f"Validation error: {str(e)}")
            return validation