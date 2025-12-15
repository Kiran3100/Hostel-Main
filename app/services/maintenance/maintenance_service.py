# app/services/maintenance/maintenance_service.py
from __future__ import annotations

from datetime import datetime, timezone, date
from typing import Callable, Optional, Sequence, List
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.services import MaintenanceRepository
from app.repositories.core import HostelRepository, RoomRepository, StudentRepository, UserRepository, SupervisorRepository
from app.schemas.common.pagination import PaginationParams, PaginatedResponse
from app.schemas.common.enums import MaintenanceStatus, Priority
from app.schemas.maintenance import (
    MaintenanceCreate,
    MaintenanceUpdate,
    MaintenanceStatusUpdate,
    MaintenanceResponse,
    MaintenanceDetail,
    RequestListItem,
    MaintenanceSummary,
    MaintenanceFilterParams,
    SearchRequest,
)
from app.services.common import UnitOfWork, pagination, errors


class MaintenanceService:
    """
    Core Maintenance service:

    - Create/update maintenance records
    - Change status
    - Retrieve single maintenance detail
    - List maintenance with basic filters/search
    - Summary stats per hostel
    """

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _get_repo(self, uow: UnitOfWork) -> MaintenanceRepository:
        return uow.get_repo(MaintenanceRepository)

    def _get_hostel_repo(self, uow: UnitOfWork) -> HostelRepository:
        return uow.get_repo(HostelRepository)

    def _get_room_repo(self, uow: UnitOfWork) -> RoomRepository:
        return uow.get_repo(RoomRepository)

    def _get_student_repo(self, uow: UnitOfWork) -> StudentRepository:
        return uow.get_repo(StudentRepository)

    def _get_user_repo(self, uow: UnitOfWork) -> UserRepository:
        return uow.get_repo(UserRepository)

    def _get_supervisor_repo(self, uow: UnitOfWork) -> SupervisorRepository:
        return uow.get_repo(SupervisorRepository)

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _request_number(self, maintenance_id: UUID) -> str:
        # Simple maintenance request number format; customize as needed
        return f"MTN-{str(maintenance_id)[:8].upper()}"

    # ------------------------------------------------------------------ #
    # Mapping helpers
    # ------------------------------------------------------------------ #
    def _to_list_item(
        self,
        m,
        now: Optional[datetime] = None,
        room_number: Optional[str] = None,
        assigned_to_name: Optional[str] = None,
    ) -> RequestListItem:
        if now is None:
            now = self._now()
        created_at = m.created_at
        est_completion = m.estimated_completion_date
        return RequestListItem(
            id=m.id,
            request_number=self._request_number(m.id),
            title=m.title,
            category=m.category.value if hasattr(m.category, "value") else str(m.category),
            priority=m.priority.value if hasattr(m.priority, "value") else str(m.priority),
            status=m.status,
            room_number=room_number,
            estimated_cost=m.estimated_cost,
            assigned_to_name=assigned_to_name,
            created_at=created_at,
            estimated_completion_date=est_completion,
        )

    def _to_response(self, m) -> MaintenanceResponse:
        hostel = getattr(m, "hostel", None)
        requested_by = getattr(m, "requested_by", None)
        assigned_to = getattr(m, "assigned_to", None)
        assigned_to_user = getattr(assigned_to, "user", None) if assigned_to else None

        return MaintenanceResponse(
            id=m.id,
            created_at=m.created_at,
            updated_at=m.updated_at,
            request_number=self._request_number(m.id),
            hostel_id=m.hostel_id,
            hostel_name=hostel.name if hostel else "",
            requested_by=m.requested_by_id,
            requested_by_name=requested_by.full_name if requested_by else "",
            title=m.title,
            category=m.category,
            priority=m.priority,
            status=m.status,
            assigned_to=m.assigned_to_id,
            assigned_to_name=assigned_to_user.full_name if assigned_to_user else None,
            estimated_cost=m.estimated_cost,
            actual_cost=m.actual_cost,
            estimated_completion_date=m.estimated_completion_date,
            completed_at=m.completed_at,
        )

    def _to_detail(
        self,
        m,
        room_number: Optional[str] = None,
    ) -> MaintenanceDetail:
        hostel = getattr(m, "hostel", None)
        requested_by = getattr(m, "requested_by", None)
        assigned_to = getattr(m, "assigned_to", None)
        assigned_to_user = getattr(assigned_to, "user", None) if assigned_to else None

        return MaintenanceDetail(
            id=m.id,
            created_at=m.created_at,
            updated_at=m.updated_at,
            request_number=self._request_number(m.id),
            hostel_id=m.hostel_id,
            hostel_name=hostel.name if hostel else "",
            requested_by=m.requested_by_id,
            requested_by_name=requested_by.full_name if requested_by else "",
            room_id=m.room_id,
            room_number=room_number,
            title=m.title,
            description=m.description,
            category=m.category,
            priority=m.priority,
            issue_type=m.issue_type.value if hasattr(m.issue_type, "value") else str(m.issue_type),
            location=m.location,
            floor=m.floor,
            specific_area=m.specific_area,
            issue_photos=m.issue_photos or [],
            completion_photos=[],
            assigned_to=m.assigned_to_id,
            assigned_to_name=assigned_to_user.full_name if assigned_to_user else None,
            assigned_by=None,
            assigned_by_name=None,
            assigned_at=None,
            vendor_name=None,
            vendor_contact=None,
            status=m.status,
            approved_by=None,
            approved_by_name=None,
            approved_at=None,
            rejected_by=None,
            rejected_at=None,
            rejection_reason=None,
            started_at=m.started_at,
            completed_at=m.completed_at,
            estimated_cost=m.estimated_cost,
            actual_cost=m.actual_cost,
            cost_approved=m.cost_approved,
            approval_threshold_exceeded=m.approval_threshold_exceeded,
            estimated_completion_date=m.estimated_completion_date,
            actual_completion_date=m.actual_completion_date,
            work_notes=None,
            materials_used=[],
            labor_hours=None,
            quality_checked_by=None,
            quality_check_passed=None,
            quality_check_notes=None,
            quality_checked_at=None,
            is_preventive=False,
            next_scheduled_date=None,
            recurrence="none",
        )

    # ------------------------------------------------------------------ #
    # Read operations
    # ------------------------------------------------------------------ #
    def get_maintenance(self, maintenance_id: UUID) -> MaintenanceDetail:
        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_repo(uow)
            room_repo = self._get_room_repo(uow)

            m = repo.get(maintenance_id)
            if m is None:
                raise errors.NotFoundError(f"Maintenance {maintenance_id} not found")

            room_number = None
            if m.room_id:
                room = room_repo.get(m.room_id)
                room_number = room.room_number if room else None

            return self._to_detail(m, room_number=room_number)

    # ------------------------------------------------------------------ #
    # Listing
    # ------------------------------------------------------------------ #
    def list_maintenance(
        self,
        params: PaginationParams,
        filters: Optional[MaintenanceFilterParams] = None,
    ) -> PaginatedResponse[RequestListItem]:
        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_repo(uow)

            raw_filters: dict = {}
            if filters:
                if filters.hostel_id:
                    raw_filters["hostel_id"] = filters.hostel_id
                if filters.requested_by:
                    raw_filters["requested_by_id"] = filters.requested_by
                if filters.assigned_to:
                    raw_filters["assigned_to_id"] = filters.assigned_to
                if filters.room_id:
                    raw_filters["room_id"] = filters.room_id
                if filters.category:
                    raw_filters["category"] = filters.category
                if filters.priority:
                    raw_filters["priority"] = filters.priority
                if filters.status:
                    raw_filters["status"] = filters.status
                if filters.approval_pending:
                    raw_filters["cost_approved"] = False

            records: Sequence = repo.get_multi(
                skip=params.offset,
                limit=params.limit,
                filters=raw_filters or None,
                order_by=None,
            )
            total = repo.count(filters=raw_filters or None)

            now = self._now()
            items: List[RequestListItem] = []
            room_ids = {r.room_id for r in records if getattr(r, "room_id", None)}
            room_map = {}
            if room_ids:
                room_repo = self._get_room_repo(uow)
                # naive: fetch each; for scale, implement bulk fetch
                for rid in room_ids:
                    room = room_repo.get(rid)
                    if room:
                        room_map[rid] = room.room_number

            sup_repo = self._get_supervisor_repo(uow)
            user_repo = self._get_user_repo(uow)
            for m in records:
                room_number = room_map.get(m.room_id) if m.room_id else None
                assigned_to_name = None
                if m.assigned_to_id:
                    sup = sup_repo.get(m.assigned_to_id)
                    if sup and getattr(sup, "user", None):
                        assigned_to_name = sup.user.full_name
                items.append(self._to_list_item(m, now=now,
                                                room_number=room_number,
                                                assigned_to_name=assigned_to_name))

            return PaginatedResponse[RequestListItem].create(
                items=items,
                total_items=total,
                page=params.page,
                page_size=params.page_size,
            )

    def search(
        self,
        params: PaginationParams,
        req: SearchRequest,
    ) -> PaginatedResponse[RequestListItem]:
        """
        Very simple search implementation (title/description/number) using in-memory filtering.
        For large data sets, replace with a dedicated query or search index.
        """
        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_repo(uow)
            records: Sequence = repo.get_multi(
                skip=0,
                limit=None,  # type: ignore[arg-type]
                filters={"hostel_id": req.hostel_id} if req.hostel_id else None,
            )

            q = req.query.lower()
            filtered = []
            for m in records:
                if req.search_in_title and q in (m.title or "").lower():
                    filtered.append(m)
                    continue
                if req.search_in_description and q in (m.description or "").lower():
                    filtered.append(m)
                    continue
                if req.search_in_number and q in self._request_number(m.id).lower():
                    filtered.append(m)

            total = len(filtered)
            start = params.offset
            end = start + params.limit
            page_items = filtered[start:end]

            now = self._now()
            items: List[RequestListItem] = []
            room_repo = self._get_room_repo(uow)
            sup_repo = self._get_supervisor_repo(uow)

            for m in page_items:
                room_number = None
                if m.room_id:
                    room = room_repo.get(m.room_id)
                    room_number = room.room_number if room else None
                assigned_to_name = None
                if m.assigned_to_id:
                    sup = sup_repo.get(m.assigned_to_id)
                    if sup and getattr(sup, "user", None):
                        assigned_to_name = sup.user.full_name
                items.append(self._to_list_item(m, now=now,
                                                room_number=room_number,
                                                assigned_to_name=assigned_to_name))

            return PaginatedResponse[RequestListItem].create(
                items=items,
                total_items=total,
                page=params.page,
                page_size=params.page_size,
            )

    # ------------------------------------------------------------------ #
    # Create / update / status
    # ------------------------------------------------------------------ #
    def create_maintenance(self, data: MaintenanceCreate) -> MaintenanceDetail:
        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_repo(uow)

            payload = data.model_dump()
            payload.setdefault("status", MaintenanceStatus.PENDING)
            m = repo.create(payload)  # type: ignore[arg-type]
            uow.commit()
            return self.get_maintenance(m.id)

    def update_maintenance(self, maintenance_id: UUID, data: MaintenanceUpdate) -> MaintenanceDetail:
        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_repo(uow)
            m = repo.get(maintenance_id)
            if m is None:
                raise errors.NotFoundError(f"Maintenance {maintenance_id} not found")

            mapping = data.model_dump(exclude_unset=True)
            for field, value in mapping.items():
                if hasattr(m, field) and field != "id":
                    setattr(m, field, value)

            uow.session.flush()  # type: ignore[union-attr]
            uow.commit()
            return self.get_maintenance(maintenance_id)

    def update_status(self, maintenance_id: UUID, data: MaintenanceStatusUpdate) -> MaintenanceDetail:
        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_repo(uow)
            m = repo.get(maintenance_id)
            if m is None:
                raise errors.NotFoundError(f"Maintenance {maintenance_id} not found")

            new_status = data.status
            now = self._now()

            m.status = new_status  # type: ignore[attr-defined]
            if new_status == MaintenanceStatus.IN_PROGRESS and m.started_at is None:
                m.started_at = now  # type: ignore[attr-defined]
            if new_status == MaintenanceStatus.COMPLETED and m.completed_at is None:
                m.completed_at = now  # type: ignore[attr-defined]

            uow.session.flush()  # type: ignore[union-attr]
            uow.commit()
            return self.get_maintenance(maintenance_id)

    # ------------------------------------------------------------------ #
    # Summary
    # ------------------------------------------------------------------ #
    def get_summary_for_hostel(self, hostel_id: UUID) -> MaintenanceSummary:
        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_repo(uow)
            records = repo.get_multi(
                skip=0,
                limit=None,  # type: ignore[arg-type]
                filters={"hostel_id": hostel_id},
            )

            total = len(records)
            pending = 0
            in_progress = 0
            completed = 0
            high_priority = 0
            urgent_priority = 0
            total_estimated = 0.0
            total_actual = 0.0
            total_completion_hours = 0.0
            completed_with_time = 0

            for m in records:
                if m.status in (MaintenanceStatus.PENDING, MaintenanceStatus.APPROVED, MaintenanceStatus.ASSIGNED):
                    pending += 1
                if m.status == MaintenanceStatus.IN_PROGRESS:
                    in_progress += 1
                if m.status == MaintenanceStatus.COMPLETED:
                    completed += 1

                if m.priority == Priority.HIGH:
                    high_priority += 1
                if m.priority in (Priority.URGENT, Priority.CRITICAL):
                    urgent_priority += 1

                if m.estimated_cost:
                    total_estimated += float(m.estimated_cost)
                if m.actual_cost:
                    total_actual += float(m.actual_cost)

                if m.completed_at and m.started_at:
                    diff_hours = (m.completed_at - m.started_at).total_seconds() / 3600.0
                    total_completion_hours += diff_hours
                    completed_with_time += 1

            avg_completion = (
                total_completion_hours / completed_with_time if completed_with_time > 0 else 0.0
            )

            return MaintenanceSummary(
                hostel_id=hostel_id,
                total_requests=total,
                pending_requests=pending,
                in_progress_requests=in_progress,
                completed_requests=completed,
                high_priority_count=high_priority,
                urgent_priority_count=urgent_priority,
                total_estimated_cost=total_estimated,
                total_actual_cost=total_actual,
                average_completion_time_hours=avg_completion,
            )