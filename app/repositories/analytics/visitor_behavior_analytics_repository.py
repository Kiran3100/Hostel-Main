# app/repositories/analytics/visitor_behavior_analytics_repository.py
from typing import Union
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.repositories.base import BaseRepository
from app.models.analytics import VisitorBehaviorAnalytics


class VisitorBehaviorAnalyticsRepository(BaseRepository[VisitorBehaviorAnalytics]):
    """
    Analytics-focused visitor behavior repository.
    """
    def __init__(self, session: Session):
        super().__init__(session, VisitorBehaviorAnalytics)

    def get_by_visitor_id(self, visitor_id: UUID) -> Union[VisitorBehaviorAnalytics, None]:
        stmt = self._base_select().where(VisitorBehaviorAnalytics.visitor_id == visitor_id)
        return self.session.execute(stmt).scalar_one_or_none()