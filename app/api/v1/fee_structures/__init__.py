# api/v1/fee_structures/__init__.py

from fastapi import APIRouter

from . import fees
from . import config

router = APIRouter(prefix="/fee-structures")

router.include_router(fees.router, tags=["Fee Structures - Core"])
router.include_router(config.router, tags=["Fee Structures - Configuration"])

__all__ = ["router"]