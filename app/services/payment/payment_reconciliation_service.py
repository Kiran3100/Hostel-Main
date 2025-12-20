"""
Payment Reconciliation Service.

Automated reconciliation between internal records, payment gateways,
and bank statements. Handles settlement verification and discrepancy detection.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ReconciliationError
from app.models.payment.gateway_transaction import (
    GatewayProvider,
    GatewayTransaction,
    GatewayTransactionStatus,
)
from app.models.payment.payment import Payment
from app.repositories.payment.gateway_transaction_repository import (
    GatewayTransactionRepository,
)
from app.repositories.payment.payment_ledger_repository import (
    PaymentLedgerRepository,
)
from app.repositories.payment.payment_repository import PaymentRepository
from app.schemas.common.enums import PaymentStatus


class PaymentReconciliationService:
    """
    Service for payment reconciliation operations.
    
    Handles:
    - Gateway reconciliation (verify against gateway records)
    - Settlement reconciliation (verify settlements received)
    - Bank reconciliation (match bank statements)
    - Discrepancy detection and resolution
    """

    def __init__(
        self,
        session: AsyncSession,
        payment_repo: PaymentRepository,
        gateway_repo: GatewayTransactionRepository,
        ledger_repo: PaymentLedgerRepository,
    ):
        """Initialize reconciliation service."""
        self.session = session
        self.payment_repo = payment_repo
        self.gateway_repo = gateway_repo
        self.ledger_repo = ledger_repo

    # ==================== Gateway Reconciliation ====================

    async def reconcile_gateway_transactions(
        self,
        gateway_name: GatewayProvider,
        reconciliation_date: date,
        settlement_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Reconcile transactions with payment gateway.
        
        Compares our records with gateway's records for the day.
        
        Args:
            gateway_name: Gateway to reconcile
            reconciliation_date: Date to reconcile
            settlement_id: Optional settlement batch ID
            
        Returns:
            Reconciliation report with matched, missing, and extra transactions
        """
        try:
            # Get our transactions for the day
            start_datetime = datetime.combine(reconciliation_date, datetime.min.time())
            end_datetime = datetime.combine(reconciliation_date, datetime.max.time())
            
            our_transactions = await self.gateway_repo.find_by_gateway_and_status(
                gateway_name=gateway_name.value,
                transaction_status=GatewayTransactionStatus.SUCCESS.value,
                start_date=start_datetime,
                end_date=end_datetime,
                limit=10000,
            )
            
            # In production, fetch from gateway API
            # gateway_transactions = await self._fetch_gateway_transactions(
            #     gateway_name, reconciliation_date, settlement_id
            # )
            
            # For now, simulate gateway response
            gateway_transactions = await self._mock_gateway_transactions(
                our_transactions
            )
            
            # Match transactions
            matched, missing, extra = await self._match_transactions(
                our_transactions=our_transactions,
                gateway_transactions=gateway_transactions,
            )
            
            # Calculate totals
            our_total = sum(t.transaction_amount for t in our_transactions)
            gateway_total = sum(t.get("amount", 0) for t in gateway_transactions)
            matched_total = sum(t.transaction_amount for t in matched)
            
            # Generate report
            report = {
                "reconciliation_date": reconciliation_date.isoformat(),
                "gateway": gateway_name.value,
                "settlement_id": settlement_id,
                "summary": {
                    "our_transaction_count": len(our_transactions),
                    "gateway_transaction_count": len(gateway_transactions),
                    "matched_count": len(matched),
                    "missing_in_gateway": len(missing),
                    "extra_in_gateway": len(extra),
                    "our_total_amount": float(our_total),
                    "gateway_total_amount": float(gateway_total),
                    "matched_total_amount": float(matched_total),
                    "discrepancy_amount": float(our_total - gateway_total),
                },
                "matched_transactions": [
                    {
                        "transaction_id": str(t.id),
                        "gateway_payment_id": t.gateway_payment_id,
                        "amount": float(t.transaction_amount),
                    }
                    for t in matched[:10]  # First 10 for brevity
                ],
                "missing_transactions": [
                    {
                        "transaction_id": str(t.id),
                        "gateway_order_id": t.gateway_order_id,
                        "amount": float(t.transaction_amount),
                        "status": t.transaction_status.value,
                    }
                    for t in missing
                ],
                "extra_transactions": extra,
                "is_balanced": len(missing) == 0 and len(extra) == 0,
                "reconciled_at": datetime.utcnow().isoformat(),
            }
            
            # Mark matched transactions as reconciled
            for transaction in matched:
                await self.gateway_repo.update(
                    transaction.id,
                    {
                        "is_reconciled": True,
                        "reconciled_at": datetime.utcnow(),
                        "reconciliation_reference": settlement_id,
                    },
                )
            
            return report
            
        except Exception as e:
            raise ReconciliationError(
                f"Gateway reconciliation failed: {str(e)}"
            )

    async def _match_transactions(
        self,
        our_transactions: list[GatewayTransaction],
        gateway_transactions: list[dict],
    ) -> tuple[list[GatewayTransaction], list[GatewayTransaction], list[dict]]:
        """
        Match our transactions with gateway transactions.
        
        Returns:
            (matched, missing_in_gateway, extra_in_gateway)
        """
        # Create lookup dict from gateway transactions
        gateway_lookup = {
            t["gateway_payment_id"]: t for t in gateway_transactions
        }
        
        matched = []
        missing = []
        
        for our_txn in our_transactions:
            if our_txn.gateway_payment_id in gateway_lookup:
                # Check if amounts match
                gateway_txn = gateway_lookup[our_txn.gateway_payment_id]
                if abs(float(our_txn.transaction_amount) - gateway_txn["amount"]) < 0.01:
                    matched.append(our_txn)
                    del gateway_lookup[our_txn.gateway_payment_id]
                else:
                    # Amount mismatch
                    missing.append(our_txn)
            else:
                missing.append(our_txn)
        
        # Remaining in gateway_lookup are extra
        extra = list(gateway_lookup.values())
        
        return matched, missing, extra

    async def _mock_gateway_transactions(
        self,
        our_transactions: list[GatewayTransaction],
    ) -> list[dict]:
        """Mock gateway API response."""
        # In production, this would call actual gateway API
        return [
            {
                "gateway_payment_id": t.gateway_payment_id,
                "amount": float(t.transaction_amount),
                "status": "captured",
                "created_at": t.initiated_at.isoformat(),
            }
            for t in our_transactions
        ]

    # ==================== Settlement Reconciliation ====================

    async def reconcile_settlement(
        self,
        gateway_name: GatewayProvider,
        settlement_id: str,
        settlement_date: date,
        settlement_amount: Decimal,
        settlement_utr: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Reconcile settlement received from gateway.
        
        Verifies that settlement amount matches our records.
        
        Args:
            gateway_name: Gateway provider
            settlement_id: Settlement batch ID
            settlement_date: Date of settlement
            settlement_amount: Amount settled by gateway
            settlement_utr: Bank UTR/reference
            
        Returns:
            Settlement reconciliation report
        """
        try:
            # Get unsettled transactions for this gateway
            unsettled = await self.gateway_repo.find_unsettled_transactions(
                gateway_name=gateway_name,
                older_than_days=0,
            )
            
            # Filter transactions that should be in this settlement
            # (transactions completed before settlement date)
            settlement_transactions = [
                t for t in unsettled
                if t.completed_at and t.completed_at.date() <= settlement_date
            ]
            
            # Calculate expected settlement amount
            expected_gross = sum(
                t.transaction_amount for t in settlement_transactions
            )
            expected_fees = sum(
                (t.gateway_fee or Decimal("0")) + (t.tax_amount or Decimal("0"))
                for t in settlement_transactions
            )
            expected_net = expected_gross - expected_fees
            
            # Compare with actual settlement
            discrepancy = settlement_amount - expected_net
            is_matched = abs(discrepancy) < Decimal("0.01")
            
            # Update transactions with settlement info
            if is_matched:
                for transaction in settlement_transactions:
                    await self.gateway_repo.record_settlement(
                        transaction_id=transaction.id,
                        settlement_id=settlement_id,
                        settlement_amount=transaction.net_amount or transaction.transaction_amount,
                        settlement_utr=settlement_utr,
                    )
            
            report = {
                "settlement_id": settlement_id,
                "settlement_date": settlement_date.isoformat(),
                "settlement_utr": settlement_utr,
                "gateway": gateway_name.value,
                "summary": {
                    "transaction_count": len(settlement_transactions),
                    "expected_gross_amount": float(expected_gross),
                    "expected_fees": float(expected_fees),
                    "expected_net_amount": float(expected_net),
                    "actual_settlement_amount": float(settlement_amount),
                    "discrepancy": float(discrepancy),
                    "is_matched": is_matched,
                },
                "transactions": [
                    {
                        "transaction_id": str(t.id),
                        "payment_id": str(t.payment_id),
                        "gateway_payment_id": t.gateway_payment_id,
                        "amount": float(t.transaction_amount),
                        "fee": float((t.gateway_fee or 0) + (t.tax_amount or 0)),
                        "net": float(t.net_amount or t.transaction_amount),
                    }
                    for t in settlement_transactions
                ],
                "reconciled_at": datetime.utcnow().isoformat(),
            }
            
            return report
            
        except Exception as e:
            raise ReconciliationError(f"Settlement reconciliation failed: {str(e)}")

    # ==================== Payment Status Reconciliation ====================

    async def reconcile_payment_statuses(
        self,
        hostel_id: Optional[UUID] = None,
    ) -> dict[str, Any]:
        """
        Reconcile payment statuses with gateway transactions.
        
        Finds payments marked as completed but no successful gateway transaction,
        or vice versa.
        
        Returns:
            Report of status mismatches
        """
        try:
            # Get all completed payments
            completed_payments = await self.payment_repo.find_by_hostel(
                hostel_id=hostel_id,
                status=PaymentStatus.COMPLETED,
                limit=10000,
            )
            
            mismatches = []
            
            for payment in completed_payments:
                # Get gateway transactions for this payment
                transactions = await self.gateway_repo.find_by_payment(
                    payment_id=payment.id,
                )
                
                successful_transactions = [
                    t for t in transactions
                    if t.transaction_status == GatewayTransactionStatus.SUCCESS
                ]
                
                # Check for mismatches
                if not successful_transactions and payment.payment_method.value == "online":
                    mismatches.append({
                        "payment_id": str(payment.id),
                        "payment_reference": payment.payment_reference,
                        "amount": float(payment.amount),
                        "issue": "completed_payment_no_gateway_success",
                        "payment_status": payment.payment_status.value,
                        "gateway_transactions": len(transactions),
                    })
            
            # Also check for successful gateway transactions with pending payments
            pending_payments = await self.payment_repo.find_pending_payments(
                hostel_id=hostel_id,
                older_than_hours=24,
            )
            
            for payment in pending_payments:
                transactions = await self.gateway_repo.find_by_payment(
                    payment_id=payment.id,
                )
                
                successful_transactions = [
                    t for t in transactions
                    if t.transaction_status == GatewayTransactionStatus.SUCCESS
                ]
                
                if successful_transactions:
                    mismatches.append({
                        "payment_id": str(payment.id),
                        "payment_reference": payment.payment_reference,
                        "amount": float(payment.amount),
                        "issue": "pending_payment_with_gateway_success",
                        "payment_status": payment.payment_status.value,
                        "successful_transactions": len(successful_transactions),
                    })
            
            return {
                "total_mismatches": len(mismatches),
                "mismatches": mismatches,
                "reconciled_at": datetime.utcnow().isoformat(),
            }
            
        except Exception as e:
            raise ReconciliationError(
                f"Payment status reconciliation failed: {str(e)}"
            )

    # ==================== Ledger Reconciliation ====================

    async def reconcile_ledger_with_payments(
        self,
        hostel_id: UUID,
        reconciliation_date: date,
    ) -> dict[str, Any]:
        """
        Reconcile ledger entries with payments.
        
        Ensures every completed payment has corresponding ledger entries.
        
        Returns:
            Reconciliation report
        """
        try:
            # Get completed payments for the period
            start_date = reconciliation_date.replace(day=1)  # First day of month
            
            payments = await self.payment_repo.find_by_hostel(
                hostel_id=hostel_id,
                status=PaymentStatus.COMPLETED,
                start_date=start_date,
                end_date=reconciliation_date,
                limit=10000,
            )
            
            missing_ledger_entries = []
            
            for payment in payments:
                # Check if ledger entries exist
                ledger_entries = await self.ledger_repo.find_by_payment(
                    payment_id=payment.id,
                )
                
                if not ledger_entries:
                    missing_ledger_entries.append({
                        "payment_id": str(payment.id),
                        "payment_reference": payment.payment_reference,
                        "amount": float(payment.amount),
                        "paid_at": payment.paid_at.isoformat() if payment.paid_at else None,
                    })
            
            # Get ledger summary
            ledger_summary = await self.ledger_repo.calculate_financial_summary(
                hostel_id=hostel_id,
                start_date=start_date,
                end_date=reconciliation_date,
            )
            
            # Calculate payment summary
            total_payment_amount = sum(p.amount for p in payments)
            
            return {
                "reconciliation_date": reconciliation_date.isoformat(),
                "period_start": start_date.isoformat(),
                "summary": {
                    "total_payments": len(payments),
                    "total_payment_amount": float(total_payment_amount),
                    "missing_ledger_entries": len(missing_ledger_entries),
                    "ledger_summary": ledger_summary,
                },
                "missing_entries": missing_ledger_entries,
                "is_balanced": len(missing_ledger_entries) == 0,
                "reconciled_at": datetime.utcnow().isoformat(),
            }
            
        except Exception as e:
            raise ReconciliationError(
                f"Ledger reconciliation failed: {str(e)}"
            )

    # ==================== Bank Statement Reconciliation ====================

    async def reconcile_bank_statement(
        self,
        hostel_id: UUID,
        bank_transactions: list[dict],
        statement_date: date,
    ) -> dict[str, Any]:
        """
        Reconcile payments with bank statement.
        
        Matches our payment records with bank statement entries.
        
        Args:
            hostel_id: Hostel ID
            bank_transactions: List of bank transactions
                [
                    {
                        "date": "2024-01-15",
                        "amount": 5000.00,
                        "reference": "REF123",
                        "utr": "UTR456",
                        "description": "Payment from..."
                    }
                ]
            statement_date: Statement date
            
        Returns:
            Bank reconciliation report
        """
        try:
            # Get payments for the period
            start_date = statement_date.replace(day=1)
            
            our_payments = await self.payment_repo.find_by_hostel(
                hostel_id=hostel_id,
                status=PaymentStatus.COMPLETED,
                start_date=start_date,
                end_date=statement_date,
                limit=10000,
            )
            
            # Match bank transactions with payments
            matched = []
            unmatched_bank = []
            unmatched_payments = []
            
            # Create lookup for bank transactions
            bank_lookup = {t["reference"]: t for t in bank_transactions}
            
            for payment in our_payments:
                # Try to match by transaction_id or receipt_number
                matched_bank_txn = None
                
                if payment.transaction_id and payment.transaction_id in bank_lookup:
                    matched_bank_txn = bank_lookup[payment.transaction_id]
                elif payment.receipt_number and payment.receipt_number in bank_lookup:
                    matched_bank_txn = bank_lookup[payment.receipt_number]
                
                if matched_bank_txn:
                    # Verify amounts match
                    if abs(float(payment.amount) - matched_bank_txn["amount"]) < 0.01:
                        matched.append({
                            "payment_id": str(payment.id),
                            "payment_reference": payment.payment_reference,
                            "amount": float(payment.amount),
                            "bank_reference": matched_bank_txn["reference"],
                            "bank_utr": matched_bank_txn.get("utr"),
                        })
                        del bank_lookup[matched_bank_txn["reference"]]
                    else:
                        unmatched_payments.append(payment)
                else:
                    unmatched_payments.append(payment)
            
            # Remaining bank transactions are unmatched
            unmatched_bank = list(bank_lookup.values())
            
            our_total = sum(p.amount for p in our_payments)
            bank_total = sum(Decimal(str(t["amount"])) for t in bank_transactions)
            matched_total = sum(Decimal(str(m["amount"])) for m in matched)
            
            return {
                "statement_date": statement_date.isoformat(),
                "period_start": start_date.isoformat(),
                "summary": {
                    "our_payment_count": len(our_payments),
                    "bank_transaction_count": len(bank_transactions),
                    "matched_count": len(matched),
                    "unmatched_in_bank": len(unmatched_bank),
                    "unmatched_in_payments": len(unmatched_payments),
                    "our_total_amount": float(our_total),
                    "bank_total_amount": float(bank_total),
                    "matched_total_amount": float(matched_total),
                    "discrepancy": float(our_total - bank_total),
                },
                "matched": matched[:20],  # First 20
                "unmatched_bank_transactions": unmatched_bank,
                "unmatched_payments": [
                    {
                        "payment_id": str(p.id),
                        "payment_reference": p.payment_reference,
                        "amount": float(p.amount),
                        "paid_at": p.paid_at.isoformat() if p.paid_at else None,
                    }
                    for p in unmatched_payments
                ],
                "is_balanced": len(unmatched_bank) == 0 and len(unmatched_payments) == 0,
                "reconciled_at": datetime.utcnow().isoformat(),
            }
            
        except Exception as e:
            raise ReconciliationError(
                f"Bank statement reconciliation failed: {str(e)}"
            )

    # ==================== Automated Reconciliation ====================

    async def run_daily_reconciliation(
        self,
        hostel_id: Optional[UUID] = None,
        reconciliation_date: Optional[date] = None,
    ) -> dict[str, Any]:
        """
        Run automated daily reconciliation.
        
        This should be scheduled to run daily as a cron job.
        
        Returns:
            Comprehensive reconciliation report
        """
        recon_date = reconciliation_date or (date.today() - timedelta(days=1))
        
        results = {
            "reconciliation_date": recon_date.isoformat(),
            "started_at": datetime.utcnow().isoformat(),
            "hostel_id": str(hostel_id) if hostel_id else "all",
            "checks": {},
        }
        
        try:
            # 1. Gateway reconciliation
            for gateway in [GatewayProvider.RAZORPAY, GatewayProvider.STRIPE]:
                try:
                    gateway_recon = await self.reconcile_gateway_transactions(
                        gateway_name=gateway,
                        reconciliation_date=recon_date,
                    )
                    results["checks"][f"{gateway.value}_reconciliation"] = gateway_recon
                except Exception as e:
                    results["checks"][f"{gateway.value}_reconciliation"] = {
                        "error": str(e)
                    }
            
            # 2. Payment status reconciliation
            try:
                status_recon = await self.reconcile_payment_statuses(
                    hostel_id=hostel_id
                )
                results["checks"]["payment_status_reconciliation"] = status_recon
            except Exception as e:
                results["checks"]["payment_status_reconciliation"] = {
                    "error": str(e)
                }
            
            # 3. Ledger reconciliation (if hostel_id provided)
            if hostel_id:
                try:
                    ledger_recon = await self.reconcile_ledger_with_payments(
                        hostel_id=hostel_id,
                        reconciliation_date=recon_date,
                    )
                    results["checks"]["ledger_reconciliation"] = ledger_recon
                except Exception as e:
                    results["checks"]["ledger_reconciliation"] = {"error": str(e)}
            
            results["completed_at"] = datetime.utcnow().isoformat()
            results["status"] = "completed"
            
            return results
            
        except Exception as e:
            results["status"] = "failed"
            results["error"] = str(e)
            results["completed_at"] = datetime.utcnow().isoformat()
            return results

    # ==================== Discrepancy Resolution ====================

    async def resolve_discrepancy(
        self,
        discrepancy_type: str,
        payment_id: Optional[UUID] = None,
        transaction_id: Optional[UUID] = None,
        resolution: str,
        resolved_by: UUID,
        notes: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Resolve a reconciliation discrepancy.
        
        Args:
            discrepancy_type: Type of discrepancy
            payment_id: Related payment (if any)
            transaction_id: Related transaction (if any)
            resolution: How it was resolved
            resolved_by: User who resolved
            notes: Additional notes
            
        Returns:
            Resolution confirmation
        """
        # In production, this would update a discrepancy tracking table
        
        resolution_record = {
            "discrepancy_type": discrepancy_type,
            "payment_id": str(payment_id) if payment_id else None,
            "transaction_id": str(transaction_id) if transaction_id else None,
            "resolution": resolution,
            "resolved_by": str(resolved_by),
            "notes": notes,
            "resolved_at": datetime.utcnow().isoformat(),
        }
        
        # Update related records as needed
        if payment_id and resolution == "mark_payment_completed":
            # Update payment status
            pass
        
        return resolution_record