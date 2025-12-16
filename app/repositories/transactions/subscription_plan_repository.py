# app/repositories/transactions/subscription_plan_repository.py
from typing import List, Union

from sqlalchemy.orm import Session

from app.repositories.base import BaseRepository
from app.models.transactions import SubscriptionPlan as SubscriptionPlanModel
from app.schemas.common.enums import SubscriptionPlan as SubscriptionPlanEnum


class SubscriptionPlanRepository(BaseRepository[SubscriptionPlanModel]):
    def __init__(self, session: Session):
        super().__init__(session, SubscriptionPlanModel)

    def list_public(self) -> List[SubscriptionPlanModel]:
        stmt = self._base_select().where(SubscriptionPlanModel.is_public.is_(True))
        stmt = stmt.order_by(SubscriptionPlanModel.sort_order.asc())
        return self.session.execute(stmt).scalars().all()

    def get_by_plan_type(self, plan_type: SubscriptionPlanEnum) -> Union[SubscriptionPlanModel, None]:
        stmt = self._base_select().where(SubscriptionPlanModel.plan_type == plan_type)
        return self.session.execute(stmt).scalar_one_or_none()