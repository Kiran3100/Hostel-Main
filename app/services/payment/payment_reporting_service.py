# app/services/payment/payment_reporting_service.py
"""
Payment Reporting Service

Provides aggregated payment analytics and report data.
"""

from __future__ import annotations

from typing import Dict, Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.payment import PaymentAggregateRepository
from app.schemas.payment import (
    PaymentReportRequest,
    PaymentAnalyticsRequest,
    PaymentAnalytics,
)
from app.core.exceptions import ValidationException


class PaymentReportingService:
    """
    High-level service for payment reporting & analytics.

    Responsibilities:
    - Produce grouped/aggregated metrics based on PaymentReportRequest
    - Generate high-level analytics using PaymentAnalyticsRequest
    """

    def __init__(
        self,
        aggregate_repo: PaymentAggregateRepository,
    ) -> None:
        self.aggregate_repo = aggregate_repo

    def get_payment_report(
        self,
        db: Session,
        request: PaymentReportRequest,
    ) -> Dict[str, Any]:
        """
        Retrieve a grouped/aggregated payment report.
        """
        data = self.aggregate_repo.build_payment_report(
            db=db,
            report_request=request.model_dump(exclude_none=True),
        )
        if not data:
            raise ValidationException("No data available for the given report request")
        return data

    def get_payment_analytics(
        self,
        db: Session,
        request: PaymentAnalyticsRequest,
    ) -> PaymentAnalytics:
        """
        Retrieve payment analytics for a period and optional hostel/filters.
        """
        data = self.aggregate_repo.build_payment_analytics(
            db=db,
            analytics_request=request.model_dump(exclude_none=True),
        )
        if not data:
            raise ValidationException("No payment analytics available")
        return PaymentAnalytics.model_validate(data)