# app/services/payment/payment_reconciliation_service.py
"""
Payment Reconciliation Service

Reconciles internal payments with gateway transactions and ledger:
- Match payments with gateway transactions
- Identify discrepancies and mismatches
- Auto-correct reconcilable differences
- Generate reconciliation reports
"""

from __future__ import annotations

from typing import Dict, Any, List, Optional, Tuple
from uuid import UUID
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.repositories.payment import (
    PaymentRepository,
    GatewayTransactionRepository,
    PaymentLedgerRepository,
)
from app.core.exceptions import (
    ValidationException,
    BusinessLogicException,
    NotFoundException,
)
from app.core.logging import LoggingContext, logger


class PaymentReconciliationService:
    """
    High-level service for payment reconciliation.

    Responsibilities:
    - Reconcile payments with gateway transactions
    - Identify and categorize discrepancies
    - Auto-correct certain types of mismatches
    - Generate reconciliation reports
    - Track reconciliation history
    - Support manual reconciliation workflows

    Delegates:
    - Payment queries to PaymentRepository
    - Gateway transaction queries to GatewayTransactionRepository
    - Ledger validation to PaymentLedgerRepository
    """

    __slots__ = ("payment_repo", "gateway_tx_repo", "ledger_repo")

    # Reconciliation match tolerance (for amount differences)
    AMOUNT_TOLERANCE = Decimal("0.01")

    # Discrepancy categories
    DISCREPANCY_TYPES = {
        "missing_gateway": "Payment exists but no gateway transaction",
        "missing_payment": "Gateway transaction exists but no payment",
        "amount_mismatch": "Payment and transaction amounts don't match",
        "status_mismatch": "Payment and transaction statuses don't match",
        "duplicate_transaction": "Multiple gateway transactions for one payment",
        "orphaned_transaction": "Gateway transaction with no valid payment reference",
    }

    def __init__(
        self,
        payment_repo: PaymentRepository,
        gateway_tx_repo: GatewayTransactionRepository,
        ledger_repo: PaymentLedgerRepository,
    ) -> None:
        self.payment_repo = payment_repo
        self.gateway_tx_repo = gateway_tx_repo
        self.ledger_repo = ledger_repo

    # -------------------------------------------------------------------------
    # Date-based reconciliation
    # -------------------------------------------------------------------------

    def reconcile_for_date(
        self,
        db: Session,
        reconciliation_date: date,
        auto_correct: bool = False,
    ) -> Dict[str, Any]:
        """
        Reconcile payments and gateway transactions for a specific date.

        Args:
            db: Database session
            reconciliation_date: Date to reconcile
            auto_correct: If True, automatically fix reconcilable discrepancies

        Returns:
            Reconciliation summary with matches and discrepancies
        """
        with LoggingContext(reconciliation_date=reconciliation_date.isoformat()):
            logger.info(f"Starting reconciliation for date: {reconciliation_date}")

            # Get all payments and transactions for the date
            payments = self.payment_repo.get_by_date(db, reconciliation_date)
            gateway_txs = self.gateway_tx_repo.get_by_date(db, reconciliation_date)

            logger.debug(
                f"Retrieved {len(payments)} payments and {len(gateway_txs)} gateway transactions"
            )

            # Build reconciliation summary
            summary = self._build_reconciliation_summary(
                db=db,
                payments=payments,
                gateway_txs=gateway_txs,
                reconciliation_date=reconciliation_date,
            )

            # Auto-correct if requested
            if auto_correct and summary["discrepancies"]:
                corrections = self._auto_correct_discrepancies(
                    db=db,
                    discrepancies=summary["discrepancies"],
                )
                summary["auto_corrections"] = corrections

            logger.info(
                f"Reconciliation completed: {summary['matched']} matched, "
                f"{summary['total_discrepancies']} discrepancies"
            )

            return summary

    def reconcile_for_date_range(
        self,
        db: Session,
        start_date: date,
        end_date: date,
        auto_correct: bool = False,
    ) -> Dict[str, Any]:
        """
        Reconcile payments for a date range.

        Args:
            db: Database session
            start_date: Start date (inclusive)
            end_date: End date (inclusive)
            auto_correct: If True, automatically fix reconcilable discrepancies

        Returns:
            Aggregated reconciliation summary
        """
        if start_date > end_date:
            raise ValidationException("Start date must be before or equal to end date")

        if (end_date - start_date).days > 31:
            raise ValidationException("Date range cannot exceed 31 days")

        with LoggingContext(
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
        ):
            logger.info(f"Starting reconciliation for range: {start_date} to {end_date}")

            aggregate_summary = {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "total_payments": 0,
                "total_gateway_transactions": 0,
                "total_matched": 0,
                "total_discrepancies": 0,
                "daily_summaries": [],
                "discrepancies_by_type": {},
            }

            current_date = start_date
            while current_date <= end_date:
                daily_summary = self.reconcile_for_date(
                    db=db,
                    reconciliation_date=current_date,
                    auto_correct=auto_correct,
                )

                aggregate_summary["total_payments"] += daily_summary["payments_count"]
                aggregate_summary["total_gateway_transactions"] += daily_summary[
                    "gateway_transactions_count"
                ]
                aggregate_summary["total_matched"] += daily_summary["matched"]
                aggregate_summary["total_discrepancies"] += daily_summary[
                    "total_discrepancies"
                ]

                aggregate_summary["daily_summaries"].append(daily_summary)

                current_date += timedelta(days=1)

            # Aggregate discrepancy types
            for daily in aggregate_summary["daily_summaries"]:
                for disc_type, count in daily.get("discrepancies_by_type", {}).items():
                    aggregate_summary["discrepancies_by_type"][disc_type] = (
                        aggregate_summary["discrepancies_by_type"].get(disc_type, 0)
                        + count
                    )

            logger.info(
                f"Range reconciliation completed: {aggregate_summary['total_matched']} matched, "
                f"{aggregate_summary['total_discrepancies']} total discrepancies"
            )

            return aggregate_summary

    def _build_reconciliation_summary(
        self,
        db: Session,
        payments: List[Any],
        gateway_txs: List[Any],
        reconciliation_date: date,
    ) -> Dict[str, Any]:
        """Build comprehensive reconciliation summary."""
        summary = {
            "date": reconciliation_date.isoformat(),
            "payments_count": len(payments),
            "gateway_transactions_count": len(gateway_txs),
            "matched": 0,
            "total_discrepancies": 0,
            "discrepancies": [],
            "discrepancies_by_type": {},
            "matched_items": [],
        }

        # Create lookup maps
        payments_by_ref = {p.payment_reference: p for p in payments}
        txs_by_ref = {}
        txs_by_payment_id = {}

        for tx in gateway_txs:
            if tx.payment_reference:
                if tx.payment_reference not in txs_by_ref:
                    txs_by_ref[tx.payment_reference] = []
                txs_by_ref[tx.payment_reference].append(tx)

            if tx.gateway_payment_id:
                txs_by_payment_id[tx.gateway_payment_id] = tx

        # Match payments with transactions
        matched_payment_ids = set()
        matched_tx_ids = set()

        for payment in payments:
            matching_txs = txs_by_ref.get(payment.payment_reference, [])

            if not matching_txs:
                # Missing gateway transaction
                summary["discrepancies"].append({
                    "type": "missing_gateway",
                    "payment_id": str(payment.id),
                    "payment_reference": payment.payment_reference,
                    "amount": float(payment.amount),
                    "status": payment.status.value,
                })
                self._increment_discrepancy_type(summary, "missing_gateway")
            elif len(matching_txs) > 1:
                # Duplicate transactions
                summary["discrepancies"].append({
                    "type": "duplicate_transaction",
                    "payment_id": str(payment.id),
                    "payment_reference": payment.payment_reference,
                    "transaction_count": len(matching_txs),
                    "transaction_ids": [str(tx.id) for tx in matching_txs],
                })
                self._increment_discrepancy_type(summary, "duplicate_transaction")
            else:
                tx = matching_txs[0]
                # Check for amount/status mismatches
                discrepancy = self._check_payment_transaction_match(payment, tx)

                if discrepancy:
                    summary["discrepancies"].append(discrepancy)
                    self._increment_discrepancy_type(summary, discrepancy["type"])
                else:
                    # Perfect match
                    summary["matched"] += 1
                    summary["matched_items"].append({
                        "payment_id": str(payment.id),
                        "transaction_id": str(tx.id),
                        "amount": float(payment.amount),
                        "status": payment.status.value,
                    })
                    matched_payment_ids.add(payment.id)
                    matched_tx_ids.add(tx.id)

        # Find orphaned transactions
        for tx in gateway_txs:
            if tx.id not in matched_tx_ids:
                summary["discrepancies"].append({
                    "type": "missing_payment",
                    "transaction_id": str(tx.id),
                    "gateway_order_id": tx.gateway_order_id,
                    "gateway_payment_id": tx.gateway_payment_id,
                    "amount": float(tx.amount) if tx.amount else 0,
                    "status": tx.status,
                })
                self._increment_discrepancy_type(summary, "missing_payment")

        summary["total_discrepancies"] = len(summary["discrepancies"])

        return summary

    def _check_payment_transaction_match(
        self,
        payment: Any,
        transaction: Any,
    ) -> Optional[Dict[str, Any]]:
        """
        Check if payment and transaction match properly.

        Returns discrepancy dict if mismatch found, None if perfect match.
        """
        # Check amount match
        payment_amount = Decimal(str(payment.amount))
        tx_amount = Decimal(str(transaction.amount)) if transaction.amount else Decimal("0")

        amount_diff = abs(payment_amount - tx_amount)
        if amount_diff > self.AMOUNT_TOLERANCE:
            return {
                "type": "amount_mismatch",
                "payment_id": str(payment.id),
                "transaction_id": str(transaction.id),
                "payment_amount": float(payment_amount),
                "transaction_amount": float(tx_amount),
                "difference": float(amount_diff),
            }

        # Check status match
        if not self._statuses_match(payment.status.value, transaction.status):
            return {
                "type": "status_mismatch",
                "payment_id": str(payment.id),
                "transaction_id": str(transaction.id),
                "payment_status": payment.status.value,
                "transaction_status": transaction.status,
            }

        return None

    def _statuses_match(self, payment_status: str, tx_status: str) -> bool:
        """Check if payment and transaction statuses are compatible."""
        # Map transaction statuses to payment statuses
        status_mapping = {
            "success": ["completed", "paid"],
            "completed": ["completed", "paid"],
            "failed": ["failed"],
            "pending": ["pending", "initiated"],
            "processing": ["processing", "pending"],
            "cancelled": ["cancelled", "failed"],
        }

        expected_payment_statuses = status_mapping.get(tx_status, [])
        return payment_status in expected_payment_statuses

    def _increment_discrepancy_type(
        self,
        summary: Dict[str, Any],
        disc_type: str,
    ) -> None:
        """Increment counter for discrepancy type."""
        summary["discrepancies_by_type"][disc_type] = (
            summary["discrepancies_by_type"].get(disc_type, 0) + 1
        )

    # -------------------------------------------------------------------------
    # Auto-correction
    # -------------------------------------------------------------------------

    def _auto_correct_discrepancies(
        self,
        db: Session,
        discrepancies: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Automatically correct reconcilable discrepancies.

        Only corrects safe discrepancies:
        - Status mismatches where transaction is authoritative
        - Small amount differences within tolerance
        """
        corrections = {
            "total_attempted": 0,
            "total_corrected": 0,
            "total_failed": 0,
            "corrections": [],
        }

        for discrepancy in discrepancies:
            disc_type = discrepancy["type"]

            if disc_type == "status_mismatch":
                result = self._correct_status_mismatch(db, discrepancy)
                self._record_correction_result(corrections, result)
            elif disc_type == "amount_mismatch":
                # Only auto-correct very small differences
                if discrepancy.get("difference", 999) <= 0.01:
                    result = self._correct_amount_mismatch(db, discrepancy)
                    self._record_correction_result(corrections, result)

        logger.info(
            f"Auto-correction completed: {corrections['total_corrected']} corrected, "
            f"{corrections['total_failed']} failed"
        )

        return corrections

    def _correct_status_mismatch(
        self,
        db: Session,
        discrepancy: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Correct a status mismatch by updating payment to match transaction."""
        try:
            payment_id = UUID(discrepancy["payment_id"])
            payment = self.payment_repo.get_by_id(db, payment_id)

            if not payment:
                return {
                    "success": False,
                    "discrepancy": discrepancy,
                    "error": "Payment not found",
                }

            # Update payment status to match transaction
            tx_status = discrepancy["transaction_status"]
            new_payment_status = self._map_tx_status_to_payment_status(tx_status)

            self.payment_repo.update(
                db,
                payment,
                data={"status": new_payment_status},
            )

            logger.info(
                f"Corrected status mismatch for payment {payment_id}: "
                f"{discrepancy['payment_status']} -> {new_payment_status}"
            )

            return {
                "success": True,
                "discrepancy": discrepancy,
                "action": "status_updated",
                "old_status": discrepancy["payment_status"],
                "new_status": new_payment_status,
            }

        except Exception as e:
            logger.error(f"Failed to correct status mismatch: {str(e)}")
            return {
                "success": False,
                "discrepancy": discrepancy,
                "error": str(e),
            }

    def _correct_amount_mismatch(
        self,
        db: Session,
        discrepancy: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Correct a small amount mismatch."""
        try:
            payment_id = UUID(discrepancy["payment_id"])
            payment = self.payment_repo.get_by_id(db, payment_id)

            if not payment:
                return {
                    "success": False,
                    "discrepancy": discrepancy,
                    "error": "Payment not found",
                }

            # Update payment amount to match transaction
            new_amount = Decimal(str(discrepancy["transaction_amount"]))

            self.payment_repo.update(
                db,
                payment,
                data={"amount": new_amount},
            )

            logger.info(
                f"Corrected amount mismatch for payment {payment_id}: "
                f"{discrepancy['payment_amount']} -> {new_amount}"
            )

            return {
                "success": True,
                "discrepancy": discrepancy,
                "action": "amount_updated",
                "old_amount": discrepancy["payment_amount"],
                "new_amount": float(new_amount),
            }

        except Exception as e:
            logger.error(f"Failed to correct amount mismatch: {str(e)}")
            return {
                "success": False,
                "discrepancy": discrepancy,
                "error": str(e),
            }

    def _map_tx_status_to_payment_status(self, tx_status: str) -> str:
        """Map transaction status to payment status."""
        mapping = {
            "success": "completed",
            "completed": "completed",
            "failed": "failed",
            "pending": "pending",
            "processing": "processing",
            "cancelled": "cancelled",
        }
        return mapping.get(tx_status, "pending")

    def _record_correction_result(
        self,
        corrections: Dict[str, Any],
        result: Dict[str, Any],
    ) -> None:
        """Record correction result in summary."""
        corrections["total_attempted"] += 1

        if result["success"]:
            corrections["total_corrected"] += 1
        else:
            corrections["total_failed"] += 1

        corrections["corrections"].append(result)

    # -------------------------------------------------------------------------
    # Manual reconciliation
    # -------------------------------------------------------------------------

    def mark_discrepancy_resolved(
        self,
        db: Session,
        payment_id: UUID,
        resolution_notes: str,
        resolved_by: UUID,
    ) -> Dict[str, Any]:
        """
        Manually mark a discrepancy as resolved.

        Args:
            db: Database session
            payment_id: Payment UUID
            resolution_notes: Notes explaining resolution
            resolved_by: UUID of user resolving

        Returns:
            Resolution details
        """
        if not resolution_notes or len(resolution_notes.strip()) < 10:
            raise ValidationException(
                "Resolution notes must be at least 10 characters"
            )

        payment = self.payment_repo.get_by_id(db, payment_id)
        if not payment:
            raise NotFoundException(f"Payment not found: {payment_id}")

        # Record resolution in payment metadata
        resolution_data = {
            "reconciliation_resolved": True,
            "reconciliation_resolved_at": datetime.utcnow().isoformat(),
            "reconciliation_resolved_by": str(resolved_by),
            "reconciliation_notes": resolution_notes,
        }

        self.payment_repo.update(
            db,
            payment,
            data={"metadata": {**payment.metadata, **resolution_data}},
        )

        logger.info(
            f"Reconciliation discrepancy manually resolved for payment: {payment_id}",
            extra={
                "payment_id": str(payment_id),
                "resolved_by": str(resolved_by),
            },
        )

        return {
            "payment_id": str(payment_id),
            "resolved": True,
            "resolved_at": resolution_data["reconciliation_resolved_at"],
            "resolved_by": str(resolved_by),
            "notes": resolution_notes,
        }

    def get_unresolved_discrepancies(
        self,
        db: Session,
        hostel_id: Optional[UUID] = None,
        days: int = 30,
    ) -> List[Dict[str, Any]]:
        """
        Get all unresolved reconciliation discrepancies.

        Args:
            db: Database session
            hostel_id: Optional hostel filter
            days: Look back this many days

        Returns:
            List of unresolved discrepancies
        """
        since_date = date.today() - timedelta(days=days)

        # Run reconciliation for the period
        summary = self.reconcile_for_date_range(
            db=db,
            start_date=since_date,
            end_date=date.today(),
            auto_correct=False,
        )

        # Filter for unresolved
        unresolved = []
        for daily in summary["daily_summaries"]:
            for disc in daily.get("discrepancies", []):
                # Check if this discrepancy has been manually resolved
                if not self._is_discrepancy_resolved(db, disc):
                    unresolved.append(disc)

        return unresolved

    def _is_discrepancy_resolved(
        self,
        db: Session,
        discrepancy: Dict[str, Any],
    ) -> bool:
        """Check if a discrepancy has been manually resolved."""
        payment_id_str = discrepancy.get("payment_id")
        if not payment_id_str:
            return False

        try:
            payment_id = UUID(payment_id_str)
            payment = self.payment_repo.get_by_id(db, payment_id)

            if not payment or not payment.metadata:
                return False

            return payment.metadata.get("reconciliation_resolved", False)

        except (ValueError, AttributeError):
            return False

    # -------------------------------------------------------------------------
    # Reporting
    # -------------------------------------------------------------------------

    def generate_reconciliation_report(
        self,
        db: Session,
        start_date: date,
        end_date: date,
        hostel_id: Optional[UUID] = None,
    ) -> Dict[str, Any]:
        """
        Generate comprehensive reconciliation report.

        Args:
            db: Database session
            start_date: Report start date
            end_date: Report end date
            hostel_id: Optional hostel filter

        Returns:
            Comprehensive reconciliation report
        """
        with LoggingContext(
            report_type="reconciliation",
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
        ):
            # Run reconciliation
            summary = self.reconcile_for_date_range(
                db=db,
                start_date=start_date,
                end_date=end_date,
                auto_correct=False,
            )

            # Add financial summary
            financial_summary = self._calculate_financial_summary(
                db=db,
                start_date=start_date,
                end_date=end_date,
                hostel_id=hostel_id,
            )

            # Combine into report
            report = {
                "report_generated_at": datetime.utcnow().isoformat(),
                "period": {
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "days": (end_date - start_date).days + 1,
                },
                "reconciliation_summary": summary,
                "financial_summary": financial_summary,
                "recommendations": self._generate_recommendations(summary),
            }

            logger.info(
                f"Reconciliation report generated for {start_date} to {end_date}"
            )

            return report

    def _calculate_financial_summary(
        self,
        db: Session,
        start_date: date,
        end_date: date,
        hostel_id: Optional[UUID],
    ) -> Dict[str, Any]:
        """Calculate financial metrics for the reconciliation period."""
        # Get payments in period
        payments = self.payment_repo.get_by_date_range(
            db=db,
            start_date=start_date,
            end_date=end_date,
            hostel_id=hostel_id,
        )

        total_amount = sum(Decimal(str(p.amount)) for p in payments)
        completed_amount = sum(
            Decimal(str(p.amount))
            for p in payments
            if p.status.value == "completed"
        )
        failed_amount = sum(
            Decimal(str(p.amount)) for p in payments if p.status.value == "failed"
        )

        return {
            "total_payment_amount": float(total_amount),
            "completed_amount": float(completed_amount),
            "failed_amount": float(failed_amount),
            "completion_rate": (
                float(completed_amount / total_amount * 100)
                if total_amount > 0
                else 0
            ),
            "payment_count": len(payments),
        }

    def _generate_recommendations(
        self,
        summary: Dict[str, Any],
    ) -> List[str]:
        """Generate recommendations based on reconciliation results."""
        recommendations = []

        total_disc = summary.get("total_discrepancies", 0)
        disc_by_type = summary.get("discrepancies_by_type", {})

        if total_disc == 0:
            recommendations.append("✓ All payments are properly reconciled")
            return recommendations

        # Check for missing gateway transactions
        missing_gw = disc_by_type.get("missing_gateway", 0)
        if missing_gw > 0:
            recommendations.append(
                f"⚠ {missing_gw} payments are missing gateway transactions. "
                "Verify these were processed correctly."
            )

        # Check for missing payments
        missing_pay = disc_by_type.get("missing_payment", 0)
        if missing_pay > 0:
            recommendations.append(
                f"⚠ {missing_pay} gateway transactions have no corresponding payment. "
                "These may need to be manually recorded."
            )

        # Check for status mismatches
        status_mismatch = disc_by_type.get("status_mismatch", 0)
        if status_mismatch > 0:
            recommendations.append(
                f"⚠ {status_mismatch} payments have status mismatches. "
                "Consider running auto-correction."
            )

        # Check for amount mismatches
        amount_mismatch = disc_by_type.get("amount_mismatch", 0)
        if amount_mismatch > 0:
            recommendations.append(
                f"⚠ {amount_mismatch} payments have amount discrepancies. "
                "Review these for potential data entry errors."
            )

        # Check for duplicates
        duplicates = disc_by_type.get("duplicate_transaction", 0)
        if duplicates > 0:
            recommendations.append(
                f"⚠ {duplicates} payments have duplicate gateway transactions. "
                "Review these to identify the correct transaction."
            )

        return recommendations