# app/services/reporting/compliance_report_service.py
"""
Compliance Report Service

Generates compliance and security audit reports using audit logs and
related analytics.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.schemas.common import DateRangeFilter
from app.schemas.audit import (
    ComplianceReport,
    SecurityAuditReport,
    AuditReport,
    AuditSummary,
)
from app.repositories.audit import AuditAggregateRepository
from app.core.exceptions import ValidationException


class ComplianceReportService:
    """
    High-level service for compliance/security reporting.

    Responsibilities:
    - Generate compliance reports (GDPR/SOC2-style) for a period
    - Generate security audit reports
    - Optionally combine into a unified audit report
    """

    def __init__(
        self,
        audit_aggregate_repo: AuditAggregateRepository,
    ) -> None:
        self.audit_aggregate_repo = audit_aggregate_repo

    def generate_compliance_report(
        self,
        db: Session,
        period: DateRangeFilter,
        tenant_id: Optional[UUID] = None,
    ) -> ComplianceReport:
        """
        Generate a compliance-focused report for a given period.

        Args:
            db: DB session
            period: DateRangeFilter (start_date, end_date)
            tenant_id: Optional tenant for multi-tenant context

        Returns:
            ComplianceReport
        """
        data = self.audit_aggregate_repo.get_compliance_report(
            db=db,
            start_date=period.start_date,
            end_date=period.end_date,
            tenant_id=tenant_id,
        )
        if not data:
            raise ValidationException("No compliance data available for the given period")

        return ComplianceReport.model_validate(data)

    def generate_security_audit_report(
        self,
        db: Session,
        period: DateRangeFilter,
        tenant_id: Optional[UUID] = None,
    ) -> SecurityAuditReport:
        """
        Generate a security audit report for a given period.
        """
        data = self.audit_aggregate_repo.get_security_audit_report(
            db=db,
            start_date=period.start_date,
            end_date=period.end_date,
            tenant_id=tenant_id,
        )
        if not data:
            raise ValidationException("No security audit data available for the given period")

        return SecurityAuditReport.model_validate(data)

    def generate_full_audit_report(
        self,
        db: Session,
        period: DateRangeFilter,
        tenant_id: Optional[UUID] = None,
    ) -> AuditReport:
        """
        Generate a full audit report, combining compliance and security sections.
        """
        compliance = self.generate_compliance_report(db, period, tenant_id)
        security = self.generate_security_audit_report(db, period, tenant_id)

        summary_data = self.audit_aggregate_repo.get_audit_summary(
            db=db,
            start_date=period.start_date,
            end_date=period.end_date,
            tenant_id=tenant_id,
        )
        summary = AuditSummary.model_validate(summary_data) if summary_data else None

        return AuditReport(
            period=period,
            generated_at=datetime.utcnow(),
            summary=summary,
            compliance_report=compliance,
            security_report=security,
            trends=None,
            key_findings=[],
            recommendations=[],
        )