# app/services/subscription/subscription_plan_service.py
from __future__ import annotations

from typing import Callable, Dict, List
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.transactions import SubscriptionPlanRepository
from app.schemas.subscription.subscription_plan_base import PlanCreate, PlanUpdate
from app.schemas.subscription.subscription_plan_response import (
    PlanResponse,
    PlanComparison,
)
from app.services.common import UnitOfWork, errors


class SubscriptionPlanService:
    """
    Manage subscription plans:

    - Create / update plans
    - Get single plan
    - List public plans
    - Compare multiple plans (feature matrix)
    """

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _get_repo(self, uow: UnitOfWork) -> SubscriptionPlanRepository:
        return uow.get_repo(SubscriptionPlanRepository)

    # ------------------------------------------------------------------ #
    # Mapping
    # ------------------------------------------------------------------ #
    def _to_response(self, p) -> PlanResponse:
        return PlanResponse(
            id=p.id,
            created_at=p.created_at,
            updated_at=p.updated_at,
            plan_name=p.plan_name,
            display_name=p.display_name,
            plan_type=p.plan_type,
            description=p.description,
            price_monthly=p.price_monthly,
            price_yearly=p.price_yearly,
            currency=p.currency,
            features=p.features or {},
            max_hostels=p.max_hostels,
            max_rooms_per_hostel=p.max_rooms_per_hostel,
            max_students=p.max_students,
            is_active=p.is_active,
            is_public=p.is_public,
            sort_order=p.sort_order,
        )

    # ------------------------------------------------------------------ #
    # CRUD
    # ------------------------------------------------------------------ #
    def create_plan(self, data: PlanCreate) -> PlanResponse:
        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_repo(uow)

            payload = data.model_dump(exclude_unset=True)
            p = repo.create(payload)  # type: ignore[arg-type]
            uow.commit()
            return self._to_response(p)

    def update_plan(self, plan_id: UUID, data: PlanUpdate) -> PlanResponse:
        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_repo(uow)

            p = repo.get(plan_id)
            if p is None:
                raise errors.NotFoundError(f"SubscriptionPlan {plan_id} not found")

            mapping = data.model_dump(exclude_unset=True)
            for field, value in mapping.items():
                if hasattr(p, field) and field != "id":
                    setattr(p, field, value)

            uow.session.flush()  # type: ignore[union-attr]
            uow.commit()
            return self._to_response(p)

    def get_plan(self, plan_id: UUID) -> PlanResponse:
        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_repo(uow)
            p = repo.get(plan_id)
            if p is None:
                raise errors.NotFoundError(f"SubscriptionPlan {plan_id} not found")
            return self._to_response(p)

    def list_public_plans(self) -> List[PlanResponse]:
        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_repo(uow)
            recs = repo.list_public()
        return [self._to_response(p) for p in recs]

    # ------------------------------------------------------------------ #
    # Comparison
    # ------------------------------------------------------------------ #
    def compare_plans(self, plan_ids: List[UUID]) -> PlanComparison:
        """
        Build a PlanComparison for the given plan_ids.
        """
        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_repo(uow)
            recs = []
            for pid in plan_ids:
                p = repo.get(pid)
                if p:
                    recs.append(p)

        responses = [self._to_response(p) for p in recs]

        # feature_matrix: feature_key -> plan_name -> value
        feature_matrix: Dict[str, Dict[str, object]] = {}
        for p in responses:
            for key, value in (p.features or {}).items():
                feature_matrix.setdefault(key, {})[p.plan_name] = value

        return PlanComparison(
            plans=responses,
            feature_matrix=feature_matrix,
        )