# app/services/reporting/financial_report_service.py
"""
Financial Report Service

Composes financial analytics into domain reports (P&L, cashflow, combined).
"""

from __future__ import annotations

from uuid import UUID
from typing import Optional

from sqlalchemy.orm import Session

from app.schemas.common import DateRangeFilter
from app.schemas.analytics import (
    ProfitAndLossReport,
    CashflowSummary,
    FinancialReport,
)
from app.repositories.analytics import FinancialAnalyticsRepository
from app.core.exceptions import ValidationException


class FinancialReportService:
    """
    High-level service for financial reports.

    Responsibilities:
    - Generate Profit & Loss statements
    - Generate cashflow summaries
    - Generate full financial reports (P&L + cashflow + tax)
    """

    def __init__(
        self,
        financial_analytics_repo: FinancialAnalyticsRepository,
    ) -> None:
        self.financial_analytics_repo = financial_analytics_repo

    def get_profit_and_loss(
        self,
        db: Session,
        hostel_id: UUID,
        period: DateRangeFilter,
    ) -> ProfitAndLossReport:
        """
        Generate a P&L report for a hostel and period.
        """
        data = self.financial_analytics_repo.build_profit_and_loss(
            db=db,
            hostel_id=hostel_id,
            start_date=period.start_date,
            end_date=period.end_date,
        )
        if not data:
            raise ValidationException("No P&L data available for this period")
        return ProfitAndLossReport.model_validate(data)

    def get_cashflow_summary(
        self,
        db: Session,
        hostel_id: UUID,
        period: DateRangeFilter,
    ) -> CashflowSummary:
        """
        Generate a cashflow summary for a hostel and period.
        """
        data = self.financial_analytics_repo.build_cashflow_summary(
            db=db,
            hostel_id=hostel_id,
            start_date=period.start_date,
            end_date=period.end_date,
        )
        if not data:
            raise ValidationException("No cashflow data available for this period")
        return CashflowSummary.model_validate(data)

    def get_financial_report(
        self,
        db: Session,
        hostel_id: UUID,
        period: DateRangeFilter,
        include_comparison: bool = True,
    ) -> FinancialReport:
        """
        Generate combined financial report (P&L + cashflow + tax + ratios).
        """
        data = self.financial_analytics_repo.build_financial_report(
            db=db,
            hostel_id=hostel_id,
            start_date=period.start_date,
            end_date=period.end_date,
            include_comparison=include_comparison,
        )
        if not data:
            raise ValidationException("No financial report available for this period")
        return FinancialReport.model_validate(data)