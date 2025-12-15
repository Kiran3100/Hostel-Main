# app/services/reporting/__init__.py
"""
Reporting services.

- FinancialReportingService:
    High-level financial reporting over payments + financial analytics.

- OccupancyReportingService:
    Hostel occupancy reporting, using occupancy analytics.

- AuditReportingService:
    Audit / override / supervisor activity reporting facades.

- ExportService:
    Generic tabular export (CSV/Excel/PDF) via a pluggable backend.
"""

from .financial_reporting_service import FinancialReportingService
from .occupancy_reporting_service import OccupancyReportingService
from .audit_reporting_service import AuditReportingService
from .export_service import ExportService, ExportBackend

__all__ = [
    "FinancialReportingService",
    "OccupancyReportingService",
    "AuditReportingService",
    "ExportService",
    "ExportBackend",
]