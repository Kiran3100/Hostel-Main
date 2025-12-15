# app/services/student/student_search_service.py
from __future__ import annotations

from typing import Callable, Dict, List
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.core import (
    StudentRepository,
    UserRepository,
    RoomRepository,
    BedRepository,
)
from app.schemas.common.pagination import PaginatedResponse
from app.schemas.student.student_filters import (
    StudentSearchRequest,
    StudentSortOptions,
)
from app.schemas.student.student_response import StudentListItem
from app.services.common import UnitOfWork


class StudentSearchService:
    """
    Advanced student search service:

    - Full-text-ish search over name/email/phone/room/institution.
    - Pagination & simple sorting options.
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

    def _get_room_repo(self, uow: UnitOfWork) -> RoomRepository:
        return uow.get_repo(RoomRepository)

    def _get_bed_repo(self, uow: UnitOfWork) -> BedRepository:
        return uow.get_repo(BedRepository)

    # ------------------------------------------------------------------ #
    # Search
    # ------------------------------------------------------------------ #
    def search(self, req: StudentSearchRequest) -> PaginatedResponse[StudentListItem]:
        with UnitOfWork(self._session_factory) as uow:
            student_repo = self._get_student_repo(uow)
            user_repo = self._get_user_repo(uow)
            room_repo = self._get_room_repo(uow)
            bed_repo = self._get_bed_repo(uow)

            filters: Dict[str, object] = {}
            if req.hostel_id:
                filters["hostel_id"] = req.hostel_id
            if req.status:
                filters["student_status"] = req.status

            students = student_repo.get_multi(
                skip=0,
                limit=None,  # type: ignore[arg-type]
                filters=filters or None,
            )

            q = req.query.lower()

            user_cache: Dict[UUID, object] = {}
            room_cache: Dict[UUID, object] = {}
            bed_cache: Dict[UUID, object] = {}

            def _matches(s) -> bool:
                # load user
                if s.user_id not in user_cache:
                    user_cache[s.user_id] = user_repo.get(s.user_id)
                user = user_cache[s.user_id]
                if user is None:
                    return False

                haystack_parts: List[str] = []
                if req.search_in_name:
                    haystack_parts.append(getattr(user, "full_name", ""))
                if req.search_in_email:
                    haystack_parts.append(getattr(user, "email", ""))
                if req.search_in_phone:
                    haystack_parts.append(getattr(user, "phone", ""))

                if req.search_in_room:
                    if s.room_id:
                        if s.room_id not in room_cache:
                            room_cache[s.room_id] = room_repo.get(s.room_id)
                        room = room_cache[s.room_id]
                        if room:
                            haystack_parts.append(room.room_number or "")
                    if s.bed_id:
                        if s.bed_id not in bed_cache:
                            bed_cache[s.bed_id] = bed_repo.get(s.bed_id)
                        bed = bed_cache[s.bed_id]
                        if bed:
                            haystack_parts.append(bed.bed_number or "")

                if req.search_in_institution:
                    haystack_parts.append(s.institution_name or "")

                haystack = " ".join(haystack_parts).lower()
                return q in haystack

            matched = [s for s in students if _matches(s)]

            # Sorting (simple: by created_at desc)
            matched_sorted = sorted(matched, key=lambda s: s.created_at, reverse=True)

            # Pagination
            page = req.page
            page_size = req.page_size
            offset = (page - 1) * page_size
            page_records = matched_sorted[offset : offset + page_size]

            items: List[StudentListItem] = []
            for s in page_records:
                user = user_cache[s.user_id]
                room_number = bed_number = None
                if s.room_id:
                    room = room_cache.get(s.room_id)
                    if room:
                        room_number = room.room_number
                if s.bed_id:
                    bed = bed_cache.get(s.bed_id)
                    if bed:
                        bed_number = bed.bed_number

                items.append(
                    StudentListItem(
                        id=s.id,
                        user_id=s.user_id,
                        full_name=user.full_name,
                        email=user.email,
                        phone=getattr(user, "phone", ""),
                        room_number=room_number,
                        bed_number=bed_number,
                        student_status=s.student_status,
                        check_in_date=s.check_in_date,
                        monthly_rent=s.monthly_rent_amount,
                        payment_status="current",
                        created_at=s.created_at,
                    )
                )

            return PaginatedResponse[StudentListItem].create(
                items=items,
                total_items=len(matched),
                page=page,
                page_size=page_size,
            )