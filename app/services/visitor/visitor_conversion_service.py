"""
Visitor Conversion Service

Tracks and manages conversions for visitors through their journey.
Supports conversion tracking from inquiry → booking → student.
"""

from __future__ import annotations

import logging
from typing import Optional, Dict, Any
from uuid import UUID
from datetime import datetime
from decimal import Decimal

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.repositories.visitor import (
    VisitorRepository,
    VisitorEngagementRepository,
)
from app.repositories.booking import BookingRepository
from app.repositories.student import StudentRepository
from app.schemas.visitor import VisitorDetail
from app.core1.exceptions import (
    ValidationException,
    NotFoundException,
    ServiceException,
)

logger = logging.getLogger(__name__)


class VisitorConversionService:
    """
    Service for handling visitor conversions and updating engagement metrics.

    Conversion funnel:
    1. Anonymous visitor → Registered visitor
    2. Visitor inquiry → Booking
    3. Visitor booking → Student (long-term)

    Each conversion updates engagement metrics and maintains audit trail.
    """

    def __init__(
        self,
        visitor_repo: VisitorRepository,
        engagement_repo: VisitorEngagementRepository,
        booking_repo: BookingRepository,
        student_repo: StudentRepository,
    ) -> None:
        """
        Initialize the conversion service.

        Args:
            visitor_repo: Repository for visitor operations
            engagement_repo: Repository for engagement tracking
            booking_repo: Repository for booking operations
            student_repo: Repository for student operations
        """
        self.visitor_repo = visitor_repo
        self.engagement_repo = engagement_repo
        self.booking_repo = booking_repo
        self.student_repo = student_repo

    def record_booking_conversion(
        self,
        db: Session,
        visitor_id: UUID,
        booking_id: UUID,
        conversion_value: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> VisitorDetail:
        """
        Record that a visitor created a booking (conversion event).

        This is a critical conversion point in the visitor journey.
        Updates:
        - Visitor engagement metrics (conversion count, value)
        - Last conversion timestamp
        - Total bookings counter
        - Conversion metadata

        Args:
            db: Database session
            visitor_id: UUID of the visitor
            booking_id: UUID of the booking created
            conversion_value: Optional override for conversion value
            metadata: Optional additional conversion metadata

        Returns:
            VisitorDetail: Updated visitor profile with engagement data

        Raises:
            NotFoundException: If visitor or booking not found
            ValidationException: If booking already recorded or invalid state
            ServiceException: If update fails
        """
        try:
            # Validate visitor exists
            visitor = self.visitor_repo.get_by_id(db, visitor_id)
            if not visitor:
                raise NotFoundException(f"Visitor {visitor_id} not found")

            # Validate booking exists
            booking = self.booking_repo.get_by_id(db, booking_id)
            if not booking:
                raise NotFoundException(f"Booking {booking_id} not found")

            # Verify booking belongs to this visitor
            if booking.visitor_id != visitor_id:
                raise ValidationException(
                    f"Booking {booking_id} does not belong to visitor {visitor_id}"
                )

            # Check if already recorded
            if self._is_booking_conversion_recorded(db, visitor_id, booking_id):
                logger.warning(
                    f"Booking conversion {booking_id} already recorded for visitor {visitor_id}"
                )
                raise ValidationException("Booking conversion already recorded")

            # Calculate conversion value
            if conversion_value is not None:
                value = Decimal(str(conversion_value))
            else:
                value = Decimal(str(booking.total_amount or 0))

            if value < 0:
                raise ValidationException("Conversion value cannot be negative")

            # Update engagement metrics
            self.engagement_repo.increment_conversions(
                db=db,
                visitor_id=visitor.id,
                value=float(value),
                conversion_type="booking",
                metadata=metadata,
            )

            # Update visitor profile
            current_bookings = visitor.total_bookings or 0
            update_data = {
                "last_conversion_at": datetime.utcnow(),
                "total_bookings": current_bookings + 1,
                "last_booking_id": booking_id,
            }

            self.visitor_repo.update(db, obj=visitor, data=update_data)

            logger.info(
                f"Recorded booking conversion for visitor {visitor_id}: "
                f"booking {booking_id}, value {value}"
            )

            # Return full profile with updated engagement
            full_profile = self.visitor_repo.get_full_profile(db, visitor.id)
            return VisitorDetail.model_validate(full_profile)

        except (NotFoundException, ValidationException):
            raise
        except Exception as e:
            logger.error(
                f"Failed to record booking conversion for visitor {visitor_id}: {str(e)}",
                exc_info=True
            )
            raise ServiceException(f"Failed to record booking conversion: {str(e)}")

    def record_student_conversion(
        self,
        db: Session,
        visitor_id: UUID,
        student_id: UUID,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> VisitorDetail:
        """
        Record that a visitor has converted to a long-term student.

        This is the ultimate conversion in the visitor journey.
        Updates:
        - Engagement metrics (marks as converted to student)
        - Visitor conversion flags
        - Student reference linkage

        Args:
            db: Database session
            visitor_id: UUID of the visitor
            student_id: UUID of the student created
            metadata: Optional additional conversion metadata

        Returns:
            VisitorDetail: Updated visitor profile

        Raises:
            NotFoundException: If visitor or student not found
            ValidationException: If already converted or invalid state
            ServiceException: If update fails
        """
        try:
            # Validate visitor exists
            visitor = self.visitor_repo.get_by_id(db, visitor_id)
            if not visitor:
                raise NotFoundException(f"Visitor {visitor_id} not found")

            # Validate student exists
            student = self.student_repo.get_by_id(db, student_id)
            if not student:
                raise NotFoundException(f"Student {student_id} not found")

            # Check if already converted
            if visitor.has_converted_to_student:
                logger.warning(
                    f"Visitor {visitor_id} already converted to student "
                    f"{visitor.converted_student_id}"
                )
                raise ValidationException("Visitor already converted to student")

            # Verify student linkage (if applicable)
            if hasattr(student, 'visitor_id') and student.visitor_id:
                if student.visitor_id != visitor_id:
                    raise ValidationException(
                        f"Student {student_id} is linked to a different visitor"
                    )

            # Update engagement with student conversion
            self.engagement_repo.mark_as_converted_to_student(
                db=db,
                visitor_id=visitor.id,
                student_id=student.id,
                metadata=metadata,
            )

            # Update visitor profile
            conversion_time = datetime.utcnow()
            update_data = {
                "has_converted_to_student": True,
                "converted_student_id": student.id,
                "last_conversion_at": conversion_time,
                "student_conversion_date": conversion_time,
            }

            self.visitor_repo.update(db, obj=visitor, data=update_data)

            logger.info(
                f"Recorded student conversion for visitor {visitor_id}: "
                f"student {student_id}"
            )

            # Return full profile with updated engagement
            full_profile = self.visitor_repo.get_full_profile(db, visitor.id)
            return VisitorDetail.model_validate(full_profile)

        except (NotFoundException, ValidationException):
            raise
        except Exception as e:
            logger.error(
                f"Failed to record student conversion for visitor {visitor_id}: {str(e)}",
                exc_info=True
            )
            raise ServiceException(f"Failed to record student conversion: {str(e)}")

    def record_inquiry_conversion(
        self,
        db: Session,
        visitor_id: UUID,
        inquiry_id: UUID,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> VisitorDetail:
        """
        Record that a visitor created an inquiry (early conversion signal).

        Args:
            db: Database session
            visitor_id: UUID of the visitor
            inquiry_id: UUID of the inquiry created
            metadata: Optional additional metadata

        Returns:
            VisitorDetail: Updated visitor profile

        Raises:
            NotFoundException: If visitor not found
            ServiceException: If update fails
        """
        try:
            visitor = self.visitor_repo.get_by_id(db, visitor_id)
            if not visitor:
                raise NotFoundException(f"Visitor {visitor_id} not found")

            # Update engagement metrics
            self.engagement_repo.increment_inquiries(
                db=db,
                visitor_id=visitor.id,
                metadata=metadata,
            )

            # Update visitor last inquiry
            current_inquiries = visitor.total_inquiries or 0
            update_data = {
                "total_inquiries": current_inquiries + 1,
                "last_inquiry_at": datetime.utcnow(),
                "last_inquiry_id": inquiry_id,
            }

            self.visitor_repo.update(db, obj=visitor, data=update_data)

            logger.info(f"Recorded inquiry conversion for visitor {visitor_id}")

            full_profile = self.visitor_repo.get_full_profile(db, visitor.id)
            return VisitorDetail.model_validate(full_profile)

        except NotFoundException:
            raise
        except Exception as e:
            logger.error(
                f"Failed to record inquiry conversion for visitor {visitor_id}: {str(e)}",
                exc_info=True
            )
            raise ServiceException(f"Failed to record inquiry conversion: {str(e)}")

    def get_conversion_funnel(
        self,
        db: Session,
        visitor_id: UUID,
    ) -> Dict[str, Any]:
        """
        Get the complete conversion funnel for a visitor.

        Returns:
            Dictionary with conversion stages and metrics
        """
        try:
            visitor = self.visitor_repo.get_by_id(db, visitor_id)
            if not visitor:
                raise NotFoundException(f"Visitor {visitor_id} not found")

            engagement = self.engagement_repo.get_by_visitor_id(db, visitor_id)

            return {
                "visitor_id": str(visitor_id),
                "stages": {
                    "registered": {
                        "completed": True,
                        "date": visitor.created_at,
                    },
                    "inquiry": {
                        "completed": (visitor.total_inquiries or 0) > 0,
                        "count": visitor.total_inquiries or 0,
                        "last_date": visitor.last_inquiry_at,
                    },
                    "booking": {
                        "completed": (visitor.total_bookings or 0) > 0,
                        "count": visitor.total_bookings or 0,
                        "last_date": visitor.last_conversion_at if visitor.total_bookings else None,
                    },
                    "student": {
                        "completed": visitor.has_converted_to_student or False,
                        "date": getattr(visitor, 'student_conversion_date', None),
                        "student_id": str(visitor.converted_student_id) if visitor.converted_student_id else None,
                    },
                },
                "engagement_score": engagement.engagement_score if engagement else 0,
                "lifetime_value": engagement.lifetime_value if engagement else 0.0,
            }

        except NotFoundException:
            raise
        except Exception as e:
            logger.error(
                f"Failed to get conversion funnel for visitor {visitor_id}: {str(e)}",
                exc_info=True
            )
            raise ServiceException(f"Failed to get conversion funnel: {str(e)}")

    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------

    def _is_booking_conversion_recorded(
        self,
        db: Session,
        visitor_id: UUID,
        booking_id: UUID,
    ) -> bool:
        """
        Check if a booking conversion has already been recorded.

        Args:
            db: Database session
            visitor_id: UUID of the visitor
            booking_id: UUID of the booking

        Returns:
            bool: True if conversion already recorded
        """
        try:
            # Check visitor's last_booking_id or query engagement records
            visitor = self.visitor_repo.get_by_id(db, visitor_id)
            if visitor and hasattr(visitor, 'last_booking_id'):
                if visitor.last_booking_id == booking_id:
                    return True

            # Additional check in engagement repository if available
            return self.engagement_repo.is_conversion_recorded(
                db, visitor_id, booking_id, "booking"
            )
        except:
            return False