# --- File: payment_gateway_repository.py ---
"""
Payment Gateway Repository.

Simplified gateway transaction tracking repository.
This is a lighter version compared to gateway_transaction_repository.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payment.payment_gateway import GatewayTransaction
from app.repositories.base.base_repository import BaseRepository


class PaymentGatewayRepository(BaseRepository[GatewayTransaction]):
    """Repository for simplified gateway transaction operations."""

    def __init__(self, session: AsyncSession):
        """Initialize payment gateway repository."""
        super().__init__(GatewayTransaction, session)

    # ==================== Core Gateway Operations ====================

    async def create_gateway_transaction(
        self,
        payment_id: UUID,
        gateway_name: str,
        gateway_order_id: str,
        transaction_type: str,
        transaction_amount: Decimal,
        request_payload: dict | None = None,
        metadata: dict | None = None,
    ) -> GatewayTransaction:
        """
        Create a new gateway transaction record.
        
        Args:
            payment_id: Payment ID
            gateway_name: Gateway name (razorpay, stripe, etc.)
            gateway_order_id: Order ID from gateway
            transaction_type: Type of transaction
            transaction_amount: Transaction amount
            request_payload: Request sent to gateway
            metadata: Additional metadata
            
        Returns:
            Created gateway transaction
        """
        transaction_data = {
            "payment_id": payment_id,
            "gateway_name": gateway_name,
            "gateway_order_id": gateway_order_id,
            "transaction_type": transaction_type,
            "transaction_status": "initiated",
            "transaction_amount": transaction_amount,
            "request_payload": request_payload,
            "initiated_at": datetime.utcnow(),
            "metadata": metadata or {},
        }
        
        return await self.create(transaction_data)

    async def update_transaction_response(
        self,
        transaction_id: UUID,
        gateway_payment_id: str,
        gateway_transaction_id: str | None = None,
        response_payload: dict | None = None,
        transaction_status: str = "success",
    ) -> GatewayTransaction:
        """
        Update transaction with gateway response.
        
        Args:
            transaction_id: Transaction ID
            gateway_payment_id: Payment ID from gateway
            gateway_transaction_id: Transaction ID from gateway
            response_payload: Response from gateway
            transaction_status: Status to set
            
        Returns:
            Updated transaction
        """
        now = datetime.utcnow()
        
        update_data = {
            "gateway_payment_id": gateway_payment_id,
            "gateway_transaction_id": gateway_transaction_id,
            "response_payload": response_payload,
            "transaction_status": transaction_status,
        }
        
        if transaction_status == "success":
            update_data["completed_at"] = now
        elif transaction_status == "failed":
            update_data["failed_at"] = now
        
        return await self.update(transaction_id, update_data)

    async def record_webhook_data(
        self,
        transaction_id: UUID,
        webhook_payload: dict,
    ) -> GatewayTransaction:
        """
        Record webhook data received from gateway.
        
        Args:
            transaction_id: Transaction ID
            webhook_payload: Webhook payload
            
        Returns:
            Updated transaction
        """
        update_data = {
            "webhook_payload": webhook_payload,
            "webhook_received_at": datetime.utcnow(),
        }
        
        return await self.update(transaction_id, update_data)

    async def mark_verified(
        self,
        transaction_id: UUID,
        signature: str | None = None,
    ) -> GatewayTransaction:
        """
        Mark transaction as verified.
        
        Args:
            transaction_id: Transaction ID
            signature: Verification signature
            
        Returns:
            Updated transaction
        """
        update_data = {
            "is_verified": True,
            "verified_at": datetime.utcnow(),
            "signature": signature,
        }
        
        return await self.update(transaction_id, update_data)

    async def update_payment_method_details(
        self,
        transaction_id: UUID,
        payment_method_used: str,
        card_last4: str | None = None,
        card_network: str | None = None,
        bank_name: str | None = None,
        upi_id: str | None = None,
    ) -> GatewayTransaction:
        """
        Update payment method details.
        
        Args:
            transaction_id: Transaction ID
            payment_method_used: Payment method used
            card_last4: Last 4 digits of card
            card_network: Card network
            bank_name: Bank name
            upi_id: UPI ID
            
        Returns:
            Updated transaction
        """
        update_data = {
            "payment_method_used": payment_method_used,
            "card_last4": card_last4,
            "card_network": card_network,
            "bank_name": bank_name,
            "upi_id": upi_id,
        }
        
        return await self.update(transaction_id, update_data)

    async def record_gateway_fees(
        self,
        transaction_id: UUID,
        gateway_fee: Decimal,
        tax_amount: Decimal | None = None,
    ) -> GatewayTransaction:
        """
        Record gateway fees for transaction.
        
        Args:
            transaction_id: Transaction ID
            gateway_fee: Gateway processing fee
            tax_amount: Tax on fee
            
        Returns:
            Updated transaction
        """
        transaction = await self.get_by_id(transaction_id)
        if not transaction:
            raise ValueError(f"Transaction not found: {transaction_id}")
        
        net_amount = transaction.transaction_amount - gateway_fee
        if tax_amount:
            net_amount -= tax_amount
        
        update_data = {
            "gateway_fee": gateway_fee,
            "tax_amount": tax_amount,
            "net_amount": net_amount,
        }
        
        return await self.update(transaction_id, update_data)

    async def record_transaction_error(
        self,
        transaction_id: UUID,
        error_code: str,
        error_message: str,
        error_description: str | None = None,
    ) -> GatewayTransaction:
        """
        Record transaction error details.
        
        Args:
            transaction_id: Transaction ID
            error_code: Error code
            error_message: Error message
            error_description: Detailed error description
            
        Returns:
            Updated transaction
        """
        update_data = {
            "transaction_status": "failed",
            "failed_at": datetime.utcnow(),
            "error_code": error_code,
            "error_message": error_message,
            "error_description": error_description,
        }
        
        return await self.update(transaction_id, update_data)

    # ==================== Query Methods ====================

    async def find_by_gateway_order_id(
        self,
        gateway_order_id: str,
        gateway_name: str | None = None,
    ) -> GatewayTransaction | None:
        """
        Find transaction by gateway order ID.
        
        Args:
            gateway_order_id: Gateway order ID
            gateway_name: Optional gateway name filter
            
        Returns:
            Transaction if found
        """
        query = select(GatewayTransaction).where(
            GatewayTransaction.gateway_order_id == gateway_order_id,
            GatewayTransaction.deleted_at.is_(None),
        )
        
        if gateway_name:
            query = query.where(GatewayTransaction.gateway_name == gateway_name)
        
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def find_by_gateway_payment_id(
        self,
        gateway_payment_id: str,
    ) -> GatewayTransaction | None:
        """
        Find transaction by gateway payment ID.
        
        Args:
            gateway_payment_id: Gateway payment ID
            
        Returns:
            Transaction if found
        """
        query = select(GatewayTransaction).where(
            GatewayTransaction.gateway_payment_id == gateway_payment_id,
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

    async def find_by_payment_id(
        self,
        payment_id: UUID,
        transaction_type: str | None = None,
    ) -> list[GatewayTransaction]:
        """
        Find all transactions for a payment.
        
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

    async def find_by_gateway_and_status(
        self,
        gateway_name: str,
        transaction_status: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[GatewayTransaction]:
        """
        Find transactions by gateway and status.
        
        Args:
            gateway_name: Gateway name
            transaction_status: Transaction status
            start_date: Optional start date
            end_date: Optional end date
            limit: Maximum results
            offset: Offset for pagination
            
        Returns:
            List of transactions
        """
        query = select(GatewayTransaction).where(
            GatewayTransaction.gateway_name == gateway_name,
            GatewayTransaction.transaction_status == transaction_status,
            GatewayTransaction.deleted_at.is_(None),
        )
        
        if start_date:
            query = query.where(GatewayTransaction.initiated_at >= start_date)
        
        if end_date:
            query = query.where(GatewayTransaction.initiated_at <= end_date)
        
        query = query.order_by(GatewayTransaction.initiated_at.desc()).limit(limit).offset(offset)
        
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def find_pending_transactions(
        self,
        gateway_name: str | None = None,
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
            GatewayTransaction.transaction_status.in_(["initiated", "pending", "processing"]),
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

    async def find_unverified_transactions(
        self,
        gateway_name: str | None = None,
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
            GatewayTransaction.transaction_status == "success",
            GatewayTransaction.is_verified == False,
            GatewayTransaction.completed_at < cutoff_time,
            GatewayTransaction.deleted_at.is_(None),
        )
        
        if gateway_name:
            query = query.where(GatewayTransaction.gateway_name == gateway_name)
        
        query = query.order_by(GatewayTransaction.completed_at.asc())
        
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def find_failed_transactions(
        self,
        gateway_name: str | None = None,
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
            GatewayTransaction.transaction_status == "failed",
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

    # ==================== Analytics Methods ====================

    async def get_gateway_statistics(
        self,
        gateway_name: str,
        start_date: datetime,
        end_date: datetime,
    ) -> dict[str, Any]:
        """
        Get statistics for a specific gateway.
        
        Args:
            gateway_name: Gateway name
            start_date: Start date
            end_date: End date
            
        Returns:
            Gateway statistics
        """
        query = select(
            func.count(GatewayTransaction.id).label("total"),
            func.count(GatewayTransaction.id).filter(
                GatewayTransaction.transaction_status == "success"
            ).label("successful"),
            func.count(GatewayTransaction.id).filter(
                GatewayTransaction.transaction_status == "failed"
            ).label("failed"),
            func.sum(GatewayTransaction.transaction_amount).filter(
                GatewayTransaction.transaction_status == "success"
            ).label("total_amount"),
            func.sum(GatewayTransaction.gateway_fee).label("total_fees"),
            func.avg(GatewayTransaction.gateway_fee).label("avg_fee"),
        ).where(
            GatewayTransaction.gateway_name == gateway_name,
            GatewayTransaction.initiated_at >= start_date,
            GatewayTransaction.initiated_at <= end_date,
            GatewayTransaction.deleted_at.is_(None),
        )
        
        result = await self.session.execute(query)
        row = result.one()
        
        success_rate = (row.successful / row.total * 100) if row.total > 0 else 0
        
        return {
            "gateway_name": gateway_name,
            "total_transactions": row.total,
            "successful_transactions": row.successful,
            "failed_transactions": row.failed,
            "success_rate": round(success_rate, 2),
            "total_amount_processed": float(row.total_amount or Decimal("0")),
            "total_fees": float(row.total_fees or Decimal("0")),
            "average_fee": float(row.avg_fee or Decimal("0")),
        }

    async def get_payment_method_breakdown(
        self,
        gateway_name: str,
        start_date: datetime,
        end_date: datetime,
    ) -> list[dict[str, Any]]:
        """
        Get payment method breakdown for a gateway.
        
        Args:
            gateway_name: Gateway name
            start_date: Start date
            end_date: End date
            
        Returns:
            Payment method breakdown
        """
        query = select(
            GatewayTransaction.payment_method_used,
            func.count(GatewayTransaction.id).label("count"),
            func.sum(GatewayTransaction.transaction_amount).label("total_amount"),
        ).where(
            GatewayTransaction.gateway_name == gateway_name,
            GatewayTransaction.transaction_status == "success",
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

    async def get_error_statistics(
        self,
        gateway_name: str,
        start_date: datetime,
        end_date: datetime,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Get error statistics for a gateway.
        
        Args:
            gateway_name: Gateway name
            start_date: Start date
            end_date: End date
            limit: Maximum error types to return
            
        Returns:
            Top errors with counts
        """
        query = select(
            GatewayTransaction.error_code,
            GatewayTransaction.error_message,
            func.count(GatewayTransaction.id).label("count"),
        ).where(
            GatewayTransaction.gateway_name == gateway_name,
            GatewayTransaction.transaction_status == "failed",
            GatewayTransaction.error_code.isnot(None),
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

    async def get_transaction_volume_by_hour(
        self,
        gateway_name: str,
        target_date: datetime,
    ) -> list[dict[str, Any]]:
        """
        Get hourly transaction volume for a specific date.
        
        Args:
            gateway_name: Gateway name
            target_date: Target date
            
        Returns:
            Hourly transaction data
        """
        start_of_day = datetime.combine(target_date.date(), datetime.min.time())
        end_of_day = datetime.combine(target_date.date(), datetime.max.time())
        
        query = select(
            func.date_part('hour', GatewayTransaction.initiated_at).label("hour"),
            func.count(GatewayTransaction.id).label("count"),
            func.sum(GatewayTransaction.transaction_amount).label("amount"),
        ).where(
            GatewayTransaction.gateway_name == gateway_name,
            GatewayTransaction.initiated_at >= start_of_day,
            GatewayTransaction.initiated_at <= end_of_day,
            GatewayTransaction.deleted_at.is_(None),
        ).group_by(func.date_part('hour', GatewayTransaction.initiated_at)).order_by("hour")
        
        result = await self.session.execute(query)
        
        return [
            {
                "hour": int(row.hour),
                "transaction_count": row.count,
                "total_amount": float(row.amount or Decimal("0")),
            }
            for row in result.all()
        ]

    async def get_verification_statistics(
        self,
        gateway_name: str | None = None,
    ) -> dict[str, Any]:
        """
        Get verification statistics.
        
        Args:
            gateway_name: Optional gateway filter
            
        Returns:
            Verification statistics
        """
        query = select(
            func.count(GatewayTransaction.id).label("total"),
            func.count(GatewayTransaction.id).filter(
                GatewayTransaction.is_verified == True
            ).label("verified"),
            func.count(GatewayTransaction.id).filter(
                and_(
                    GatewayTransaction.transaction_status == "success",
                    GatewayTransaction.is_verified == False,
                )
            ).label("unverified_success"),
        ).where(
            GatewayTransaction.deleted_at.is_(None),
        )
        
        if gateway_name:
            query = query.where(GatewayTransaction.gateway_name == gateway_name)
        
        result = await self.session.execute(query)
        row = result.one()
        
        verification_rate = (row.verified / row.total * 100) if row.total > 0 else 0
        
        return {
            "total_transactions": row.total,
            "verified_transactions": row.verified,
            "unverified_successful": row.unverified_success,
            "verification_rate": round(verification_rate, 2),
        }

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

    async def find_retriable_transactions(
        self,
        gateway_name: str | None = None,
        max_retries: int = 3,
    ) -> list[GatewayTransaction]:
        """
        Find transactions that can be retried.
        
        Args:
            gateway_name: Optional gateway filter
            max_retries: Maximum retry attempts
            
        Returns:
            List of retriable transactions
        """
        query = select(GatewayTransaction).where(
            GatewayTransaction.transaction_status == "failed",
            GatewayTransaction.retry_count < max_retries,
            GatewayTransaction.deleted_at.is_(None),
        )
        
        if gateway_name:
            query = query.where(GatewayTransaction.gateway_name == gateway_name)
        
        query = query.order_by(GatewayTransaction.failed_at.asc())
        
        result = await self.session.execute(query)
        return list(result.scalars().all())

    # ==================== Customer Information ====================

    async def find_by_customer_email(
        self,
        customer_email: str,
        limit: int = 50,
    ) -> list[GatewayTransaction]:
        """
        Find transactions by customer email.
        
        Args:
            customer_email: Customer email
            limit: Maximum results
            
        Returns:
            List of transactions
        """
        query = select(GatewayTransaction).where(
            func.lower(GatewayTransaction.customer_email) == customer_email.lower(),
            GatewayTransaction.deleted_at.is_(None),
        ).order_by(GatewayTransaction.initiated_at.desc()).limit(limit)
        
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def find_by_customer_phone(
        self,
        customer_phone: str,
        limit: int = 50,
    ) -> list[GatewayTransaction]:
        """
        Find transactions by customer phone.
        
        Args:
            customer_phone: Customer phone
            limit: Maximum results
            
        Returns:
            List of transactions
        """
        query = select(GatewayTransaction).where(
            GatewayTransaction.customer_phone == customer_phone,
            GatewayTransaction.deleted_at.is_(None),
        ).order_by(GatewayTransaction.initiated_at.desc()).limit(limit)
        
        result = await self.session.execute(query)
        return list(result.scalars().all())

    # ==================== Bulk Operations ====================

    async def bulk_verify_transactions(
        self,
        transaction_ids: list[UUID],
    ) -> int:
        """
        Bulk verify multiple transactions.
        
        Args:
            transaction_ids: List of transaction IDs
            
        Returns:
            Number of transactions verified
        """
        from sqlalchemy import update as sql_update
        
        stmt = sql_update(GatewayTransaction).where(
            GatewayTransaction.id.in_(transaction_ids),
            GatewayTransaction.deleted_at.is_(None),
        ).values(
            is_verified=True,
            verified_at=datetime.utcnow(),
        )
        
        result = await self.session.execute(stmt)
        await self.session.commit()
        
        return result.rowcount

    async def bulk_update_status(
        self,
        transaction_ids: list[UUID],
        new_status: str,
    ) -> int:
        """
        Bulk update transaction status.
        
        Args:
            transaction_ids: List of transaction IDs
            new_status: New status to set
            
        Returns:
            Number of transactions updated
        """
        from sqlalchemy import update as sql_update
        
        stmt = sql_update(GatewayTransaction).where(
            GatewayTransaction.id.in_(transaction_ids),
            GatewayTransaction.deleted_at.is_(None),
        ).values(transaction_status=new_status)
        
        result = await self.session.execute(stmt)
        await self.session.commit()
        
        return result.rowcount