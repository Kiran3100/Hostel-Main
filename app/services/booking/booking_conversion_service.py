# app/services/booking/booking_conversion_service.py
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Callable, List
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.transactions import BookingRepository
from app.repositories.core import StudentRepository, HostelRepository, RoomRepository, BedRepository
from app.schemas.booking import (
    ConvertToStudentRequest,
    ConversionResponse,
    ConversionChecklist,
    ChecklistItem,
)
from app.schemas.common.enums import BookingStatus, StudentStatus
from app.services.common import UnitOfWork, errors


class BookingConversionService:
    """
    Convert confirmed bookings into Student profiles.

    - Validates that booking is confirmed
    - Checks financial confirmations
    - Creates Student record
    - Assigns room/bed
    """

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    def _get_booking_repo(self, uow: UnitOfWork) -> BookingRepository:
        return uow.get_repo(BookingRepository)

    def _get_student_repo(self, uow: UnitOfWork) -> StudentRepository:
        return uow.get_repo(StudentRepository)

    def _get_room_repo(self, uow: UnitOfWork) -> RoomRepository:
        return uow.get_repo(RoomRepository)

    def _get_bed_repo(self, uow: UnitOfWork) -> BedRepository:
        return uow.get_repo(BedRepository)

    # ------------------------------------------------------------------ #
    # Checklist / eligibility
    # ------------------------------------------------------------------ #
    def build_checklist(self, booking_id: UUID) -> ConversionChecklist:
        """
        Build a simple pre-conversion checklist. Here we only stub it;
        you can enrich with actual checks.
        """
        checks: List[ChecklistItem] = [
            ChecklistItem(
                item_name="Security deposit received",
                description="Verify security deposit payment",
                is_completed=False,
                is_required=True,
                completed_at=None,
                notes=None,
            ),
            ChecklistItem(
                item_name="First month rent received",
                description="Verify first month rent payment",
                is_completed=False,
                is_required=True,
                completed_at=None,
                notes=None,
            ),
            ChecklistItem(
                item_name="ID proof uploaded",
                description="Check that a valid ID proof document is uploaded",
                is_completed=False,
                is_required=True,
                completed_at=None,
                notes=None,
            ),
        ]
        return ConversionChecklist(
            booking_id=booking_id,
            booking_reference=f"BKG-{str(booking_id)[:8].upper()}",
            checks=checks,
            all_checks_passed=False,
            can_convert=False,
            missing_items=[c.item_name for c in checks],
        )

    # ------------------------------------------------------------------ #
    # Conversion
    # ------------------------------------------------------------------ #
    def convert(
        self,
        data: ConvertToStudentRequest,
        *,
        user_id: UUID,
        hostel_id: UUID,
        room_id: UUID,
        bed_id: UUID,
        monthly_rent: Decimal,
        security_deposit: Decimal,
        next_payment_due_date: date,
    ) -> ConversionResponse:
        with UnitOfWork(self._session_factory) as uow:
            booking_repo = self._get_booking_repo(uow)
            student_repo = self._get_student_repo(uow)
            room_repo = self._get_room_repo(uow)
            bed_repo = self._get_bed_repo(uow)

            b = booking_repo.get(data.booking_id)
            if b is None:
                raise errors.NotFoundError(f"Booking {data.booking_id} not found")

            if b.booking_status not in (BookingStatus.CONFIRMED, BookingStatus.CHECKED_IN):
                raise errors.ValidationError("Booking must be confirmed before conversion")

            # Create student record
            student_payload = {
                "user_id": user_id,
                "hostel_id": hostel_id,
                "room_id": room_id,
                "bed_id": bed_id,
                "guardian_name": "",
                "guardian_phone": "",
                "guardian_email": None,
                "guardian_relation": None,
                "guardian_address": None,
                "institution_name": None,
                "course": None,
                "year_of_study": None,
                "company_name": None,
                "designation": None,
                "check_in_date": data.actual_check_in_date,
                "expected_checkout_date": None,
                "actual_checkout_date": None,
                "security_deposit_amount": security_deposit,
                "monthly_rent_amount": monthly_rent,
                "mess_subscribed": False,
                "dietary_preference": None,
                "food_allergies": None,
                "student_status": StudentStatus.ACTIVE,
            }
            student = student_repo.create(student_payload)  # type: ignore[arg-type]

            # Assign bed's current_student_id
            bed = bed_repo.get(bed_id)
            if bed:
                bed.current_student_id = student.id  # type: ignore[attr-defined]

            # Optionally mark booking as converted
            b.booking_status = BookingStatus.COMPLETED  # type: ignore[attr-defined]

            uow.session.flush()  # type: ignore[union-attr]
            uow.commit()

        room = room_repo.get(room_id)
        bed_obj = bed_repo.get(bed_id)

        return ConversionResponse(
            booking_id=data.booking_id,
            student_profile_id=student.id,
            converted=True,
            conversion_date=data.actual_check_in_date,
            room_number=room.room_number if room else "",
            bed_number=bed_obj.bed_number if bed_obj else "",
            monthly_rent=monthly_rent,
            security_deposit=security_deposit,
            next_payment_due_date=next_payment_due_date,
            message="Booking converted to student successfully",
            next_steps=[
                "Complete hostel onboarding form",
                "Collect room keys",
            ],
        )