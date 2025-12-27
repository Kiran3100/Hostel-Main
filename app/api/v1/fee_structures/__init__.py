from fastapi import APIRouter

from . import calculate, fee_structures

router = APIRouter()

router.include_router(fee_structures.router)
router.include_router(calculate.router)

__all__ = ["router"]