# app/services/attendance/attendance_alert_service.py
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Callable, Dict, List, Optional, Protocol
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.repositories.core import StudentRepository, HostelRepository
from app.schemas.attendance.attendance_alert import (
    AttendanceAlert,
    AlertConfig,
    AlertTrigger,
    AlertAcknowledgment,
    AlertList,
    AlertSummary,
)
from app.services.common import UnitOfWork, errors


class AlertStore(Protocol):
    """
    Abstract store for attendance alerts and alert configuration.
    """

    def create_alert(self, record: dict) -> dict: ...
    def update_alert(self, alert_id: UUID, data: dict) -> dict: ...
    def get_alert(self, alert_id: UUID) -> Optional[dict]: ...
    def list_alerts_for_hostel(self, hostel_id: UUID) -> List[dict]: ...

    def get_config(self, hostel_id: UUID) -> Optional[dict]: ...
    def save_config(self, hostel_id: UUID, data: dict) -> None: ...


class AttendanceAlertService:
    """
    Attendance alert service:

    - Manage AlertConfig per hostel
    - Trigger manual alerts
    - Acknowledge alerts
    - List alerts and build summary
    """

    def __init__(
        self,
        session_factory: Callable[[], Session],
        store: AlertStore,
    ) -> None:
        self._session_factory = session_factory
        self._store = store

    def _get_hostel_repo(self, uow: UnitOfWork) -> HostelRepository:
        return uow.get_repo(HostelRepository)

    def _get_student_repo(self, uow: UnitOfWork) -> StudentRepository:
        return uow.get_repo(StudentRepository)

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    # ------------------------------------------------------------------ #
    # Config
    # ------------------------------------------------------------------ #
    def get_config(self, hostel_id: UUID) -> AlertConfig:
        record = self._store.get_config(hostel_id)
        if record:
            return AlertConfig.model_validate(record)
        # Default config if none stored
        cfg = AlertConfig(
            hostel_id=hostel_id,
        )
        self._store.save_config(hostel_id, cfg.model_dump())
        return cfg

    def set_config(self, cfg: AlertConfig) -> None:
        self._store.save_config(cfg.hostel_id, cfg.model_dump())

    # ------------------------------------------------------------------ #
    # Alerts
    # ------------------------------------------------------------------ #
    def trigger_manual_alert(
        self,
        hostel_id: UUID,
        data: AlertTrigger,
    ) -> AttendanceAlert:
        """
        Manually trigger an alert for a student.
        """
        now = self._now()

        with UnitOfWork(self._session_factory) as uow:
            hostel_repo = self._get_hostel_repo(uow)
            student_repo = self._get_student_repo(uow)

            hostel = hostel_repo.get(hostel_id)
            if hostel is None:
                raise errors.NotFoundError(f"Hostel {hostel_id} not found")

            student = student_repo.get(data.student_id)
            if student is None or not getattr(student, "user", None):
                raise errors.NotFoundError(f"Student {data.student_id} not found")

            student_name = student.user.full_name

        alert_id = uuid4()
        record = {
            "id": alert_id,
            "alert_id": alert_id,
            "hostel_id": hostel_id,
            "student_id": data.student_id,
            "student_name": student_name,
            "alert_type": data.alert_type,
            "severity": data.severity,
            "message": data.custom_message,
            "details": {},
            "triggered_at": now,
            "triggered_by_rule": None,
            "acknowledged": False,
            "acknowledged_by": None,
            "acknowledged_at": None,
            "actions_taken": [],
            "resolved": False,
            "resolved_at": None,
            "created_at": now,
            "updated_at": now,
        }
        created = self._store.create_alert(record)
        return AttendanceAlert.model_validate(created)

    def acknowledge_alert(self, data: AlertAcknowledgment) -> AttendanceAlert:
        """
        Acknowledge an alert and record the action taken.
        """
        now = self._now()
        record = self._store.get_alert(data.alert_id)
        if not record:
            raise errors.NotFoundError(f"Alert {data.alert_id} not found")

        record["acknowledged"] = True
        record["acknowledged_by"] = str(data.acknowledged_by)
        record["acknowledged_at"] = now
        actions = record.get("actions_taken", []) or []
        actions.append(data.action_taken)
        record["actions_taken"] = actions
        record["updated_at"] = now

        updated = self._store.update_alert(data.alert_id, record)
        return AttendanceAlert.model_validate(updated)

    def list_alerts_for_hostel(self, hostel_id: UUID) -> AlertList:
        records = self._store.list_alerts_for_hostel(hostel_id)
        alerts: List[AttendanceAlert] = [
            AttendanceAlert.model_validate(r) for r in records
        ]

        total_alerts = len(alerts)
        unack = sum(1 for a in alerts if not a.acknowledged)
        critical = sum(1 for a in alerts if a.severity == "critical")

        return AlertList(
            hostel_id=hostel_id,
            total_alerts=total_alerts,
            unacknowledged_alerts=unack,
            critical_alerts=critical,
            alerts=alerts,
        )

    def get_alert_summary(
        self,
        hostel_id: UUID,
        *,
        period_start: date,
        period_end: date,
    ) -> AlertSummary:
        records = self._store.list_alerts_for_hostel(hostel_id)
        filtered: List[dict] = []
        for r in records:
            ta: datetime = r.get("triggered_at")
            if not isinstance(ta, datetime):
                continue
            d = ta.date()
            if d < period_start or d > period_end:
                continue
            filtered.append(r)

        total_alerts = len(filtered)

        low_att = cons_abs = late_ent = pattern = 0
        crit = high = med = low_s = 0
        acknowledged = resolved = 0

        for r in filtered:
            atype = r.get("alert_type")
            sev = r.get("severity")

            if atype == "low_attendance":
                low_att += 1
            elif atype == "consecutive_absences":
                cons_abs += 1
            elif atype == "late_entry":
                late_ent += 1
            elif atype == "irregular_pattern":
                pattern += 1

            if sev == "critical":
                crit += 1
            elif sev == "high":
                high += 1
            elif sev == "medium":
                med += 1
            elif sev == "low":
                low_s += 1

            if r.get("acknowledged"):
                acknowledged += 1
            if r.get("resolved"):
                resolved += 1

        pending = total_alerts - resolved

        return AlertSummary(
            hostel_id=hostel_id,
            period_start=period_start,
            period_end=period_end,
            total_alerts=total_alerts,
            low_attendance_alerts=low_att,
            consecutive_absence_alerts=cons_abs,
            late_entry_alerts=late_ent,
            pattern_alerts=pattern,
            critical_count=crit,
            high_count=high,
            medium_count=med,
            low_count=low_s,
            acknowledged_count=acknowledged,
            resolved_count=resolved,
            pending_count=pending,
        )