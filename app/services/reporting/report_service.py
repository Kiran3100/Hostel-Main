# app/services/reporting/report_service.py
"""
Report Service (Facade)

Provides a unified interface over multiple report services with
enhanced error handling, validation, and performance optimization.
"""

from __future__ import annotations

import logging
from typing import Dict, Any, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.schemas.common import DateRangeFilter
from app.schemas.analytics import (
    CustomReportRequest,
    CustomReportResult,
    FinancialReport,
)
from app.schemas.audit import AuditReport, ComplianceReport, SecurityAuditReport
from app.services.reporting.compliance_report_service import ComplianceReportService
from app.services.reporting.custom_report_service import CustomReportService
from app.services.reporting.financial_report_service import FinancialReportService
from app.services.reporting.operational_report_service import OperationalReportService
from app.core.exceptions import ValidationException
from app.utils.metrics import track_performance

logger = logging.getLogger(__name__)


class ReportService:
    """
    Facade service for all reporting operations.

    This service provides a unified interface to access all report types
    and delegates to specialized services for actual implementation.

    Responsibilities:
    - Expose simple methods for major report types
    - Coordinate between different reporting services
    - Provide unified error handling
    - Track metrics across all report types

    Attributes:
        financial_service: Service for financial reports
        operational_service: Service for operational reports
        compliance_service: Service for compliance/security reports
        custom_service: Service for custom reports
    """

    def __init__(
        self,
        financial_service: FinancialReportService,
        operational_service: OperationalReportService,
        compliance_service: ComplianceReportService,
        custom_service: CustomReportService,
    ) -> None:
        """
        Initialize the report service facade.

        Args:
            financial_service: Financial report service
            operational_service: Operational report service
            compliance_service: Compliance report service
            custom_service: Custom report service
        """
        if not all([
            financial_service,
            operational_service,
            compliance_service,
            custom_service,
        ]):
            raise ValueError("All report services are required")
        
        self.financial_service = financial_service
        self.operational_service = operational_service
        self.compliance_service = compliance_service
        self.custom_service = custom_service
        
        logger.info("ReportService facade initialized successfully")

    # -------------------------------------------------------------------------
    # Financial Reports
    # -------------------------------------------------------------------------

    @track_performance("get_financial_report")
    def get_financial_report(
        self,
        db: Session,
        hostel_id: UUID,
        period: DateRangeFilter,
        include_comparison: bool = True,
        include_ratios: bool = True,
        include_trends: bool = True,
    ) -> FinancialReport:
        """
        Generate comprehensive financial report for a hostel.

        Args:
            db: Database session
            hostel_id: ID of the hostel
            period: Date range for the report
            include_comparison: Whether to include period comparisons
            include_ratios: Whether to include financial ratios
            include_trends: Whether to include trend analysis

        Returns:
            FinancialReport: Comprehensive financial report

        Raises:
            ValidationException: If validation fails
        """
        logger.info(
            f"Generating financial report for hostel {hostel_id}, "
            f"period {period.start_date} to {period.end_date}"
        )
        
        try:
            return self.financial_service.get_financial_report(
                db=db,
                hostel_id=hostel_id,
                period=period,
                include_comparison=include_comparison,
                include_ratios=include_ratios,
                include_trends=include_trends,
            )
        except Exception as e:
            logger.error(f"Error generating financial report: {str(e)}")
            raise

    def get_profit_and_loss(
        self,
        db: Session,
        hostel_id: UUID,
        period: DateRangeFilter,
    ) -> Dict[str, Any]:
        """
        Generate Profit & Loss statement.

        Args:
            db: Database session
            hostel_id: ID of the hostel
            period: Date range for the report

        Returns:
            P&L report data
        """
        logger.info(f"Generating P&L report for hostel {hostel_id}")
        
        try:
            return self.financial_service.get_profit_and_loss(
                db=db,
                hostel_id=hostel_id,
                period=period,
            )
        except Exception as e:
            logger.error(f"Error generating P&L report: {str(e)}")
            raise

    def get_cashflow_summary(
        self,
        db: Session,
        hostel_id: UUID,
        period: DateRangeFilter,
    ) -> Dict[str, Any]:
        """
        Generate cashflow summary.

        Args:
            db: Database session
            hostel_id: ID of the hostel
            period: Date range for the report

        Returns:
            Cashflow summary data
        """
        logger.info(f"Generating cashflow summary for hostel {hostel_id}")
        
        try:
            return self.financial_service.get_cashflow_summary(
                db=db,
                hostel_id=hostel_id,
                period=period,
            )
        except Exception as e:
            logger.error(f"Error generating cashflow summary: {str(e)}")
            raise

    # -------------------------------------------------------------------------
    # Operational Reports
    # -------------------------------------------------------------------------

    @track_performance("get_operational_report")
    def get_operational_report(
        self,
        db: Session,
        hostel_id: UUID,
        period: DateRangeFilter,
        include_trends: bool = True,
        include_recommendations: bool = True,
    ) -> Dict[str, Any]:
        """
        Generate comprehensive operational report for a hostel.

        Args:
            db: Database session
            hostel_id: ID of the hostel
            period: Date range for the report
            include_trends: Whether to include trend analysis
            include_recommendations: Whether to include recommendations

        Returns:
            Dictionary containing operational metrics

        Raises:
            ValidationException: If validation fails
        """
        logger.info(
            f"Generating operational report for hostel {hostel_id}, "
            f"period {period.start_date} to {period.end_date}"
        )
        
        try:
            return self.operational_service.get_operational_report(
                db=db,
                hostel_id=hostel_id,
                period=period,
                include_trends=include_trends,
                include_recommendations=include_recommendations,
            )
        except Exception as e:
            logger.error(f"Error generating operational report: {str(e)}")
            raise

    def get_performance_summary(
        self,
        db: Session,
        hostel_id: UUID,
        period: DateRangeFilter,
    ) -> Dict[str, Any]:
        """
        Get quick performance summary without full report.

        Args:
            db: Database session
            hostel_id: ID of the hostel
            period: Date range for the summary

        Returns:
            Performance summary dictionary
        """
        logger.info(f"Generating performance summary for hostel {hostel_id}")
        
        try:
            return self.operational_service.get_performance_summary(
                db=db,
                hostel_id=hostel_id,
                period=period,
            )
        except Exception as e:
            logger.error(f"Error generating performance summary: {str(e)}")
            raise

    # -------------------------------------------------------------------------
    # Compliance & Security Reports
    # -------------------------------------------------------------------------

    @track_performance("get_compliance_report")
    def get_compliance_report(
        self,
        db: Session,
        period: DateRangeFilter,
        tenant_id: Optional[UUID] = None,
    ) -> ComplianceReport:
        """
        Generate compliance report for GDPR, SOC2, etc.

        Args:
            db: Database session
            period: Date range for the report
            tenant_id: Optional tenant ID

        Returns:
            ComplianceReport: Compliance metrics and violations

        Raises:
            ValidationException: If validation fails
        """
        logger.info(
            f"Generating compliance report for period {period.start_date} to "
            f"{period.end_date}, tenant_id={tenant_id}"
        )
        
        try:
            return self.compliance_service.generate_compliance_report(
                db=db,
                period=period,
                tenant_id=tenant_id,
            )
        except Exception as e:
            logger.error(f"Error generating compliance report: {str(e)}")
            raise

    @track_performance("get_security_audit_report")
    def get_security_audit_report(
        self,
        db: Session,
        period: DateRangeFilter,
        tenant_id: Optional[UUID] = None,
    ) -> SecurityAuditReport:
        """
        Generate security audit report.

        Args:
            db: Database session
            period: Date range for the report
            tenant_id: Optional tenant ID

        Returns:
            SecurityAuditReport: Security events and metrics

        Raises:
            ValidationException: If validation fails
        """
        logger.info(
            f"Generating security audit report for period {period.start_date} to "
            f"{period.end_date}, tenant_id={tenant_id}"
        )
        
        try:
            return self.compliance_service.generate_security_audit_report(
                db=db,
                period=period,
                tenant_id=tenant_id,
            )
        except Exception as e:
            logger.error(f"Error generating security audit report: {str(e)}")
            raise

    @track_performance("get_full_audit_report")
    def get_full_audit_report(
        self,
        db: Session,
        period: DateRangeFilter,
        tenant_id: Optional[UUID] = None,
        include_trends: bool = True,
        include_recommendations: bool = True,
    ) -> AuditReport:
        """
        Generate comprehensive audit report (compliance + security).

        Args:
            db: Database session
            period: Date range for the report
            tenant_id: Optional tenant ID
            include_trends: Whether to include trend analysis
            include_recommendations: Whether to include recommendations

        Returns:
            AuditReport: Complete audit report

        Raises:
            ValidationException: If validation fails
        """
        logger.info(
            f"Generating full audit report for period {period.start_date} to "
            f"{period.end_date}, tenant_id={tenant_id}"
        )
        
        try:
            return self.compliance_service.generate_full_audit_report(
                db=db,
                period=period,
                tenant_id=tenant_id,
                include_trends=include_trends,
                include_recommendations=include_recommendations,
            )
        except Exception as e:
            logger.error(f"Error generating full audit report: {str(e)}")
            raise

    # -------------------------------------------------------------------------
    # Custom Reports
    # -------------------------------------------------------------------------

    @track_performance("run_custom_report")
    def run_custom_report(
        self,
        db: Session,
        request: CustomReportRequest,
        owner_id: Optional[UUID] = None,
        use_cache: bool = True,
    ) -> CustomReportResult:
        """
        Execute a custom report from request definition.

        Args:
            db: Database session
            request: Custom report request
            owner_id: Optional owner ID
            use_cache: Whether to use cached results

        Returns:
            CustomReportResult: Report execution result

        Raises:
            ValidationException: If validation or execution fails
        """
        logger.info(f"Running custom report '{request.name}', owner={owner_id}")
        
        try:
            return self.custom_service.run_report(
                db=db,
                request=request,
                owner_id=owner_id,
                use_cache=use_cache,
            )
        except Exception as e:
            logger.error(f"Error running custom report: {str(e)}")
            raise

    def run_saved_report(
        self,
        db: Session,
        definition_id: UUID,
        parameters: Optional[Dict[str, Any]] = None,
        use_cache: bool = True,
        owner_id: Optional[UUID] = None,
    ) -> CustomReportResult:
        """
        Execute a saved custom report definition.

        Args:
            db: Database session
            definition_id: ID of saved report definition
            parameters: Optional runtime parameters
            use_cache: Whether to use cached results
            owner_id: Optional owner ID for authorization

        Returns:
            CustomReportResult: Report execution result

        Raises:
            ValidationException: If execution fails
        """
        logger.info(f"Running saved report {definition_id}")
        
        try:
            return self.custom_service.run_saved_report(
                db=db,
                definition_id=definition_id,
                parameters=parameters,
                use_cache=use_cache,
                owner_id=owner_id,
            )
        except Exception as e:
            logger.error(f"Error running saved report: {str(e)}")
            raise

    # -------------------------------------------------------------------------
    # Unified Report Dashboard
    # -------------------------------------------------------------------------

    @track_performance("get_unified_dashboard")
    def get_unified_dashboard(
        self,
        db: Session,
        hostel_id: UUID,
        period: DateRangeFilter,
    ) -> Dict[str, Any]:
        """
        Generate unified dashboard with all report types.

        This method aggregates financial, operational, and compliance
        metrics into a single dashboard view.

        Args:
            db: Database session
            hostel_id: ID of the hostel
            period: Date range for the dashboard

        Returns:
            Dictionary containing all dashboard metrics

        Raises:
            ValidationException: If validation fails
        """
        logger.info(
            f"Generating unified dashboard for hostel {hostel_id}, "
            f"period {period.start_date} to {period.end_date}"
        )
        
        try:
            dashboard = {
                "hostel_id": str(hostel_id),
                "period": {
                    "start_date": period.start_date.isoformat(),
                    "end_date": period.end_date.isoformat(),
                },
                "financial": None,
                "operational": None,
                "performance_summary": None,
            }
            
            # Fetch financial report
            try:
                dashboard["financial"] = self.get_financial_report(
                    db=db,
                    hostel_id=hostel_id,
                    period=period,
                ).model_dump()
            except Exception as e:
                logger.warning(f"Failed to load financial data: {str(e)}")
            
            # Fetch operational report
            try:
                dashboard["operational"] = self.get_operational_report(
                    db=db,
                    hostel_id=hostel_id,
                    period=period,
                )
            except Exception as e:
                logger.warning(f"Failed to load operational data: {str(e)}")
            
            # Fetch performance summary
            try:
                dashboard["performance_summary"] = self.get_performance_summary(
                    db=db,
                    hostel_id=hostel_id,
                    period=period,
                )
            except Exception as e:
                logger.warning(f"Failed to load performance summary: {str(e)}")
            
            logger.info(f"Successfully generated unified dashboard for hostel {hostel_id}")
            
            return dashboard
            
        except Exception as e:
            logger.error(f"Error generating unified dashboard: {str(e)}")
            raise ValidationException(f"Failed to generate unified dashboard: {str(e)}")