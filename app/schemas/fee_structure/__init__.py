# --- File: app/schemas/fee_structure/__init__.py ---
"""
Fee structure and configuration schemas package.

This module exports all fee structure-related schemas for easy importing
across the application.
"""

from app.schemas.fee_structure.charge_component import (
    ChargeComponent,
    ChargeComponentBase,
    ChargeComponentCreate,
    ChargeComponentUpdate,
)
from app.schemas.fee_structure.fee_base import (
    FeeStructureBase,
    FeeStructureCreate,
    FeeStructureUpdate,
)
from app.schemas.fee_structure.fee_config import (
    ChargesBreakdown,
    DiscountConfiguration,
    DiscountCreate,
    DiscountUpdate,
    FeeComparison,
    FeeConfiguration,
    FeeProjection,
    FeeQuoteRequest,
    HistoricalData,
    MonthlyProjection,
)
from app.schemas.fee_structure.fee_response import (
    FeeCalculation,
    FeeDetail,
    FeeHistory,
    FeeHistoryItem,
    FeeStructureList,
    FeeStructureResponse,
)

__all__ = [
    # Base
    "FeeStructureBase",
    "FeeStructureCreate",
    "FeeStructureUpdate",
    # Response
    "FeeStructureResponse",
    "FeeDetail",
    "FeeStructureList",
    "FeeHistory",
    "FeeHistoryItem",
    "FeeCalculation",
    # Configuration
    "FeeConfiguration",
    "ChargesBreakdown",
    "DiscountConfiguration",
    "DiscountCreate",
    "DiscountUpdate",
    "FeeComparison",
    "FeeQuoteRequest",
    "FeeProjection",
    "MonthlyProjection",
    "HistoricalData",
    # Charge Components
    "ChargeComponent",
    "ChargeComponentBase",
    "ChargeComponentCreate",
    "ChargeComponentUpdate",
]