# app/services/booking/booking_service.py
from __future__ import annotations

from datetime import datetime, timezone, timedelta, date
from decimal import Decimal
from typing import Callable, Optional, Sequence, List
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.transactions import BookingRepository
from app.repositories.core import HostelRepository, RoomRepository, BedRepository
from app.schemas.common.enums import BookingStatus, BookingSource, RoomType
from app.schemas.common.pagination import PaginationParams, PaginatedResponse
from app.schemas.booking import (
    BookingCreate,
    BookingUpdate,
    BookingRequest,
    QuickBookingRequest,
    BookingFilterParams,
    BookingSortOptions,
    BookingSearchRequest,
    BookingResponse,
    BookingDetail,
    BookingListItem,
    BookingConfirmation,
)
from app.services.common import UnitOfWork, pagination, errors


class BookingService:
    """
    Core booking service (internal txn_booking model):

    - Create booking from internal BookingCreate or public BookingRequest/QuickBookingRequest
    - Get single booking (detail)
    - List / search bookings with filters & sorting
    - Update booking & booking status
    """

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _get_booking_repo(self, uow: UnitOfWork) -> BookingRepository:
        return uow.get_repo(BookingRepository)

    def _get_hostel_repo(self, uow: UnitOfWork) -> HostelRepository:
        return uow.get_repo(HostelRepository)

    def _get_room_repo(self, uow: UnitOfWork) -> RoomRepository:
        return uow.get_repo(RoomRepository)

    def _get_bed_repo(self, uow: UnitOfWork) -> BedRepository:
        return uow.get_repo(BedRepository)

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _expected_checkout_date(self, check_in: date, months: int) -> date:
        # Very simple month→days approximation; customize as needed
        return check_in + timedelta(days=30 * months)

    def _booking_reference(self, booking_id: UUID) -> str:
        return f"BKG-{str(booking_id)[:8].upper()}"

    # ------------------------------------------------------------------ #
    # Mapping helpers
    # ------------------------------------------------------------------ #
    def _to_response(self, b) -> BookingResponse:
        hostel = getattr(b, "hostel", None)
        advance_paid = any((p.payment_status.name == "COMPLETED" and p.payment_type.name == "BOOKING_ADVANCE")
                           for p in getattr(b, "payments", []) or [])

        return BookingResponse(
            id=b.id,
            created_at=b.created_at,
            updated_at=b.updated_at,
            booking_reference=self._booking_reference(b.id),
            visitor_id=b.visitor_id,
            hostel_id=b.hostel_id,
            hostel_name=hostel.name if hostel else "",
            room_type_requested=b.room_type_requested,
            preferred_check_in_date=b.preferred_check_in_date,
            stay_duration_months=b.stay_duration_months,
            expected_check_out_date=self._expected_checkout_date(
                b.preferred_check_in_date, b.stay_duration_months
            ),
            guest_name=b.guest_name,
            guest_email=b.guest_email,
            guest_phone=b.guest_phone,
            quoted_rent_monthly=b.quoted_rent_monthly,
            total_amount=b.total_amount,
            security_deposit=b.security_deposit,
            advance_amount=b.advance_amount,
            advance_paid=advance_paid,
            booking_status=b.booking_status,
            booking_date=b.booking_date,
            expires_at=b.expires_at,
        )

    def _to_detail(self, b, hostel_name: str, hostel_city: str, hostel_address: str, hostel_phone: str,
                   room_number: Optional[str], bed_number: Optional[str]) -> BookingDetail:
        advance_payment = None
        for p in getattr(b, "payments", []) or []:
            if p.payment_type.name == "BOOKING_ADVANCE":
                advance_payment = p
                break

        advance_paid = advance_payment is not None and advance_payment.payment_status.name == "COMPLETED"
        advance_payment_id = advance_payment.id if advance_payment else None

        approved_by = None
        approved_by_name = None
        # You can later wire this to a workflow/approval store

        rejected_by = None
        rejected_at = None
        rejection_reason = None

        cancelled_by = None
        cancelled_at = None
        cancellation_reason = None

        converted_to_student = False
        student_profile_id = None
        conversion_date = None

        return BookingDetail(
            id=b.id,
            created_at=b.created_at,
            updated_at=b.updated_at,
            booking_reference=self._booking_reference(b.id),
            visitor_id=b.visitor_id,
            visitor_name=b.guest_name,
            hostel_id=b.hostel_id,
            hostel_name=hostel_name,
            hostel_city=hostel_city,
            hostel_address=hostel_address,
            hostel_phone=hostel_phone,
            room_type_requested=b.room_type_requested,
            preferred_check_in_date=b.preferred_check_in_date,
            stay_duration_months=b.stay_duration_months,
            expected_check_out_date=self._expected_checkout_date(
                b.preferred_check_in_date, b.stay_duration_months
            ),
            room_id=b.room_id,
            room_number=room_number,
            bed_id=b.bed_id,
            bed_number=bed_number,
            guest_name=b.guest_name,
            guest_email=b.guest_email,
            guest_phone=b.guest_phone,
            guest_id_proof_type=None,
            guest_id_proof_number=None,
            emergency_contact_name=None,
            emergency_contact_phone=None,
            emergency_contact_relation=None,
            institution_or_company=None,
            designation_or_course=None,
            special_requests=None,
            dietary_preferences=None,
            has_vehicle=False,
            vehicle_details=None,
            quoted_rent_monthly=b.quoted_rent_monthly,
            total_amount=b.total_amount,
            security_deposit=b.security_deposit,
            advance_amount=b.advance_amount,
            advance_paid=advance_paid,
            advance_payment_id=advance_payment_id,
            booking_status=b.booking_status,
            approved_by=approved_by,
            approved_by_name=approved_by_name,
            approved_at=None,
            rejected_by=rejected_by,
            rejected_at=rejected_at,
            rejection_reason=rejection_reason,
            cancelled_by=cancelled_by,
            cancelled_at=cancelled_at,
            cancellation_reason=cancellation_reason,
            converted_to_student=converted_to_student,
            student_profile_id=student_profile_id,
            conversion_date=conversion_date,
            source=b.source,
            referral_code=b.referral_code,
            booking_date=b.booking_date,
            expires_at=b.expires_at,
        )

    def _to_list_item(self, b, hostel_name: str, is_urgent: bool, days_until_checkin: Optional[int]) -> BookingListItem:
        expected_checkout = self._expected_checkout_date(b.preferred_check_in_date, b.stay_duration_months)
        return BookingListItem(
            id=b.id,
            booking_reference=self._booking_reference(b.id),
            guest_name=b.guest_name,
            guest_phone=b.guest_phone,
            hostel_name=hostel_name,
            room_type_requested=b.room_type_requested.value if hasattr(b.room_type_requested, "value") else str(b.room_type_requested),
            preferred_check_in_date=b.preferred_check_in_date,
            stay_duration_months=b.stay_duration_months,
            total_amount=b.total_amount,
            advance_paid=False,  # you can enrich like in _to_response if needed
            booking_status=b.booking_status,
            booking_date=b.booking_date,
            is_urgent=is_urgent,
            days_until_checkin=days_until_checkin,
        )

    # ------------------------------------------------------------------ #
    # Read
    # ------------------------------------------------------------------ #
    def get_booking(self, booking_id: UUID) -> BookingDetail:
        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_booking_repo(uow)
            hostel_repo = self._get_hostel_repo(uow)
            room_repo = self._get_room_repo(uow)
            bed_repo = self._get_bed_repo(uow)

            b = repo.get(booking_id)
            if b is None:
                raise errors.NotFoundError(f"Booking {booking_id} not found")

            hostel = hostel_repo.get(b.hostel_id)
            room = room_repo.get(b.room_id) if b.room_id else None
            bed = bed_repo.get(b.bed_id) if b.bed_id else None

            hostel_name = hostel.name if hostel else ""
            hostel_city = hostel.city if hostel else ""
            hostel_address = hostel.address_line1 if hostel else ""
            hostel_phone = hostel.contact_phone if hostel else ""
            room_number = room.room_number if room else None
            bed_number = bed.bed_number if bed else None

            return self._to_detail(
                b,
                hostel_name=hostel_name,
                hostel_city=hostel_city,
                hostel_address=hostel_address,
                hostel_phone=hostel_phone,
                room_number=room_number,
                bed_number=bed_number,
            )

    # ------------------------------------------------------------------ #
    # Listing & filtering
    # ------------------------------------------------------------------ #
    def list_bookings(
        self,
        params: PaginationParams,
        filters: Optional[BookingFilterParams] = None,
        sort: Optional[BookingSortOptions] = None,
    ) -> PaginatedResponse[BookingListItem]:
        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_booking_repo(uow)
            hostel_repo = self._get_hostel_repo(uow)

            raw_filters: dict = {}
            if filters:
                if filters.hostel_id:
                    raw_filters["hostel_id"] = filters.hostel_id
                if filters.status:
                    raw_filters["booking_status"] = filters.status
                if filters.room_type:
                    raw_filters["room_type_requested"] = filters.room_type
                if filters.source:
                    raw_filters["source"] = filters.source
                if filters.advance_paid is not None:
                    # This requires payment join; here we skip and let higher layer handle.
                    pass
                if filters.converted_to_student is not None:
                    # Requires conversion tracking; skip here.
                    pass

            order_by = None
            if sort:
                col_map = {
                    "booking_date": repo.model.booking_date,          # type: ignore[attr-defined]
                    "check_in_date": repo.model.preferred_check_in_date,  # type: ignore[attr-defined]
                    "guest_name": repo.model.guest_name,             # type: ignore[attr-defined]
                    "status": repo.model.booking_status,             # type: ignore[attr-defined]
                    "total_amount": repo.model.total_amount,         # type: ignore[attr-defined]
                }
                sort_col = col_map.get(sort.sort_by, repo.model.booking_date)  # type: ignore[attr-defined]
                order_by = [sort_col.asc() if sort.sort_order == "asc" else sort_col.desc()]

            records: Sequence = repo.get_multi(
                skip=params.offset,
                limit=params.limit,
                filters=raw_filters or None,
                order_by=order_by,
            )
            total = repo.count(filters=raw_filters or None)

            now = date.today()
            items: List[BookingListItem] = []
            hostel_name_cache: dict[UUID, str] = {}

            for b in records:
                if b.hostel_id not in hostel_name_cache:
                    h = hostel_repo.get(b.hostel_id)
                    hostel_name_cache[b.hostel_id] = h.name if h else ""
                hostel_name = hostel_name_cache[b.hostel_id]

                days_until_checkin: Optional[int] = None
                if b.preferred_check_in_date:
                    days_until_checkin = (b.preferred_check_in_date - now).days
                is_urgent = days_until_checkin is not None and days_until_checkin <= 1 and b.booking_status == BookingStatus.PENDING

                items.append(
                    self._to_list_item(
                        b,
                        hostel_name=hostel_name,
                        is_urgent=is_urgent,
                        days_until_checkin=days_until_checkin,
                    )
                )

            return PaginatedResponse[BookingListItem].create(
                items=items,
                total_items=total,
                page=params.page,
                page_size=params.page_size,
            )

    def search_bookings(
        self,
        params: PaginationParams,
        req: BookingSearchRequest,
    ) -> PaginatedResponse[BookingListItem]:
        """
        Simple in-memory search on booking_reference, guest name, email, phone.
        For large datasets, replace with dedicated queries.
        """
        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_booking_repo(uow)
            hostel_repo = self._get_hostel_repo(uow)

            filters: dict = {}
            if req.hostel_id:
                filters["hostel_id"] = req.hostel_id
            if req.status:
                filters["booking_status"] = req.status

            records: Sequence = repo.get_multi(
                skip=0,
                limit=None,  # type: ignore[arg-type]
                filters=filters or None,
                order_by=[repo.model.booking_date.desc()],  # type: ignore[attr-defined]
            )

            q = req.query.lower()
            filtered: List = []
            for b in records:
                ref = self._booking_reference(b.id).lower()
                if req.search_in_reference and q in ref:
                    filtered.append(b)
                    continue
                if req.search_in_guest_name and q in (b.guest_name or "").lower():
                    filtered.append(b)
                    continue
                if req.search_in_email and q in (b.guest_email or "").lower():
                    filtered.append(b)
                    continue
                if req.search_in_phone and q in (b.guest_phone or "").lower():
                    filtered.append(b)

            total = len(filtered)
            start = params.offset
            end = start + params.limit
            page_items = filtered[start:end]

            now = date.today()
            items: List[BookingListItem] = []
            hostel_name_cache: dict[UUID, str] = {}

            for b in page_items:
                if b.hostel_id not in hostel_name_cache:
                    h = hostel_repo.get(b.hostel_id)
                    hostel_name_cache[b.hostel_id] = h.name if h else ""
                hostel_name = hostel_name_cache[b.hostel_id]

                days_until_checkin: Optional[int] = None
                if b.preferred_check_in_date:
                    days_until_checkin = (b.preferred_check_in_date - now).days
                is_urgent = days_until_checkin is not None and days_until_checkin <= 1 and b.booking_status == BookingStatus.PENDING

                items.append(
                    self._to_list_item(
                        b,
                        hostel_name=hostel_name,
                        is_urgent=is_urgent,
                        days_until_checkin=days_until_checkin,
                    )
                )

            return PaginatedResponse[BookingListItem].create(
                items=items,
                total_items=total,
                page=params.page,
                page_size=params.page_size,
            )

    # ------------------------------------------------------------------ #
    # Create
    # ------------------------------------------------------------------ #
    def create_booking(self, data: BookingCreate) -> BookingDetail:
        """
        Internal creation using BookingCreate schema (admin/dashboard).
        """
        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_booking_repo(uow)

            payload = data.model_dump()
            # Ensure default status
            payload.setdefault("booking_status", BookingStatus.PENDING)
            payload.setdefault("source", BookingSource.WEBSITE)
            payload.setdefault("booking_date", self._now())
            booking = repo.create(payload)  # type: ignore[arg-type]
            uow.commit()
            return self.get_booking(booking.id)

    def create_booking_from_request(
        self,
        visitor_id: UUID,
        data: BookingRequest,
        *,
        source: BookingSource = BookingSource.WEBSITE,
    ) -> BookingDetail:
        """
        Public-facing booking request → internal booking.
        """
        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_booking_repo(uow)

            total_amount = Decimal(str(data.stay_duration_months or 1)) * Decimal("0")
            # A real implementation would consult FeeStructure; here we require client to
            # send correct total_amount via a separate handler, or you can extend this.

            payload = {
                "visitor_id": visitor_id,
                "hostel_id": data.hostel_id,
                "room_type_requested": data.room_type_requested,
                "preferred_check_in_date": data.preferred_check_in_date,
                "stay_duration_months": data.stay_duration_months,
                "quoted_rent_monthly": Decimal("0"),
                "total_amount": total_amount,
                "security_deposit": Decimal("0"),
                "advance_amount": Decimal("0"),
                "booking_status": BookingStatus.PENDING,
                "source": source,
                "referral_code": data.referral_code,
                "booking_date": self._now(),
                "expires_at": None,
                "guest_name": data.guest_info.guest_name,
                "guest_email": data.guest_info.guest_email,
                "guest_phone": data.guest_info.guest_phone,
                "room_id": None,
                "bed_id": None,
            }
            booking = repo.create(payload)  # type: ignore[arg-type]
            uow.commit()
            return self.get_booking(booking.id)

    def quick_booking(
        self,
        visitor_id: UUID,
        data: QuickBookingRequest,
        *,
        source: BookingSource = BookingSource.WEBSITE,
    ) -> BookingDetail:
        """
        Minimal quick-booking endpoint.
        """
        br = BookingRequest(
            hostel_id=data.hostel_id,
            room_type_requested=data.room_type_requested,
            preferred_check_in_date=data.check_in_date,
            stay_duration_months=data.duration_months,
            guest_info={
                "guest_name": data.name,
                "guest_email": data.email,
                "guest_phone": data.phone,
            },
        )  # type: ignore[arg-type]

        return self.create_booking_from_request(visitor_id, br, source=source)

    # ------------------------------------------------------------------ #
    # Update
    # ------------------------------------------------------------------ #
    def update_booking(self, booking_id: UUID, data: BookingUpdate) -> BookingDetail:
        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_booking_repo(uow)
            b = repo.get(booking_id)
            if b is None:
                raise errors.NotFoundError(f"Booking {booking_id} not found")

            mapping = data.model_dump(exclude_unset=True)
            for field, value in mapping.items():
                if hasattr(b, field) and field != "id":
                    setattr(b, field, value)

            uow.session.flush()  # type: ignore[union-attr]
            uow.commit()
            return self.get_booking(booking_id)

    def set_status(self, booking_id: UUID, status: BookingStatus) -> BookingDetail:
        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_booking_repo(uow)
            b = repo.get(booking_id)
            if b is None:
                raise errors.NotFoundError(f"Booking {booking_id} not found")

            b.booking_status = status  # type: ignore[attr-defined]
            uow.session.flush()  # type: ignore[union-attr]
            uow.commit()
            return self.get_booking(booking_id)

    # ------------------------------------------------------------------ #
    # Confirmation
    # ------------------------------------------------------------------ #
    def build_confirmation(self, booking_id: UUID, *, hostel_contact_email: Optional[str]) -> BookingConfirmation:
        """
        Build a BookingConfirmation response from an existing booking.
        """
        detail = self.get_booking(booking_id)
        balance = detail.total_amount - detail.advance_amount
        return BookingConfirmation(
            booking_id=detail.id,
            booking_reference=detail.booking_reference,
            hostel_name=detail.hostel_name,
            room_type=detail.room_type_requested.value if hasattr(detail.room_type_requested, "value") else str(detail.room_type_requested),
            check_in_date=detail.preferred_check_in_date,
            total_amount=detail.total_amount,
            advance_amount=detail.advance_amount,
            balance_amount=balance,
            confirmation_message="Your booking has been confirmed.",
            next_steps=[
                "Complete payment before check-in.",
                "Bring a valid ID proof.",
            ],
            hostel_contact_phone=detail.hostel_phone,
            hostel_contact_email=hostel_contact_email,
        )