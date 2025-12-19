# --- File: payment_aggregate_repository.py ---
"""
Payment Aggregate Repository.

Provides aggregated data and analytics across all payment-related entities.
Complex queries that span multiple payment tables.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models.payment.gateway_transaction import (
    GatewayProvider,
    GatewayTransaction,
    GatewayTransactionStatus,
)
from app.models.payment.payment import Payment
from app.models.payment.payment_ledger import PaymentLedger, TransactionType
from app.models.payment.payment_refund import PaymentRefund, RefundStatus
from app.models.payment.payment_reminder import PaymentReminder, ReminderStatus
from app.models.payment.payment_schedule import PaymentSchedule, ScheduleStatus
from app.repositories.base.base_repository import BaseRepository
from app.schemas.common.enums import PaymentMethod, PaymentStatus, PaymentType


class PaymentAggregateRepository:
    """Repository for aggregated payment analytics and reporting."""

    def __init__(self, session: AsyncSession):
        """Initialize payment aggregate repository."""
        self.session = session

    # ==================== Comprehensive Financial Reports ====================

    async def get_financial_dashboard(
        self,
        hostel_id: UUID,
        start_date: date,
        end_date: date,
    ) -> dict[str, Any]:
        """
        Get comprehensive financial dashboard data.
        
        Args:
            hostel_id: Hostel ID
            start_date: Start date
            end_date: End date
            
        Returns:
            Complete financial dashboard data
        """
        # Revenue statistics
        revenue_query = select(
            func.count(Payment.id).label("total_payments"),
            func.sum(Payment.amount).label("total_revenue"),
            func.sum(Payment.refund_amount).label("total_refunds"),
            func.avg(Payment.amount).label("average_payment"),
            func.count(Payment.id).filter(
                Payment.payment_status == PaymentStatus.COMPLETED
            ).label("completed_payments"),
            func.count(Payment.id).filter(
                Payment.payment_status == PaymentStatus.PENDING
            ).label("pending_payments"),
            func.count(Payment.id).filter(
                Payment.payment_status == PaymentStatus.FAILED
            ).label("failed_payments"),
        ).where(
            Payment.hostel_id == hostel_id,
            Payment.created_at >= datetime.combine(start_date, datetime.min.time()),
            Payment.created_at <= datetime.combine(end_date, datetime.max.time()),
            Payment.deleted_at.is_(None),
        )
        
        revenue_result = await self.session.execute(revenue_query)
        revenue_row = revenue_result.one()
        
        total_revenue = revenue_row.total_revenue or Decimal("0")
        total_refunds = revenue_row.total_refunds or Decimal("0")
        net_revenue = total_revenue - total_refunds
        
        # Payment method breakdown
        method_query = select(
            Payment.payment_method,
            func.count(Payment.id).label("count"),
            func.sum(Payment.amount).label("amount"),
        ).where(
            Payment.hostel_id == hostel_id,
            Payment.payment_status == PaymentStatus.COMPLETED,
            Payment.paid_at >= datetime.combine(start_date, datetime.min.time()),
            Payment.paid_at <= datetime.combine(end_date, datetime.max.time()),
            Payment.deleted_at.is_(None),
        ).group_by(Payment.payment_method)
        
        method_result = await self.session.execute(method_query)
        payment_methods = [
            {
                "method": row.payment_method.value,
                "count": row.count,
                "amount": float(row.amount or Decimal("0")),
            }
            for row in method_result.all()
        ]
        
        # Payment type breakdown
        type_query = select(
            Payment.payment_type,
            func.count(Payment.id).label("count"),
            func.sum(Payment.amount).label("amount"),
        ).where(
            Payment.hostel_id == hostel_id,
            Payment.payment_status == PaymentStatus.COMPLETED,
            Payment.paid_at >= datetime.combine(start_date, datetime.min.time()),
            Payment.paid_at <= datetime.combine(end_date, datetime.max.time()),
            Payment.deleted_at.is_(None),
        ).group_by(Payment.payment_type)
        
        type_result = await self.session.execute(type_query)
        payment_types = [
            {
                "type": row.payment_type.value,
                "count": row.count,
                "amount": float(row.amount or Decimal("0")),
            }
            for row in type_result.all()
        ]
        
        # Gateway performance
        gateway_query = select(
            GatewayTransaction.gateway_name,
            func.count(GatewayTransaction.id).label("total"),
            func.count(GatewayTransaction.id).filter(
                GatewayTransaction.transaction_status == GatewayTransactionStatus.SUCCESS
            ).label("successful"),
            func.sum(GatewayTransaction.transaction_amount).filter(
                GatewayTransaction.transaction_status == GatewayTransactionStatus.SUCCESS
            ).label("amount"),
        ).join(
            Payment, GatewayTransaction.payment_id == Payment.id
        ).where(
            Payment.hostel_id == hostel_id,
            GatewayTransaction.initiated_at >= datetime.combine(start_date, datetime.min.time()),
            GatewayTransaction.initiated_at <= datetime.combine(end_date, datetime.max.time()),
            GatewayTransaction.deleted_at.is_(None),
        ).group_by(GatewayTransaction.gateway_name)
        
        gateway_result = await self.session.execute(gateway_query)
        gateway_performance = []
        for row in gateway_result.all():
            success_rate = (row.successful / row.total * 100) if row.total > 0 else 0
            gateway_performance.append({
                "gateway": row.gateway_name.value,
                "total_transactions": row.total,
                "successful_transactions": row.successful,
                "success_rate": round(success_rate, 2),
                "total_amount": float(row.amount or Decimal("0")),
            })
        
        # Refund statistics
        refund_query = select(
            func.count(PaymentRefund.id).label("total_refunds"),
            func.sum(PaymentRefund.refund_amount).label("total_amount"),
            func.count(PaymentRefund.id).filter(
                PaymentRefund.refund_status == RefundStatus.COMPLETED
            ).label("completed"),
            func.count(PaymentRefund.id).filter(
                PaymentRefund.refund_status == RefundStatus.PENDING
            ).label("pending"),
        ).join(
            Payment, PaymentRefund.payment_id == Payment.id
        ).where(
            Payment.hostel_id == hostel_id,
            PaymentRefund.requested_at >= datetime.combine(start_date, datetime.min.time()),
            PaymentRefund.requested_at <= datetime.combine(end_date, datetime.max.time()),
            PaymentRefund.deleted_at.is_(None),
        )
        
        refund_result = await self.session.execute(refund_query)
        refund_row = refund_result.one()
        
        return {
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
            },
            "revenue": {
                "total_payments": revenue_row.total_payments,
                "total_revenue": float(total_revenue),
                "total_refunds": float(total_refunds),
                "net_revenue": float(net_revenue),
                "average_payment": float(revenue_row.average_payment or Decimal("0")),
            },
            "payment_status": {
                "completed": revenue_row.completed_payments,
                "pending": revenue_row.pending_payments,
                "failed": revenue_row.failed_payments,
            },
            "payment_methods": payment_methods,
            "payment_types": payment_types,
            "gateway_performance": gateway_performance,
            "refunds": {
                "total_refunds": refund_row.total_refunds or 0,
                "total_amount": float(refund_row.total_amount or Decimal("0")),
                "completed": refund_row.completed or 0,
                "pending": refund_row.pending or 0,
            },
        }

    async def get_revenue_trends(
        self,
        hostel_id: UUID,
        start_date: date,
        end_date: date,
        interval: str = "day",  # day, week, month
    ) -> list[dict[str, Any]]:
        """
        Get detailed revenue trends with multiple dimensions.
        
        Args:
            hostel_id: Hostel ID
            start_date: Start date
            end_date: End date
            interval: Grouping interval
            
        Returns:
            Revenue trend data
        """
        # Determine date truncation
        if interval == "day":
            date_trunc = func.date_trunc('day', Payment.paid_at)
        elif interval == "week":
            date_trunc = func.date_trunc('week', Payment.paid_at)
        else:  # month
            date_trunc = func.date_trunc('month', Payment.paid_at)
        
        query = select(
            date_trunc.label("period"),
            func.count(Payment.id).label("payment_count"),
            func.sum(Payment.amount).label("total_revenue"),
            func.sum(Payment.refund_amount).label("total_refunds"),
            func.avg(Payment.amount).label("average_payment"),
            func.count(Payment.id).filter(
                Payment.payment_method == PaymentMethod.ONLINE
            ).label("online_payments"),
            func.count(Payment.id).filter(
                Payment.payment_method == PaymentMethod.CASH
            ).label("cash_payments"),
        ).where(
            Payment.hostel_id == hostel_id,
            Payment.payment_status == PaymentStatus.COMPLETED,
            Payment.paid_at >= datetime.combine(start_date, datetime.min.time()),
            Payment.paid_at <= datetime.combine(end_date, datetime.max.time()),
            Payment.deleted_at.is_(None),
        ).group_by(date_trunc).order_by(date_trunc)
        
        result = await self.session.execute(query)
        
        trends = []
        for row in result.all():
            total_revenue = row.total_revenue or Decimal("0")
            total_refunds = row.total_refunds or Decimal("0")
            
            trends.append({
                "period": row.period.isoformat() if row.period else None,
                "payment_count": row.payment_count,
                "total_revenue": float(total_revenue),
                "total_refunds": float(total_refunds),
                "net_revenue": float(total_revenue - total_refunds),
                "average_payment": float(row.average_payment or Decimal("0")),
                "online_payments": row.online_payments,
                "cash_payments": row.cash_payments,
            })
        
        return trends

    # ==================== Student Financial Analysis ====================

    async def get_student_financial_summary(
        self,
        student_id: UUID,
        hostel_id: UUID,
    ) -> dict[str, Any]:
        """
        Get comprehensive financial summary for a student.
        
        Args:
            student_id: Student ID
            hostel_id: Hostel ID
            
        Returns:
            Student financial summary
        """
        # Payment summary
        payment_query = select(
            func.count(Payment.id).label("total_payments"),
            func.sum(Payment.amount).label("total_paid"),
            func.sum(Payment.amount).filter(
                Payment.payment_status == PaymentStatus.PENDING
            ).label("pending_amount"),
            func.sum(Payment.amount).filter(
                Payment.is_overdue == True
            ).label("overdue_amount"),
        ).where(
            Payment.student_id == student_id,
            Payment.hostel_id == hostel_id,
            Payment.deleted_at.is_(None),
        )
        
        payment_result = await self.session.execute(payment_query)
        payment_row = payment_result.one()
        
        # Ledger balance
        ledger_query = select(
            func.sum(PaymentLedger.amount)
        ).where(
            PaymentLedger.student_id == student_id,
            PaymentLedger.hostel_id == hostel_id,
            PaymentLedger.is_reversed == False,
            PaymentLedger.deleted_at.is_(None),
        )
        
        ledger_result = await self.session.execute(ledger_query)
        current_balance = ledger_result.scalar() or Decimal("0")
        
        # Active schedules
        schedule_query = select(
            func.count(PaymentSchedule.id).label("active_schedules"),
            func.sum(PaymentSchedule.amount).label("recurring_amount"),
        ).where(
            PaymentSchedule.student_id == student_id,
            PaymentSchedule.hostel_id == hostel_id,
            PaymentSchedule.is_active == True,
            PaymentSchedule.deleted_at.is_(None),
        )
        
        schedule_result = await self.session.execute(schedule_query)
        schedule_row = schedule_result.one()
        
        # Payment history by type
        type_query = select(
            Payment.payment_type,
            func.sum(Payment.amount).label("amount"),
        ).where(
            Payment.student_id == student_id,
            Payment.hostel_id == hostel_id,
            Payment.payment_status == PaymentStatus.COMPLETED,
            Payment.deleted_at.is_(None),
        ).group_by(Payment.payment_type)
        
        type_result = await self.session.execute(type_query)
        payment_by_type = {
            row.payment_type.value: float(row.amount or Decimal("0"))
            for row in type_result.all()
        }
        
        # Recent transactions
        recent_query = select(Payment).where(
            Payment.student_id == student_id,
            Payment.hostel_id == hostel_id,
            Payment.deleted_at.is_(None),
        ).order_by(Payment.created_at.desc()).limit(5)
        
        recent_result = await self.session.execute(recent_query)
        recent_payments = [
            {
                "id": str(payment.id),
                "reference": payment.payment_reference,
                "amount": float(payment.amount),
                "type": payment.payment_type.value,
                "status": payment.payment_status.value,
                "date": payment.created_at.isoformat(),
            }
            for payment in recent_result.scalars().all()
        ]
        
        return {
            "student_id": str(student_id),
            "current_balance": float(current_balance),
            "payment_summary": {
                "total_payments": payment_row.total_payments,
                "total_paid": float(payment_row.total_paid or Decimal("0")),
                "pending_amount": float(payment_row.pending_amount or Decimal("0")),
                "overdue_amount": float(payment_row.overdue_amount or Decimal("0")),
            },
            "active_schedules": {
                "count": schedule_row.active_schedules or 0,
                "monthly_recurring": float(schedule_row.recurring_amount or Decimal("0")),
            },
            "payment_by_type": payment_by_type,
            "recent_payments": recent_payments,
        }

    async def get_student_payment_history(
        self,
        student_id: UUID,
        hostel_id: UUID,
        start_date: date | None = None,
        end_date: date | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        """
        Get detailed payment history for a student.
        
        Args:
            student_id: Student ID
            hostel_id: Hostel ID
            start_date: Optional start date
            end_date: Optional end date
            limit: Maximum results
            offset: Offset for pagination
            
        Returns:
            Payment history with statistics
        """
        query = select(Payment).where(
            Payment.student_id == student_id,
            Payment.hostel_id == hostel_id,
            Payment.deleted_at.is_(None),
        )
        
        if start_date:
            query = query.where(
                Payment.created_at >= datetime.combine(start_date, datetime.min.time())
            )
        
        if end_date:
            query = query.where(
                Payment.created_at <= datetime.combine(end_date, datetime.max.time())
            )
        
        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        count_result = await self.session.execute(count_query)
        total_count = count_result.scalar() or 0
        
        # Get paginated results
        query = query.order_by(Payment.created_at.desc()).limit(limit).offset(offset)
        result = await self.session.execute(query)
        
        payments = []
        for payment in result.scalars().all():
            payments.append({
                "id": str(payment.id),
                "reference": payment.payment_reference,
                "type": payment.payment_type.value,
                "amount": float(payment.amount),
                "status": payment.payment_status.value,
                "method": payment.payment_method.value,
                "created_at": payment.created_at.isoformat(),
                "paid_at": payment.paid_at.isoformat() if payment.paid_at else None,
                "due_date": payment.due_date.isoformat() if payment.due_date else None,
                "is_overdue": payment.is_overdue,
                "receipt_number": payment.receipt_number,
            })
        
        return {
            "total_count": total_count,
            "limit": limit,
            "offset": offset,
            "payments": payments,
        }

    # ==================== Outstanding Payments Analysis ====================

    async def get_outstanding_payments_report(
        self,
        hostel_id: UUID,
        aging_brackets: list[int] = [0, 30, 60, 90],  # days
    ) -> dict[str, Any]:
        """
        Get detailed outstanding payments report with aging analysis.
        
        Args:
            hostel_id: Hostel ID
            aging_brackets: Aging brackets in days
            
        Returns:
            Outstanding payments report with aging
        """
        today = date.today()
        
        # Build aging cases
        aging_cases = []
        for i, days in enumerate(aging_brackets):
            if i < len(aging_brackets) - 1:
                next_days = aging_brackets[i + 1]
                label = f"{days}-{next_days}_days"
                condition = and_(
                    func.date_part('day', today - Payment.due_date) >= days,
                    func.date_part('day', today - Payment.due_date) < next_days,
                )
            else:
                label = f"{days}_plus_days"
                condition = func.date_part('day', today - Payment.due_date) >= days
            
            aging_cases.append((label, condition))
        
        # Query for aging analysis
        aging_query = select(
            *[
                func.sum(
                    case((condition, Payment.amount), else_=0)
                ).label(label)
                for label, condition in aging_cases
            ],
            func.count(Payment.id).label("total_count"),
            func.sum(Payment.amount).label("total_amount"),
        ).where(
            Payment.hostel_id == hostel_id,
            Payment.payment_status.in_([PaymentStatus.PENDING, PaymentStatus.PROCESSING]),
            Payment.due_date < today,
            Payment.deleted_at.is_(None),
        )
        
        aging_result = await self.session.execute(aging_query)
        aging_row = aging_result.one()
        
        aging_breakdown = {}
        for label, _ in aging_cases:
            aging_breakdown[label] = float(getattr(aging_row, label) or Decimal("0"))
        
        # Get top delinquent students
        student_query = select(
            Payment.student_id,
            func.count(Payment.id).label("overdue_count"),
            func.sum(Payment.amount).label("overdue_amount"),
            func.min(Payment.due_date).label("oldest_due_date"),
        ).where(
            Payment.hostel_id == hostel_id,
            Payment.payment_status.in_([PaymentStatus.PENDING, PaymentStatus.PROCESSING]),
            Payment.due_date < today,
            Payment.deleted_at.is_(None),
        ).group_by(Payment.student_id).order_by(
            func.sum(Payment.amount).desc()
        ).limit(10)
        
        student_result = await self.session.execute(student_query)
        
        top_delinquent = [
            {
                "student_id": str(row.student_id),
                "overdue_count": row.overdue_count,
                "overdue_amount": float(row.overdue_amount or Decimal("0")),
                "oldest_due_date": row.oldest_due_date.isoformat(),
                "days_overdue": (today - row.oldest_due_date).days,
            }
            for row in student_result.all()
        ]
        
        return {
            "summary": {
                "total_outstanding_count": aging_row.total_count,
                "total_outstanding_amount": float(aging_row.total_amount or Decimal("0")),
            },
            "aging_breakdown": aging_breakdown,
            "top_delinquent_students": top_delinquent,
        }

    # ==================== Gateway Analytics ====================

    async def get_gateway_comparison(
        self,
        hostel_id: UUID,
        start_date: datetime,
        end_date: datetime,
    ) -> list[dict[str, Any]]:
        """
        Compare performance across payment gateways.
        
        Args:
            hostel_id: Hostel ID
            start_date: Start date
            end_date: End date
            
        Returns:
            Gateway comparison data
        """
        query = select(
            GatewayTransaction.gateway_name,
            func.count(GatewayTransaction.id).label("total_transactions"),
            func.count(GatewayTransaction.id).filter(
                GatewayTransaction.transaction_status == GatewayTransactionStatus.SUCCESS
            ).label("successful"),
            func.count(GatewayTransaction.id).filter(
                GatewayTransaction.transaction_status == GatewayTransactionStatus.FAILED
            ).label("failed"),
            func.sum(GatewayTransaction.transaction_amount).filter(
                GatewayTransaction.transaction_status == GatewayTransactionStatus.SUCCESS
            ).label("total_amount"),
            func.avg(GatewayTransaction.response_time_ms).label("avg_response_time"),
            func.sum(GatewayTransaction.gateway_fee).label("total_fees"),
        ).join(
            Payment, GatewayTransaction.payment_id == Payment.id
        ).where(
            Payment.hostel_id == hostel_id,
            GatewayTransaction.initiated_at >= start_date,
            GatewayTransaction.initiated_at <= end_date,
            GatewayTransaction.deleted_at.is_(None),
        ).group_by(GatewayTransaction.gateway_name)
        
        result = await self.session.execute(query)
        
        comparison = []
        for row in result.all():
            success_rate = (
                (row.successful / row.total_transactions * 100)
                if row.total_transactions > 0 else 0
            )
            
            comparison.append({
                "gateway": row.gateway_name.value,
                "total_transactions": row.total_transactions,
                "successful_transactions": row.successful,
                "failed_transactions": row.failed,
                "success_rate": round(success_rate, 2),
                "total_amount": float(row.total_amount or Decimal("0")),
                "avg_response_time_ms": round(row.avg_response_time or 0, 2),
                "total_fees": float(row.total_fees or Decimal("0")),
            })
        
        return comparison

    async def get_payment_method_analysis(
        self,
        hostel_id: UUID,
        start_date: datetime,
        end_date: datetime,
    ) -> dict[str, Any]:
        """
        Analyze payment method usage and performance.
        
        Args:
            hostel_id: Hostel ID
            start_date: Start date
            end_date: End date
            
        Returns:
            Payment method analysis
        """
        # Gateway transaction payment methods
        gateway_query = select(
            GatewayTransaction.payment_method_used,
            func.count(GatewayTransaction.id).label("count"),
            func.sum(GatewayTransaction.transaction_amount).label("amount"),
            func.count(GatewayTransaction.id).filter(
                GatewayTransaction.transaction_status == GatewayTransactionStatus.SUCCESS
            ).label("successful"),
        ).join(
            Payment, GatewayTransaction.payment_id == Payment.id
        ).where(
            Payment.hostel_id == hostel_id,
            GatewayTransaction.payment_method_used.isnot(None),
            GatewayTransaction.initiated_at >= start_date,
            GatewayTransaction.initiated_at <= end_date,
            GatewayTransaction.deleted_at.is_(None),
        ).group_by(GatewayTransaction.payment_method_used)
        
        gateway_result = await self.session.execute(gateway_query)
        
        detailed_methods = []
        for row in gateway_result.all():
            success_rate = (row.successful / row.count * 100) if row.count > 0 else 0
            detailed_methods.append({
                "method": row.payment_method_used,
                "count": row.count,
                "amount": float(row.amount or Decimal("0")),
                "success_rate": round(success_rate, 2),
            })
        
        # Overall payment method distribution
        overall_query = select(
            Payment.payment_method,
            func.count(Payment.id).label("count"),
            func.sum(Payment.amount).label("amount"),
        ).where(
            Payment.hostel_id == hostel_id,
            Payment.payment_status == PaymentStatus.COMPLETED,
            Payment.paid_at >= start_date,
            Payment.paid_at <= end_date,
            Payment.deleted_at.is_(None),
        ).group_by(Payment.payment_method)
        
        overall_result = await self.session.execute(overall_query)
        
        overall_methods = [
            {
                "method": row.payment_method.value,
                "count": row.count,
                "amount": float(row.amount or Decimal("0")),
            }
            for row in overall_result.all()
        ]
        
        return {
            "overall_distribution": overall_methods,
            "detailed_methods": detailed_methods,
        }

    # ==================== Refund Analytics ====================

    async def get_refund_analysis(
        self,
        hostel_id: UUID,
        start_date: datetime,
        end_date: datetime,
    ) -> dict[str, Any]:
        """
        Comprehensive refund analysis.
        
        Args:
            hostel_id: Hostel ID
            start_date: Start date
            end_date: End date
            
        Returns:
            Refund analysis data
        """
        # Overall refund statistics
        overall_query = select(
            func.count(PaymentRefund.id).label("total_refunds"),
            func.sum(PaymentRefund.refund_amount).label("total_amount"),
            func.avg(PaymentRefund.refund_amount).label("avg_amount"),
            func.count(PaymentRefund.id).filter(
                PaymentRefund.is_partial == True
            ).label("partial_refunds"),
            func.avg(
                func.extract('epoch', PaymentRefund.completed_at - PaymentRefund.requested_at) / 3600
            ).label("avg_processing_hours"),
        ).join(
            Payment, PaymentRefund.payment_id == Payment.id
        ).where(
            Payment.hostel_id == hostel_id,
            PaymentRefund.requested_at >= start_date,
            PaymentRefund.requested_at <= end_date,
            PaymentRefund.deleted_at.is_(None),
        )
        
        overall_result = await self.session.execute(overall_query)
        overall_row = overall_result.one()
        
        # Status breakdown
        status_query = select(
            PaymentRefund.refund_status,
            func.count(PaymentRefund.id).label("count"),
            func.sum(PaymentRefund.refund_amount).label("amount"),
        ).join(
            Payment, PaymentRefund.payment_id == Payment.id
        ).where(
            Payment.hostel_id == hostel_id,
            PaymentRefund.requested_at >= start_date,
            PaymentRefund.requested_at <= end_date,
            PaymentRefund.deleted_at.is_(None),
        ).group_by(PaymentRefund.refund_status)
        
        status_result = await self.session.execute(status_query)
        
        status_breakdown = [
            {
                "status": row.refund_status.value,
                "count": row.count,
                "amount": float(row.amount or Decimal("0")),
            }
            for row in status_result.all()
        ]
        
        # Category breakdown
        category_query = select(
            PaymentRefund.refund_category,
            func.count(PaymentRefund.id).label("count"),
            func.sum(PaymentRefund.refund_amount).label("amount"),
        ).join(
            Payment, PaymentRefund.payment_id == Payment.id
        ).where(
            Payment.hostel_id == hostel_id,
            PaymentRefund.refund_category.isnot(None),
            PaymentRefund.requested_at >= start_date,
            PaymentRefund.requested_at <= end_date,
            PaymentRefund.deleted_at.is_(None),
        ).group_by(PaymentRefund.refund_category)
        
        category_result = await self.session.execute(category_query)
        
        category_breakdown = [
            {
                "category": row.refund_category,
                "count": row.count,
                "amount": float(row.amount or Decimal("0")),
            }
            for row in category_result.all()
        ]
        
        return {
            "overall": {
                "total_refunds": overall_row.total_refunds or 0,
                "total_amount": float(overall_row.total_amount or Decimal("0")),
                "average_amount": float(overall_row.avg_amount or Decimal("0")),
                "partial_refunds": overall_row.partial_refunds or 0,
                "full_refunds": (overall_row.total_refunds or 0) - (overall_row.partial_refunds or 0),
                "avg_processing_hours": round(overall_row.avg_processing_hours or 0, 2),
            },
            "status_breakdown": status_breakdown,
            "category_breakdown": category_breakdown,
        }

    # ==================== Collection Performance ====================

    async def get_collection_performance(
        self,
        hostel_id: UUID,
        start_date: date,
        end_date: date,
    ) -> dict[str, Any]:
        """
        Analyze payment collection performance.
        
        Args:
            hostel_id: Hostel ID
            start_date: Start date
            end_date: End date
            
        Returns:
            Collection performance metrics
        """
        # Schedule-based collection
        schedule_query = select(
            func.sum(PaymentSchedule.total_payments_generated).label("generated"),
            func.sum(PaymentSchedule.total_payments_completed).label("completed"),
            func.sum(PaymentSchedule.total_amount_collected).label("collected"),
        ).where(
            PaymentSchedule.hostel_id == hostel_id,
            PaymentSchedule.deleted_at.is_(None),
        )
        
        schedule_result = await self.session.execute(schedule_query)
        schedule_row = schedule_result.one()
        
        collection_rate = (
            (schedule_row.completed / schedule_row.generated * 100)
            if schedule_row.generated and schedule_row.generated > 0 else 0
        )
        
        # On-time payment rate
        ontime_query = select(
            func.count(Payment.id).label("total"),
            func.count(Payment.id).filter(
                and_(
                    Payment.paid_at.isnot(None),
                    Payment.due_date.isnot(None),
                    Payment.paid_at <= func.cast(Payment.due_date, DateTime),
                )
            ).label("on_time"),
        ).where(
            Payment.hostel_id == hostel_id,
            Payment.payment_status == PaymentStatus.COMPLETED,
            Payment.paid_at >= datetime.combine(start_date, datetime.min.time()),
            Payment.paid_at <= datetime.combine(end_date, datetime.max.time()),
            Payment.deleted_at.is_(None),
        )
        
        ontime_result = await self.session.execute(ontime_query)
        ontime_row = ontime_result.one()
        
        ontime_rate = (
            (ontime_row.on_time / ontime_row.total * 100)
            if ontime_row.total > 0 else 0
        )
        
        # Average collection time
        collection_time_query = select(
            func.avg(
                func.extract('epoch', Payment.paid_at - Payment.created_at) / 86400
            ).label("avg_days"),
        ).where(
            Payment.hostel_id == hostel_id,
            Payment.payment_status == PaymentStatus.COMPLETED,
            Payment.paid_at.isnot(None),
            Payment.paid_at >= datetime.combine(start_date, datetime.min.time()),
            Payment.paid_at <= datetime.combine(end_date, datetime.max.time()),
            Payment.deleted_at.is_(None),
        )
        
        collection_time_result = await self.session.execute(collection_time_query)
        avg_collection_days = collection_time_result.scalar() or 0
        
        return {
            "schedule_collection": {
                "payments_generated": schedule_row.generated or 0,
                "payments_completed": schedule_row.completed or 0,
                "collection_rate": round(collection_rate, 2),
                "total_collected": float(schedule_row.collected or Decimal("0")),
            },
            "payment_timing": {
                "total_payments": ontime_row.total,
                "on_time_payments": ontime_row.on_time,
                "on_time_rate": round(ontime_rate, 2),
                "average_collection_days": round(avg_collection_days, 2),
            },
        }

    # ==================== Reminder Effectiveness ====================

    async def get_reminder_effectiveness_report(
        self,
        hostel_id: UUID,
        start_date: datetime,
        end_date: datetime,
    ) -> dict[str, Any]:
        """
        Analyze reminder effectiveness and impact on payments.
        
        Args:
            hostel_id: Hostel ID
            start_date: Start date
            end_date: End date
            
        Returns:
            Reminder effectiveness analysis
        """
        # Overall reminder statistics
        reminder_query = select(
            func.count(PaymentReminder.id).label("total_sent"),
            func.count(PaymentReminder.id).filter(
                PaymentReminder.reminder_status == ReminderStatus.DELIVERED
            ).label("delivered"),
            func.count(PaymentReminder.id).filter(
                PaymentReminder.email_opened == True
            ).label("opened"),
            func.count(PaymentReminder.id).filter(
                PaymentReminder.email_clicked == True
            ).label("clicked"),
        ).where(
            PaymentReminder.hostel_id == hostel_id,
            PaymentReminder.sent_at >= start_date,
            PaymentReminder.sent_at <= end_date,
            PaymentReminder.deleted_at.is_(None),
        )
        
        reminder_result = await self.session.execute(reminder_query)
        reminder_row = reminder_result.one()
        
        delivery_rate = (
            (reminder_row.delivered / reminder_row.total_sent * 100)
            if reminder_row.total_sent > 0 else 0
        )
        open_rate = (
            (reminder_row.opened / reminder_row.total_sent * 100)
            if reminder_row.total_sent > 0 else 0
        )
        click_rate = (
            (reminder_row.clicked / reminder_row.total_sent * 100)
            if reminder_row.total_sent > 0 else 0
        )
        
        # Payment correlation - payments made after reminders
        correlation_query = select(
            func.count(Payment.id).filter(
                and_(
                    Payment.reminder_sent_count > 0,
                    Payment.payment_status == PaymentStatus.COMPLETED,
                )
            ).label("paid_after_reminder"),
            func.count(Payment.id).filter(
                Payment.payment_status == PaymentStatus.COMPLETED
            ).label("total_paid"),
        ).where(
            Payment.hostel_id == hostel_id,
            Payment.paid_at >= start_date,
            Payment.paid_at <= end_date,
            Payment.deleted_at.is_(None),
        )
        
        correlation_result = await self.session.execute(correlation_query)
        correlation_row = correlation_result.one()
        
        reminder_conversion = (
            (correlation_row.paid_after_reminder / correlation_row.total_paid * 100)
            if correlation_row.total_paid > 0 else 0
        )
        
        return {
            "reminder_delivery": {
                "total_sent": reminder_row.total_sent,
                "delivered": reminder_row.delivered,
                "delivery_rate": round(delivery_rate, 2),
            },
            "engagement": {
                "opened": reminder_row.opened,
                "clicked": reminder_row.clicked,
                "open_rate": round(open_rate, 2),
                "click_rate": round(click_rate, 2),
            },
            "payment_impact": {
                "payments_after_reminder": correlation_row.paid_after_reminder,
                "total_payments": correlation_row.total_paid,
                "reminder_conversion_rate": round(reminder_conversion, 2),
            },
        }

    # ==================== Ledger Analysis ====================

    async def get_ledger_reconciliation_report(
        self,
        hostel_id: UUID,
        as_of_date: date | None = None,
    ) -> dict[str, Any]:
        """
        Generate ledger reconciliation report.
        
        Args:
            hostel_id: Hostel ID
            as_of_date: As of date (default: today)
            
        Returns:
            Ledger reconciliation report
        """
        target_date = as_of_date or date.today()
        
        # Total debits and credits
        totals_query = select(
            func.sum(
                case((PaymentLedger.amount < 0, func.abs(PaymentLedger.amount)), else_=0)
            ).label("total_debits"),
            func.sum(
                case((PaymentLedger.amount > 0, PaymentLedger.amount), else_=0)
            ).label("total_credits"),
            func.sum(PaymentLedger.amount).label("net_balance"),
        ).where(
            PaymentLedger.hostel_id == hostel_id,
            PaymentLedger.transaction_date <= target_date,
            PaymentLedger.is_reversed == False,
            PaymentLedger.deleted_at.is_(None),
        )
        
        totals_result = await self.session.execute(totals_query)
        totals_row = totals_result.one()
        
        # Transaction type breakdown
        type_query = select(
            PaymentLedger.transaction_type,
            func.count(PaymentLedger.id).label("count"),
            func.sum(PaymentLedger.amount).label("amount"),
        ).where(
            PaymentLedger.hostel_id == hostel_id,
            PaymentLedger.transaction_date <= target_date,
            PaymentLedger.is_reversed == False,
            PaymentLedger.deleted_at.is_(None),
        ).group_by(PaymentLedger.transaction_type)
        
        type_result = await self.session.execute(type_query)
        
        transaction_breakdown = [
            {
                "type": row.transaction_type.value,
                "count": row.count,
                "amount": float(row.amount or Decimal("0")),
            }
            for row in type_result.all()
        ]
        
        # Unreconciled entries
        unreconciled_query = select(
            func.count(PaymentLedger.id),
            func.sum(PaymentLedger.amount),
        ).where(
            PaymentLedger.hostel_id == hostel_id,
            PaymentLedger.is_reconciled == False,
            PaymentLedger.is_reversed == False,
            PaymentLedger.transaction_date <= target_date,
            PaymentLedger.deleted_at.is_(None),
        )
        
        unreconciled_result = await self.session.execute(unreconciled_query)
        unreconciled_count, unreconciled_amount = unreconciled_result.one()
        
        return {
            "as_of_date": target_date.isoformat(),
            "totals": {
                "total_debits": float(totals_row.total_debits or Decimal("0")),
                "total_credits": float(totals_row.total_credits or Decimal("0")),
                "net_balance": float(totals_row.net_balance or Decimal("0")),
            },
            "transaction_breakdown": transaction_breakdown,
            "reconciliation_status": {
                "unreconciled_entries": unreconciled_count or 0,
                "unreconciled_amount": float(unreconciled_amount or Decimal("0")),
            },
        }