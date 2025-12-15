# app/services/inquiry/inquiry_service.py
from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable, Optional, Sequence, List
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.services import InquiryRepository
from app.repositories.core import HostelRepository, AdminRepository
from app.schemas.common.enums import InquiryStatus
from app.schemas.common.pagination import PaginationParams, PaginatedResponse
from app.schemas.inquiry import (
    InquiryCreate,
    InquiryResponse,
    InquiryDetail,
    InquiryListItem,
    InquiryStatusUpdate,
)
from app.services.common import UnitOfWork, errors


class InquiryService:
    """
    Visitor inquiry service:

    - Create inquiry
    - Get inquiry detail
    - List inquiries for a hostel
    - Update inquiry status
    """

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _get_inquiry_repo(self, uow: UnitOfWork) -> InquiryRepository:
        return uow.get_repo(InquiryRepository)

    def _get_hostel_repo(self, uow: UnitOfWork) -> HostelRepository:
        return uow.get_repo(HostelRepository)

    def _get_admin_repo(self, uow: UnitOfWork) -> AdminRepository:
        return uow.get_repo(AdminRepository)

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    # ------------------------------------------------------------------ #
    # Mapping helpers
    # ------------------------------------------------------------------ #
    def _to_response(self, inq, *, hostel_name: str) -> InquiryResponse:
        return InquiryResponse(
            id=inq.id,
            created_at=inq.created_at,
            updated_at=inq.updated_at,
            hostel_id=inq.hostel_id,
            hostel_name=hostel_name,
            visitor_name=inq.visitor_name,
            visitor_email=inq.visitor_email,
            visitor_phone=inq.visitor_phone,
            preferred_check_in_date=inq.preferred_check_in_date,
            stay_duration_months=inq.stay_duration_months,
            room_type_preference=inq.room_type_preference,
            status=inq.status,
        )

    def _to_detail(
        self,
        inq,
        *,
        hostel_name: str,
        contacted_by_name: Optional[str],
    ) -> InquiryDetail:
        return InquiryDetail(
            id=inq.id,
            created_at=inq.created_at,
            updated_at=inq.updated_at,
            hostel_id=inq.hostel_id,
            hostel_name=hostel_name,
            visitor_name=inq.visitor_name,
            visitor_email=inq.visitor_email,
            visitor_phone=inq.visitor_phone,
            preferred_check_in_date=inq.preferred_check_in_date,
            stay_duration_months=inq.stay_duration_months,
            room_type_preference=inq.room_type_preference,
            message=inq.message,
            inquiry_source=inq.inquiry_source,
            status=inq.status,
            contacted_by=inq.contacted_by_id,
            contacted_by_name=contacted_by_name,
            contacted_at=inq.contacted_at,
            notes=inq.notes,
        )

    def _to_list_item(self, inq, *, hostel_name: str) -> InquiryListItem:
        return InquiryListItem(
            id=inq.id,
            hostel_name=hostel_name,
            visitor_name=inq.visitor_name,
            visitor_phone=inq.visitor_phone,
            preferred_check_in_date=inq.preferred_check_in_date,
            stay_duration_months=inq.stay_duration_months,
            room_type_preference=inq.room_type_preference,
            status=inq.status,
            created_at=inq.created_at,
        )

    # ------------------------------------------------------------------ #
    # Create / read
    # ------------------------------------------------------------------ #
    def create_inquiry(self, data: InquiryCreate) -> InquiryDetail:
        """
        Create a new visitor inquiry.

        - Validates hostel existence.
        - Uses the default status from InquiryCreate (typically NEW).
        """
        with UnitOfWork(self._session_factory) as uow:
            inquiry_repo = self._get_inquiry_repo(uow)
            hostel_repo = self._get_hostel_repo(uow)

            hostel = hostel_repo.get(data.hostel_id)
            if hostel is None:
                raise errors.NotFoundError(f"Hostel {data.hostel_id} not found")

            payload = data.model_dump()
            inq = inquiry_repo.create(payload)  # type: ignore[arg-type]
            uow.commit()

            return self._to_detail(
                inq,
                hostel_name=hostel.name,
                contacted_by_name=None,
            )

    def get_inquiry(self, inquiry_id: UUID) -> InquiryDetail:
        """
        Fetch detailed information for a single inquiry.
        """
        with UnitOfWork(self._session_factory) as uow:
            inquiry_repo = self._get_inquiry_repo(uow)
            hostel_repo = self._get_hostel_repo(uow)
            admin_repo = self._get_admin_repo(uow)

            inq = inquiry_repo.get(inquiry_id)
            if inq is None:
                raise errors.NotFoundError(f"Inquiry {inquiry_id} not found")

            hostel = hostel_repo.get(inq.hostel_id)
            hostel_name = hostel.name if hostel else ""

            contacted_by_name = None
            if inq.contacted_by_id:
                admin = admin_repo.get(inq.contacted_by_id)
                if admin and getattr(admin, "user", None):
                    contacted_by_name = admin.user.full_name

            return self._to_detail(
                inq,
                hostel_name=hostel_name,
                contacted_by_name=contacted_by_name,
            )

    # ------------------------------------------------------------------ #
    # Listing
    # ------------------------------------------------------------------ #
    def list_inquiries_for_hostel(
        self,
        hostel_id: UUID,
        params: PaginationParams,
        *,
        status: Optional[InquiryStatus] = None,
    ) -> PaginatedResponse[InquiryListItem]:
        """
        List inquiries for a hostel with optional status filter.
        """
        with UnitOfWork(self._session_factory) as uow:
            inquiry_repo = self._get_inquiry_repo(uow)
            hostel_repo = self._get_hostel_repo(uow)

            hostel = hostel_repo.get(hostel_id)
            if hostel is None:
                raise errors.NotFoundError(f"Hostel {hostel_id} not found")
            hostel_name = hostel.name

            filters: dict = {"hostel_id": hostel_id}
            if status is not None:
                filters["status"] = status

            records: Sequence = inquiry_repo.get_multi(
                skip=params.offset,
                limit=params.limit,
                filters=filters or None,
                order_by=[inquiry_repo.model.created_at.desc()],  # type: ignore[attr-defined]
            )
            total = inquiry_repo.count(filters=filters or None)

            items: List[InquiryListItem] = [
                self._to_list_item(inq, hostel_name=hostel_name) for inq in records
            ]

            return PaginatedResponse[InquiryListItem].create(
                items=items,
                total_items=total,
                page=params.page,
                page_size=params.page_size,
            )

    # ------------------------------------------------------------------ #
    # Status update
    # ------------------------------------------------------------------ #
    def update_status(self, data: InquiryStatusUpdate) -> InquiryDetail:
        """
        Update inquiry.status and optionally append notes.

        Status transitions (e.g., NEW -> PENDING -> CONTACTED -> CLOSED)
        are not enforced here; they should be validated at API/business layer
        if you want strict workflows.
        """
        with UnitOfWork(self._session_factory) as uow:
            inquiry_repo = self._get_inquiry_repo(uow)
            hostel_repo = self._get_hostel_repo(uow)
            admin_repo = self._get_admin_repo(uow)

            inq = inquiry_repo.get(data.inquiry_id)
            if inq is None:
                raise errors.NotFoundError(f"Inquiry {data.inquiry_id} not found")

            inq.status = data.new_status  # type: ignore[attr-defined]

            if data.notes:
                # Append notes to existing notes (simple concatenation)
                existing = inq.notes or ""  # type: ignore[attr-defined]
                if existing:
                    existing += "\n"
                inq.notes = existing + data.notes  # type: ignore[attr-defined]

            uow.session.flush()  # type: ignore[union-attr]
            uow.commit()

            hostel = hostel_repo.get(inq.hostel_id)
            hostel_name = hostel.name if hostel else ""

            contacted_by_name = None
            if inq.contacted_by_id:
                admin = admin_repo.get(inq.contacted_by_id)
                if admin and getattr(admin, "user", None):
                    contacted_by_name = admin.user.full_name

            return self._to_detail(
                inq,
                hostel_name=hostel_name,
                contacted_by_name=contacted_by_name,
            )