# app/services/reporting/financial_reporting_service.py
from __future__ import annotations

from typing import Callable, Dict, Any, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.schemas.common.filters import DateRangeFilter
from app.schemas.payment.payment_filters import PaymentReportRequest
from app.schemas.analytics.financial_analytics import FinancialReport
from app.services.common import UnitOfWork
from app.services.payment import PaymentReportingService
from app.services.analytics import FinancialAnalyticsService


class FinancialReportingService:
    """
    Financial reporting facade.

    - Payment volume/amount reports (grouped by day/week/month/type/method)
      via PaymentReportingService.
    - Higher-level FinancialReport (P&L, cashflow, ratios) via
      FinancialAnalyticsService.
    """

    def __init__(
        self,
        session_factory: Callable[[], Session],
    ) -> None:
        self._session_factory = session_factory
        # Underlying services created on demand using the same session_factory
        self._payment_reporting = PaymentReportingService(session_factory)
        self._financial_analytics = FinancialAnalyticsService(session_factory)

    # ------------------------------------------------------------------ #
    # Payment-based reports
    # ------------------------------------------------------------------ #
    def build_payment_report(self, req: PaymentReportRequest) -> Dict[str, Any]:
        """
        Delegate to PaymentReportingService.build_report.
        """
        return self._payment_reporting.build_report(req)

    # ------------------------------------------------------------------ #
    # Financial analytics
    # ------------------------------------------------------------------ #
    def get_financial_analytics(
        self,
        *,
        scope_type: str,           # "hostel" or "platform"
        scope_id: Optional[UUID],
        period: DateRangeFilter,
    ) -> FinancialReport:
        """
        Convenience wrapper over FinancialAnalyticsService.get_financial_report.
        """
        return self._financial_analytics.get_financial_report(
            scope_type=scope_type,
            scope_id=scope_id,
            period=period,
        )