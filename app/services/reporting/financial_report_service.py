# app/services/reporting/financial_report_service.py
"""
Financial Report Service

Composes financial analytics into domain reports (P&L, cashflow, combined)
with enhanced validation, error handling, and performance optimization.
"""

from __future__ import annotations

import logging
from uuid import UUID
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.schemas.common import DateRangeFilter
from app.schemas.analytics import (
    ProfitAndLossReport,
    CashflowSummary,
    FinancialReport,
)
from app.repositories.analytics import FinancialAnalyticsRepository
from app.core1.exceptions import ValidationException, NotFoundException
from app.utils.metrics import track_performance
from app.utils.cache_utils import cache_result

logger = logging.getLogger(__name__)


class FinancialReportService:
    """
    High-level service for financial reports.

    Responsibilities:
    - Generate Profit & Loss statements with validation
    - Generate cashflow summaries
    - Generate comprehensive financial reports (P&L + cashflow + tax + ratios)
    - Provide comparative analysis and trends

    Attributes:
        financial_analytics_repo: Repository for financial analytics
        enable_caching: Whether to enable result caching
    """

    def __init__(
        self,
        financial_analytics_repo: FinancialAnalyticsRepository,
        enable_caching: bool = True,
    ) -> None:
        """
        Initialize the financial report service.

        Args:
            financial_analytics_repo: Repository for financial analytics
            enable_caching: Whether to enable caching (default: True)
        """
        if not financial_analytics_repo:
            raise ValueError("FinancialAnalyticsRepository cannot be None")
        
        self.financial_analytics_repo = financial_analytics_repo
        self.enable_caching = enable_caching
        
        logger.info(
            f"FinancialReportService initialized (caching={enable_caching})"
        )

    def _validate_date_range(self, period: DateRangeFilter) -> None:
        """
        Validate the date range for financial reports.

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
        
        if period.end_date > datetime.utcnow().date():
            raise ValidationException("End date cannot be in the future")
        
        # Financial reports should not exceed 5 years for performance
        days_diff = (period.end_date - period.start_date).days
        if days_diff > 1825:  # ~5 years
            raise ValidationException(
                "Financial report period cannot exceed 5 years (1825 days)"
            )

    def _validate_hostel_id(self, hostel_id: UUID) -> None:
        """
        Validate hostel ID.

        Args:
            hostel_id: Hostel UUID to validate

        Raises:
            ValidationException: If hostel_id is invalid
        """
        if not hostel_id:
            raise ValidationException("Hostel ID is required")

    @track_performance("profit_and_loss_report")
    @cache_result(ttl=3600, key_prefix="pl_report")
    def get_profit_and_loss(
        self,
        db: Session,
        hostel_id: UUID,
        period: DateRangeFilter,
        include_breakdown: bool = True,
    ) -> ProfitAndLossReport:
        """
        Generate a comprehensive Profit & Loss report for a hostel and period.

        This method generates detailed P&L statements including revenue,
        expenses, and net profit calculations with optional breakdowns.

        Args:
            db: Database session
            hostel_id: ID of the hostel
            period: DateRangeFilter (start_date, end_date)
            include_breakdown: Whether to include detailed breakdowns

        Returns:
            ProfitAndLossReport: Validated P&L report

        Raises:
            ValidationException: If validation fails or no data available
            NotFoundException: If hostel not found
        """
        logger.info(
            f"Generating P&L report for hostel {hostel_id}, "
            f"period {period.start_date} to {period.end_date}"
        )
        
        try:
            # Validate inputs
            self._validate_hostel_id(hostel_id)
            self._validate_date_range(period)
            
            # Build P&L report
            data = self.financial_analytics_repo.build_profit_and_loss(
                db=db,
                hostel_id=hostel_id,
                start_date=period.start_date,
                end_date=period.end_date,
                include_breakdown=include_breakdown,
            )
            
            if not data:
                logger.warning(
                    f"No P&L data found for hostel {hostel_id}, "
                    f"period {period.start_date} to {period.end_date}"
                )
                raise ValidationException(
                    "No P&L data available for this period"
                )
            
            # Validate and create report
            report = ProfitAndLossReport.model_validate(data)
            
            # Log key metrics
            if hasattr(report, 'net_profit'):
                logger.info(
                    f"P&L report generated - Net Profit: {report.net_profit}"
                )
            
            return report
            
        except (ValidationException, NotFoundException):
            raise
        except SQLAlchemyError as e:
            logger.error(f"Database error generating P&L report: {str(e)}")
            raise ValidationException(f"Failed to generate P&L report: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error generating P&L report: {str(e)}", exc_info=True)
            raise ValidationException(f"P&L report generation failed: {str(e)}")

    @track_performance("cashflow_summary")
    @cache_result(ttl=3600, key_prefix="cashflow")
    def get_cashflow_summary(
        self,
        db: Session,
        hostel_id: UUID,
        period: DateRangeFilter,
        include_projections: bool = False,
    ) -> CashflowSummary:
        """
        Generate a cashflow summary for a hostel and period.

        This method creates detailed cashflow analysis including operating,
        investing, and financing activities.

        Args:
            db: Database session
            hostel_id: ID of the hostel
            period: DateRangeFilter (start_date, end_date)
            include_projections: Whether to include future projections

        Returns:
            CashflowSummary: Validated cashflow summary

        Raises:
            ValidationException: If validation fails or no data available
            NotFoundException: If hostel not found
        """
        logger.info(
            f"Generating cashflow summary for hostel {hostel_id}, "
            f"period {period.start_date} to {period.end_date}"
        )
        
        try:
            # Validate inputs
            self._validate_hostel_id(hostel_id)
            self._validate_date_range(period)
            
            # Build cashflow summary
            data = self.financial_analytics_repo.build_cashflow_summary(
                db=db,
                hostel_id=hostel_id,
                start_date=period.start_date,
                end_date=period.end_date,
                include_projections=include_projections,
            )
            
            if not data:
                logger.warning(
                    f"No cashflow data found for hostel {hostel_id}, "
                    f"period {period.start_date} to {period.end_date}"
                )
                raise ValidationException(
                    "No cashflow data available for this period"
                )
            
            # Validate and create summary
            summary = CashflowSummary.model_validate(data)
            
            # Log key metrics
            if hasattr(summary, 'net_cashflow'):
                logger.info(
                    f"Cashflow summary generated - Net Cashflow: {summary.net_cashflow}"
                )
            
            return summary
            
        except (ValidationException, NotFoundException):
            raise
        except SQLAlchemyError as e:
            logger.error(f"Database error generating cashflow summary: {str(e)}")
            raise ValidationException(f"Failed to generate cashflow summary: {str(e)}")
        except Exception as e:
            logger.error(
                f"Unexpected error generating cashflow summary: {str(e)}",
                exc_info=True
            )
            raise ValidationException(f"Cashflow summary generation failed: {str(e)}")

    @track_performance("financial_report")
    @cache_result(ttl=3600, key_prefix="financial_report")
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
        Generate comprehensive financial report (P&L + cashflow + tax + ratios).

        This method creates a complete financial report including all major
        financial statements, ratios, and comparative analysis.

        Args:
            db: Database session
            hostel_id: ID of the hostel
            period: DateRangeFilter (start_date, end_date)
            include_comparison: Whether to include period-over-period comparison
            include_ratios: Whether to include financial ratios
            include_trends: Whether to include trend analysis

        Returns:
            FinancialReport: Comprehensive financial report

        Raises:
            ValidationException: If validation fails or no data available
            NotFoundException: If hostel not found
        """
        logger.info(
            f"Generating comprehensive financial report for hostel {hostel_id}, "
            f"period {period.start_date} to {period.end_date}"
        )
        
        try:
            # Validate inputs
            self._validate_hostel_id(hostel_id)
            self._validate_date_range(period)
            
            # Build financial report
            data = self.financial_analytics_repo.build_financial_report(
                db=db,
                hostel_id=hostel_id,
                start_date=period.start_date,
                end_date=period.end_date,
                include_comparison=include_comparison,
                include_ratios=include_ratios,
                include_trends=include_trends,
            )
            
            if not data:
                logger.warning(
                    f"No financial data found for hostel {hostel_id}, "
                    f"period {period.start_date} to {period.end_date}"
                )
                raise ValidationException(
                    "No financial report available for this period"
                )
            
            # Validate and create report
            report = FinancialReport.model_validate(data)
            
            # Log summary
            logger.info(
                f"Financial report generated successfully for hostel {hostel_id}"
            )
            
            return report
            
        except (ValidationException, NotFoundException):
            raise
        except SQLAlchemyError as e:
            logger.error(f"Database error generating financial report: {str(e)}")
            raise ValidationException(f"Failed to generate financial report: {str(e)}")
        except Exception as e:
            logger.error(
                f"Unexpected error generating financial report: {str(e)}",
                exc_info=True
            )
            raise ValidationException(f"Financial report generation failed: {str(e)}")

    def get_comparative_analysis(
        self,
        db: Session,
        hostel_id: UUID,
        current_period: DateRangeFilter,
        comparison_period: DateRangeFilter,
    ) -> Dict[str, Any]:
        """
        Generate comparative financial analysis between two periods.

        Args:
            db: Database session
            hostel_id: ID of the hostel
            current_period: Current period date range
            comparison_period: Comparison period date range

        Returns:
            Dictionary containing comparative analysis

        Raises:
            ValidationException: If validation fails
        """
        logger.info(
            f"Generating comparative analysis for hostel {hostel_id}"
        )
        
        try:
            # Validate inputs
            self._validate_hostel_id(hostel_id)
            self._validate_date_range(current_period)
            self._validate_date_range(comparison_period)
            
            # Generate reports for both periods
            current_report = self.get_financial_report(
                db=db,
                hostel_id=hostel_id,
                period=current_period,
                include_comparison=False,
            )
            
            comparison_report = self.get_financial_report(
                db=db,
                hostel_id=hostel_id,
                period=comparison_period,
                include_comparison=False,
            )
            
            # Calculate variances and growth rates
            analysis = self._calculate_comparative_metrics(
                current_report,
                comparison_report,
            )
            
            logger.info("Comparative analysis generated successfully")
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error generating comparative analysis: {str(e)}")
            raise ValidationException(f"Comparative analysis failed: {str(e)}")

    def _calculate_comparative_metrics(
        self,
        current: FinancialReport,
        comparison: FinancialReport,
    ) -> Dict[str, Any]:
        """
        Calculate comparative metrics between two financial reports.

        Args:
            current: Current period report
            comparison: Comparison period report

        Returns:
            Dictionary containing variance and growth metrics
        """
        metrics = {
            "current_period": current.model_dump(),
            "comparison_period": comparison.model_dump(),
            "variances": {},
            "growth_rates": {},
        }
        
        try:
            # Calculate revenue variance and growth
            if hasattr(current, 'total_revenue') and hasattr(comparison, 'total_revenue'):
                revenue_var = current.total_revenue - comparison.total_revenue
                revenue_growth = (
                    (revenue_var / comparison.total_revenue * 100)
                    if comparison.total_revenue != 0
                    else 0
                )
                
                metrics["variances"]["revenue"] = revenue_var
                metrics["growth_rates"]["revenue"] = revenue_growth
            
            # Calculate profit variance and growth
            if hasattr(current, 'net_profit') and hasattr(comparison, 'net_profit'):
                profit_var = current.net_profit - comparison.net_profit
                profit_growth = (
                    (profit_var / comparison.net_profit * 100)
                    if comparison.net_profit != 0
                    else 0
                )
                
                metrics["variances"]["profit"] = profit_var
                metrics["growth_rates"]["profit"] = profit_growth
            
        except Exception as e:
            logger.warning(f"Error calculating some comparative metrics: {str(e)}")
        
        return metrics