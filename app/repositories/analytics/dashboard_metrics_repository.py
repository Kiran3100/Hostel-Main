# app/repositories/analytics/dashboard_metrics_repository.py
from datetime import date
from typing import Union
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.repositories.base import BaseRepository
from app.models.analytics import DashboardMetrics


class DashboardMetricsRepository(BaseRepository[DashboardMetrics]):
    def __init__(self, session: Session):
        super().__init__(session, DashboardMetrics)

    def get_for_scope_and_period(
        self,
        *,
        scope_type: str,
        scope_id: Union[UUID, None],
        period_start: date,
        period_end: date,
    ) -> Union[DashboardMetrics, None]:
        stmt = (
            self._base_select()
            .where(
                and_(
                    DashboardMetrics.scope_type == scope_type,
                    DashboardMetrics.scope_id == scope_id,
                    DashboardMetrics.period_start == period_start,
                    DashboardMetrics.period_end == period_end,
                )
            )
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def get_latest_for_scope(
        self,
        *,
        scope_type: str,
        scope_id: Union[UUID, None],
    ) -> Union[DashboardMetrics, None]:
        stmt = (
            self._base_select()
            .where(
                and_(
                    DashboardMetrics.scope_type == scope_type,
                    DashboardMetrics.scope_id == scope_id,
                )
            )
            .order_by(DashboardMetrics.generated_at.desc())
            .limit(1)
        )
        return self.session.execute(stmt).scalar_one_or_none()