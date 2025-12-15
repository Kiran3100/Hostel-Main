# app/services/complaint/complaint_service.py
from __future__ import annotations

from datetime import datetime, timezone, date
from typing import Callable, Optional, Sequence, List
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.services import ComplaintRepository
from app.repositories.core import RoomRepository, StudentRepository
from app.schemas.common.pagination import PaginationParams, PaginatedResponse
from app.schemas.common.enums import ComplaintStatus, Priority
from app.schemas.complaint import (
    ComplaintCreate,
    ComplaintUpdate,
    ComplaintStatusUpdate,
    ComplaintResponse,
    ComplaintDetail,
    ComplaintListItem,
    ComplaintFilterParams,
    ComplaintSortOptions,
    ComplaintSummary,
)
from app.services.common import UnitOfWork, pagination, errors


class ComplaintService:
    """
    Core Complaint service:

    - Create / update complaints
    - Change status
    - Retrieve single complaint detail
    - List complaints with basic filters/sorting
    - Summary stats per hostel
    """

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _get_repo(self, uow: UnitOfWork) -> ComplaintRepository:
        return uow.get_repo(ComplaintRepository)

    def _get_room_repo(self, uow: UnitOfWork) -> RoomRepository:
        return uow.get_repo(RoomRepository)

    def _get_student_repo(self, uow: UnitOfWork) -> StudentRepository:
        return uow.get_repo(StudentRepository)

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _complaint_number(self, complaint_id: UUID) -> str:
        # Simple complaint number format; customize as needed
        return f"CMP-{str(complaint_id)[:8].upper()}"

    # ------------------------------------------------------------------ #
    # Mapping helpers
    # ------------------------------------------------------------------ #
    def _to_list_item(self, c, now: Optional[datetime] = None, room_number: Optional[str] = None,
                      raised_by_name: Optional[str] = None,
                      assigned_to_name: Optional[str] = None) -> ComplaintListItem:
        if now is None:
            now = self._now()
        opened_at = c.opened_at
        age_hours = int((now - opened_at).total_seconds() // 3600) if opened_at else 0

        return ComplaintListItem(
            id=c.id,
            complaint_number=self._complaint_number(c.id),
            title=c.title,
            category=c.category.value if hasattr(c.category, "value") else str(c.category),
            priority=c.priority.value if hasattr(c.priority, "value") else str(c.priority),
            status=c.status,
            raised_by_name=raised_by_name or "",
            room_number=room_number,
            assigned_to_name=assigned_to_name,
            opened_at=opened_at,
            age_hours=age_hours,
            sla_breach=c.sla_breach,
        )

    def _to_response(self, c, now: Optional[datetime] = None) -> ComplaintResponse:
        if now is None:
            now = self._now()
        opened_at = c.opened_at
        age_hours = int((now - opened_at).total_seconds() // 3600) if opened_at else 0

        hostel_name = c.hostel.name if getattr(c, "hostel", None) else ""
        raised_by_name = c.raised_by.full_name if getattr(c, "raised_by", None) else ""
        assigned_to_name = None
        if getattr(c, "assigned_to", None) is not None and getattr(c.assigned_to, "user", None):
            assigned_to_name = c.assigned_to.user.full_name

        return ComplaintResponse(
            id=c.id,
            created_at=c.created_at,
            updated_at=c.updated_at,
            complaint_number=self._complaint_number(c.id),
            hostel_id=c.hostel_id,
            hostel_name=hostel_name,
            raised_by=c.raised_by_id,
            raised_by_name=raised_by_name,
            student_id=c.student_id,
            title=c.title,
            category=c.category,
            priority=c.priority,
            status=c.status,
            assigned_to=c.assigned_to_id,
            assigned_to_name=assigned_to_name,
            opened_at=c.opened_at,
            resolved_at=c.resolved_at,
            sla_breach=c.sla_breach,
            age_hours=age_hours,
        )

    def _to_detail(self, c, room_number: Optional[str] = None,
                   student_name: Optional[str] = None) -> ComplaintDetail:
        hostel = getattr(c, "hostel", None)
        raised_by = getattr(c, "raised_by", None)
        raised_by_user = raised_by
        assigned_to = getattr(c, "assigned_to", None)
        assigned_to_user = getattr(assigned_to, "user", None)

        assigned_by = None
        assigned_by_name = None

        closed_by = None
        closed_by_name = None

        escalated = False
        escalated_to = None
        escalated_to_name = None
        escalated_at = None
        escalation_reason = None

        overridden_by_admin = False
        override_admin_id = None
        override_timestamp = None
        override_reason = None

        # Note: for comments/feedback/override/escalation details you may want
        # dedicated models; this implementation focuses on Complaint core fields.
        return ComplaintDetail(
            id=c.id,
            created_at=c.created_at,
            updated_at=c.updated_at,
            complaint_number=self._complaint_number(c.id),
            hostel_id=c.hostel_id,
            hostel_name=hostel.name if hostel else "",
            raised_by=c.raised_by_id,
            raised_by_name=raised_by_user.full_name if raised_by_user else "",
            raised_by_email=raised_by_user.email if raised_by_user else "",
            raised_by_phone=raised_by_user.phone if getattr(raised_by_user, "phone", None) else "",
            student_id=c.student_id,
            student_name=student_name,
            room_number=room_number,
            title=c.title,
            description=c.description,
            category=c.category,
            sub_category=c.sub_category,
            priority=c.priority,
            room_id=c.room_id,
            location_details=c.location_details,
            attachments=c.attachments or [],
            assigned_to=c.assigned_to_id,
            assigned_to_name=assigned_to_user.full_name if assigned_to_user else None,
            assigned_by=assigned_by,
            assigned_by_name=assigned_by_name,
            assigned_at=None,
            reassigned_count=0,
            status=c.status,
            opened_at=c.opened_at,
            in_progress_at=c.in_progress_at,
            resolved_at=c.resolved_at,
            closed_at=c.closed_at,
            closed_by=closed_by,
            closed_by_name=closed_by_name,
            resolution_notes=None,
            resolution_attachments=[],
            estimated_resolution_time=None,
            actual_resolution_time=None,
            student_feedback=None,
            student_rating=None,
            feedback_submitted_at=None,
            sla_breach=c.sla_breach,
            sla_breach_reason=c.sla_breach_reason,
            escalated=escalated,
            escalated_to=escalated_to,
            escalated_to_name=escalated_to_name,
            escalated_at=escalated_at,
            escalation_reason=escalation_reason,
            overridden_by_admin=overridden_by_admin,
            override_admin_id=override_admin_id,
            override_timestamp=override_timestamp,
            override_reason=override_reason,
            total_comments=0,
            age_hours=int((self._now() - c.opened_at).total_seconds() // 3600) if c.opened_at else 0,
            time_to_resolve_hours=None,
        )

    # ------------------------------------------------------------------ #
    # Read operations
    # ------------------------------------------------------------------ #
    def get_complaint(self, complaint_id: UUID) -> ComplaintDetail:
        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_repo(uow)
            room_repo = self._get_room_repo(uow)
            student_repo = self._get_student_repo(uow)

            c = repo.get(complaint_id)
            if c is None:
                raise errors.NotFoundError(f"Complaint {complaint_id} not found")

            room_number = None
            if c.room_id:
                room = room_repo.get(c.room_id)
                room_number = room.room_number if room else None

            student_name = None
            if c.student_id:
                student = student_repo.get(c.student_id)
                if student and getattr(student, "user", None):
                    student_name = student.user.full_name

            return self._to_detail(c, room_number=room_number, student_name=student_name)

    # ------------------------------------------------------------------ #
    # Listing
    # ------------------------------------------------------------------ #
    def list_complaints(
        self,
        params: PaginationParams,
        filters: Optional[ComplaintFilterParams] = None,
        sort: Optional[ComplaintSortOptions] = None,
    ) -> PaginatedResponse[ComplaintListItem]:
        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_repo(uow)

            raw_filters: dict = {}
            if filters:
                if filters.hostel_id:
                    raw_filters["hostel_id"] = filters.hostel_id
                if filters.raised_by:
                    raw_filters["raised_by_id"] = filters.raised_by
                if filters.student_id:
                    raw_filters["student_id"] = filters.student_id
                if filters.assigned_to:
                    raw_filters["assigned_to_id"] = filters.assigned_to
                if filters.category:
                    raw_filters["category"] = filters.category
                if filters.priority:
                    raw_filters["priority"] = filters.priority
                if filters.status:
                    raw_filters["status"] = filters.status
                if filters.room_id:
                    raw_filters["room_id"] = filters.room_id
                if filters.sla_breached_only:
                    raw_filters["sla_breach"] = True

            # Sorting
            order_by = None
            if sort:
                col_map = {
                    "opened_at": repo.model.opened_at,      # type: ignore[attr-defined]
                    "priority": repo.model.priority,        # type: ignore[attr-defined]
                    "status": repo.model.status,            # type: ignore[attr-defined]
                    "category": repo.model.category,        # type: ignore[attr-defined]
                    "age": repo.model.opened_at,            # type: ignore[attr-defined]
                }
                sort_col = col_map.get(sort.sort_by, repo.model.opened_at)  # type: ignore[attr-defined]
                order_by = [sort_col.asc() if sort.sort_order == "asc" else sort_col.desc()]

            records: Sequence = repo.get_multi(
                skip=params.offset,
                limit=params.limit,
                filters=raw_filters or None,
                order_by=order_by,
            )
            total = repo.count(filters=raw_filters or None)

            now = self._now()
            items: List[ComplaintListItem] = []
            for c in records:
                raised_by_name = c.raised_by.full_name if getattr(c, "raised_by", None) else ""
                assigned_to_name = None
                if getattr(c, "assigned_to", None) is not None and getattr(c.assigned_to, "user", None):
                    assigned_to_name = c.assigned_to.user.full_name
                room_number = None
                if c.room_id and getattr(c, "room", None):
                    room_number = c.room.room_number
                items.append(self._to_list_item(c, now=now,
                                                room_number=room_number,
                                                raised_by_name=raised_by_name,
                                                assigned_to_name=assigned_to_name))

            return PaginatedResponse[ComplaintListItem].create(
                items=items,
                total_items=total,
                page=params.page,
                page_size=params.page_size,
            )

    def list_open_for_hostel(
        self,
        hostel_id: UUID,
        params: PaginationParams,
        *,
        category: Optional[ComplaintStatus] = None,
        priority: Optional[Priority] = None,
    ) -> PaginatedResponse[ComplaintListItem]:
        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_repo(uow)
            records = repo.list_open_for_hostel(
                hostel_id,
                category=category,
                priority=priority,
            )
            total = len(records)
            start = params.offset
            end = start + params.limit
            page_items = records[start:end]

            now = self._now()
            items = []
            for c in page_items:
                raised_by_name = c.raised_by.full_name if getattr(c, "raised_by", None) else ""
                assigned_to_name = None
                if getattr(c, "assigned_to", None) is not None and getattr(c.assigned_to, "user", None):
                    assigned_to_name = c.assigned_to.user.full_name
                items.append(self._to_list_item(c, now=now,
                                                raised_by_name=raised_by_name,
                                                assigned_to_name=assigned_to_name))

            return PaginatedResponse[ComplaintListItem].create(
                items=items,
                total_items=total,
                page=params.page,
                page_size=params.page_size,
            )

    # ------------------------------------------------------------------ #
    # Create / update / status
    # ------------------------------------------------------------------ #
    def create_complaint(self, data: ComplaintCreate) -> ComplaintDetail:
        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_repo(uow)

            payload = data.model_dump()
            # Ensure initial status
            payload.setdefault("status", ComplaintStatus.OPEN)
            complaint = repo.create(payload)  # type: ignore[arg-type]
            uow.commit()

            # For detail we may want student/room names; keep it minimal here
            return self.get_complaint(complaint.id)

    def update_complaint(self, complaint_id: UUID, data: ComplaintUpdate) -> ComplaintDetail:
        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_repo(uow)
            complaint = repo.get(complaint_id)
            if complaint is None:
                raise errors.NotFoundError(f"Complaint {complaint_id} not found")

            # Prevent direct status manipulation here; use status_update
            update_data = data.model_copy()
            update_data.status = None
            mapping_dict = update_data.model_dump(exclude_unset=True)
            for field, value in mapping_dict.items():
                if field == "status":
                    continue
                if hasattr(complaint, field):
                    setattr(complaint, field, value)

            uow.session.flush()  # type: ignore[union-attr]
            uow.commit()
            return self.get_complaint(complaint_id)

    def update_status(self, complaint_id: UUID, data: ComplaintStatusUpdate) -> ComplaintDetail:
        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_repo(uow)
            complaint = repo.get(complaint_id)
            if complaint is None:
                raise errors.NotFoundError(f"Complaint {complaint_id} not found")

            new_status = data.status
            now = self._now()

            complaint.status = new_status  # type: ignore[attr-defined]
            if new_status == ComplaintStatus.IN_PROGRESS and complaint.in_progress_at is None:
                complaint.in_progress_at = now  # type: ignore[attr-defined]
            if new_status == ComplaintStatus.RESOLVED and complaint.resolved_at is None:
                complaint.resolved_at = now  # type: ignore[attr-defined]
            if new_status == ComplaintStatus.CLOSED and complaint.closed_at is None:
                complaint.closed_at = now  # type: ignore[attr-defined]

            uow.session.flush()  # type: ignore[union-attr]
            uow.commit()
            return self.get_complaint(complaint_id)

    # ------------------------------------------------------------------ #
    # Summary
    # ------------------------------------------------------------------ #
    def get_summary_for_hostel(self, hostel_id: UUID) -> ComplaintSummary:
        """
        Simple summary metrics for a hostel's complaints.
        """
        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_repo(uow)
            complaints = repo.get_multi(
                skip=0,
                limit=None,  # type: ignore[arg-type]
                filters={"hostel_id": hostel_id},
            )

            total = len(complaints)
            open_count = 0
            in_progress = 0
            resolved = 0
            high_priority = 0
            urgent_priority = 0
            sla_breached = 0
            total_resolution_hours = 0
            resolved_with_time = 0

            for c in complaints:
                if c.status == ComplaintStatus.OPEN:
                    open_count += 1
                if c.status == ComplaintStatus.IN_PROGRESS:
                    in_progress += 1
                if c.status == ComplaintStatus.RESOLVED:
                    resolved += 1

                if c.priority == Priority.HIGH:
                    high_priority += 1
                if c.priority in (Priority.URGENT, Priority.CRITICAL):
                    urgent_priority += 1

                if c.sla_breach:
                    sla_breached += 1

                if c.resolved_at and c.opened_at:
                    diff = c.resolved_at - c.opened_at
                    hours = diff.total_seconds() / 3600.0
                    total_resolution_hours += hours
                    resolved_with_time += 1

            avg_resolution = (
                total_resolution_hours / resolved_with_time if resolved_with_time > 0 else 0.0
            )

            return ComplaintSummary(
                hostel_id=hostel_id,
                total_complaints=total,
                open_complaints=open_count,
                in_progress_complaints=in_progress,
                resolved_complaints=resolved,
                high_priority_count=high_priority,
                urgent_priority_count=urgent_priority,
                sla_breached_count=sla_breached,
                average_resolution_time_hours=avg_resolution,
            )