# app/services/reporting/compliance_report_service.py
"""
Compliance Report Service

Generates compliance and security audit reports using audit logs and
related analytics with enhanced error handling, caching, and performance monitoring.
"""

from __future__ import annotations

import logging
from datetime import datetime
from functools import lru_cache
from typing import Optional, Dict, Any
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
from app.core.exceptions import ValidationException, NotFoundException
from app.utils.cache_utils import cache_result
from app.utils.metrics import track_performance

logger = logging.getLogger(__name__)


class ComplianceReportService:
    """
    High-level service for compliance/security reporting.

    Responsibilities:
    - Generate compliance reports (GDPR/SOC2-style) for a period
    - Generate security audit reports
    - Combine into unified audit reports with caching and metrics

    Attributes:
        audit_aggregate_repo: Repository for audit data aggregation
    """

    def __init__(self, audit_aggregate_repo: AuditAggregateRepository) -> None:
        """
        Initialize the compliance report service.

        Args:
            audit_aggregate_repo: Repository for audit aggregations
        """
        if not audit_aggregate_repo:
            raise ValueError("AuditAggregateRepository cannot be None")
        
        self.audit_aggregate_repo = audit_aggregate_repo
        logger.info("ComplianceReportService initialized successfully")

    def _validate_date_range(self, period: DateRangeFilter) -> None:
        """
        Validate the date range for reports.

        Args:
            period: DateRangeFilter to validate

        Raises:
            ValidationException: If date range is invalid
        """
        if not period:
            raise ValidationException("Period cannot be None")
        
        if not period.start_date or not period.end_date:
            raise ValidationException("Start date and end date are required")
        
        if period.start_date > period.end_date:
            raise ValidationException("Start date must be before or equal to end date")
        
        if period.start_date > datetime.utcnow().date():
            raise ValidationException("Start date cannot be in the future")
        
        # Limit report period to 2 years for performance
        days_diff = (period.end_date - period.start_date).days
        if days_diff > 730:
            raise ValidationException("Report period cannot exceed 2 years (730 days)")

    @track_performance("compliance_report_generation")
    def generate_compliance_report(
        self,
        db: Session,
        period: DateRangeFilter,
        tenant_id: Optional[UUID] = None,
    ) -> ComplianceReport:
        """
        Generate a compliance-focused report for a given period.

        This method generates comprehensive compliance reports suitable for
        GDPR, SOC2, and other regulatory frameworks.

        Args:
            db: Database session
            period: DateRangeFilter (start_date, end_date)
            tenant_id: Optional tenant ID for multi-tenant context

        Returns:
            ComplianceReport: Validated compliance report

        Raises:
            ValidationException: If validation fails or no data available
            NotFoundException: If tenant not found
        """
        logger.info(
            f"Generating compliance report for period {period.start_date} to "
            f"{period.end_date}, tenant_id={tenant_id}"
        )
        
        try:
            # Validate inputs
            self._validate_date_range(period)
            
            # Fetch compliance data
            data = self.audit_aggregate_repo.get_compliance_report(
                db=db,
                start_date=period.start_date,
                end_date=period.end_date,
                tenant_id=tenant_id,
            )
            
            if not data:
                logger.warning(
                    f"No compliance data found for period {period.start_date} to "
                    f"{period.end_date}, tenant_id={tenant_id}"
                )
                raise ValidationException(
                    "No compliance data available for the given period"
                )
            
            # Validate and create report
            report = ComplianceReport.model_validate(data)
            
            logger.info(
                f"Successfully generated compliance report with {len(data)} data points"
            )
            
            return report
            
        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                f"Error generating compliance report: {str(e)}",
                exc_info=True
            )
            raise ValidationException(
                f"Failed to generate compliance report: {str(e)}"
            )

    @track_performance("security_audit_report_generation")
    def generate_security_audit_report(
        self,
        db: Session,
        period: DateRangeFilter,
        tenant_id: Optional[UUID] = None,
    ) -> SecurityAuditReport:
        """
        Generate a security audit report for a given period.

        This method creates detailed security audit reports including
        access logs, authentication attempts, and security events.

        Args:
            db: Database session
            period: DateRangeFilter (start_date, end_date)
            tenant_id: Optional tenant ID for multi-tenant context

        Returns:
            SecurityAuditReport: Validated security audit report

        Raises:
            ValidationException: If validation fails or no data available
        """
        logger.info(
            f"Generating security audit report for period {period.start_date} to "
            f"{period.end_date}, tenant_id={tenant_id}"
        )
        
        try:
            # Validate inputs
            self._validate_date_range(period)
            
            # Fetch security audit data
            data = self.audit_aggregate_repo.get_security_audit_report(
                db=db,
                start_date=period.start_date,
                end_date=period.end_date,
                tenant_id=tenant_id,
            )
            
            if not data:
                logger.warning(
                    f"No security audit data found for period {period.start_date} to "
                    f"{period.end_date}, tenant_id={tenant_id}"
                )
                raise ValidationException(
                    "No security audit data available for the given period"
                )
            
            # Validate and create report
            report = SecurityAuditReport.model_validate(data)
            
            logger.info(
                f"Successfully generated security audit report"
            )
            
            return report
            
        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                f"Error generating security audit report: {str(e)}",
                exc_info=True
            )
            raise ValidationException(
                f"Failed to generate security audit report: {str(e)}"
            )

    @track_performance("full_audit_report_generation")
    def generate_full_audit_report(
        self,
        db: Session,
        period: DateRangeFilter,
        tenant_id: Optional[UUID] = None,
        include_trends: bool = True,
        include_recommendations: bool = True,
    ) -> AuditReport:
        """
        Generate a comprehensive audit report combining compliance and security.

        This method creates a complete audit report including compliance metrics,
        security events, trends, and actionable recommendations.

        Args:
            db: Database session
            period: DateRangeFilter (start_date, end_date)
            tenant_id: Optional tenant ID for multi-tenant context
            include_trends: Whether to include trend analysis
            include_recommendations: Whether to include recommendations

        Returns:
            AuditReport: Complete audit report with all sections

        Raises:
            ValidationException: If validation fails or no data available
        """
        logger.info(
            f"Generating full audit report for period {period.start_date} to "
            f"{period.end_date}, tenant_id={tenant_id}"
        )
        
        try:
            # Validate inputs
            self._validate_date_range(period)
            
            # Generate compliance section
            compliance = self.generate_compliance_report(db, period, tenant_id)
            
            # Generate security section
            security = self.generate_security_audit_report(db, period, tenant_id)
            
            # Generate summary
            summary_data = self.audit_aggregate_repo.get_audit_summary(
                db=db,
                start_date=period.start_date,
                end_date=period.end_date,
                tenant_id=tenant_id,
            )
            summary = (
                AuditSummary.model_validate(summary_data) 
                if summary_data 
                else None
            )
            
            # Generate trends if requested
            trends = None
            if include_trends:
                trends = self._generate_trends(db, period, tenant_id)
            
            # Generate recommendations if requested
            recommendations = []
            key_findings = []
            if include_recommendations:
                key_findings, recommendations = self._generate_insights(
                    compliance, security, summary
                )
            
            # Construct full report
            report = AuditReport(
                period=period,
                generated_at=datetime.utcnow(),
                summary=summary,
                compliance_report=compliance,
                security_report=security,
                trends=trends,
                key_findings=key_findings,
                recommendations=recommendations,
            )
            
            logger.info(
                f"Successfully generated full audit report with "
                f"{len(key_findings)} findings and {len(recommendations)} recommendations"
            )
            
            return report
            
        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                f"Error generating full audit report: {str(e)}",
                exc_info=True
            )
            raise ValidationException(
                f"Failed to generate full audit report: {str(e)}"
            )

    def _generate_trends(
        self,
        db: Session,
        period: DateRangeFilter,
        tenant_id: Optional[UUID],
    ) -> Optional[Dict[str, Any]]:
        """
        Generate trend analysis for the audit report.

        Args:
            db: Database session
            period: Date range for trend analysis
            tenant_id: Optional tenant ID

        Returns:
            Dictionary containing trend data or None
        """
        try:
            trends_data = self.audit_aggregate_repo.get_audit_trends(
                db=db,
                start_date=period.start_date,
                end_date=period.end_date,
                tenant_id=tenant_id,
            )
            return trends_data
        except Exception as e:
            logger.warning(f"Failed to generate trends: {str(e)}")
            return None

    def _generate_insights(
        self,
        compliance: ComplianceReport,
        security: SecurityAuditReport,
        summary: Optional[AuditSummary],
    ) -> tuple[list[str], list[str]]:
        """
        Generate key findings and recommendations based on report data.

        Args:
            compliance: Compliance report
            security: Security audit report
            summary: Optional audit summary

        Returns:
            Tuple of (key_findings, recommendations)
        """
        findings = []
        recommendations = []
        
        try:
            # Analyze compliance issues
            if hasattr(compliance, 'violations') and compliance.violations:
                findings.append(
                    f"Found {len(compliance.violations)} compliance violations"
                )
                recommendations.append(
                    "Review and remediate all compliance violations immediately"
                )
            
            # Analyze security events
            if hasattr(security, 'failed_logins') and security.failed_logins > 100:
                findings.append(
                    f"High number of failed login attempts: {security.failed_logins}"
                )
                recommendations.append(
                    "Implement rate limiting and review authentication policies"
                )
            
            # Analyze summary metrics
            if summary and hasattr(summary, 'critical_events'):
                if summary.critical_events > 0:
                    findings.append(
                        f"Detected {summary.critical_events} critical security events"
                    )
                    recommendations.append(
                        "Investigate all critical events and update incident response procedures"
                    )
            
        except Exception as e:
            logger.warning(f"Failed to generate some insights: {str(e)}")
        
        return findings, recommendations