"""
Fee Structure Service Layer

Provides comprehensive business logic for:
- Fee Structure lifecycle management (CRUD, versioning, status transitions)
- Charge components, rules, and discount configurations
- Fee approval workflows with audit trails
- Real-time fee calculations, quotes, and recomputations
- Revenue projections and forecasting
- Pro-ration calculations for mid-cycle changes

Version: 2.0.0
"""

from app.services.fee_structure.fee_structure_service import FeeStructureService
from app.services.fee_structure.fee_approval_service import FeeApprovalService
from app.services.fee_structure.charge_component_service import ChargeComponentService
from app.services.fee_structure.fee_calculation_service import FeeCalculationService
from app.services.fee_structure.fee_projection_service import FeeProjectionService
from app.services.fee_structure.proration_service import ProrationService

__all__ = [
    "FeeStructureService",
    "FeeApprovalService",
    "ChargeComponentService",
    "FeeCalculationService",
    "FeeProjectionService",
    "ProrationService",
]

__version__ = "2.0.0"