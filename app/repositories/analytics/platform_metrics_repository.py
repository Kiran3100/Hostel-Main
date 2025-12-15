# app/repositories/analytics/platform_metrics_repository.py
from __future__ import annotations

from datetime import date
from typing import Optional

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.repositories.base import BaseRepository
from app.models.analytics import PlatformMetrics, GrowthMetrics, PlatformUsageAnalytics


class PlatformMetricsRepository(BaseRepository[PlatformMetrics]):
    def __init__(self, session: Session):
        super().__init__(session, PlatformMetrics)

    def get_latest(self) -> Optional[PlatformMetrics]:
        stmt = self._base_select().order_by(PlatformMetrics.generated_at.desc()).limit(1)
        return self.session.execute(stmt).scalar_one_or_none()


class GrowthMetricsRepository(BaseRepository[GrowthMetrics]):
    def __init__(self, session: Session):
        super().__init__(session, GrowthMetrics)

    def get_for_period(self, *, period_start: date, period_end: date) -> Optional[GrowthMetrics]:
        stmt = (
            self._base_select()
            .where(
                and_(
                    GrowthMetrics.period_start == period_start,
                    GrowthMetrics.period_end == period_end,
                )
            )
        )
        return self.session.execute(stmt).scalar_one_or_none()


class PlatformUsageAnalyticsRepository(BaseRepository[PlatformUsageAnalytics]):
    def __init__(self, session: Session):
        super().__init__(session, PlatformUsageAnalytics)

    def get_latest(self) -> Optional[PlatformUsageAnalytics]:
        stmt = self._base_select().order_by(PlatformUsageAnalytics.generated_at.desc()).limit(1)
        return self.session.execute(stmt).scalar_one_or_none()