# --- File: C:\Hostel-Main\app\repositories\fee_structure\__init__.py ---
"""
Fee Structure Repositories Package

This module exports all fee structure-related repositories.
"""

from app.repositories.fee_structure.fee_structure_repository import (
    FeeStructureRepository,
)
from app.repositories.fee_structure.charge_component_repository import (
    ChargeComponentRepository,
    ChargeRuleRepository,
    DiscountConfigurationRepository,
)
from app.repositories.fee_structure.fee_calculation_repository import (
    FeeCalculationRepository,
    FeeProjectionRepository,
)
from app.repositories.fee_structure.fee_aggregate_repository import (
    FeeAggregateRepository,
)

__all__ = [
    # Fee Structure
    "FeeStructureRepository",
    # Charge Components
    "ChargeComponentRepository",
    "ChargeRuleRepository",
    "DiscountConfigurationRepository",
    # Calculations
    "FeeCalculationRepository",
    "FeeProjectionRepository",
    # Aggregates
    "FeeAggregateRepository",
]