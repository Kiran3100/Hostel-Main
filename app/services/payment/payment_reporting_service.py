"""
Payment Reporting Service.

Comprehensive reporting and analytics with export capabilities.
Generates financial reports, collection reports, aging reports, etc.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.payment.payment_aggregate_repository import (
    PaymentAggregateRepository,
)
from app.repositories.payment.payment_repository import PaymentRepository
from app.repositories.payment.payment_ledger_repository import (
    PaymentLedgerRepository,
)
from app.repositories.payment.gateway_transaction_repository import (
    GatewayTransactionRepository,
)
from app.schemas.common.enums import PaymentType


class PaymentReportingService:
    """
    Service for payment reporting and analytics.
    
    Provides:
    - Financial dashboards
    - Revenue reports
    - Collection reports
    - Aging analysis
    - Gateway performance
    - Student payment history
    - Export capabilities
    """

    def __init__(
        self,
        session: AsyncSession,
        payment_repo: PaymentRepository,
        ledger_repo: PaymentLedgerRepository,
        gateway_repo: GatewayTransactionRepository,
        aggregate_repo: PaymentAggregateRepository,
    ):
        """Initialize reporting service."""
        self.session = session
        self.payment_repo = payment_repo
        self.ledger_repo = ledger_repo
        self.gateway_repo = gateway_repo
        self.aggregate_repo = aggregate_repo

    # ==================== Financial Dashboard ====================

    async def get_financial_dashboard(
        self,
        hostel_id: UUID,
        start_date: date,
        end_date: date,
    ) -> dict[str, Any]:
        """
        Get comprehensive financial dashboard.
        
        Returns all key financial metrics for the period.
        """
        return await self.aggregate_repo.get_financial_dashboard(
            hostel_id=hostel_id,
            start_date=start_date,
            end_date=end_date,
        )

    # ==================== Revenue Reports ====================

    async def generate_revenue_report(
        self,
        hostel_id: UUID,
        start_date: date,
        end_date: date,
        group_by: str = "day",  # day, week, month
    ) -> dict[str, Any]:
        """
        Generate detailed revenue report.
        
        Args:
            hostel_id: Hostel ID
            start_date: Report start date
            end_date: Report end date
            group_by: Grouping interval
            
        Returns:
            Comprehensive revenue report with trends
        """
        # Get revenue statistics
        revenue_stats = await self.payment_repo.calculate_revenue_statistics(
            hostel_id=hostel_id,
            start_date=start_date,
            end_date=end_date,
        )
        
        # Get revenue trends
        revenue_trends = await self.payment_repo.get_revenue_trends(
            hostel_id=hostel_id,
            start_date=start_date,
            end_date=end_date,
            interval=group_by,
        )
        
        # Get payment method distribution
        payment_methods = await self.payment_repo.get_payment_method_distribution(
            hostel_id=hostel_id,
            start_date=start_date,
            end_date=end_date,
        )
        
        # Get revenue by payment type
        revenue_by_type = {}
        for payment_type in PaymentType:
            type_stats = await self.payment_repo.calculate_revenue_statistics(
                hostel_id=hostel_id,
                start_date=start_date,
                end_date=end_date,
                payment_type=payment_type,
            )
            if type_stats["total_payments"] > 0:
                revenue_by_type[payment_type.value] = type_stats
        
        return {
            "report_type": "revenue_report",
            "hostel_id": str(hostel_id),
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
            },
            "summary": revenue_stats,
            "trends": revenue_trends,
            "payment_methods": payment_methods,
            "revenue_by_type": revenue_by_type,
            "generated_at": datetime.utcnow().isoformat(),
        }

    async def generate_monthly_revenue_summary(
        self,
        hostel_id: UUID,
        year: int,
        month: int,
    ) -> dict[str, Any]:
        """
        Generate monthly revenue summary.
        
        Detailed breakdown for a specific month.
        """
        start_date = date(year, month, 1)
        
        # Calculate last day of month
        if month == 12:
            end_date = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = date(year, month + 1, 1) - timedelta(days=1)
        
        return await self.generate_revenue_report(
            hostel_id=hostel_id,
            start_date=start_date,
            end_date=end_date,
            group_by="day",
        )

    # ==================== Collection Reports ====================

    async def generate_collection_report(
        self,
        hostel_id: UUID,
        start_date: date,
        end_date: date,
    ) -> dict[str, Any]:
        """
        Generate payment collection performance report.
        
        Shows collection efficiency and outstanding amounts.
        """
        # Get collection performance
        collection_perf = await self.aggregate_repo.get_collection_performance(
            hostel_id=hostel_id,
            start_date=start_date,
            end_date=end_date,
        )
        
        # Get outstanding payments
        outstanding_report = await self.aggregate_repo.get_outstanding_payments_report(
            hostel_id=hostel_id,
        )
        
        # Get overdue payments
        overdue_payments = await self.payment_repo.find_overdue_payments(
            hostel_id=hostel_id,
        )
        
        overdue_summary = {
            "count": len(overdue_payments),
            "total_amount": float(sum(p.amount for p in overdue_payments)),
            "oldest_due_date": min(
                (p.due_date for p in overdue_payments),
                default=None
            ),
        }
        
        return {
            "report_type": "collection_report",
            "hostel_id": str(hostel_id),
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
            },
            "collection_performance": collection_perf,
            "outstanding_summary": outstanding_report["summary"],
            "aging_breakdown": outstanding_report["aging_breakdown"],
            "overdue_summary": overdue_summary,
            "top_delinquent_students": outstanding_report["top_delinquent_students"],
            "generated_at": datetime.utcnow().isoformat(),
        }

    # ==================== Aging Reports ====================

    async def generate_aging_report(
        self,
        hostel_id: UUID,
        aging_buckets: Optional[list[int]] = None,
    ) -> dict[str, Any]:
        """
        Generate accounts receivable aging report.
        
        Shows outstanding amounts by age brackets.
        
        Args:
            hostel_id: Hostel ID
            aging_buckets: Age brackets in days [0, 30, 60, 90]
            
        Returns:
            Aging analysis report
        """
        if not aging_buckets:
            aging_buckets = [0, 30, 60, 90]
        
        outstanding_report = await self.aggregate_repo.get_outstanding_payments_report(
            hostel_id=hostel_id,
            aging_brackets=aging_buckets,
        )
        
        # Calculate aging percentages
        total_amount = outstanding_report["summary"]["total_outstanding_amount"]
        aging_percentages = {}
        
        for bracket, amount in outstanding_report["aging_breakdown"].items():
            percentage = (amount / total_amount * 100) if total_amount > 0 else 0
            aging_percentages[bracket] = {
                "amount": amount,
                "percentage": round(percentage, 2),
            }
        
        return {
            "report_type": "aging_report",
            "hostel_id": str(hostel_id),
            "as_of_date": date.today().isoformat(),
            "summary": outstanding_report["summary"],
            "aging_buckets": aging_buckets,
            "aging_breakdown": aging_percentages,
            "top_delinquent_students": outstanding_report["top_delinquent_students"],
            "generated_at": datetime.utcnow().isoformat(),
        }

    # ==================== Gateway Reports ====================

    async def generate_gateway_performance_report(
        self,
        hostel_id: UUID,
        start_date: datetime,
        end_date: datetime,
    ) -> dict[str, Any]:
        """
        Generate gateway performance comparison report.
        
        Compares all payment gateways on various metrics.
        """
        gateway_comparison = await self.aggregate_repo.get_gateway_comparison(
            hostel_id=hostel_id,
            start_date=start_date,
            end_date=end_date,
        )
        
        payment_method_analysis = await self.aggregate_repo.get_payment_method_analysis(
            hostel_id=hostel_id,
            start_date=start_date,
            end_date=end_date,
        )
        
        return {
            "report_type": "gateway_performance_report",
            "hostel_id": str(hostel_id),
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
            },
            "gateway_comparison": gateway_comparison,
            "payment_method_analysis": payment_method_analysis,
            "recommendations": self._generate_gateway_recommendations(
                gateway_comparison
            ),
            "generated_at": datetime.utcnow().isoformat(),
        }

    def _generate_gateway_recommendations(
        self,
        gateway_comparison: list[dict],
    ) -> list[str]:
        """Generate recommendations based on gateway performance."""
        recommendations = []
        
        if not gateway_comparison:
            return recommendations
        
        # Find best performing gateway
        best_gateway = max(
            gateway_comparison,
            key=lambda x: x["success_rate"],
            default=None
        )
        
        if best_gateway and best_gateway["success_rate"] > 95:
            recommendations.append(
                f"Consider routing more traffic to {best_gateway['gateway']} "
                f"(success rate: {best_gateway['success_rate']}%)"
            )
        
        # Find gateways with high fees
        for gateway in gateway_comparison:
            if gateway["total_fees"] > 0:
                avg_fee_percentage = (
                    gateway["total_fees"] / gateway["total_amount"] * 100
                    if gateway["total_amount"] > 0 else 0
                )
                if avg_fee_percentage > 2:
                    recommendations.append(
                        f"High fees on {gateway['gateway']}: "
                        f"{avg_fee_percentage:.2f}% average"
                    )
        
        return recommendations

    # ==================== Student Reports ====================

    async def generate_student_payment_report(
        self,
        student_id: UUID,
        hostel_id: UUID,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> dict[str, Any]:
        """
        Generate comprehensive payment report for a student.
        
        Useful for student portal or parent access.
        """
        # Get financial summary
        financial_summary = await self.aggregate_repo.get_student_financial_summary(
            student_id=student_id,
            hostel_id=hostel_id,
        )
        
        # Get payment history
        payment_history = await self.aggregate_repo.get_student_payment_history(
            student_id=student_id,
            hostel_id=hostel_id,
            start_date=start_date,
            end_date=end_date,
        )
        
        # Get ledger balance
        balance_info = await self.ledger_repo.get_student_balance(
            student_id=student_id,
            hostel_id=hostel_id,
        )
        
        return {
            "report_type": "student_payment_report",
            "student_id": str(student_id),
            "hostel_id": str(hostel_id),
            "period": {
                "start_date": start_date.isoformat() if start_date else None,
                "end_date": end_date.isoformat() if end_date else None,
            },
            "current_balance": balance_info,
            "financial_summary": financial_summary,
            "payment_history": payment_history,
            "generated_at": datetime.utcnow().isoformat(),
        }

    # ==================== Refund Reports ====================

    async def generate_refund_report(
        self,
        hostel_id: UUID,
        start_date: datetime,
        end_date: datetime,
    ) -> dict[str, Any]:
        """
        Generate refund analysis report.
        
        Shows refund trends, reasons, and processing times.
        """
        refund_analysis = await self.aggregate_repo.get_refund_analysis(
            hostel_id=hostel_id,
            start_date=start_date,
            end_date=end_date,
        )
        
        return {
            "report_type": "refund_report",
            "hostel_id": str(hostel_id),
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
            },
            "refund_analysis": refund_analysis,
            "generated_at": datetime.utcnow().isoformat(),
        }

    # ==================== Reminder Reports ====================

    async def generate_reminder_effectiveness_report(
        self,
        hostel_id: UUID,
        start_date: datetime,
        end_date: datetime,
    ) -> dict[str, Any]:
        """
        Generate reminder effectiveness report.
        
        Shows how well reminders are working to drive payments.
        """
        effectiveness = await self.aggregate_repo.get_reminder_effectiveness_report(
            hostel_id=hostel_id,
            start_date=start_date,
            end_date=end_date,
        )
        
        return {
            "report_type": "reminder_effectiveness_report",
            "hostel_id": str(hostel_id),
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
            },
            "effectiveness": effectiveness,
            "generated_at": datetime.utcnow().isoformat(),
        }

    # ==================== Export Functions ====================

    async def export_report_to_csv(
        self,
        report_data: dict[str, Any],
    ) -> str:
        """
        Export report to CSV format.
        
        In production, this would generate actual CSV file.
        
        Returns:
            CSV file path or URL
        """
        # TODO: Implement CSV generation
        # import csv
        # Generate CSV from report_data
        
        return "path/to/report.csv"

    async def export_report_to_pdf(
        self,
        report_data: dict[str, Any],
    ) -> str:
        """
        Export report to PDF format.
        
        In production, integrate with ReportLab or WeasyPrint.
        
        Returns:
            PDF file path or URL
        """
        # TODO: Implement PDF generation
        # Use reportlab or weasyprint
        
        return "path/to/report.pdf"

    async def export_report_to_excel(
        self,
        report_data: dict[str, Any],
    ) -> str:
        """
        Export report to Excel format.
        
        In production, use openpyxl or xlsxwriter.
        
        Returns:
            Excel file path or URL
        """
        # TODO: Implement Excel generation
        # Use openpyxl or xlsxwriter
        
        return "path/to/report.xlsx"

    # ==================== Scheduled Reports ====================

    async def generate_daily_summary_report(
        self,
        hostel_id: UUID,
        report_date: Optional[date] = None,
    ) -> dict[str, Any]:
        """
        Generate daily summary report.
        
        This should be scheduled to run daily and emailed to management.
        """
        target_date = report_date or date.today() - timedelta(days=1)
        
        # Revenue for the day
        revenue_report = await self.generate_revenue_report(
            hostel_id=hostel_id,
            start_date=target_date,
            end_date=target_date,
            group_by="day",
        )
        
        # Collection status
        collection_report = await self.generate_collection_report(
            hostel_id=hostel_id,
            start_date=target_date,
            end_date=target_date,
        )
        
        return {
            "report_type": "daily_summary",
            "hostel_id": str(hostel_id),
            "report_date": target_date.isoformat(),
            "revenue": revenue_report["summary"],
            "collection": collection_report["collection_performance"],
            "outstanding": collection_report["outstanding_summary"],
            "generated_at": datetime.utcnow().isoformat(),
        }

    async def generate_weekly_summary_report(
        self,
        hostel_id: UUID,
        week_end_date: Optional[date] = None,
    ) -> dict[str, Any]:
        """Generate weekly summary report."""
        end_date = week_end_date or date.today()
        start_date = end_date - timedelta(days=7)
        
        return await self.generate_revenue_report(
            hostel_id=hostel_id,
            start_date=start_date,
            end_date=end_date,
            group_by="day",
        )

    async def generate_monthly_summary_report(
        self,
        hostel_id: UUID,
        year: Optional[int] = None,
        month: Optional[int] = None,
    ) -> dict[str, Any]:
        """Generate monthly summary report."""
        today = date.today()
        year = year or today.year
        month = month or today.month
        
        return await self.generate_monthly_revenue_summary(
            hostel_id=hostel_id,
            year=year,
            month=month,
        )