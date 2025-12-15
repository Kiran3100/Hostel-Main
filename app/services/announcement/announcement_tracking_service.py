# app/services/announcement/announcement_tracking_service.py
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
from typing import Callable, Dict, List, Optional, Protocol
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.content import AnnouncementRepository
from app.repositories.core import StudentRepository, RoomRepository
from app.schemas.announcement.announcement_tracking import (
    ReadReceipt,
    ReadReceiptResponse,
    AcknowledgmentTracking,
    PendingAcknowledgment,
    AcknowledgmentRequest,
    EngagementMetrics,
    ReadingTime,
    AnnouncementAnalytics,
)
from app.schemas.announcement.announcement_delivery import DeliveryStatus
from app.services.common import UnitOfWork, errors


class AnnouncementTrackingStore(Protocol):
    """
    Storage for per-recipient read receipts and acknowledgments.

    Implementations might use dedicated tables or Redis-like stores.
    """

    # Read receipts
    def save_read_receipt(self, record: dict) -> None: ...
    def get_read_receipt(self, announcement_id: UUID, student_id: UUID) -> Optional[dict]: ...
    def list_read_receipts(self, announcement_id: UUID) -> List[dict]: ...

    # Acknowledgments
    def save_acknowledgment(self, record: dict) -> None: ...
    def get_acknowledgment(self, announcement_id: UUID, student_id: UUID) -> Optional[dict]: ...
    def list_acknowledgments(self, announcement_id: UUID) -> List[dict]: ...

    # Recipient metadata for acknowledgments / analytics
    def list_recipients(self, announcement_id: UUID) -> List[dict]: ...
    # Expected recipient record:
    # {
    #   "student_id": str,
    #   "student_name": str,
    #   "room_number": str | None,
    #   "delivered_at": datetime,
    #   "read": bool,
    #   "read_at": datetime | None,
    #   "acknowledged": bool,
    # }


class AnnouncementTrackingService:
    """
    Track read receipts and acknowledgments for announcements, and compute
    engagement analytics.

    - Records ReadReceipt per student/announcement
    - Records acknowledgments
    - Builds AcknowledgmentTracking and EngagementMetrics
    - Can assemble full AnnouncementAnalytics when given DeliveryStatus
    """

    def __init__(
        self,
        session_factory: Callable[[], Session],
        store: AnnouncementTrackingStore,
    ) -> None:
        self._session_factory = session_factory
        self._store = store

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _get_announcement_repo(self, uow: UnitOfWork) -> AnnouncementRepository:
        return uow.get_repo(AnnouncementRepository)

    def _get_student_repo(self, uow: UnitOfWork) -> StudentRepository:
        return uow.get_repo(StudentRepository)

    def _get_room_repo(self, uow: UnitOfWork) -> RoomRepository:
        return uow.get_repo(RoomRepository)

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    # ------------------------------------------------------------------ #
    # Read receipts
    # ------------------------------------------------------------------ #
    def mark_read(self, data: ReadReceipt) -> ReadReceiptResponse:
        """
        Record that a student has read an announcement.

        - Idempotent: if a receipt already exists, Announcement.read_count
          is only incremented once per student.
        """
        read_at = data.read_at or self._now()

        with UnitOfWork(self._session_factory) as uow:
            announcement_repo = self._get_announcement_repo(uow)
            student_repo = self._get_student_repo(uow)

            a = announcement_repo.get(data.announcement_id)
            if a is None:
                raise errors.NotFoundError(
                    f"Announcement {data.announcement_id} not found"
                )

            s = student_repo.get(data.student_id)
            if s is None:
                raise errors.NotFoundError(
                    f"Student {data.student_id} not found"
                )

            existing = self._store.get_read_receipt(
                data.announcement_id, data.student_id
            )

            if not existing:
                record = {
                    "announcement_id": str(data.announcement_id),
                    "student_id": str(data.student_id),
                    "read_at": read_at,
                    "reading_time_seconds": data.reading_time_seconds,
                    "device_type": data.device_type,
                }
                self._store.save_read_receipt(record)

                # Increment read_count once per student
                a.read_count = (a.read_count or 0) + 1  # type: ignore[attr-defined]
                uow.session.flush()  # type: ignore[union-attr]
                uow.commit()

        ack_record = self._store.get_acknowledgment(
            data.announcement_id, data.student_id
        )
        acknowledged = bool(ack_record and ack_record.get("acknowledged"))

        return ReadReceiptResponse(
            id=None,
            created_at=read_at,
            updated_at=read_at,
            announcement_id=data.announcement_id,
            student_id=data.student_id,
            read_at=read_at,
            requires_acknowledgment=False,
            acknowledged=acknowledged,
        )

    # ------------------------------------------------------------------ #
    # Acknowledgments
    # ------------------------------------------------------------------ #
    def submit_acknowledgment(self, data: AcknowledgmentRequest) -> None:
        """
        Store a student's acknowledgment decision.
        """
        record = {
            "announcement_id": str(data.announcement_id),
            "student_id": str(data.student_id),
            "acknowledged": data.acknowledged,
            "acknowledgment_note": data.acknowledgment_note,
            "acknowledged_at": self._now(),
        }
        self._store.save_acknowledgment(record)

    def get_acknowledgment_tracking(
        self,
        announcement_id: UUID,
        *,
        requires_acknowledgment: bool = True,
    ) -> AcknowledgmentTracking:
        """
        Build AcknowledgmentTracking for an announcement.
        """
        with UnitOfWork(self._session_factory) as uow:
            announcement_repo = self._get_announcement_repo(uow)
            a = announcement_repo.get(announcement_id)
            if a is None:
                raise errors.NotFoundError(
                    f"Announcement {announcement_id} not found"
                )
            total_recipients = a.total_recipients or 0

        ack_records = self._store.list_acknowledgments(announcement_id)
        acknowledged_count = sum(
            1 for r in ack_records if r.get("acknowledged", False)
        )

        pending_students_raw = self._store.list_recipients(announcement_id)
        pending_students: List[PendingAcknowledgment] = []
        for r in pending_students_raw:
            if r.get("acknowledged"):
                continue
            pending_students.append(
                PendingAcknowledgment(
                    student_id=UUID(r["student_id"]),
                    student_name=r.get("student_name", ""),
                    room_number=r.get("room_number"),
                    delivered_at=r.get("delivered_at"),
                    read=r.get("read", False),
                    read_at=r.get("read_at"),
                )
            )

        pending_ack = max(0, total_recipients - acknowledged_count)
        acknowledgment_rate = (
            Decimal(str(acknowledged_count)) / Decimal(str(total_recipients)) * 100
            if total_recipients > 0
            else Decimal("0")
        )

        return AcknowledgmentTracking(
            announcement_id=announcement_id,
            requires_acknowledgment=requires_acknowledgment,
            total_recipients=total_recipients,
            acknowledged_count=acknowledged_count,
            pending_acknowledgments=pending_ack,
            acknowledgment_rate=acknowledgment_rate,
            pending_students=pending_students,
        )

    # ------------------------------------------------------------------ #
    # Engagement & reading time
    # ------------------------------------------------------------------ #
    def get_engagement_metrics(self, announcement_id: UUID) -> EngagementMetrics:
        """
        Compute EngagementMetrics based on Announcement + read receipts +
        acknowledgments. Delivery metrics are approximated assuming all
        targeted recipients were delivered.
        """
        with UnitOfWork(self._session_factory) as uow:
            announcement_repo = self._get_announcement_repo(uow)
            a = announcement_repo.get(announcement_id)
            if a is None:
                raise errors.NotFoundError(
                    f"Announcement {announcement_id} not found"
                )
            title = a.title or ""
            total_recipients = a.total_recipients or 0
            read_count = a.read_count or 0

        delivered_count = total_recipients
        delivery_rate = (
            Decimal(str(delivered_count)) / Decimal(str(total_recipients)) * 100
            if total_recipients > 0
            else Decimal("0")
        )
        read_rate = (
            Decimal(str(read_count)) / Decimal(str(total_recipients)) * 100
            if total_recipients > 0
            else Decimal("0")
        )

        read_receipts = self._store.list_read_receipts(announcement_id)
        ack_records = self._store.list_acknowledgments(announcement_id)
        acknowledged_count = sum(
            1 for r in ack_records if r.get("acknowledged", False)
        )
        acknowledgment_rate = (
            Decimal(str(acknowledged_count)) / Decimal(str(total_recipients)) * 100
            if total_recipients > 0
            else Decimal("0")
        )

        times = [
            Decimal(str(r.get("reading_time_seconds")))
            for r in read_receipts
            if r.get("reading_time_seconds") is not None
        ]
        avg_reading_time = (
            sum(times) / Decimal(str(len(times))) if times else None
        )

        avg_time_to_read = None  # delivery→read delta not tracked here

        if total_recipients > 0:
            engagement_score = (read_rate + acknowledgment_rate) / 2
        else:
            engagement_score = Decimal("0")

        return EngagementMetrics(
            announcement_id=announcement_id,
            title=title,
            total_recipients=total_recipients,
            delivered_count=delivered_count,
            delivery_rate=delivery_rate,
            read_count=read_count,
            read_rate=read_rate,
            average_reading_time_seconds=avg_reading_time,
            acknowledged_count=acknowledged_count,
            acknowledgment_rate=acknowledgment_rate,
            average_time_to_read_hours=avg_time_to_read,
            engagement_score=engagement_score,
        )

    def get_reading_time_stats(self, announcement_id: UUID) -> ReadingTime:
        """
        Build ReadingTime statistics from stored read receipts.
        """
        receipts = self._store.list_read_receipts(announcement_id)
        times = [
            int(r.get("reading_time_seconds"))
            for r in receipts
            if r.get("reading_time_seconds") is not None
        ]
        if not times:
            return ReadingTime(
                announcement_id=announcement_id,
                average_reading_time_seconds=Decimal("0"),
                median_reading_time_seconds=Decimal("0"),
                min_reading_time_seconds=0,
                max_reading_time_seconds=0,
                quick_readers=0,
                normal_readers=0,
                thorough_readers=0,
            )

        times_sorted = sorted(times)
        total = len(times)
        avg = Decimal(str(sum(times))) / Decimal(str(total))
        median = Decimal(str(times_sorted[total // 2]))

        quick = sum(1 for t in times if t < 30)
        normal = sum(1 for t in times if 30 <= t <= 120)
        thorough = sum(1 for t in times if t > 120)

        return ReadingTime(
            announcement_id=announcement_id,
            average_reading_time_seconds=avg,
            median_reading_time_seconds=median,
            min_reading_time_seconds=min(times),
            max_reading_time_seconds=max(times),
            quick_readers=quick,
            normal_readers=normal,
            thorough_readers=thorough,
        )

    # ------------------------------------------------------------------ #
    # Combined analytics
    # ------------------------------------------------------------------ #
    def get_announcement_analytics(
        self,
        announcement_id: UUID,
        *,
        delivery_status: DeliveryStatus,
    ) -> AnnouncementAnalytics:
        """
        Build full AnnouncementAnalytics combining:
        - DeliveryStatus (from AnnouncementDeliveryService)
        - EngagementMetrics (from this service)
        - Reading distributions and device breakdown
        """
        engagement = self.get_engagement_metrics(announcement_id)

        with UnitOfWork(self._session_factory) as uow:
            announcement_repo = self._get_announcement_repo(uow)
            a = announcement_repo.get(announcement_id)
            if a is None:
                raise errors.NotFoundError(
                    f"Announcement {announcement_id} not found"
                )
            published_at = a.published_at or a.created_at

        receipts = self._store.list_read_receipts(announcement_id)

        by_hour: Dict[str, int] = {}
        by_day: Dict[str, int] = {}
        for r in receipts:
            ra = r.get("read_at")
            if not isinstance(ra, datetime):
                continue
            h_key = ra.strftime("%Y-%m-%d %H:00")
            d_key = ra.date().isoformat()
            by_hour[h_key] = by_hour.get(h_key, 0) + 1
            by_day[d_key] = by_day.get(d_key, 0) + 1

        device_counts = Counter(
            (r.get("device_type") or "unknown") for r in receipts
        )

        return AnnouncementAnalytics(
            announcement_id=announcement_id,
            title=engagement.title,
            published_at=published_at,
            delivery_metrics=delivery_status,
            engagement_metrics=engagement,
            reading_by_hour=by_hour,
            reading_by_day=by_day,
            reads_by_device=dict(device_counts),
        )