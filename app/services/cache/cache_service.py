# app/cache/services_cache.py
from __future__ import annotations

from typing import Optional
from uuid import UUID

from app.cache.base import BaseCache, CacheBackend
from app.repositories.services import (
    AttendanceRepository,
    ComplaintRepository,
    InquiryRepository,
    LeaveApplicationRepository,
    MaintenanceRepository,
)
from models.services import (
    Attendance,
    Complaint,
    Inquiry,
    LeaveApplication,
    Maintenance,
)


class ServicesCache:
    """
    Central cache facade for service-layer entities.

    It wraps the underlying repositories with simple read-through caches
    (by primary key). Call the `invalidate_*` methods after writes.
    """

    def __init__(
        self,
        backend: CacheBackend,
        *,
        attendance_repo: AttendanceRepository,
        complaint_repo: ComplaintRepository,
        inquiry_repo: InquiryRepository,
        leave_repo: LeaveApplicationRepository,
        maintenance_repo: MaintenanceRepository,
        default_ttl: int | None = 300,
    ) -> None:
        self._attendance_repo = attendance_repo
        self._complaint_repo = complaint_repo
        self._inquiry_repo = inquiry_repo
        self._leave_repo = leave_repo
        self._maintenance_repo = maintenance_repo

        self._attendance_cache = BaseCache[Attendance](backend, prefix="attendance", default_ttl=default_ttl)
        self._complaint_cache = BaseCache[Complaint](backend, prefix="complaint", default_ttl=default_ttl)
        self._inquiry_cache = BaseCache[Inquiry](backend, prefix="inquiry", default_ttl=default_ttl)
        self._leave_cache = BaseCache[LeaveApplication](backend, prefix="leave_application", default_ttl=default_ttl)
        self._maintenance_cache = BaseCache[Maintenance](backend, prefix="maintenance", default_ttl=default_ttl)

    # ------------------------------------------------------------------ #
    # Attendance
    # ------------------------------------------------------------------ #
    def get_attendance_by_id(self, attendance_id: UUID) -> Optional[Attendance]:
        key = str(attendance_id)

        def _load() -> Optional[Attendance]:
            return self._attendance_repo.get(attendance_id)

        return self._attendance_cache.get_or_load(key, _load)

    def invalidate_attendance(self, attendance_id: UUID) -> None:
        self._attendance_cache.delete(str(attendance_id))

    # ------------------------------------------------------------------ #
    # Complaint
    # ------------------------------------------------------------------ #
    def get_complaint_by_id(self, complaint_id: UUID) -> Optional[Complaint]:
        key = str(complaint_id)

        def _load() -> Optional[Complaint]:
            return self._complaint_repo.get(complaint_id)

        return self._complaint_cache.get_or_load(key, _load)

    def invalidate_complaint(self, complaint_id: UUID) -> None:
        self._complaint_cache.delete(str(complaint_id))

    # ------------------------------------------------------------------ #
    # Inquiry
    # ------------------------------------------------------------------ #
    def get_inquiry_by_id(self, inquiry_id: UUID) -> Optional[Inquiry]:
        key = str(inquiry_id)

        def _load() -> Optional[Inquiry]:
            return self._inquiry_repo.get(inquiry_id)

        return self._inquiry_cache.get_or_load(key, _load)

    def invalidate_inquiry(self, inquiry_id: UUID) -> None:
        self._inquiry_cache.delete(str(inquiry_id))

    # ------------------------------------------------------------------ #
    # LeaveApplication
    # ------------------------------------------------------------------ #
    def get_leave_application_by_id(self, leave_id: UUID) -> Optional[LeaveApplication]:
        key = str(leave_id)

        def _load() -> Optional[LeaveApplication]:
            return self._leave_repo.get(leave_id)

        return self._leave_cache.get_or_load(key, _load)

    def invalidate_leave_application(self, leave_id: UUID) -> None:
        self._leave_cache.delete(str(leave_id))

    # ------------------------------------------------------------------ #
    # Maintenance
    # ------------------------------------------------------------------ #
    def get_maintenance_by_id(self, maintenance_id: UUID) -> Optional[Maintenance]:
        key = str(maintenance_id)

        def _load() -> Optional[Maintenance]:
            return self._maintenance_repo.get(maintenance_id)

        return self._maintenance_cache.get_or_load(key, _load)

    def invalidate_maintenance(self, maintenance_id: UUID) -> None:
        self._maintenance_cache.delete(str(maintenance_id))