from fastapi import APIRouter

from . import requests
from . import assignment
from . import approval
from . import completion
from . import schedule
from . import cost
from . import analytics

router = APIRouter(prefix="/maintenance")

router.include_router(requests.router, tags=["Maintenance - Requests"])
router.include_router(assignment.router, tags=["Maintenance - Assignment"])
router.include_router(approval.router, tags=["Maintenance - Approval"])
router.include_router(completion.router, tags=["Maintenance - Completion"])
router.include_router(schedule.router, tags=["Maintenance - Preventive Schedule"])
router.include_router(cost.router, tags=["Maintenance - Cost & Budgets"])
router.include_router(analytics.router, tags=["Maintenance - Analytics"])

__all__ = ["router"]