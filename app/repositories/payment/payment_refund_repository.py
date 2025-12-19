# --- File: payment_refund_repository.py ---
"""
Payment Refund Repository.

Handles payment refund requests, approvals, and processing.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payment.payment_refund import PaymentRefund, RefundStatus
from app.repositories.base.base_repository import BaseRepository


class PaymentRefundRepository(BaseRepository[PaymentRefund]):
    """Repository for payment refund operations."""

    def __init__(self, session: AsyncSession):
        """Initialize payment refund repository."""
        super().__init__(PaymentRefund, session)

    # ==================== Core Refund Operations ====================

    async def create_refund_request(
        self,
        payment_id: UUID,
        requested_by: UUID,
        refund_amount: Decimal,
        original_amount: Decimal,
        refund_reason: str,
        refund_category: str | None = None,
        metadata: dict | None = None,
    ) -> PaymentRefund:
        """
        Create a new refund request.
        
        Args:
            payment_id: Payment ID
            requested_by: User requesting refund
            refund_amount: Amount to refund
            original_amount: Original payment amount
            refund_reason: Reason for refund
            refund_category: Category of refund
            metadata: Additional metadata
            
        Returns:
            Created refund request
        """
        refund_reference = await self._generate_refund_reference()
        
        is_partial = refund_amount < original_amount
        
        refund_data = {
            "payment_id": payment_id,
            "requested_by": requested_by,
            "refund_reference": refund_reference,
            "refund_amount": refund_amount,
            "original_amount": original_amount,
            "is_partial": is_partial,
            "refund_reason": refund_reason,
            "refund_category": refund_category,
            "refund_status": RefundStatus.PENDING,
            "requested_at": datetime.utcnow(),
            "metadata": metadata or {},
        }
        
        return await self.create(refund_data)

    async def approve_refund(
        self,
        refund_id: UUID,
        approved_by: UUID,
        approval_notes: str | None = None,
    ) -> PaymentRefund:
        """
        Approve a refund request.
        
        Args:
            refund_id: Refund ID
            approved_by: User approving the refund
            approval_notes: Approval notes
            
        Returns:
            Updated refund
        """
        update_data = {
            "refund_status": RefundStatus.APPROVED,
            "approved_by": approved_by,
            "approved_at": datetime.utcnow(),
            "approval_notes": approval_notes,
        }
        
        return await self.update(refund_id, update_data)

    async def reject_refund(
        self,
        refund_id: UUID,
        approved_by: UUID,
        rejection_reason: str,
    ) -> PaymentRefund:
        """
        Reject a refund request.
        
        Args:
            refund_id: Refund ID
            approved_by: User rejecting the refund
            rejection_reason: Reason for rejection
            
        Returns:
            Updated refund
        """
        update_data = {
            "refund_status": RefundStatus.REJECTED,
            "approved_by": approved_by,
            "rejected_at": datetime.utcnow(),
            "rejection_reason": rejection_reason,
        }
        
        return await self.update(refund_id, update_data)

    async def initiate_refund_processing(
        self,
        refund_id: UUID,
        processed_by: UUID,
        gateway_refund_id: str | None = None,
    ) -> PaymentRefund:
        """
        Initiate refund processing.
        
        Args:
            refund_id: Refund ID
            processed_by: User processing the refund
            gateway_refund_id: Gateway refund ID
            
        Returns:
            Updated refund
        """
        update_data = {
            "refund_status": RefundStatus.PROCESSING,
            "processed_by": processed_by,
            "processed_at": datetime.utcnow(),
            "gateway_refund_id": gateway_refund_id,
        }
        
        return await self.update(refund_id, update_data)

    async def complete_refund(
        self,
        refund_id: UUID,
        processed_amount: Decimal,
        transaction_id: str | None = None,
        gateway_response: dict | None = None,
        processing_fee: Decimal | None = None,
    ) -> PaymentRefund:
        """
        Mark refund as completed.
        
        Args:
            refund_id: Refund ID
            processed_amount: Actually processed amount
            transaction_id: Transaction ID
            gateway_response: Gateway response
            processing_fee: Processing fee deducted
            
        Returns:
            Updated refund
        """
        update_data = {
            "refund_status": RefundStatus.COMPLETED,
            "completed_at": datetime.utcnow(),
            "processed_amount": processed_amount,
            "transaction_id": transaction_id,
            "gateway_response": gateway_response,
            "processing_fee": processing_fee,
        }
        
        return await self.update(refund_id, update_data)

    async def mark_refund_failed(
        self,
        refund_id: UUID,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> PaymentRefund:
        """
        Mark refund as failed.
        
        Args:
            refund_id: Refund ID
            error_code: Error code
            error_message: Error message
            
        Returns:
            Updated refund
        """
        update_data = {
            "refund_status": RefundStatus.FAILED,
            "failed_at": datetime.utcnow(),
            "error_code": error_code,
            "error_message": error_message,
        }
        
        return await self.update(refund_id, update_data)

    async def cancel_refund(
        self,
        refund_id: UUID,
    ) -> PaymentRefund:
        """
        Cancel a refund request.
        
        Args:
            refund_id: Refund ID
            
        Returns:
            Updated refund
        """
        update_data = {
            "refund_status": RefundStatus.CANCELLED,
        }
        
        return await self.update(refund_id, update_data)

    # ==================== Query Methods ====================

    async def find_by_reference(
        self,
        refund_reference: str,
    ) -> PaymentRefund | None:
        """
        Find refund by reference number.
        
        Args:
            refund_reference: Refund reference
            
        Returns:
            Refund if found
        """
        query = select(PaymentRefund).where(
            func.lower(PaymentRefund.refund_reference) == refund_reference.lower(),
            PaymentRefund.deleted_at.is_(None),
        )
        
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def find_by_payment(
        self,
        payment_id: UUID,
        status: RefundStatus | None = None,
    ) -> list[PaymentRefund]:
        """
        Find refunds for a payment.
        
        Args:
            payment_id: Payment ID
            status: Optional status filter
            
        Returns:
            List of refunds
        """
        query = select(PaymentRefund).where(
            PaymentRefund.payment_id == payment_id,
            PaymentRefund.deleted_at.is_(None),
        )
        
        if status:
            query = query.where(PaymentRefund.refund_status == status)
        
        query = query.order_by(PaymentRefund.requested_at.desc())
        
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def find_pending_refunds(
        self,
        older_than_hours: int | None = None,
    ) -> list[PaymentRefund]:
        """
        Find pending refund requests.
        
        Args:
            older_than_hours: Find requests older than specified hours
            
        Returns:
            List of pending refunds
        """
        query = select(PaymentRefund).where(
            PaymentRefund.refund_status == RefundStatus.PENDING,
            PaymentRefund.deleted_at.is_(None),
        )
        
        if older_than_hours:
            cutoff_time = datetime.utcnow() - timedelta(hours=older_than_hours)
            query = query.where(PaymentRefund.requested_at < cutoff_time)
        
        query = query.order_by(PaymentRefund.requested_at.asc())
        
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def find_approved_refunds(
        self,
        unprocessed_only: bool = True,
    ) -> list[PaymentRefund]:
        """
        Find approved refunds ready for processing.
        
        Args:
            unprocessed_only: Only return unprocessed approved refunds
            
        Returns:
            List of approved refunds
        """
        query = select(PaymentRefund).where(
            PaymentRefund.refund_status == RefundStatus.APPROVED,
            PaymentRefund.deleted_at.is_(None),
        )
        
        if unprocessed_only:
            query = query.where(PaymentRefund.processed_at.is_(None))
        
        query = query.order_by(PaymentRefund.approved_at.asc())
        
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def find_processing_refunds(
        self,
        older_than_hours: int = 24,
    ) -> list[PaymentRefund]:
        """
        Find refunds stuck in processing state.
        
        Args:
            older_than_hours: Find refunds processing longer than specified hours
            
        Returns:
            List of stuck refunds
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=older_than_hours)
        
        query = select(PaymentRefund).where(
            PaymentRefund.refund_status == RefundStatus.PROCESSING,
            PaymentRefund.processed_at < cutoff_time,
            PaymentRefund.deleted_at.is_(None),
        ).order_by(PaymentRefund.processed_at.asc())
        
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def find_by_requester(
        self,
        requested_by: UUID,
        status: RefundStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[PaymentRefund]:
        """
        Find refunds requested by a user.
        
        Args:
            requested_by: User ID
            status: Optional status filter
            limit: Maximum results
            offset: Offset for pagination
            
        Returns:
            List of refunds
        """
        query = select(PaymentRefund).where(
            PaymentRefund.requested_by == requested_by,
            PaymentRefund.deleted_at.is_(None),
        )
        
        if status:
            query = query.where(PaymentRefund.refund_status == status)
        
        query = query.order_by(PaymentRefund.requested_at.desc()).limit(limit).offset(offset)
        
        result = await self.session.execute(query)
        return list(result.scalars().all())

    # ==================== Analytics Methods ====================

    async def calculate_refund_statistics(
        self,
        start_date: datetime,
        end_date: datetime,
        refund_category: str | None = None,
    ) -> dict[str, Any]:
        """
        Calculate refund statistics for a period.
        
        Args:
            start_date: Start date
            end_date: End date
            refund_category: Optional category filter
            
        Returns:
            Refund statistics
        """
        query = select(
            func.count(PaymentRefund.id).label("total_refunds"),
            func.sum(PaymentRefund.refund_amount).label("total_amount"),
            func.avg(PaymentRefund.refund_amount).label("average_amount"),
            func.count(PaymentRefund.id).filter(
                PaymentRefund.is_partial == True
            ).label("partial_refunds"),
        ).where(
            PaymentRefund.requested_at >= start_date,
            PaymentRefund.requested_at <= end_date,
            PaymentRefund.deleted_at.is_(None),
        )
        
        if refund_category:
            query = query.where(PaymentRefund.refund_category == refund_category)
        
        result = await self.session.execute(query)
        row = result.one()
        
        # Status breakdown
        status_query = select(
            PaymentRefund.refund_status,
            func.count(PaymentRefund.id).label("count"),
        ).where(
            PaymentRefund.requested_at >= start_date,
            PaymentRefund.requested_at <= end_date,
            PaymentRefund.deleted_at.is_(None),
        ).group_by(PaymentRefund.refund_status)
        
        if refund_category:
            status_query = status_query.where(PaymentRefund.refund_category == refund_category)
        
        status_result = await self.session.execute(status_query)
        status_breakdown = {row.refund_status.value: row.count for row in status_result.all()}
        
        return {
            "total_refunds": row.total_refunds or 0,
            "total_amount": float(row.total_amount or Decimal("0")),
            "average_amount": float(row.average_amount or Decimal("0")),
            "partial_refunds": row.partial_refunds or 0,
            "full_refunds": (row.total_refunds or 0) - (row.partial_refunds or 0),
            "status_breakdown": status_breakdown,
        }

    async def get_refund_approval_time(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> dict[str, Any]:
        """
        Calculate average refund approval time.
        
        Args:
            start_date: Start date
            end_date: End date
            
        Returns:
            Approval time statistics
        """
        # Calculate time difference in hours
        from sqlalchemy import extract
        
        query = select(
            func.avg(
                extract('epoch', PaymentRefund.approved_at - PaymentRefund.requested_at) / 3600
            ).label("avg_hours"),
            func.min(
                extract('epoch', PaymentRefund.approved_at - PaymentRefund.requested_at) / 3600
            ).label("min_hours"),
            func.max(
                extract('epoch', PaymentRefund.approved_at - PaymentRefund.requested_at) / 3600
            ).label("max_hours"),
        ).where(
            PaymentRefund.approved_at.isnot(None),
            PaymentRefund.requested_at >= start_date,
            PaymentRefund.requested_at <= end_date,
            PaymentRefund.deleted_at.is_(None),
        )
        
        result = await self.session.execute(query)
        row = result.one()
        
        return {
            "average_approval_hours": round(row.avg_hours or 0, 2),
            "min_approval_hours": round(row.min_hours or 0, 2),
            "max_approval_hours": round(row.max_hours or 0, 2),
        }

    async def get_refund_categories_breakdown(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> list[dict[str, Any]]:
        """
        Get breakdown of refunds by category.
        
        Args:
            start_date: Start date
            end_date: End date
            
        Returns:
            Category breakdown
        """
        query = select(
            PaymentRefund.refund_category,
            func.count(PaymentRefund.id).label("count"),
            func.sum(PaymentRefund.refund_amount).label("total_amount"),
            func.avg(PaymentRefund.refund_amount).label("avg_amount"),
        ).where(
            PaymentRefund.refund_category.isnot(None),
            PaymentRefund.requested_at >= start_date,
            PaymentRefund.requested_at <= end_date,
            PaymentRefund.deleted_at.is_(None),
        ).group_by(PaymentRefund.refund_category).order_by(
            func.sum(PaymentRefund.refund_amount).desc()
        )
        
        result = await self.session.execute(query)
        
        return [
            {
                "category": row.refund_category,
                "count": row.count,
                "total_amount": float(row.total_amount or Decimal("0")),
                "average_amount": float(row.avg_amount or Decimal("0")),
            }
            for row in result.all()
        ]

    async def get_refund_success_rate(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> dict[str, Any]:
        """
        Calculate refund processing success rate.
        
        Args:
            start_date: Start date
            end_date: End date
            
        Returns:
            Success rate statistics
        """
        # Total processed (approved + processing + completed + failed)
        total_query = select(func.count(PaymentRefund.id)).where(
            PaymentRefund.refund_status.in_([
                RefundStatus.APPROVED,
                RefundStatus.PROCESSING,
                RefundStatus.COMPLETED,
                RefundStatus.FAILED,
            ]),
            PaymentRefund.requested_at >= start_date,
            PaymentRefund.requested_at <= end_date,
            PaymentRefund.deleted_at.is_(None),
        )
        total_result = await self.session.execute(total_query)
        total = total_result.scalar() or 0
        
        # Completed
        completed_query = select(func.count(PaymentRefund.id)).where(
            PaymentRefund.refund_status == RefundStatus.COMPLETED,
            PaymentRefund.requested_at >= start_date,
            PaymentRefund.requested_at <= end_date,
            PaymentRefund.deleted_at.is_(None),
        )
        completed_result = await self.session.execute(completed_query)
        completed = completed_result.scalar() or 0
        
        # Failed
        failed_query = select(func.count(PaymentRefund.id)).where(
            PaymentRefund.refund_status == RefundStatus.FAILED,
            PaymentRefund.requested_at >= start_date,
            PaymentRefund.requested_at <= end_date,
            PaymentRefund.deleted_at.is_(None),
        )
        failed_result = await self.session.execute(failed_query)
        failed = failed_result.scalar() or 0
        
        success_rate = (completed / total * 100) if total > 0 else 0
        
        return {
            "total_processed": total,
            "completed": completed,
            "failed": failed,
            "success_rate": round(success_rate, 2),
        }

    # ==================== Helper Methods ====================

    async def _generate_refund_reference(self) -> str:
        """Generate unique refund reference."""
        from datetime import date
        
        today_start = datetime.combine(date.today(), datetime.min.time())
        
        query = select(func.count(PaymentRefund.id)).where(
            PaymentRefund.requested_at >= today_start,
        )
        
        result = await self.session.execute(query)
        count = result.scalar() or 0
        
        # Format: RFD-YYYYMMDD-NNNN
        return f"RFD-{date.today().strftime('%Y%m%d')}-{count + 1:04d}"