# app/services/notice/notice_service.py
from __future__ import annotations

from datetime import datetime, date, timezone
from typing import Callable, Dict, List, Optional, Sequence
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.content import NoticeRepository
from app.repositories.core import HostelRepository
from app.schemas.common.enums import TargetAudience
from app.schemas.common.pagination import PaginationParams, PaginatedResponse
from app.schemas.notice.notice_base import (
    NoticeCreate,
    NoticeUpdate,
)
from app.schemas.notice.notice_filters import (
    NoticeFilterParams,
)
from app.schemas.notice.notice_response import (
    NoticeResponse,
    NoticeDetail,
    NoticeList,
    NoticeListItem,
)
from app.services.common import UnitOfWork, errors


class NoticeService:
    """
    Core Notice service:

    - Create / update notices
    - Retrieve single notice detail
    - List & search notices (with filters)
    - List active notices for hostel / system-wide
    """

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _get_notice_repo(self, uow: UnitOfWork) -> NoticeRepository:
        return uow.get_repo(NoticeRepository)

    def _get_hostel_repo(self, uow: UnitOfWork) -> HostelRepository:
        return uow.get_repo(HostelRepository)

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    # ------------------------------------------------------------------ #
    # Mapping helpers
    # ------------------------------------------------------------------ #
    def _to_response(
        self,
        n,
        *,
        hostel_name: str,
    ) -> NoticeResponse:
        return NoticeResponse(
            id=n.id,
            created_at=n.created_at,
            updated_at=n.updated_at,
            hostel_id=n.hostel_id,
            hostel_name=hostel_name,
            title=n.notice_title,
            content=n.notice_content,
            category=n.category,
            target_audience=n.target_audience,
            priority=n.priority,
            is_urgent=n.is_urgent,
            published_at=n.published_at,
            expires_at=n.expires_at,
        )

    def _to_detail(
        self,
        n,
        *,
        hostel_name: str,
    ) -> NoticeDetail:
        return NoticeDetail(
            id=n.id,
            created_at=n.created_at,
            updated_at=n.updated_at,
            hostel_id=n.hostel_id,
            hostel_name=hostel_name,
            title=n.notice_title,
            content=n.notice_content,
            category=n.category,
            target_audience=n.target_audience,
            priority=n.priority,
            is_urgent=n.is_urgent,
            published_at=n.published_at,
            expires_at=n.expires_at,
            is_active=(
                n.published_at is not None
                and (n.expires_at is None or n.expires_at > self._now())
            ),
        )

    def _to_list_item(self, n) -> NoticeListItem:
        return NoticeListItem(
            id=n.id,
            title=n.notice_title,
            category=n.category,
            priority=n.priority,
            is_urgent=n.is_urgent,
            published_at=n.published_at,
            expires_at=n.expires_at,
        )

    # ------------------------------------------------------------------ #
    # Read operations
    # ------------------------------------------------------------------ #
    def get_notice(self, notice_id: UUID) -> NoticeDetail:
        """
        Fetch a single notice with full detail.
        """
        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_notice_repo(uow)
            hostel_repo = self._get_hostel_repo(uow)

            n = repo.get(notice_id)
            if n is None:
                raise errors.NotFoundError(f"Notice {notice_id} not found")

            hostel_name = ""
            if n.hostel_id:
                hostel = hostel_repo.get(n.hostel_id)
                hostel_name = hostel.name if hostel else ""

            return self._to_detail(n, hostel_name=hostel_name)

    def list_active_notices(
        self,
        *,
        hostel_id: Optional[UUID] = None,
        audience: Optional[TargetAudience] = None,
    ) -> List[NoticeResponse]:
        """
        List currently active notices (published & not expired).

        - If hostel_id is None, includes system-wide notices.
        - If audience is provided, filter by target_audience.
        """
        now = self._now()

        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_notice_repo(uow)
            hostel_repo = self._get_hostel_repo(uow)

            notices = repo.list_active_notices(
                hostel_id=hostel_id,
                audience=audience,
                now=now,
            )

            hostel_cache: Dict[UUID, str] = {}
            responses: List[NoticeResponse] = []

            for n in notices:
                hostel_name = ""
                if n.hostel_id:
                    if n.hostel_id not in hostel_cache:
                        h = hostel_repo.get(n.hostel_id)
                        hostel_cache[n.hostel_id] = h.name if h else ""
                    hostel_name = hostel_cache[n.hostel_id]
                responses.append(self._to_response(n, hostel_name=hostel_name))

            return responses

    def list_notices(
        self,
        params: PaginationParams,
        filters: Optional[NoticeFilterParams] = None,
    ) -> PaginatedResponse[NoticeListItem]:
        """
        Paginated listing of notices with filter support (admin/system view).
        """
        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_notice_repo(uow)

            raw_filters: Dict[str, object] = {}
            if filters:
                if filters.hostel_id:
                    raw_filters["hostel_id"] = filters.hostel_id
                if filters.category:
                    raw_filters["category"] = filters.category
                if filters.priority:
                    raw_filters["priority"] = filters.priority
                if filters.target_audience:
                    raw_filters["target_audience"] = filters.target_audience
                if filters.is_urgent is not None:
                    raw_filters["is_urgent"] = filters.is_urgent

            records: Sequence = repo.get_multi(
                skip=0,
                limit=None,  # type: ignore[arg-type]
                filters=raw_filters or None,
            )

            def _matches_advanced(n) -> bool:
                if not filters:
                    return True

                # Text search
                if filters.search:
                    q = filters.search.lower()
                    text = f"{n.notice_title or ''} {n.notice_content or ''}".lower()
                    if q not in text:
                        return False

                # Published date range
                if filters.published_date_from or filters.published_date_to:
                    if not n.published_at:
                        return False
                    d = n.published_at.date()
                    if filters.published_date_from and d < filters.published_date_from:
                        return False
                    if filters.published_date_to and d > filters.published_date_to:
                        return False

                # Created date range
                if filters.created_date_from or filters.created_date_to:
                    d = n.created_at.date()
                    if filters.created_date_from and d < filters.created_date_from:
                        return False
                    if filters.created_date_to and d > filters.created_date_to:
                        return False

                today = date.today()
                # Active / expired flags
                if filters.active_only:
                    if n.published_at is None:
                        return False
                    if n.expires_at and n.expires_at.date() <= today:
                        return False
                if filters.expired_only:
                    if not n.expires_at or n.expires_at.date() > today:
                        return False

                return True

            filtered = [n for n in records if _matches_advanced(n)]

            def _sort_key(n) -> datetime:
                return n.published_at or n.created_at

            sorted_records = sorted(filtered, key=_sort_key, reverse=True)

            start = params.offset
            end = start + params.limit
            page_records = sorted_records[start:end]

            items: List[NoticeListItem] = [
                self._to_list_item(n) for n in page_records
            ]

            return PaginatedResponse[NoticeListItem].create(
                items=items,
                total_items=len(sorted_records),
                page=params.page,
                page_size=params.page_size,
            )

    # ------------------------------------------------------------------ #
    # Create / update
    # ------------------------------------------------------------------ #
    def create_notice(self, data: NoticeCreate) -> NoticeDetail:
        """
        Create a new notice.

        - If hostel_id is None, it's treated as a system-wide notice.
        """
        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_notice_repo(uow)
            hostel_repo = self._get_hostel_repo(uow)

            if data.hostel_id:
                hostel = hostel_repo.get(data.hostel_id)
                if hostel is None:
                    raise errors.NotFoundError(f"Hostel {data.hostel_id} not found")
                hostel_name = hostel.name
            else:
                hostel_name = ""

            payload = {
                "hostel_id": data.hostel_id,
                "notice_title": data.notice_title,
                "notice_content": data.notice_content,
                "category": data.category,
                "target_audience": data.target_audience,
                "priority": data.priority,
                "is_urgent": data.is_urgent,
                "published_at": data.published_at,
                "expires_at": data.expires_at,
            }
            n = repo.create(payload)  # type: ignore[arg-type]
            uow.commit()

            return self._to_detail(n, hostel_name=hostel_name)

    def update_notice(
        self,
        notice_id: UUID,
        data: NoticeUpdate,
    ) -> NoticeDetail:
        """
        Update mutable notice fields.
        """
        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_notice_repo(uow)
            hostel_repo = self._get_hostel_repo(uow)

            n = repo.get(notice_id)
            if n is None:
                raise errors.NotFoundError(f"Notice {notice_id} not found")

            update_data = data.model_dump(exclude_unset=True)
            for field, value in update_data.items():
                if hasattr(n, field) and field != "id":
                    setattr(n, field, value)

            uow.session.flush()  # type: ignore[union-attr]
            uow.commit()

            hostel_name = ""
            if n.hostel_id:
                hostel = hostel_repo.get(n.hostel_id)
                hostel_name = hostel.name if hostel else ""

            return self._to_detail(n, hostel_name=hostel_name)