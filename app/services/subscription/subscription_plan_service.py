"""
Subscription Plan Service

Manages subscription plans and their feature sets.
"""

from __future__ import annotations

from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.subscription import SubscriptionPlanRepository
from app.schemas.subscription import (
    SubscriptionPlanBase,
    PlanCreate,
    PlanUpdate,
    PlanResponse,
    PlanFeatures,
    PlanComparison,
)
from app.core.exceptions import ValidationException


class SubscriptionPlanService:
    """
    High-level service for subscription plans.

    Responsibilities:
    - Create/update/delete plans
    - List/search plans
    - Get plan features
    - Compare plans
    """

    def __init__(
        self,
        plan_repo: SubscriptionPlanRepository,
    ) -> None:
        self.plan_repo = plan_repo

    # -------------------------------------------------------------------------
    # CRUD
    # -------------------------------------------------------------------------

    def create_plan(
        self,
        db: Session,
        data: PlanCreate,
    ) -> PlanResponse:
        obj = self.plan_repo.create(
            db,
            data=data.model_dump(exclude_none=True),
        )
        return PlanResponse.model_validate(obj)

    def update_plan(
        self,
        db: Session,
        plan_id: UUID,
        data: PlanUpdate,
    ) -> PlanResponse:
        plan = self.plan_repo.get_by_id(db, plan_id)
        if not plan:
            raise ValidationException("Plan not found")

        updated = self.plan_repo.update(
            db,
            plan,
            data=data.model_dump(exclude_none=True),
        )
        return PlanResponse.model_validate(updated)

    def delete_plan(
        self,
        db: Session,
        plan_id: UUID,
    ) -> None:
        plan = self.plan_repo.get_by_id(db, plan_id)
        if not plan:
            return
        self.plan_repo.delete(db, plan)

    # -------------------------------------------------------------------------
    # Retrieval
    # -------------------------------------------------------------------------

    def get_plan(
        self,
        db: Session,
        plan_id: UUID,
    ) -> PlanResponse:
        plan = self.plan_repo.get_by_id(db, plan_id)
        if not plan:
            raise ValidationException("Plan not found")
        return PlanResponse.model_validate(plan)

    def list_plans(
        self,
        db: Session,
        active_only: bool = True,
        public_only: bool = False,
    ) -> List[PlanResponse]:
        objs = self.plan_repo.get_all(
            db,
            active_only=active_only,
            public_only=public_only,
        )
        return [PlanResponse.model_validate(o) for o in objs]

    def search_plans(
        self,
        db: Session,
        search_term: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        has_trial: Optional[bool] = None,
    ) -> List[PlanResponse]:
        objs = self.plan_repo.search_plans(
            db,
            search_term=search_term,
            min_price=min_price,
            max_price=max_price,
            has_trial=has_trial,
        )
        return [PlanResponse.model_validate(o) for o in objs]

    # -------------------------------------------------------------------------
    # Features & comparison
    # -------------------------------------------------------------------------

    def get_plan_features(
        self,
        db: Session,
        plan_id: UUID,
        feature_labels: Optional[Dict[str, str]] = None,
    ) -> PlanFeatures:
        """
        Return a human-friendly feature set for a plan.
        """
        plan = self.plan_repo.get_by_id(db, plan_id)
        if not plan:
            raise ValidationException("Plan not found")

        plan_resp = PlanResponse.model_validate(plan)
        return PlanFeatures.from_plan_response(plan_resp, feature_labels or {})

    def compare_plans(
        self,
        db: Session,
        plan_ids: List[UUID],
    ) -> PlanComparison:
        """
        Build a comparison matrix of multiple plans.
        """
        if len(plan_ids) < 2:
            raise ValidationException("At least two plans required for comparison")

        objs = [self.plan_repo.get_by_id(db, pid) for pid in plan_ids]
        if any(o is None for o in objs):
            raise ValidationException("One or more plans not found")

        plans = [PlanResponse.model_validate(o) for o in objs]
        return PlanComparison.create(plans)