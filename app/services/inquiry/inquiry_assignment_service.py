# app/services/inquiry/inquiry_assignment_service.py
from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.services import InquiryRepository
from app.repositories.core import AdminRepository, HostelRepository
from app.schemas.common.enums import InquiryStatus
from app.schemas.inquiry import (
    InquiryAssignment,
    InquiryDetail,
)
from app.services.common import UnitOfWork, errors


class InquiryAssignmentService:
    """
    Handle assigning inquiries to admins / staff.

    Semantics:
    - inquiry.contacted_by_id is used as the "assigned_to" admin/staff.
    - inquiry.status is typically moved out of NEW when assigned (e.g., to PENDING).
    - contacted_at is set when first assigned.
    - assignment_notes are appended to inquiry.notes.
    """

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    def _get_inquiry_repo(self, uow: UnitOfWork) -> InquiryRepository:
        return uow.get_repo(InquiryRepository)

    def _get_admin_repo(self, uow: UnitOfWork) -> AdminRepository:
        return uow.get_repo(AdminRepository)

    def _get_hostel_repo(self, uow: UnitOfWork) -> HostelRepository:
        return uow.get_repo(HostelRepository)

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    # ------------------------------------------------------------------ #
    # Assign
    # ------------------------------------------------------------------ #
    def assign(self, data: InquiryAssignment) -> InquiryDetail:
        """
        Assign an inquiry to an admin/staff.

        - Sets inquiry.contacted_by_id = assigned_to
        - Sets inquiry.contacted_at if not already set
        - Optionally updates status to a non-NEW state (e.g., PENDING)
        - Appends assignment_notes into inquiry.notes
        """
        with UnitOfWork(self._session_factory) as uow:
            inquiry_repo = self._get_inquiry_repo(uow)
            admin_repo = self._get_admin_repo(uow)
            hostel_repo = self._get_hostel_repo(uow)

            inq = inquiry_repo.get(data.inquiry_id)
            if inq is None:
                raise errors.NotFoundError(f"Inquiry {data.inquiry_id} not found")

            assigned_admin = admin_repo.get(data.assigned_to)
            if assigned_admin is None:
                raise errors.NotFoundError(f"Admin {data.assigned_to} not found")

            # Set contacted_by and contacted_at
            inq.contacted_by_id = data.assigned_to  # type: ignore[attr-defined]
            if inq.contacted_at is None:
                inq.contacted_at = self._now()  # type: ignore[attr-defined]

            # Move status from NEW → PENDING by default (if still NEW)
            try:
                if inq.status == InquiryStatus.NEW:
                    inq.status = InquiryStatus.PENDING  # type: ignore[attr-defined]
            except Exception:
                # If enum does not have PENDING, ignore; status is left as is
                pass

            # Append assignment notes to inquiry.notes
            if data.assignment_notes:
                existing = inq.notes or ""  # type: ignore[attr-defined]
                if existing:
                    existing += "\n"
                inq.notes = existing + data.assignment_notes  # type: ignore[attr-defined]

            uow.session.flush()  # type: ignore[union-attr]
            uow.commit()

            hostel = hostel_repo.get(inq.hostel_id)
            hostel_name = hostel.name if hostel else ""

            assigned_user = assigned_admin.user if getattr(assigned_admin, "user", None) else None
            contacted_by_name = assigned_user.full_name if assigned_user else None

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