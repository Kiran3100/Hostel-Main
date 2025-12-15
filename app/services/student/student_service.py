# app/services/student/student_service.py
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Callable, Dict, List, Optional, Sequence
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.core import (
    StudentRepository,
    UserRepository,
    HostelRepository,
    RoomRepository,
    BedRepository,
)
from app.schemas.common.enums import StudentStatus
from app.schemas.common.pagination import PaginationParams, PaginatedResponse
from app.schemas.student import (
    StudentCreate,
    StudentUpdate,
    StudentResponse,
    StudentDetail,
    StudentListItem,
    StudentFilterParams,
    StudentSortOptions,
)
from app.services.common import UnitOfWork, errors


class StudentService:
    """
    Core student service:

    - Create/update students
    - Get student detail
    - List students with filters + sorting
    """

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _get_student_repo(self, uow: UnitOfWork) -> StudentRepository:
        return uow.get_repo(StudentRepository)

    def _get_user_repo(self, uow: UnitOfWork) -> UserRepository:
        return uow.get_repo(UserRepository)

    def _get_hostel_repo(self, uow: UnitOfWork) -> HostelRepository:
        return uow.get_repo(HostelRepository)

    def _get_room_repo(self, uow: UnitOfWork) -> RoomRepository:
        return uow.get_repo(RoomRepository)

    def _get_bed_repo(self, uow: UnitOfWork) -> BedRepository:
        return uow.get_repo(BedRepository)

    def _now(self) -> datetime:
        return datetime.utcnow()

    # ------------------------------------------------------------------ #
    # Mapping helpers
    # ------------------------------------------------------------------ #
    def _room_bed_labels(self, student, room_repo: RoomRepository, bed_repo: BedRepository) -> tuple[Optional[str], Optional[str]]:
        room_number = bed_number = None
        if student.room_id:
            room = room_repo.get(student.room_id)
            room_number = room.room_number if room else None
        if student.bed_id:
            bed = bed_repo.get(student.bed_id)
            bed_number = bed.bed_number if bed else None
        return room_number, bed_number

    def _to_response(
        self,
        s,
        *,
        hostel_name: str,
        room_number: Optional[str],
        bed_number: Optional[str],
        user,
    ) -> StudentResponse:
        # Payment & deposit derived fields are placeholders here
        security_deposit_paid = False

        return StudentResponse(
            id=s.id,
            created_at=s.created_at,
            updated_at=s.updated_at,
            user_id=s.user_id,
            hostel_id=s.hostel_id,
            hostel_name=hostel_name,
            room_id=s.room_id,
            room_number=room_number,
            bed_id=s.bed_id,
            bed_number=bed_number,
            full_name=user.full_name,
            email=user.email,
            phone=getattr(user, "phone", ""),
            guardian_name=s.guardian_name,
            guardian_phone=s.guardian_phone,
            student_status=s.student_status,
            check_in_date=s.check_in_date,
            expected_checkout_date=s.expected_checkout_date,
            monthly_rent_amount=s.monthly_rent_amount,
            security_deposit_amount=s.security_deposit_amount,
            security_deposit_paid=security_deposit_paid,
            mess_subscribed=s.mess_subscribed,
        )

    def _to_detail(
        self,
        s,
        *,
        user,
        hostel_name: str,
        room_number: Optional[str],
        room_type: Optional[str],
        bed_number: Optional[str],
    ) -> StudentDetail:
        return StudentDetail(
            id=s.id,
            created_at=s.created_at,
            updated_at=s.updated_at,
            user_id=user.id,
            full_name=user.full_name,
            email=user.email,
            phone=getattr(user, "phone", ""),
            gender=getattr(user, "gender", None).value if getattr(user, "gender", None) else None,
            date_of_birth=getattr(user, "date_of_birth", None),
            profile_image_url=getattr(user, "profile_image_url", None),
            hostel_id=s.hostel_id,
            hostel_name=hostel_name,
            room_id=s.room_id,
            room_number=room_number,
            room_type=room_type,
            bed_id=s.bed_id,
            bed_number=bed_number,
            id_proof_type=s.id_proof_type,
            id_proof_number=s.id_proof_number,
            id_proof_document_url=None,
            guardian_name=s.guardian_name,
            guardian_phone=s.guardian_phone,
            guardian_email=s.guardian_email,
            guardian_relation=s.guardian_relation,
            guardian_address=s.guardian_address,
            institution_name=s.institution_name,
            course=s.course,
            year_of_study=s.year_of_study,
            student_id_number=None,
            company_name=s.company_name,
            designation=s.designation,
            company_id_url=None,
            check_in_date=s.check_in_date,
            expected_checkout_date=s.expected_checkout_date,
            actual_checkout_date=s.actual_checkout_date,
            security_deposit_amount=s.security_deposit_amount,
            security_deposit_paid=False,
            security_deposit_paid_date=None,
            monthly_rent_amount=s.monthly_rent_amount,
            mess_subscribed=s.mess_subscribed,
            dietary_preference=s.dietary_preference,
            food_allergies=s.food_allergies,
            student_status=s.student_status,
            notice_period_start=None,
            notice_period_end=None,
            booking_id=None,
            additional_documents=[],
        )

    def _to_list_item(
        self,
        s,
        *,
        user,
        room_number: Optional[str],
        bed_number: Optional[str],
        payment_status: str,
    ) -> StudentListItem:
        return StudentListItem(
            id=s.id,
            user_id=user.id,
            full_name=user.full_name,
            email=user.email,
            phone=getattr(user, "phone", ""),
            room_number=room_number,
            bed_number=bed_number,
            student_status=s.student_status,
            check_in_date=s.check_in_date,
            monthly_rent=s.monthly_rent_amount,
            payment_status=payment_status,
            created_at=s.created_at,
        )

    # ------------------------------------------------------------------ #
    # CRUD
    # ------------------------------------------------------------------ #
    def create_student(self, data: StudentCreate) -> StudentDetail:
        with UnitOfWork(self._session_factory) as uow:
            student_repo = self._get_student_repo(uow)
            user_repo = self._get_user_repo(uow)
            hostel_repo = self._get_hostel_repo(uow)
            room_repo = self._get_room_repo(uow)

            user = user_repo.get(data.user_id)
            if user is None:
                raise errors.NotFoundError(f"User {data.user_id} not found")

            hostel = hostel_repo.get(data.hostel_id)
            if hostel is None:
                raise errors.NotFoundError(f"Hostel {data.hostel_id} not found")

            if data.room_id:
                room = room_repo.get(data.room_id)
                if room is None:
                    raise errors.NotFoundError(f"Room {data.room_id} not found")

            payload = data.model_dump(exclude_unset=True)
            student = student_repo.create(payload)  # type: ignore[arg-type]
            uow.commit()

            room_number, bed_number = self._room_bed_labels(student, room_repo, self._get_bed_repo(uow))
            room_type = None
            if student.room_id:
                room = room_repo.get(student.room_id)
                room_type = room.room_type.value if room and hasattr(room.room_type, "value") else None

            return self._to_detail(
                student,
                user=user,
                hostel_name=hostel.name,
                room_number=room_number,
                room_type=room_type,
                bed_number=bed_number,
            )

    def update_student(self, student_id: UUID, data: StudentUpdate) -> StudentDetail:
        with UnitOfWork(self._session_factory) as uow:
            student_repo = self._get_student_repo(uow)

            s = student_repo.get(student_id)
            if s is None:
                raise errors.NotFoundError(f"Student {student_id} not found")

            mapping = data.model_dump(exclude_unset=True)
            for field, value in mapping.items():
                if hasattr(s, field) and field != "id":
                    setattr(s, field, value)

            uow.session.flush()  # type: ignore[union-attr]
            uow.commit()

        return self.get_student(student_id)

    def get_student(self, student_id: UUID) -> StudentDetail:
        with UnitOfWork(self._session_factory) as uow:
            student_repo = self._get_student_repo(uow)
            user_repo = self._get_user_repo(uow)
            hostel_repo = self._get_hostel_repo(uow)
            room_repo = self._get_room_repo(uow)

            s = student_repo.get(student_id)
            if s is None:
                raise errors.NotFoundError(f"Student {student_id} not found")

            user = user_repo.get(s.user_id)
            if user is None:
                raise errors.NotFoundError(f"User {s.user_id} not found")

            hostel = hostel_repo.get(s.hostel_id)
            hostel_name = hostel.name if hostel else ""

            room_number, bed_number = self._room_bed_labels(s, room_repo, self._get_bed_repo(uow))
            room_type = None
            if s.room_id:
                room = room_repo.get(s.room_id)
                room_type = room.room_type.value if room and hasattr(room.room_type, "value") else None

            return self._to_detail(
                s,
                user=user,
                hostel_name=hostel_name,
                room_number=room_number,
                room_type=room_type,
                bed_number=bed_number,
            )

    # ------------------------------------------------------------------ #
    # Listing with filters/sort
    # ------------------------------------------------------------------ #
    def list_students(
        self,
        params: PaginationParams,
        filters: Optional[StudentFilterParams] = None,
        sort: Optional[StudentSortOptions] = None,
    ) -> PaginatedResponse[StudentListItem]:
        with UnitOfWork(self._session_factory) as uow:
            student_repo = self._get_student_repo(uow)
            user_repo = self._get_user_repo(uow)
            room_repo = self._get_room_repo(uow)
            bed_repo = self._get_bed_repo(uow)

            raw_filters: Dict[str, object] = {}
            if filters:
                if filters.hostel_id:
                    raw_filters["hostel_id"] = filters.hostel_id
                elif filters.hostel_ids:
                    raw_filters["hostel_id"] = filters.hostel_ids
                if filters.status:
                    raw_filters["student_status"] = filters.status
                elif filters.statuses:
                    raw_filters["student_status"] = filters.statuses

            records: Sequence = student_repo.get_multi(
                skip=0,
                limit=None,  # type: ignore[arg-type]
                filters=raw_filters or None,
            )

            # Advanced filter logic
            def _matches(s) -> bool:
                if not filters:
                    return True

                if filters.checked_in_after and (not s.check_in_date or s.check_in_date < filters.checked_in_after):
                    return False
                if filters.checked_in_before and (not s.check_in_date or s.check_in_date > filters.checked_in_before):
                    return False

                if filters.expected_checkout_after and (
                    not s.expected_checkout_date or s.expected_checkout_date < filters.expected_checkout_after
                ):
                    return False
                if filters.expected_checkout_before and (
                    not s.expected_checkout_date or s.expected_checkout_date > filters.expected_checkout_before
                ):
                    return False

                if filters.mess_subscribed is not None and s.mess_subscribed != filters.mess_subscribed:
                    return False

                if filters.institution_name and (s.institution_name or "").lower() != filters.institution_name.lower():
                    return False
                if filters.course and (s.course or "").lower() != filters.course.lower():
                    return False
                if filters.company_name and (s.company_name or "").lower() != filters.company_name.lower():
                    return False

                return True

            filtered = [s for s in records if _matches(s)]

            # Sorting
            sort = sort or StudentSortOptions()
            def _sort_key(s):
                if sort.sort_by == "name":
                    return getattr(s, "full_name", "").lower()
                if sort.sort_by == "check_in_date":
                    return s.check_in_date or datetime.min.date()
                if sort.sort_by == "monthly_rent":
                    return s.monthly_rent_amount or Decimal("0")
                # Fallback: created_at
                return s.created_at

            reverse = sort.sort_order == "desc"
            filtered_sorted = sorted(filtered, key=_sort_key, reverse=reverse)

            # Pagination
            start = params.offset
            end = start + params.limit
            page_records = filtered_sorted[start:end]

            # Map to list items
            user_cache: Dict[UUID, object] = {}
            room_cache: Dict[UUID, object] = {}
            bed_cache: Dict[UUID, object] = {}

            items: List[StudentListItem] = []
            for s in page_records:
                # user
                if s.user_id not in user_cache:
                    user_cache[s.user_id] = user_repo.get(s.user_id)
                user = user_cache[s.user_id]
                if user is None:
                    continue

                # room/bed
                room_number = bed_number = None
                if s.room_id:
                    if s.room_id not in room_cache:
                        room_cache[s.room_id] = room_repo.get(s.room_id)
                    room = room_cache[s.room_id]
                    room_number = room.room_number if room else None
                if s.bed_id:
                    if s.bed_id not in bed_cache:
                        bed_cache[s.bed_id] = bed_repo.get(s.bed_id)
                    bed = bed_cache[s.bed_id]
                    bed_number = bed.bed_number if bed else None

                # payment_status placeholder
                payment_status = "current"
                items.append(
                    self._to_list_item(
                        s,
                        user=user,
                        room_number=room_number,
                        bed_number=bed_number,
                        payment_status=payment_status,
                    )
                )

            return PaginatedResponse[StudentListItem].create(
                items=items,
                total_items=len(filtered_sorted),
                page=params.page,
                page_size=params.page_size,
            )