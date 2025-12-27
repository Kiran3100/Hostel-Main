# app/services/payment/payment_reporting_service.py
"""
Payment Reporting Service

Provides aggregated payment analytics and report data:
- Generate payment reports with grouping
- Provide analytics dashboards
- Export capabilities
- Trend analysis
"""

from __future__ import annotations

from typing import Dict, Any, Optional, List
from uuid import UUID
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.repositories.payment import PaymentAggregateRepository
from app.schemas.payment import (
    PaymentReportRequest,
    PaymentAnalyticsRequest,
    PaymentAnalytics,
)
from app.core1.exceptions import ValidationException, NotFoundException
from app.core1.logging import LoggingContext, logger


class PaymentReportingService:
    """
    High-level service for payment reporting & analytics.

    Responsibilities:
    - Generate grouped/aggregated reports
    - Provide high-level analytics
    - Support custom report configurations
    - Generate trend analysis
    - Export data in various formats

    Delegates:
    - Aggregate queries to PaymentAggregateRepository
    """

    __slots__ = ("aggregate_repo",)

    # Report grouping options
    VALID_GROUP_BY = {
        "date",
        "week",
        "month",
        "quarter",
        "year",
        "fee_type",
        "payment_method",
        "status",
        "hostel",
        "student",
    }

    # Metric options
    VALID_METRICS = {
        "count",
        "sum",
        "average",
        "min",
        "max",
        "success_rate",
        "failure_rate",
    }

    def __init__(
        self,
        aggregate_repo: PaymentAggregateRepository,
    ) -> None:
        self.aggregate_repo = aggregate_repo

    # -------------------------------------------------------------------------
    # Standard reports
    # -------------------------------------------------------------------------

    def get_payment_report(
        self,
        db: Session,
        request: PaymentReportRequest,
    ) -> Dict[str, Any]:
        """
        Retrieve a grouped/aggregated payment report.

        Args:
            db: Database session
            request: Report configuration

        Returns:
            Report data with grouping and aggregations

        Raises:
            ValidationException: If report request is invalid
            NotFoundException: If no data available
        """
        self._validate_report_request(request)

        with LoggingContext(
            report_type=request.report_type,
            group_by=request.group_by,
        ):
            logger.info(f"Generating payment report: {request.report_type}")

            data = self.aggregate_repo.build_payment_report(
                db=db,
                report_request=request.model_dump(exclude_none=True),
            )

            if not data:
                raise NotFoundException(
                    "No data available for the given report request"
                )

            # Enhance report with metadata
            report = {
                "report_type": request.report_type,
                "generated_at": datetime.utcnow().isoformat(),
                "parameters": request.model_dump(exclude_none=True),
                "data": data,
                "summary": self._calculate_report_summary(data),
            }

            logger.info(
                f"Payment report generated successfully",
                extra={"record_count": len(data.get("groups", []))},
            )

            return report

    def _validate_report_request(self, request: PaymentReportRequest) -> None:
        """Validate payment report request."""
        if request.group_by:
            invalid_groups = set(request.group_by) - self.VALID_GROUP_BY
            if invalid_groups:
                raise ValidationException(
                    f"Invalid group_by options: {invalid_groups}"
                )

        if request.metrics:
            invalid_metrics = set(request.metrics) - self.VALID_METRICS
            if invalid_metrics:
                raise ValidationException(
                    f"Invalid metrics: {invalid_metrics}"
                )

        if request.start_date and request.end_date:
            if request.start_date > request.end_date:
                raise ValidationException("start_date must be before end_date")

            # Limit report range
            days_diff = (request.end_date - request.start_date).days
            if days_diff > 365:
                raise ValidationException("Report range cannot exceed 365 days")

    def _calculate_report_summary(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate summary statistics for report data."""
        if not data or "groups" not in data:
            return {}

        groups = data["groups"]
        if not groups:
            return {}

        total_amount = sum(
            Decimal(str(g.get("total_amount", 0))) for g in groups
        )
        total_count = sum(g.get("count", 0) for g in groups)
        avg_amount = total_amount / total_count if total_count > 0 else Decimal("0")

        return {
            "total_groups": len(groups),
            "total_payments": total_count,
            "total_amount": float(total_amount),
            "average_amount": float(avg_amount),
        }

    # -------------------------------------------------------------------------
    # Analytics
    # -------------------------------------------------------------------------

    def get_payment_analytics(
        self,
        db: Session,
        request: PaymentAnalyticsRequest,
    ) -> PaymentAnalytics:
        """
        Retrieve comprehensive payment analytics.

        Args:
            db: Database session
            request: Analytics request parameters

        Returns:
            PaymentAnalytics with metrics and insights

        Raises:
            ValidationException: If request is invalid
            NotFoundException: If no data available
        """
        self._validate_analytics_request(request)

        with LoggingContext(
            hostel_id=str(request.hostel_id) if request.hostel_id else None,
            period_days=request.period_days,
        ):
            logger.info("Generating payment analytics")

            data = self.aggregate_repo.build_payment_analytics(
                db=db,
                analytics_request=request.model_dump(exclude_none=True),
            )

            if not data:
                raise NotFoundException("No payment analytics available")

            analytics = PaymentAnalytics.model_validate(data)

            # Enhance with derived metrics
            analytics = self._enhance_analytics(analytics)

            logger.info(
                "Payment analytics generated successfully",
                extra={
                    "total_payments": analytics.total_payments,
                    "total_amount": float(analytics.total_amount),
                },
            )

            return analytics

    def _validate_analytics_request(
        self, request: PaymentAnalyticsRequest
    ) -> None:
        """Validate analytics request."""
        if request.period_days and request.period_days > 365:
            raise ValidationException("Analytics period cannot exceed 365 days")

        if request.start_date and request.end_date:
            if request.start_date > request.end_date:
                raise ValidationException("start_date must be before end_date")

    def _enhance_analytics(
        self, analytics: PaymentAnalytics
    ) -> PaymentAnalytics:
        """Enhance analytics with derived metrics."""
        # Add completion rate if not present
        if not hasattr(analytics, "completion_rate") or analytics.completion_rate is None:
            if analytics.total_payments > 0:
                analytics.completion_rate = (
                    analytics.completed_payments / analytics.total_payments * 100
                )
            else:
                analytics.completion_rate = 0

        # Add average transaction value
        if not hasattr(analytics, "average_transaction") or analytics.average_transaction is None:
            if analytics.completed_payments > 0:
                analytics.average_transaction = (
                    analytics.total_amount / analytics.completed_payments
                )
            else:
                analytics.average_transaction = Decimal("0")

        return analytics

    # -------------------------------------------------------------------------
    # Trend analysis
    # -------------------------------------------------------------------------

    def get_payment_trends(
        self,
        db: Session,
        hostel_id: Optional[UUID] = None,
        days: int = 30,
        interval: str = "day",
    ) -> Dict[str, Any]:
        """
        Get payment trends over time.

        Args:
            db: Database session
            hostel_id: Optional hostel filter
            days: Number of days to analyze
            interval: Grouping interval (day, week, month)

        Returns:
            Trend data with time series
        """
        if interval not in {"day", "week", "month"}:
            raise ValidationException("interval must be 'day', 'week', or 'month'")

        if days > 365:
            raise ValidationException("Trend analysis cannot exceed 365 days")

        with LoggingContext(hostel_id=str(hostel_id) if hostel_id else None):
            end_date = date.today()
            start_date = end_date - timedelta(days=days)

            trends = self.aggregate_repo.get_payment_trends(
                db=db,
                hostel_id=hostel_id,
                start_date=start_date,
                end_date=end_date,
                interval=interval,
            )

            # Calculate trend indicators
            trend_analysis = self._analyze_trends(trends)

            return {
                "period": {
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "days": days,
                    "interval": interval,
                },
                "data_points": trends,
                "analysis": trend_analysis,
            }

    def _analyze_trends(self, trends: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze trend data to identify patterns."""
        if not trends or len(trends) < 2:
            return {"trend": "insufficient_data"}

        # Calculate simple moving average
        amounts = [float(t.get("total_amount", 0)) for t in trends]
        counts = [t.get("count", 0) for t in trends]

        # Trend direction
        first_half_avg = sum(amounts[: len(amounts) // 2]) / max(
            len(amounts) // 2, 1
        )
        second_half_avg = sum(amounts[len(amounts) // 2 :]) / max(
            len(amounts) - len(amounts) // 2, 1
        )

        if second_half_avg > first_half_avg * 1.1:
            trend_direction = "increasing"
        elif second_half_avg < first_half_avg * 0.9:
            trend_direction = "decreasing"
        else:
            trend_direction = "stable"

        return {
            "trend": trend_direction,
            "first_period_average": first_half_avg,
            "second_period_average": second_half_avg,
            "overall_average": sum(amounts) / len(amounts),
            "peak_amount": max(amounts),
            "peak_count": max(counts),
        }

    # -------------------------------------------------------------------------
    # Custom reports
    # -------------------------------------------------------------------------

    def generate_custom_report(
        self,
        db: Session,
        hostel_id: Optional[UUID],
        config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Generate a custom report based on configuration.

        Args:
            db: Database session
            hostel_id: Optional hostel filter
            config: Custom report configuration

        Returns:
            Custom report data
        """
        # Validate config
        required_fields = ["metrics", "group_by", "date_range"]
        missing = [f for f in required_fields if f not in config]
        if missing:
            raise ValidationException(f"Missing required config fields: {missing}")

        with LoggingContext(report_type="custom"):
            logger.info("Generating custom payment report")

            data = self.aggregate_repo.build_custom_report(
                db=db,
                hostel_id=hostel_id,
                config=config,
            )

            return {
                "report_type": "custom",
                "generated_at": datetime.utcnow().isoformat(),
                "configuration": config,
                "data": data,
            }

    # -------------------------------------------------------------------------
    # Export
    # -------------------------------------------------------------------------

    def export_report(
        self,
        db: Session,
        request: PaymentReportRequest,
        format: str = "json",
    ) -> Any:
        """
        Export report in specified format.

        Args:
            db: Database session
            request: Report request
            format: Export format (json, csv, excel)

        Returns:
            Exported data in requested format
        """
        if format not in {"json", "csv", "excel"}:
            raise ValidationException("format must be 'json', 'csv', or 'excel'")

        report = self.get_payment_report(db, request)

        if format == "json":
            return report
        elif format == "csv":
            return self._export_to_csv(report)
        elif format == "excel":
            return self._export_to_excel(report)

    def _export_to_csv(self, report: Dict[str, Any]) -> str:
        """Export report to CSV format."""
        import csv
        import io

        output = io.StringIO()
        if not report.get("data", {}).get("groups"):
            return ""

        groups = report["data"]["groups"]
        if not groups:
            return ""

        # Get headers from first group
        headers = list(groups[0].keys())
        writer = csv.DictWriter(output, fieldnames=headers)

        writer.writeheader()
        for group in groups:
            writer.writerow(group)

        return output.getvalue()

    def _export_to_excel(self, report: Dict[str, Any]) -> bytes:
        """Export report to Excel format."""
        # This would require openpyxl or xlsxwriter
        # Placeholder implementation
        raise NotImplementedError("Excel export not yet implemented")