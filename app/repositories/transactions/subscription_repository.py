# app/repositories/transactions/subscription_repository.py
from datetime import date
from typing import List, Union
from uuid import UUID

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.repositories.base import BaseRepository
from app.models.transactions import Subscription
from app.schemas.common.enums import SubscriptionStatus


class SubscriptionRepository(BaseRepository[Subscription]):
    def __init__(self, session: Session):
        super().__init__(session, Subscription)

    def get_active_for_hostel(self, hostel_id: UUID, as_of: Union[date, None] = None) -> Union[Subscription, None]:
        stmt = self._base_select().where(
            Subscription.hostel_id == hostel_id,
            Subscription.status == SubscriptionStatus.ACTIVE,
        )
        if as_of is not None:
            stmt = stmt.where(
                Subscription.start_date <= as_of,
                Subscription.end_date >= as_of,
            )
        stmt = stmt.order_by(Subscription.start_date.desc()).limit(1)
        return self.session.execute(stmt).scalar_one_or_none()