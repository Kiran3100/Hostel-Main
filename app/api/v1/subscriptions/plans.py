# app/api/v1/subscriptions/plans.py
from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core import get_session
from app.services import UnitOfWork
from app.schemas.subscription.subscription_plan_base import PlanCreate, PlanUpdate
from app.schemas.subscription.subscription_plan_response import (
    PlanResponse,
    PlanComparison,
)
from app.services.subscription import SubscriptionPlanService
from . import CurrentUser, get_current_user

router = APIRouter(tags=["Subscription - Plans"])


def _get_service(session: Session) -> SubscriptionPlanService:
    uow = UnitOfWork(session)
    return SubscriptionPlanService(uow)


@router.get("/", response_model=List[PlanResponse])
def list_plans(
    public_only: bool = Query(
        True,
        description="If true, return only public plans; otherwise return all plans.",
    ),
    include_inactive: bool = Query(
        False,
        description="If true, include inactive plans (admin use).",
    ),
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> List[PlanResponse]:
    """
    List subscription plans.

    Expected service method:
        list_plans(public_only: bool, include_inactive: bool) -> list[PlanResponse]
    """
    service = _get_service(session)
    return service.list_plans(
        public_only=public_only,
        include_inactive=include_inactive,
    )


@router.get("/public", response_model=List[PlanResponse])
def list_public_plans(
    session: Session = Depends(get_session),
) -> List[PlanResponse]:
    """
    Public endpoint: list only public & active plans (no auth required).

    Expected service method:
        list_public_plans() -> list[PlanResponse]
    """
    service = _get_service(session)
    return service.list_public_plans()


@router.get("/comparison", response_model=PlanComparison)
def compare_plans(
    plan_ids: Optional[List[UUID]] = Query(
        None,
        description="Optional list of plan IDs to compare; if omitted, compare all public plans.",
    ),
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> PlanComparison:
    """
    Compare plans via feature matrix.

    Expected service method:
        get_plan_comparison(plan_ids: Optional[list[UUID]]) -> PlanComparison
    """
    service = _get_service(session)
    return service.get_plan_comparison(plan_ids=plan_ids)


@router.get("/{plan_id}", response_model=PlanResponse)
def get_plan(
    plan_id: UUID,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> PlanResponse:
    """
    Get a single subscription plan by ID.

    Expected service method:
        get_plan(plan_id: UUID) -> PlanResponse
    """
    service = _get_service(session)
    return service.get_plan(plan_id=plan_id)


@router.post(
    "/",
    response_model=PlanResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_plan(
    payload: PlanCreate,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> PlanResponse:
    """
    Create a new subscription plan.

    Expected service method:
        create_plan(data: PlanCreate) -> PlanResponse
    """
    service = _get_service(session)
    return service.create_plan(data=payload)


@router.patch("/{plan_id}", response_model=PlanResponse)
def update_plan(
    plan_id: UUID,
    payload: PlanUpdate,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> PlanResponse:
    """
    Update an existing subscription plan.

    Expected service method:
        update_plan(plan_id: UUID, data: PlanUpdate) -> PlanResponse
    """
    service = _get_service(session)
    return service.update_plan(
        plan_id=plan_id,
        data=payload,
    )