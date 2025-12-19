# --- File: gateway_transaction_repository.py ---
"""
Gateway Transaction Repository.

Multi-gateway management with load balancing, performance monitoring,
and cost optimization.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payment.gateway_transaction import (
    GatewayProvider,
    GatewayTransaction,
    GatewayTransactionStatus,
    GatewayTransactionType,
)
from app.repositories.base.base_repository import BaseRepository


class GatewayTransactionRepository(BaseRepository[GatewayTransaction]):
    """Repository for gateway transaction operations."""

    def __init__(self, session: AsyncSession):
        """Initialize gateway transaction repository."""
        super().__init__(GatewayTransaction, session)

    # ==================== Core Transaction Operations ====================

    async def create_transaction(
        self,
        payment_id: UUID,
        gateway_name: GatewayProvider,
        transaction_type: GatewayTransactionType,
        transaction_amount: Decimal,
        currency: str = "INR",
        request_payload: dict | None = None,
        metadata: dict | None = None,
    ) -> GatewayTransaction:
        """
        Create a new gateway transaction.
        
        Args:
            payment_id: Payment ID
            gateway_name: Payment gateway provider
            transaction_type: Type of transaction
            transaction_amount: Transaction amount
            currency: Currency code
            request_payload: Request payload sent to gateway
            metadata: Additional metadata
            
        Returns:
            Created gateway transaction
        """
        transaction_reference = await self._generate_transaction_reference(gateway_name)
        
        transaction_data = {
            "payment_id": payment_id,
            "gateway_name": gateway_name,
            "transaction_type": transaction_type,
            "transaction_status": GatewayTransactionStatus.INITIATED,
            "transaction_reference": transaction_reference,
            "transaction_amount": transaction_amount,
            "currency": currency,
            "request_payload": request_payload,
            "initiated_at": datetime.utcnow(),
            "metadata": metadata or {},
        }
        
        return await self.create(transaction_data)

    async def update_transaction_status(
        self,
        transaction_id: UUID,
        status: GatewayTransactionStatus,
        gateway_payment_id: str | None = None,
        gateway_transaction_id: str | None = None,
        response_payload: dict | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> GatewayTransaction:
        """
        Update transaction status.
        
        Args:
            transaction_id: Transaction ID
            status: New transaction status
            gateway_payment_id: Payment ID from gateway
            gateway_transaction_id: Transaction ID from gateway
            response_payload: Response from gateway
            error_code: Error code if failed
            error_message: Error message if failed
            
        Returns:
            Updated transaction
        """
        now = datetime.utcnow()
        update_data = {
            "transaction_status": status,
            "response_payload": response_payload,
        }
        
        if gateway_payment_id:
            update_data["gateway_payment_id"] = gateway_payment_id
        
        if gateway_transaction_id:
            update_data["gateway_transaction_id"] = gateway_transaction_id
        
        if status == GatewayTransactionStatus.PROCESSING:
            update_data["processing_started_at"] = now
        elif status == GatewayTransactionStatus.SUCCESS:
            update_data["completed_at"] = now
        elif status == GatewayTransactionStatus.FAILED:
            update_data["failed_at"] = now
            update_data["error_code"] = error_code
            update_data["error_message"] = error_message
        elif status == GatewayTransactionStatus.CANCELLED:
            update_data["cancelled_at"] = now
        elif status == GatewayTransactionStatus.TIMEOUT:
            update_data["timeout_at"] = now
        
        return await self.update(transaction_id, update_data)

    async def record_webhook(
        self,
        transaction_id: UUID,
        webhook_payload: dict,
        webhook_event_type: str,
        webhook_signature: str | None = None,
    ) -> GatewayTransaction:
        """
        Record webhook received from gateway.
        
        Args:
            transaction_id: Transaction ID
            webhook_payload: Webhook data
            webhook_event_type: Type of webhook event
            webhook_signature: Webhook signature for verification
            
        Returns:
            Updated transaction
        """
        update_data = {
            "webhook_payload": webhook_payload,
            "webhook_event_type": webhook_event_type,
            "webhook_signature": webhook_signature,
            "webhook_received_at": datetime.utcnow(),
        }
        
        return await self.update(transaction_id, update_data)

    async def mark_verified(
        self,
        transaction_id: UUID,
        verification_method: str = "signature",
    ) -> GatewayTransaction:
        """
        Mark transaction as verified.
        
        Args:
            transaction_id: Transaction ID
            verification_method: Method used for verification
            
        Returns:
            Updated transaction
        """
        update_data = {
            "is_verified": True,
            "verified_at": datetime.utcnow(),
            "verification_method": verification_method,
        }
        
        return await self.update(transaction_id, update_data)

    async def record_settlement(
        self,
        transaction_id: UUID,
        settlement_id: str,
        settlement_amount: Decimal,
        settlement_utr: str | None = None,
    ) -> GatewayTransaction:
        """
        Record settlement information.
        
        Args:
            transaction_id: Transaction ID
            settlement_id: Settlement batch ID
            settlement_amount: Settled amount
            settlement_utr: Settlement UTR
            
        Returns:
            Updated transaction
        """
        update_data = {
            "settlement_id": settlement_id,
            "settlement_date": datetime.utcnow(),
            "settlement_amount": settlement_amount,
            "settlement_utr": settlement_utr,
        }
        
        return await self.update(transaction_id, update_data)

    # ==================== Query Methods ====================

    async def find_by_gateway_order_id(
        self,
        gateway_order_id: str,
    ) -> GatewayTransaction | None:
        """
        Find transaction by gateway order ID.
        
        Args:
            gateway_order_id: Gateway order ID
            
        Returns:
            Transaction if found
        """
        query = select(GatewayTransaction).where(
            GatewayTransaction.gateway_order_id == gateway_order_id,
            GatewayTransaction.deleted_at.is_(None),
        )
        
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def find_by_gateway_transaction_id(
        self,
        gateway_transaction_id: str,
    ) -> GatewayTransaction | None:
        """
        Find transaction by gateway transaction ID.
        
        Args:
            gateway_transaction_id: Gateway transaction ID
            
        Returns:
            Transaction if found
        """
        query = select(GatewayTransaction).where(
            GatewayTransaction.gateway_transaction_id == gateway_transaction_id,
            GatewayTransaction.deleted_at.is_(None),
        )
        
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def find_by_payment(
        self,
        payment_id: UUID,
        transaction_type: GatewayTransactionType | None = None,
    ) -> list[GatewayTransaction]:
        """
        Find transactions for a payment.
        
        Args:
            payment_id: Payment ID
            transaction_type: Optional transaction type filter
            
        Returns:
            List of transactions
        """
        query = select(GatewayTransaction).where(
            GatewayTransaction.payment_id == payment_id,
            GatewayTransaction.deleted_at.is_(None),
        )
        
        if transaction_type:
            query = query.where(GatewayTransaction.transaction_type == transaction_type)
        
        query = query.order_by(GatewayTransaction.initiated_at.desc())
        
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def find_pending_transactions(
        self,
        gateway_name: GatewayProvider | None = None,
        older_than_minutes: int | None = None,
    ) -> list[GatewayTransaction]:
        """
        Find pending transactions.
        
        Args:
            gateway_name: Optional gateway filter
            older_than_minutes: Find transactions older than specified minutes
            
        Returns:
            List of pending transactions
        """
        query = select(GatewayTransaction).where(
            GatewayTransaction.transaction_status.in_([
                GatewayTransactionStatus.INITIATED,
                GatewayTransactionStatus.PENDING,
                GatewayTransactionStatus.PROCESSING,
            ]),
            GatewayTransaction.deleted_at.is_(None),
        )
        
        if gateway_name:
            query = query.where(GatewayTransaction.gateway_name == gateway_name)
        
        if older_than_minutes:
            cutoff_time = datetime.utcnow() - timedelta(minutes=older_than_minutes)
            query = query.where(GatewayTransaction.initiated_at < cutoff_time)
        
        query = query.order_by(GatewayTransaction.initiated_at.asc())
        
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def find_failed_transactions(
        self,
        gateway_name: GatewayProvider | None = None,
        error_code: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[GatewayTransaction]:
        """
        Find failed transactions.
        
        Args:
            gateway_name: Optional gateway filter
            error_code: Optional error code filter
            start_date: Start date filter
            end_date: End date filter
            
        Returns:
            List of failed transactions
        """
        query = select(GatewayTransaction).where(
            GatewayTransaction.transaction_status == GatewayTransactionStatus.FAILED,
            GatewayTransaction.deleted_at.is_(None),
        )
        
        if gateway_name:
            query = query.where(GatewayTransaction.gateway_name == gateway_name)
        
        if error_code:
            query = query.where(GatewayTransaction.error_code == error_code)
        
        if start_date:
            query = query.where(GatewayTransaction.failed_at >= start_date)
        
        if end_date:
            query = query.where(GatewayTransaction.failed_at <= end_date)
        
        query = query.order_by(GatewayTransaction.failed_at.desc())
        
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def find_unverified_transactions(
        self,
        gateway_name: GatewayProvider | None = None,
        older_than_hours: int = 1,
    ) -> list[GatewayTransaction]:
        """
        Find unverified successful transactions.
        
        Args:
            gateway_name: Optional gateway filter
            older_than_hours: Find transactions older than specified hours
            
        Returns:
            List of unverified transactions
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=older_than_hours)
        
        query = select(GatewayTransaction).where(
            GatewayTransaction.transaction_status == GatewayTransactionStatus.SUCCESS,
            GatewayTransaction.is_verified == False,
            GatewayTransaction.completed_at < cutoff_time,
            GatewayTransaction.deleted_at.is_(None),
        )
        
        if gateway_name:
            query = query.where(GatewayTransaction.gateway_name == gateway_name)
        
        query = query.order_by(GatewayTransaction.completed_at.asc())
        
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def find_unsettled_transactions(
        self,
        gateway_name: GatewayProvider | None = None,
        older_than_days: int = 2,
    ) -> list[GatewayTransaction]:
        """
        Find successful but unsettled transactions.
        
        Args:
            gateway_name: Optional gateway filter
            older_than_days: Find transactions older than specified days
            
        Returns:
            List of unsettled transactions
        """
        cutoff_date = datetime.utcnow() - timedelta(days=older_than_days)
        
        query = select(GatewayTransaction).where(
            GatewayTransaction.transaction_status == GatewayTransactionStatus.SUCCESS,
            GatewayTransaction.settlement_id.is_(None),
            GatewayTransaction.completed_at < cutoff_date,
            GatewayTransaction.deleted_at.is_(None),
        )
        
        if gateway_name:
            query = query.where(GatewayTransaction.gateway_name == gateway_name)
        
        query = query.order_by(GatewayTransaction.completed_at.asc())
        
        result = await self.session.execute(query)
        return list(result.scalars().all())

    # ==================== Analytics Methods ====================

    async def calculate_gateway_performance(
        self,
        gateway_name: GatewayProvider,
        start_date: datetime,
        end_date: datetime,
    ) -> dict[str, Any]:
        """
        Calculate gateway performance metrics.
        
        Args:
            gateway_name: Gateway provider
            start_date: Start date
            end_date: End date
            
        Returns:
            Performance metrics
        """
        # Total transactions
        total_query = select(func.count(GatewayTransaction.id)).where(
            GatewayTransaction.gateway_name == gateway_name,
            GatewayTransaction.initiated_at >= start_date,
            GatewayTransaction.initiated_at <= end_date,
            GatewayTransaction.deleted_at.is_(None),
        )
        total_result = await self.session.execute(total_query)
        total = total_result.scalar() or 0
        
        # Successful transactions
        success_query = select(func.count(GatewayTransaction.id)).where(
            GatewayTransaction.gateway_name == gateway_name,
            GatewayTransaction.transaction_status == GatewayTransactionStatus.SUCCESS,
            GatewayTransaction.initiated_at >= start_date,
            GatewayTransaction.initiated_at <= end_date,
            GatewayTransaction.deleted_at.is_(None),
        )
        success_result = await self.session.execute(success_query)
        success = success_result.scalar() or 0
        
        # Failed transactions
        failed_query = select(func.count(GatewayTransaction.id)).where(
            GatewayTransaction.gateway_name == gateway_name,
            GatewayTransaction.transaction_status == GatewayTransactionStatus.FAILED,
            GatewayTransaction.initiated_at >= start_date,
            GatewayTransaction.initiated_at <= end_date,
            GatewayTransaction.deleted_at.is_(None),
        )
        failed_result = await self.session.execute(failed_query)
        failed = failed_result.scalar() or 0
        
        # Average response time
        avg_time_query = select(
            func.avg(GatewayTransaction.response_time_ms)
        ).where(
            GatewayTransaction.gateway_name == gateway_name,
            GatewayTransaction.response_time_ms.isnot(None),
            GatewayTransaction.initiated_at >= start_date,
            GatewayTransaction.initiated_at <= end_date,
            GatewayTransaction.deleted_at.is_(None),
        )
        avg_time_result = await self.session.execute(avg_time_query)
        avg_time = avg_time_result.scalar() or 0
        
        # Total amount processed
        amount_query = select(
            func.sum(GatewayTransaction.transaction_amount)
        ).where(
            GatewayTransaction.gateway_name == gateway_name,
            GatewayTransaction.transaction_status == GatewayTransactionStatus.SUCCESS,
            GatewayTransaction.initiated_at >= start_date,
            GatewayTransaction.initiated_at <= end_date,
            GatewayTransaction.deleted_at.is_(None),
        )
        amount_result = await self.session.execute(amount_query)
        total_amount = amount_result.scalar() or Decimal("0")
        
        success_rate = (success / total * 100) if total > 0 else 0
        
        return {
            "gateway_name": gateway_name.value,
            "total_transactions": total,
            "successful_transactions": success,
            "failed_transactions": failed,
            "pending_transactions": total - success - failed,
            "success_rate": round(success_rate, 2),
            "average_response_time_ms": round(avg_time, 2),
            "total_amount_processed": float(total_amount),
        }

    async def get_failure_reasons(
        self,
        gateway_name: GatewayProvider,
        start_date: datetime,
        end_date: datetime,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Get top failure reasons for a gateway.
        
        Args:
            gateway_name: Gateway provider
            start_date: Start date
            end_date: End date
            limit: Maximum results
            
        Returns:
            List of failure reasons with counts
        """
        query = select(
            GatewayTransaction.error_code,
            GatewayTransaction.error_message,
            func.count(GatewayTransaction.id).label("count"),
        ).where(
            GatewayTransaction.gateway_name == gateway_name,
            GatewayTransaction.transaction_status == GatewayTransactionStatus.FAILED,
            GatewayTransaction.failed_at >= start_date,
            GatewayTransaction.failed_at <= end_date,
            GatewayTransaction.deleted_at.is_(None),
        ).group_by(
            GatewayTransaction.error_code,
            GatewayTransaction.error_message,
        ).order_by(func.count(GatewayTransaction.id).desc()).limit(limit)
        
        result = await self.session.execute(query)
        
        return [
            {
                "error_code": row.error_code,
                "error_message": row.error_message,
                "count": row.count,
            }
            for row in result.all()
        ]

    async def get_payment_method_distribution(
        self,
        gateway_name: GatewayProvider,
        start_date: datetime,
        end_date: datetime,
    ) -> list[dict[str, Any]]:
        """
        Get payment method distribution for a gateway.
        
        Args:
            gateway_name: Gateway provider
            start_date: Start date
            end_date: End date
            
        Returns:
            Payment method distribution
        """
        query = select(
            GatewayTransaction.payment_method_used,
            func.count(GatewayTransaction.id).label("count"),
            func.sum(GatewayTransaction.transaction_amount).label("total_amount"),
        ).where(
            GatewayTransaction.gateway_name == gateway_name,
            GatewayTransaction.transaction_status == GatewayTransactionStatus.SUCCESS,
            GatewayTransaction.payment_method_used.isnot(None),
            GatewayTransaction.completed_at >= start_date,
            GatewayTransaction.completed_at <= end_date,
            GatewayTransaction.deleted_at.is_(None),
        ).group_by(GatewayTransaction.payment_method_used)
        
        result = await self.session.execute(query)
        
        return [
            {
                "payment_method": row.payment_method_used,
                "count": row.count,
                "total_amount": float(row.total_amount or Decimal("0")),
            }
            for row in result.all()
        ]

    # ==================== Retry Management ====================

    async def increment_retry_count(
        self,
        transaction_id: UUID,
    ) -> GatewayTransaction:
        """
        Increment retry count for a transaction.
        
        Args:
            transaction_id: Transaction ID
            
        Returns:
            Updated transaction
        """
        transaction = await self.get_by_id(transaction_id)
        if not transaction:
            raise ValueError(f"Transaction not found: {transaction_id}")
        
        update_data = {
            "retry_count": transaction.retry_count + 1,
            "last_retry_at": datetime.utcnow(),
        }
        
        return await self.update(transaction_id, update_data)

    # ==================== Helper Methods ====================

    async def _generate_transaction_reference(
        self,
        gateway_name: GatewayProvider,
    ) -> str:
        """Generate unique transaction reference."""
        # Get count of transactions for today
        today_start = datetime.combine(datetime.utcnow().date(), datetime.min.time())
        
        query = select(func.count(GatewayTransaction.id)).where(
            GatewayTransaction.gateway_name == gateway_name,
            GatewayTransaction.initiated_at >= today_start,
        )
        
        result = await self.session.execute(query)
        count = result.scalar() or 0
        
        # Format: GTX-GATEWAY-YYYYMMDD-NNNN
        gateway_code = gateway_name.value[:3].upper()
        date_str = datetime.utcnow().strftime('%Y%m%d')
        return f"GTX-{gateway_code}-{date_str}-{count + 1:04d}"