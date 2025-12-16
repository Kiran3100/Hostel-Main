# app/repositories/analytics/analytics_data_repository.py
from datetime import datetime
from typing import Union

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.repositories.base import BaseRepository
from app.models.analytics import AnalyticsData


class AnalyticsDataRepository(BaseRepository[AnalyticsData]):
    def __init__(self, session: Session):
        super().__init__(session, AnalyticsData)

    def get_for_period(
        self,
        *,
        period_start: datetime,
        period_end: datetime,
    ) -> Union[AnalyticsData, None]:
        stmt = (
            self._base_select()
            .where(
                and_(
                    AnalyticsData.period_start == period_start,
                    AnalyticsData.period_end == period_end,
                )
            )
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def get_latest(self) -> Union[AnalyticsData, None]:
        stmt = self._base_select().order_by(AnalyticsData.period_end.desc()).limit(1)
        return self.session.execute(stmt).scalar_one_or_none()