"""
Visitor Conversion Service

Tracks conversions for visitors (e.g., inquiry → booking, booking → student).
"""

from __future__ import annotations

from typing import Optional, Dict, Any
from uuid import UUID
from datetime import datetime

from sqlalchemy.orm import Session

from app.repositories.visitor import (
    VisitorRepository,
    VisitorEngagementRepository,
)
from app.repositories.booking import BookingRepository
from app.repositories.student import StudentRepository
from app.schemas.visitor import VisitorDetail
from app.core.exceptions import ValidationException


class VisitorConversionService:
    """
    Service for handling visitor conversions and updating engagement metrics.

    Scenarios:
    - Visitor inquiry converted to booking
    - Visitor booking converted to student
    """

    def __init__(
        self,
        visitor_repo: VisitorRepository,
        engagement_repo: VisitorEngagementRepository,
        booking_repo: BookingRepository,
        student_repo: StudentRepository,
    ) -> None:
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
    ) -> VisitorDetail:
        """
        Record that a visitor created a booking (conversion event).

        Updates:
        - Visitor engagement metrics
        - Last_conversion_at
        """
        visitor = self.visitor_repo.get_by_id(db, visitor_id)
        if not visitor:
            raise ValidationException("Visitor not found")

        booking = self.booking_repo.get_by_id(db, booking_id)
        if not booking:
            raise ValidationException("Booking not found")

        value = conversion_value or float(booking.total_amount or 0)

        # Update engagement metrics
        self.engagement_repo.increment_conversions(
            db=db,
            visitor_id=visitor.id,
            value=value,
        )

        # Update visitor profile
        self.visitor_repo.update(
            db,
            obj=visitor,
            data={
                "last_conversion_at": datetime.utcnow(),
                "total_bookings": (visitor.total_bookings or 0) + 1,
            },
        )

        full = self.visitor_repo.get_full_profile(db, visitor.id)
        return VisitorDetail.model_validate(full)

    def record_student_conversion(
        self,
        db: Session,
        visitor_id: UUID,
        student_id: UUID,
    ) -> VisitorDetail:
        """
        Record that a visitor has converted to a long-term student.

        Updates engagement and may mark visitor as "converted".
        """
        visitor = self.visitor_repo.get_by_id(db, visitor_id)
        if not visitor:
            raise ValidationException("Visitor not found")

        student = self.student_repo.get_by_id(db, student_id)
        if not student:
            raise ValidationException("Student not found")

        self.engagement_repo.mark_as_converted_to_student(
            db=db,
            visitor_id=visitor.id,
            student_id=student.id,
        )

        self.visitor_repo.update(
            db,
            obj=visitor,
            data={
                "has_converted_to_student": True,
                "converted_student_id": student.id,
                "last_conversion_at": datetime.utcnow(),
            },
        )

        full = self.visitor_repo.get_full_profile(db, visitor.id)
        return VisitorDetail.model_validate(full)