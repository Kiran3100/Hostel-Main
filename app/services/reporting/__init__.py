# app/services/reporting/__init__.py
"""
Reporting services package.

Provides comprehensive reporting services for:

- Financial reports (P&L, cashflow, comprehensive financial analysis):
  - FinancialReportService

- Operational reports (bookings, complaints, occupancy, team performance):
  - OperationalReportService

- Compliance & security (GDPR, SOC2, audit trails):
  - ComplianceReportService

- Custom reports (user-defined, scheduled, cached):
  - CustomReportService

- Export functionality (JSON, CSV, Excel, PDF):
  - ReportExportService

- Scheduling (automated report execution):
  - ReportSchedulingService

- Unified facade (single entry point for all reports):
  - ReportService

All services include:
- Comprehensive error handling and logging
- Input validation
- Performance tracking
- Caching where appropriate
- Authorization checks
"""

from .compliance_report_service import ComplianceReportService
from .custom_report_service import CustomReportService
from .financial_report_service import FinancialReportService
from .operational_report_service import OperationalReportService
from .report_export_service import ReportExportService
from .report_scheduling_service import ReportSchedulingService
from .report_service import ReportService

__all__ = [
    "ComplianceReportService",
    "CustomReportService",
    "FinancialReportService",
    "OperationalReportService",
    "ReportExportService",
    "ReportSchedulingService",
    "ReportService",
]

# Version info
__version__ = "2.0.0"
__author__ = "Hostel Management System"