# --- File: app/services/attendance/check_in_service.py ---
"""
Check-in service for real-time attendance marking.

Provides mobile check-in, geolocation validation, and
real-time attendance processing with policy enforcement.
"""

from datetime import date, datetime, time
from decimal import Decimal
from typing import Optional, Dict, Any, Tuple
from uuid import UUID
import math

from sqlalchemy.orm import Session

from app.models.attendance.attendance_record import AttendanceRecord
from app.models.base.enums import AttendanceStatus, AttendanceMode
from app.repositories.attendance.attendance_record_repository import (
    AttendanceRecordRepository,
)
from app.repositories.attendance.attendance_policy_repository import (
    AttendancePolicyRepository,
)
from app.core.exceptions import ValidationError, NotFoundError, BusinessLogicError
from app.core.logging import get_logger

logger = get_logger(__name__)


class CheckInService:
    """
    Service for real-time check-in operations.
    """

    def __init__(self, session: Session):
        """
        Initialize service with database session.

        Args:
            session: SQLAlchemy database session
        """
        self.session = session
        self.attendance_repo = AttendanceRecordRepository(session)
        self.policy_repo = AttendancePolicyRepository(session)

    # ==================== Check-In Operations ====================

    def mobile_check_in(
        self,
        student_id: UUID,
        hostel_id: UUID,
        latitude: Decimal,
        longitude: Decimal,
        device_info: Dict[str, Any],
        check_in_time: Optional[time] = None,
    ) -> Dict[str, Any]:
        """
        Process mobile check-in with geolocation validation.

        Args:
            student_id: Student identifier
            hostel_id: Hostel identifier
            latitude: Check-in latitude
            longitude: Check-in longitude
            device_info: Device information
            check_in_time: Optional check-in time (uses current if not provided)

        Returns:
            Check-in result dictionary

        Raises:
            ValidationError: If validation fails
            BusinessLogicError: If business rules violated
        """
        try:
            # Use current time if not provided
            if check_in_time is None:
                check_in_time = datetime.now().time()

            current_date = date.today()

            # Check if already checked in today
            existing = self.attendance_repo.get_by_student_and_date(
                student_id=student_id,
                attendance_date=current_date,
            )

            if existing:
                raise BusinessLogicError("Already checked in for today")

            # Validate geolocation
            geo_validation = self._validate_geolocation(
                hostel_id=hostel_id,
                latitude=latitude,
                longitude=longitude,
            )

            if not geo_validation["valid"]:
                raise ValidationError(
                    f"Check-in location invalid: {geo_validation['reason']}"
                )

            # Get policy and calculate late status
            policy = self.policy_repo.get_by_hostel(hostel_id)
            is_late = False
            late_minutes = None

            if policy:
                late_result = self._calculate_late_status(
                    check_in_time=check_in_time,
                    policy=policy,
                )
                is_late = late_result["is_late"]
                late_minutes = late_result["late_minutes"]

            # Create attendance record
            record = self.attendance_repo.create_attendance(
                hostel_id=hostel_id,
                student_id=student_id,
                attendance_date=current_date,
                status=AttendanceStatus.PRESENT,
                marked_by=student_id,  # Self check-in
                check_in_time=check_in_time,
                is_late=is_late,
                late_minutes=late_minutes,
                attendance_mode=AttendanceMode.SELF_SERVICE,
                location_lat=latitude,
                location_lng=longitude,
                device_info=device_info,
            )

            self.session.commit()

            logger.info(
                f"Mobile check-in successful for student {student_id} at {check_in_time}"
            )

            return {
                "success": True,
                "attendance_id": str(record.id),
                "check_in_time": check_in_time.isoformat(),
                "is_late": is_late,
                "late_minutes": late_minutes,
                "status": "present",
                "message": self._get_check_in_message(is_late, late_minutes),
                "geolocation_verified": True,
            }

        except Exception as e:
            self.session.rollback()
            logger.error(f"Error in mobile check-in: {str(e)}")
            raise

    def qr_code_check_in(
        self,
        student_id: UUID,
        hostel_id: UUID,
        qr_code_data: str,
        check_in_time: Optional[time] = None,
    ) -> Dict[str, Any]:
        """
        Process QR code check-in.

        Args:
            student_id: Student identifier
            hostel_id: Hostel identifier
            qr_code_data: QR code data
            check_in_time: Optional check-in time

        Returns:
            Check-in result dictionary

        Raises:
            ValidationError: If QR code invalid
            BusinessLogicError: If business rules violated
        """
        try:
            # Validate QR code
            qr_validation = self._validate_qr_code(
                hostel_id=hostel_id,
                qr_code_data=qr_code_data,
            )

            if not qr_validation["valid"]:
                raise ValidationError(f"Invalid QR code: {qr_validation['reason']}")

            # Use current time if not provided
            if check_in_time is None:
                check_in_time = datetime.now().time()

            current_date = date.today()

            # Check if already checked in
            existing = self.attendance_repo.get_by_student_and_date(
                student_id=student_id,
                attendance_date=current_date,
            )

            if existing:
                raise BusinessLogicError("Already checked in for today")

            # Get policy and calculate late status
            policy = self.policy_repo.get_by_hostel(hostel_id)
            is_late = False
            late_minutes = None

            if policy:
                late_result = self._calculate_late_status(
                    check_in_time=check_in_time,
                    policy=policy,
                )
                is_late = late_result["is_late"]
                late_minutes = late_result["late_minutes"]

            # Create attendance record
            record = self.attendance_repo.create_attendance(
                hostel_id=hostel_id,
                student_id=student_id,
                attendance_date=current_date,
                status=AttendanceStatus.PRESENT,
                marked_by=student_id,
                check_in_time=check_in_time,
                is_late=is_late,
                late_minutes=late_minutes,
                attendance_mode=AttendanceMode.QR_CODE,
                device_info={"qr_code_id": qr_validation.get("qr_id")},
            )

            self.session.commit()

            logger.info(f"QR check-in successful for student {student_id}")

            return {
                "success": True,
                "attendance_id": str(record.id),
                "check_in_time": check_in_time.isoformat(),
                "is_late": is_late,
                "late_minutes": late_minutes,
                "status": "present",
                "message": self._get_check_in_message(is_late, late_minutes),
            }

        except Exception as e:
            self.session.rollback()
            logger.error(f"Error in QR check-in: {str(e)}")
            raise

    def biometric_check_in(
        self,
        student_id: UUID,
        hostel_id: UUID,
        biometric_data: Dict[str, Any],
        check_in_time: Optional[time] = None,
    ) -> Dict[str, Any]:
        """
        Process biometric check-in.

        Args:
            student_id: Student identifier
            hostel_id: Hostel identifier
            biometric_data: Biometric verification data
            check_in_time: Optional check-in time

        Returns:
            Check-in result dictionary

        Raises:
            ValidationError: If biometric verification fails
            BusinessLogicError: If business rules violated
        """
        try:
            # Validate biometric data
            biometric_validation = self._validate_biometric(
                student_id=student_id,
                biometric_data=biometric_data,
            )

            if not biometric_validation["valid"]:
                raise ValidationError(
                    f"Biometric verification failed: {biometric_validation['reason']}"
                )

            # Use current time if not provided
            if check_in_time is None:
                check_in_time = datetime.now().time()

            current_date = date.today()

            # Check if already checked in
            existing = self.attendance_repo.get_by_student_and_date(
                student_id=student_id,
                attendance_date=current_date,
            )

            if existing:
                raise BusinessLogicError("Already checked in for today")

            # Get policy and calculate late status
            policy = self.policy_repo.get_by_hostel(hostel_id)
            is_late = False
            late_minutes = None

            if policy:
                late_result = self._calculate_late_status(
                    check_in_time=check_in_time,
                    policy=policy,
                )
                is_late = late_result["is_late"]
                late_minutes = late_result["late_minutes"]

            # Create attendance record
            record = self.attendance_repo.create_attendance(
                hostel_id=hostel_id,
                student_id=student_id,
                attendance_date=current_date,
                status=AttendanceStatus.PRESENT,
                marked_by=student_id,
                check_in_time=check_in_time,
                is_late=is_late,
                late_minutes=late_minutes,
                attendance_mode=AttendanceMode.BIOMETRIC,
                device_info={
                    "biometric_type": biometric_data.get("type"),
                    "confidence_score": biometric_data.get("confidence"),
                },
            )

            self.session.commit()

            logger.info(f"Biometric check-in successful for student {student_id}")

            return {
                "success": True,
                "attendance_id": str(record.id),
                "check_in_time": check_in_time.isoformat(),
                "is_late": is_late,
                "late_minutes": late_minutes,
                "status": "present",
                "message": self._get_check_in_message(is_late, late_minutes),
                "biometric_verified": True,
            }

        except Exception as e:
            self.session.rollback()
            logger.error(f"Error in biometric check-in: {str(e)}")
            raise

    def check_out(
        self,
        student_id: UUID,
        check_out_time: Optional[time] = None,
    ) -> Dict[str, Any]:
        """
        Process check-out.

        Args:
            student_id: Student identifier
            check_out_time: Optional check-out time

        Returns:
            Check-out result dictionary

        Raises:
            NotFoundError: If no check-in found
        """
        try:
            # Use current time if not provided
            if check_out_time is None:
                check_out_time = datetime.now().time()

            current_date = date.today()

            # Get today's attendance record
            record = self.attendance_repo.get_by_student_and_date(
                student_id=student_id,
                attendance_date=current_date,
            )

            if not record:
                raise NotFoundError("No check-in found for today")

            if record.check_out_time:
                raise BusinessLogicError("Already checked out for today")

            # Update with check-out time
            record.check_out_time = check_out_time

            self.session.commit()

            logger.info(f"Check-out successful for student {student_id}")

            return {
                "success": True,
                "attendance_id": str(record.id),
                "check_in_time": record.check_in_time.isoformat() if record.check_in_time else None,
                "check_out_time": check_out_time.isoformat(),
                "message": "Check-out successful",
            }

        except Exception as e:
            self.session.rollback()
            logger.error(f"Error in check-out: {str(e)}")
            raise

    # ==================== Check-In Status ====================

    def get_check_in_status(
        self,
        student_id: UUID,
        check_date: Optional[date] = None,
    ) -> Dict[str, Any]:
        """
        Get check-in status for student.

        Args:
            student_id: Student identifier
            check_date: Date to check (defaults to today)

        Returns:
            Status dictionary
        """
        if check_date is None:
            check_date = date.today()

        record = self.attendance_repo.get_by_student_and_date(
            student_id=student_id,
            attendance_date=check_date,
        )

        if not record:
            return {
                "checked_in": False,
                "date": check_date.isoformat(),
                "message": "Not checked in yet",
            }

        return {
            "checked_in": True,
            "checked_out": record.check_out_time is not None,
            "date": check_date.isoformat(),
            "check_in_time": record.check_in_time.isoformat() if record.check_in_time else None,
            "check_out_time": record.check_out_time.isoformat() if record.check_out_time else None,
            "is_late": record.is_late,
            "late_minutes": record.late_minutes,
            "status": record.status.value,
            "mode": record.attendance_mode.value,
        }

    def can_check_in(
        self,
        student_id: UUID,
        hostel_id: UUID,
    ) -> Dict[str, Any]:
        """
        Check if student can check in.

        Args:
            student_id: Student identifier
            hostel_id: Hostel identifier

        Returns:
            Eligibility dictionary
        """
        current_date = date.today()

        # Check if already checked in
        existing = self.attendance_repo.get_by_student_and_date(
            student_id=student_id,
            attendance_date=current_date,
        )

        if existing:
            return {
                "can_check_in": False,
                "reason": "Already checked in for today",
                "existing_record": {
                    "check_in_time": existing.check_in_time.isoformat() if existing.check_in_time else None,
                    "status": existing.status.value,
                },
            }

        # Check if within allowed hours (would use policy)
        # Simplified here

        return {
            "can_check_in": True,
            "message": "Check-in allowed",
        }

    # ==================== Validation Helpers ====================

    def _validate_geolocation(
        self,
        hostel_id: UUID,
        latitude: Decimal,
        longitude: Decimal,
    ) -> Dict[str, Any]:
        """
        Validate check-in geolocation.

        Args:
            hostel_id: Hostel identifier
            latitude: Check-in latitude
            longitude: Check-in longitude

        Returns:
            Validation result
        """
        # In a real implementation, this would:
        # 1. Get hostel's registered location
        # 2. Calculate distance using haversine formula
        # 3. Check if within allowed radius

        # Simplified validation
        hostel_lat = Decimal("40.7128")  # Example coordinates
        hostel_lng = Decimal("-74.0060")
        max_distance_km = 0.5  # 500 meters

        distance = self._calculate_distance(
            lat1=float(hostel_lat),
            lon1=float(hostel_lng),
            lat2=float(latitude),
            lon2=float(longitude),
        )

        valid = distance <= max_distance_km

        return {
            "valid": valid,
            "distance_km": round(distance, 3),
            "max_allowed_km": max_distance_km,
            "reason": f"Distance {distance:.3f}km exceeds maximum {max_distance_km}km" if not valid else None,
        }

    def _validate_qr_code(
        self,
        hostel_id: UUID,
        qr_code_data: str,
    ) -> Dict[str, Any]:
        """
        Validate QR code data.

        Args:
            hostel_id: Hostel identifier
            qr_code_data: QR code data string

        Returns:
            Validation result
        """
        # In a real implementation, this would:
        # 1. Decode QR code data
        # 2. Verify signature/encryption
        # 3. Check expiration
        # 4. Verify hostel ID matches

        # Simplified validation
        try:
            # Parse QR code data (assumed format: "hostel_id:timestamp:signature")
            parts = qr_code_data.split(":")
            if len(parts) != 3:
                return {"valid": False, "reason": "Invalid QR code format"}

            qr_hostel_id = parts[0]
            timestamp = int(parts[1])
            signature = parts[2]

            # Verify hostel ID
            if qr_hostel_id != str(hostel_id):
                return {"valid": False, "reason": "QR code not valid for this hostel"}

            # Check if not expired (valid for 5 minutes)
            current_timestamp = int(datetime.now().timestamp())
            if current_timestamp - timestamp > 300:
                return {"valid": False, "reason": "QR code expired"}

            return {
                "valid": True,
                "qr_id": signature,
            }

        except Exception as e:
            return {"valid": False, "reason": f"QR code validation error: {str(e)}"}

    def _validate_biometric(
        self,
        student_id: UUID,
        biometric_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Validate biometric data.

        Args:
            student_id: Student identifier
            biometric_data: Biometric data

        Returns:
            Validation result
        """
        # In a real implementation, this would:
        # 1. Retrieve stored biometric template
        # 2. Compare with provided biometric
        # 3. Calculate confidence score
        # 4. Verify threshold

        # Simplified validation
        required_fields = ["type", "data", "confidence"]
        if not all(field in biometric_data for field in required_fields):
            return {"valid": False, "reason": "Missing required biometric fields"}

        confidence = biometric_data.get("confidence", 0)
        min_confidence = 0.85

        if confidence < min_confidence:
            return {
                "valid": False,
                "reason": f"Confidence score {confidence} below threshold {min_confidence}",
            }

        return {
            "valid": True,
            "confidence": confidence,
        }

    def _calculate_late_status(
        self,
        check_in_time: time,
        policy: Any,
    ) -> Dict[str, Any]:
        """
        Calculate late status based on policy.

        Args:
            check_in_time: Check-in time
            policy: Attendance policy

        Returns:
            Late status result
        """
        # Default start time (would come from hostel configuration)
        standard_start_time = time(9, 0)

        # Calculate difference in minutes
        check_in_datetime = datetime.combine(date.today(), check_in_time)
        standard_datetime = datetime.combine(date.today(), standard_start_time)

        time_diff = check_in_datetime - standard_datetime
        raw_late_minutes = int(time_diff.total_seconds() / 60)

        # Apply grace period
        effective_late_minutes = max(0, raw_late_minutes - policy.grace_period_minutes)

        # Determine if late based on threshold
        is_late = effective_late_minutes >= policy.late_entry_threshold_minutes

        return {
            "is_late": is_late,
            "late_minutes": effective_late_minutes if is_late else None,
            "raw_late_minutes": raw_late_minutes,
            "grace_applied": policy.grace_period_minutes,
            "threshold": policy.late_entry_threshold_minutes,
        }

    def _calculate_distance(
        self,
        lat1: float,
        lon1: float,
        lat2: float,
        lon2: float,
    ) -> float:
        """
        Calculate distance between two points using Haversine formula.

        Args:
            lat1: Latitude of point 1
            lon1: Longitude of point 1
            lat2: Latitude of point 2
            lon2: Longitude of point 2

        Returns:
            Distance in kilometers
        """
        # Earth's radius in kilometers
        R = 6371.0

        # Convert to radians
        lat1_rad = math.radians(lat1)
        lon1_rad = math.radians(lon1)
        lat2_rad = math.radians(lat2)
        lon2_rad = math.radians(lon2)

        # Differences
        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad

        # Haversine formula
        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
        )
        c = 2 * math.asin(math.sqrt(a))

        return R * c

    def _get_check_in_message(
        self,
        is_late: bool,
        late_minutes: Optional[int],
    ) -> str:
        """Generate user-friendly check-in message."""
        if not is_late:
            return "Check-in successful! You're on time."
        else:
            return f"Check-in successful, but you are {late_minutes} minutes late."