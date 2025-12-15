# app/services/fee_structure/__init__.py
"""
Fee structure services.

- FeeStructureService: CRUD & listing for fee structures per hostel.
- FeeConfigService: compute effective fee configuration & breakdown.
"""

from .fee_structure_service import FeeStructureService
from .fee_config_service import FeeConfigService

__all__ = [
    "FeeStructureService",
    "FeeConfigService",
]