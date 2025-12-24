# app/services/reporting/report_service.py
"""
Report Service (Facade)

Provides a unified interface over multiple report services:
- Financial
- Operational
- Compliance/Security
- Custom
"""

from __future__ import annotations

from typing import Dict, Any, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.schemas.common import DateRangeFilter
from app.schemas.analytics import (
    CustomReportRequest,
    CustomReportResult,
)
from app.schemas.audit import AuditReport, ComplianceReport, SecurityAuditReport
from app.schemas.analytics import FinancialReport
from app.services.reporting.compliance_report_service import ComplianceReportService
from app.services.reporting.custom_report_service import CustomReportService
from app.services.reporting.financial_report_service import FinancialReportService
from app.services.reporting.operational_report_service import OperationalReportService


class ReportService:
    """
    Facade service for reporting.

    Responsibilities:
    - Expose simple methods for major report types:
      - financial
      - operational
      - compliance/security
      - custom
    - Internally delegates to specialized services.
    """

    def __init__(
        self,
        financial_service: FinancialReportService,
        operational_service: OperationalReportService,
        compliance_service: ComplianceReportService,
        custom_service: CustomReportService,
    ) -> None:
        self.financial_service = financial_service
        self.operational_service = operational_service
        self.compliance_service = compliance_service
        self.custom_service = custom_service

    # -------------------------------------------------------------------------
    # Financial
    # -------------------------------------------------------------------------

    def get_financial_report(
        self,
        db: Session,
        hostel_id: UUID,
        period: DateRangeFilter,
        include_comparison: bool = True,
    ) -> FinancialReport:
        return self.financial_service.get_financial_report(
            db=db,
            hostel_id=hostel_id,
            period=period,
            include_comparison=include_comparison,
        )

    # -------------------------------------------------------------------------
    # Operational
    # -------------------------------------------------------------------------

    def get_operational_report(
        self,
        db: Session,
        hostel_id: UUID,
        period: DateRangeFilter,
    ) -> Dict[str, Any]:
        return self.operational_service.get_operational_report(
            db=db,
            hostel_id=hostel_id,
            period=period,
        )

    # -------------------------------------------------------------------------
    # Compliance / Security
    # -------------------------------------------------------------------------

    def get_compliance_report(
        self,
        db: Session,
        period: DateRangeFilter,
        tenant_id: Optional[UUID] = None,
    ) -> ComplianceReport:
        return self.compliance_service.generate_compliance_report(
            db=db,
            period=period,
            tenant_id=tenant_id,
        )

    def get_security_audit_report(
        self,
        db: Session,
        period: DateRangeFilter,
        tenant_id: Optional[UUID] = None,
    ) -> SecurityAuditReport:
        return self.compliance_service.generate_security_audit_report(
            db=db,
            period=period,
            tenant_id=tenant_id,
        )

    def get_full_audit_report(
        self,
        db: Session,
        period: DateRangeFilter,
        tenant_id: Optional[UUID] = None,
    ) -> AuditReport:
        return self.compliance_service.generate_full_audit_report(
            db=db,
            period=period,
            tenant_id=tenant_id,
        )

    # -------------------------------------------------------------------------
    # Custom
    # -------------------------------------------------------------------------

    def run_custom_report(
        self,
        db: Session,
        request: CustomReportRequest,
        owner_id: Optional[UUID] = None,
        use_cache: bool = True,
    ) -> CustomReportResult:
        return self.custom_service.run_report(
            db=db,
            request=request,
            owner_id=owner_id,
            use_cache=use_cache,
        )