# app/services/reporting/audit_reporting_service.py
from __future__ import annotations

from typing import Callable, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.schemas.common.filters import DateRangeFilter
from app.schemas.audit import (
    AuditFilterParams,
    AuditReport,
)
from app.schemas.audit import (
    AdminOverrideSummary,
)
from app.schemas.audit import (
    SupervisorActivityFilter,
    SupervisorActivitySummary,
)
from app.services.common import UnitOfWork
from app.services.audit import (
    AuditLogService,
    AdminOverrideAuditService,
    SupervisorActivityService,
)


class AuditReportingService:
    """
    Aggregated audit reporting facade:

    - High-level AuditReport over audit_log table.
    - AdminOverride summaries.
    - Supervisor activity summaries.
    """

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory
        self._audit_log_service = AuditLogService(session_factory)
        self._override_service = AdminOverrideAuditService(session_factory)
        self._supervisor_service = SupervisorActivityService(session_factory)

    # ------------------------------------------------------------------ #
    # Audit logs
    # ------------------------------------------------------------------ #
    def build_audit_report(
        self,
        period: DateRangeFilter,
        *,
        hostel_id: Optional[UUID] = None,
    ) -> AuditReport:
        """
        Delegate to AuditLogService.build_report.
        """
        return self._audit_log_service.build_report(
            period=period,
            hostel_id=hostel_id,
        )

    # ------------------------------------------------------------------ #
    # Admin overrides
    # ------------------------------------------------------------------ #
    def get_admin_override_summary(
        self,
        period: DateRangeFilter,
        *,
        supervisor_id: Optional[UUID] = None,
        hostel_id: Optional[UUID] = None,
    ) -> AdminOverrideSummary:
        """
        Delegate to AdminOverrideAuditService.get_summary.
        """
        return self._override_service.get_summary(
            period=period,
            supervisor_id=supervisor_id,
            hostel_id=hostel_id,
        )

    # ------------------------------------------------------------------ #
    # Supervisor activity
    # ------------------------------------------------------------------ #
    def get_supervisor_activity_summary(
        self,
        filters: SupervisorActivityFilter,
    ) -> SupervisorActivitySummary:
        """
        Delegate to SupervisorActivityService.get_summary.
        """
        return self._supervisor_service.get_summary(filters)