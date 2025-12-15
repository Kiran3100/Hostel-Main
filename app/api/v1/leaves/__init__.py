# api/v1/leaves/__init__.py
from __future__ import annotations

from fastapi import APIRouter

from . import leaves
from . import apply
from . import approval
from . import balance

router = APIRouter(prefix="/leaves")

router.include_router(leaves.router, tags=["Leaves - Core"])
router.include_router(apply.router, tags=["Leaves - Apply & Cancel"])
router.include_router(approval.router, tags=["Leaves - Approval"])
router.include_router(balance.router, tags=["Leaves - Balance"])

__all__ = ["router"]