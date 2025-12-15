# app/repositories/analytics/supervisor_performance_metrics_repository.py
from __future__ import annotations

from datetime import date
from typing import Optional
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.repositories.base import BaseRepository
from app.models.analytics import SupervisorPerformanceMetrics


class SupervisorPerformanceMetricsRepository(BaseRepository[SupervisorPerformanceMetrics]):
    def __init__(self, session: Session):
        super().__init__(session, SupervisorPerformanceMetrics)

    def get_for_supervisor_period(
        self,
        *,
        supervisor_id: UUID,
        hostel_id: UUID,
        period_start: date,
        period_end: date,
    ) -> Optional[SupervisorPerformanceMetrics]:
        stmt = (
            self._base_select()
            .where(
                and_(
                    SupervisorPerformanceMetrics.supervisor_id == supervisor_id,
                    SupervisorPerformanceMetrics.hostel_id == hostel_id,
                    SupervisorPerformanceMetrics.period_start == period_start,
                    SupervisorPerformanceMetrics.period_end == period_end,
                )
            )
        )
        return self.session.execute(stmt).scalar_one_or_none()