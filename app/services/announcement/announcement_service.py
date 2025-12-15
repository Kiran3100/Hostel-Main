# app/services/announcement/announcement_service.py
from __future__ import annotations

from datetime import datetime, date, timezone
from decimal import Decimal
from typing import Callable, Dict, List, Optional, Sequence
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.content import AnnouncementRepository
from app.repositories.core import HostelRepository, UserRepository
from app.schemas.announcement.announcement_base import (
    AnnouncementCreate,
    AnnouncementUpdate,
)
from app.schemas.announcement.announcement_filters import (
    AnnouncementFilterParams,
    SearchRequest,
    ArchiveRequest,
)
from app.schemas.announcement.announcement_response import (
    AnnouncementResponse,
    AnnouncementDetail,
    AnnouncementList,
    AnnouncementListItem,
)
from app.schemas.common.enums import TargetAudience
from app.schemas.common.pagination import PaginationParams, PaginatedResponse
from app.services.common import UnitOfWork, errors


class AnnouncementService:
    """
    Core Announcement service:

    - Create / update announcements
    - Publish / unpublish
    - Retrieve single announcement detail
    - List & search announcements (with filters)
    - Archive old announcements (soft-delete via BaseRepository)
    """

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _get_announcement_repo(self, uow: UnitOfWork) -> AnnouncementRepository:
        return uow.get_repo(AnnouncementRepository)

    def _get_hostel_repo(self, uow: UnitOfWork) -> HostelRepository:
        return uow.get_repo(HostelRepository)

    def _get_user_repo(self, uow: UnitOfWork) -> UserRepository:
        return uow.get_repo(UserRepository)

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    # ------------------------------------------------------------------ #
    # Mapping helpers
    # ------------------------------------------------------------------ #
    def _to_response(
        self,
        a,
        *,
        hostel_name: str,
        creator_name: str,
    ) -> AnnouncementResponse:
        return AnnouncementResponse(
            id=a.id,
            created_at=a.created_at,
            updated_at=a.updated_at,
            hostel_id=a.hostel_id,
            hostel_name=hostel_name,
            title=a.title,
            content=a.content,
            category=a.category,
            priority=a.priority,
            is_urgent=a.is_urgent,
            is_pinned=a.is_pinned,
            created_by=a.created_by_id,
            created_by_name=creator_name,
            is_published=a.is_published,
            published_at=a.published_at,
            total_recipients=a.total_recipients or 0,
            read_count=a.read_count or 0,
        )

    def _to_detail(
        self,
        a,
        *,
        hostel_name: str,
        creator_name: str,
    ) -> AnnouncementDetail:
        total_recipients = a.total_recipients or 0
        read_count = a.read_count or 0
        engagement_rate = (
            (Decimal(str(read_count)) / Decimal(str(total_recipients)) * 100)
            if total_recipients > 0
            else Decimal("0")
        )

        return AnnouncementDetail(
            id=a.id,
            created_at=a.created_at,
            updated_at=a.updated_at,
            hostel_id=a.hostel_id,
            hostel_name=hostel_name,
            title=a.title,
            content=a.content,
            category=a.category,
            priority=a.priority,
            is_urgent=a.is_urgent,
            is_pinned=a.is_pinned,
            target_audience=a.target_audience.value
            if hasattr(a.target_audience, "value")
            else str(a.target_audience),
            target_room_ids=a.target_room_ids or [],
            target_student_ids=a.target_student_ids or [],
            target_floor_numbers=a.target_floor_numbers or [],
            attachments=a.attachments or [],
            scheduled_publish_at=a.scheduled_publish_at,
            published_at=a.published_at,
            expires_at=a.expires_at,
            is_published=a.is_published,
            created_by=a.created_by_id,
            created_by_name=creator_name,
            created_by_role=a.created_by_role or "",
            approved_by=None,
            approved_by_name=None,
            approved_at=None,
            requires_approval=False,
            send_email=False,
            send_sms=False,
            send_push=True,
            email_sent_at=None,
            sms_sent_at=None,
            push_sent_at=None,
            total_recipients=total_recipients,
            read_count=read_count,
            acknowledged_count=0,
            engagement_rate=engagement_rate,
        )

    def _to_list_item(
        self,
        a,
        *,
        creator_name: str,
    ) -> AnnouncementListItem:
        return AnnouncementListItem(
            id=a.id,
            title=a.title,
            category=a.category.value
            if hasattr(a.category, "value")
            else str(a.category),
            priority=a.priority.value
            if hasattr(a.priority, "value")
            else str(a.priority),
            is_urgent=a.is_urgent,
            is_pinned=a.is_pinned,
            created_by_name=creator_name,
            published_at=a.published_at,
            read_count=a.read_count or 0,
            total_recipients=a.total_recipients or 0,
            is_read=False,
        )

    # ------------------------------------------------------------------ #
    # Read operations
    # ------------------------------------------------------------------ #
    def get_announcement(self, announcement_id: UUID) -> AnnouncementDetail:
        """
        Fetch a single announcement with full detail.
        """
        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_announcement_repo(uow)
            hostel_repo = self._get_hostel_repo(uow)
            user_repo = self._get_user_repo(uow)

            a = repo.get(announcement_id)
            if a is None:
                raise errors.NotFoundError(f"Announcement {announcement_id} not found")

            hostel = hostel_repo.get(a.hostel_id)
            hostel_name = hostel.name if hostel else ""

            creator = (
                user_repo.get(a.created_by_id)
                if getattr(a, "created_by_id", None)
                else None
            )
            creator_name = creator.full_name if creator else ""

            return self._to_detail(a, hostel_name=hostel_name, creator_name=creator_name)

    def list_for_hostel(
        self,
        hostel_id: UUID,
        *,
        include_unpublished: bool = False,
    ) -> AnnouncementList:
        """
        Non-paginated list of announcements for a hostel (e.g., admin dashboard).

        - Optionally includes unpublished announcements.
        - Pinned announcements first, then most recently published/created.
        """
        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_announcement_repo(uow)
            hostel_repo = self._get_hostel_repo(uow)
            user_repo = self._get_user_repo(uow)

            hostel = hostel_repo.get(hostel_id)
            hostel_name = hostel.name if hostel else ""

            records: Sequence = repo.get_multi(
                skip=0,
                limit=None,  # type: ignore[arg-type]
                filters={"hostel_id": hostel_id},
            )

            if not include_unpublished:
                records = [a for a in records if a.is_published]

            def _sort_key(a) -> tuple:
                published = a.published_at or a.created_at
                return (
                    not a.is_pinned,
                    published or datetime.min.replace(tzinfo=timezone.utc),
                )

            sorted_records = sorted(records, key=_sort_key, reverse=True)

            creator_name_cache: Dict[UUID, str] = {}
            items: List[AnnouncementListItem] = []
            now = self._now()

            for a in sorted_records:
                cid = getattr(a, "created_by_id", None)
                creator_name = ""
                if cid:
                    if cid not in creator_name_cache:
                        u = user_repo.get(cid)
                        creator_name_cache[cid] = u.full_name if u else ""
                    creator_name = creator_name_cache[cid]
                items.append(self._to_list_item(a, creator_name=creator_name))

            total = len(sorted_records)
            active_announcements = 0
            pinned_announcements = 0

            for a in sorted_records:
                is_expired = a.expires_at is not None and a.expires_at <= now
                if a.is_published and not is_expired:
                    active_announcements += 1
                if a.is_pinned:
                    pinned_announcements += 1

            return AnnouncementList(
                hostel_id=hostel_id,
                total_announcements=total,
                active_announcements=active_announcements,
                pinned_announcements=pinned_announcements,
                announcements=items,
            )

    def list_announcements(
        self,
        params: PaginationParams,
        filters: Optional[AnnouncementFilterParams] = None,
    ) -> PaginatedResponse[AnnouncementListItem]:
        """
        Paginated listing of announcements with filter support (admin view).
        """
        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_announcement_repo(uow)
            user_repo = self._get_user_repo(uow)

            raw_filters: Dict[str, object] = {}
            if filters:
                if filters.hostel_id:
                    raw_filters["hostel_id"] = filters.hostel_id
                if filters.hostel_ids:
                    raw_filters["hostel_id"] = filters.hostel_ids
                if filters.category:
                    raw_filters["category"] = filters.category
                elif filters.categories:
                    raw_filters["category"] = filters.categories
                if filters.priority:
                    raw_filters["priority"] = filters.priority
                elif filters.priorities:
                    raw_filters["priority"] = filters.priorities
                if filters.is_published is not None:
                    raw_filters["is_published"] = filters.is_published
                if filters.is_urgent is not None:
                    raw_filters["is_urgent"] = filters.is_urgent
                if filters.is_pinned is not None:
                    raw_filters["is_pinned"] = filters.is_pinned
                if filters.created_by:
                    raw_filters["created_by_id"] = filters.created_by
                if filters.created_by_role:
                    raw_filters["created_by_role"] = filters.created_by_role

            # Fetch superset and refine in Python
            records: Sequence = repo.get_multi(
                skip=0,
                limit=None,  # type: ignore[arg-type]
                filters=raw_filters or None,
            )

            def _matches_advanced_filters(a) -> bool:
                if not filters:
                    return True

                # Text search
                if filters.search:
                    q = filters.search.lower()
                    text = f"{a.title or ''} {a.content or ''}".lower()
                    if q not in text:
                        return False

                # Published date range
                if filters.published_date_from or filters.published_date_to:
                    if not a.published_at:
                        return False
                    d = a.published_at.date()
                    if filters.published_date_from and d < filters.published_date_from:
                        return False
                    if filters.published_date_to and d > filters.published_date_to:
                        return False

                # Created date range
                if filters.created_date_from or filters.created_date_to:
                    d = a.created_at.date()
                    if filters.created_date_from and d < filters.created_date_from:
                        return False
                    if filters.created_date_to and d > filters.created_date_to:
                        return False

                today = date.today()
                # Active / expired
                if filters.active_only:
                    if a.expires_at and a.expires_at.date() <= today:
                        return False
                if filters.expired_only:
                    if not a.expires_at or a.expires_at.date() > today:
                        return False

                # approval_pending cannot be resolved here (no approval table), ignore
                return True

            filtered = [a for a in records if _matches_advanced_filters(a)]

            def _sort_key(a) -> tuple:
                published = a.published_at or a.created_at
                return (
                    not a.is_pinned,
                    published or datetime.min.replace(tzinfo=timezone.utc),
                )

            sorted_records = sorted(filtered, key=_sort_key, reverse=True)

            start = params.offset
            end = start + params.limit
            page_records = sorted_records[start:end]

            creator_name_cache: Dict[UUID, str] = {}
            items: List[AnnouncementListItem] = []
            for a in page_records:
                cid = getattr(a, "created_by_id", None)
                creator_name = ""
                if cid:
                    if cid not in creator_name_cache:
                        u = user_repo.get(cid)
                        creator_name_cache[cid] = u.full_name if u else ""
                    creator_name = creator_name_cache[cid]
                items.append(self._to_list_item(a, creator_name=creator_name))

            return PaginatedResponse[AnnouncementListItem].create(
                items=items,
                total_items=len(sorted_records),
                page=params.page,
                page_size=params.page_size,
            )

    def search_announcements(
        self,
        params: PaginationParams,
        req: SearchRequest,
    ) -> PaginatedResponse[AnnouncementListItem]:
        """
        Simple search on title/content within a hostel.
        """
        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_announcement_repo(uow)
            user_repo = self._get_user_repo(uow)

            filters: Dict[str, object] = {}
            if req.hostel_id:
                filters["hostel_id"] = req.hostel_id

            records: Sequence = repo.get_multi(
                skip=0,
                limit=None,  # type: ignore[arg-type]
                filters=filters or None,
            )

            q = req.query.lower()
            def _matches(a) -> bool:
                text_title = (a.title or "").lower()
                text_content = (a.content or "").lower()
                if req.search_in_title and q in text_title:
                    return True
                if req.search_in_content and q in text_content:
                    return True
                return False

            matched = [a for a in records if _matches(a)]

            def _sort_key(a) -> datetime:
                return a.published_at or a.created_at

            matched_sorted = sorted(
                matched,
                key=_sort_key,
                reverse=True,
            )

            start = params.offset
            end = start + params.limit
            page_records = matched_sorted[start:end]

            creator_name_cache: Dict[UUID, str] = {}
            items: List[AnnouncementListItem] = []
            for a in page_records:
                cid = getattr(a, "created_by_id", None)
                creator_name = ""
                if cid:
                    if cid not in creator_name_cache:
                        u = user_repo.get(cid)
                        creator_name_cache[cid] = u.full_name if u else ""
                    creator_name = creator_name_cache[cid]
                items.append(self._to_list_item(a, creator_name=creator_name))

            return PaginatedResponse[AnnouncementListItem].create(
                items=items,
                total_items=len(matched_sorted),
                page=params.page,
                page_size=params.page_size,
            )

    # ------------------------------------------------------------------ #
    # Create / update / publish / archive
    # ------------------------------------------------------------------ #
    def create_announcement(self, data: AnnouncementCreate) -> AnnouncementDetail:
        """
        Create a new announcement.

        - Validates hostel existence.
        - Resolves creator role from User.user_role.
        """
        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_announcement_repo(uow)
            hostel_repo = self._get_hostel_repo(uow)
            user_repo = self._get_user_repo(uow)

            hostel = hostel_repo.get(data.hostel_id)
            if hostel is None:
                raise errors.NotFoundError(f"Hostel {data.hostel_id} not found")

            creator = user_repo.get(data.created_by)
            if creator is None:
                raise errors.NotFoundError(f"User {data.created_by} not found")

            creator_role = (
                creator.user_role.value
                if getattr(creator, "user_role", None)
                else "unknown"
            )

            payload = {
                "hostel_id": data.hostel_id,
                "title": data.title,
                "content": data.content,
                "category": data.category,
                "priority": data.priority,
                "is_urgent": data.is_urgent,
                "is_pinned": data.is_pinned,
                "target_audience": (
                    TargetAudience(data.target_audience)
                    if isinstance(data.target_audience, str)
                    else data.target_audience
                ),
                "target_room_ids": data.target_room_ids or [],
                "target_student_ids": data.target_student_ids or [],
                "target_floor_numbers": data.target_floor_numbers or [],
                "attachments": [str(u) for u in data.attachments] if data.attachments else [],
                "expires_at": data.expires_at,
                "created_by_id": data.created_by,
                "created_by_role": creator_role,
                "is_published": False,
                "scheduled_publish_at": None,
                "published_at": None,
                "total_recipients": 0,
                "read_count": 0,
            }
            a = repo.create(payload)  # type: ignore[arg-type]
            uow.commit()

            return self._to_detail(
                a,
                hostel_name=hostel.name,
                creator_name=creator.full_name,
            )

    def update_announcement(
        self,
        announcement_id: UUID,
        data: AnnouncementUpdate,
    ) -> AnnouncementDetail:
        """
        Update mutable announcement fields (title, content, priority, flags, expiry).

        Publication state is handled via publish()/unpublish().
        """
        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_announcement_repo(uow)
            hostel_repo = self._get_hostel_repo(uow)
            user_repo = self._get_user_repo(uow)

            a = repo.get(announcement_id)
            if a is None:
                raise errors.NotFoundError(f"Announcement {announcement_id} not found")

            update_data = data.model_dump(exclude_unset=True)
            for field, value in update_data.items():
                if field == "is_published":
                    # use publish/unpublish methods instead
                    continue
                if hasattr(a, field):
                    setattr(a, field, value)

            uow.session.flush()  # type: ignore[union-attr]
            uow.commit()

            hostel = hostel_repo.get(a.hostel_id)
            hostel_name = hostel.name if hostel else ""
            creator = (
                user_repo.get(a.created_by_id)
                if getattr(a, "created_by_id", None)
                else None
            )
            creator_name = creator.full_name if creator else ""

            return self._to_detail(a, hostel_name=hostel_name, creator_name=creator_name)

    def publish(
        self,
        announcement_id: UUID,
        *,
        publish_at: Optional[datetime] = None,
    ) -> AnnouncementDetail:
        """
        Publish an announcement.

        - If publish_at is None, uses current time.
        - Clears scheduled_publish_at.
        """
        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_announcement_repo(uow)
            hostel_repo = self._get_hostel_repo(uow)
            user_repo = self._get_user_repo(uow)

            a = repo.get(announcement_id)
            if a is None:
                raise errors.NotFoundError(f"Announcement {announcement_id} not found")

            ts = publish_at or self._now()
            a.is_published = True  # type: ignore[attr-defined]
            a.published_at = ts  # type: ignore[attr-defined]
            a.scheduled_publish_at = None  # type: ignore[attr-defined]

            uow.session.flush()  # type: ignore[union-attr]
            uow.commit()

            hostel = hostel_repo.get(a.hostel_id)
            hostel_name = hostel.name if hostel else ""
            creator = (
                user_repo.get(a.created_by_id)
                if getattr(a, "created_by_id", None)
                else None
            )
            creator_name = creator.full_name if creator else ""

            return self._to_detail(a, hostel_name=hostel_name, creator_name=creator_name)

    def unpublish(self, announcement_id: UUID) -> AnnouncementDetail:
        """
        Unpublish an announcement (soft-unpublish).
        """
        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_announcement_repo(uow)
            hostel_repo = self._get_hostel_repo(uow)
            user_repo = self._get_user_repo(uow)

            a = repo.get(announcement_id)
            if a is None:
                raise errors.NotFoundError(f"Announcement {announcement_id} not found")

            a.is_published = False  # type: ignore[attr-defined]
            # Keep published_at as a historical timestamp

            uow.session.flush()  # type: ignore[union-attr]
            uow.commit()

            hostel = hostel_repo.get(a.hostel_id)
            hostel_name = hostel.name if hostel else ""
            creator = (
                user_repo.get(a.created_by_id)
                if getattr(a, "created_by_id", None)
                else None
            )
            creator_name = creator.full_name if creator else ""

            return self._to_detail(a, hostel_name=hostel_name, creator_name=creator_name)

    def archive_announcements(self, req: ArchiveRequest) -> int:
        """
        Archive (soft-delete) announcements before a given date, based on criteria.

        Uses BaseRepository.bulk_delete with soft-delete semantics (is_deleted).
        """
        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_announcement_repo(uow)

            # Fetch candidates and filter in Python; then bulk_delete by IDs.
            records: Sequence = repo.get_multi(
                skip=0,
                limit=None,  # type: ignore[arg-type]
                filters={"hostel_id": req.hostel_id},
            )

            def _matches(a) -> bool:
                # Cutoff by created_at
                if a.created_at.date() >= req.archive_before_date:
                    return False

                # Expired only?
                if req.archive_expired_only:
                    if not a.expires_at or a.expires_at.date() >= req.archive_before_date:
                        return False

                # Exclude pinned/important
                if req.exclude_pinned and a.is_pinned:
                    return False
                if req.exclude_important and a.is_urgent:
                    return False

                # read_only / recipients logic would require per-recipient tracking;
                # here we only check read_count == total_recipients when requested.
                if req.archive_read_only:
                    if (
                        a.total_recipients
                        and a.read_count is not None
                        and a.read_count < a.total_recipients
                    ):
                        return False

                return True

            to_archive_ids: List[UUID] = [
                a.id for a in records if _matches(a)
            ]
            if not to_archive_ids:
                return 0

            # Bulk soft-delete by id
            deleted = repo.bulk_delete(
                filters={"id": to_archive_ids},
                hard_delete=False,
            )
            uow.commit()
            return deleted