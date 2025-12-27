"""
Fee Structures API Module

This module aggregates all fee structure-related endpoints including:
- Fee structure CRUD operations
- Charge component management
- Discount configuration
- Fee calculations and quotes
- Revenue projections

Version: 1.0.0
"""

from fastapi import APIRouter

from .calculate import router as calculate_router
from .fee_structures import router as fee_structures_router

# Main router for fee structures module
router = APIRouter()

# Include sub-routers with proper ordering
# Fee structures router first (base CRUD operations)
router.include_router(
    fee_structures_router,
    prefix="",
    tags=["fee-structures"]
)

# Calculation router second (dependent operations)
router.include_router(
    calculate_router,
    prefix="",
    tags=["fee-structures:calculate"]
)

# Export router for use in main API
__all__ = ["router"]