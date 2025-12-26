# app/services/payment/payment_reconciliation_service.py
"""
Payment Reconciliation Service

Reconciles internal payments with gateway transactions and ledger.
"""

from __future__ import annotations

from typing import Dict, Any, List
from uuid import UUID
from datetime import date

from sqlalchemy.orm import Session

from app.repositories.payment import (
    PaymentRepository,
    GatewayTransactionRepository,
    PaymentLedgerRepository,
)
from app.core.exceptions import ValidationException


class PaymentReconciliationService:
    """
    High-level service for payment reconciliation.

    Responsibilities:
    - Reconcile payments with gateway transactions
    - Identify discrepancies for a given date range
    - Optionally auto-correct some discrepancies
    """

    def __init__(
        self,
        payment_repo: PaymentRepository,
        gateway_tx_repo: GatewayTransactionRepository,
        ledger_repo: PaymentLedgerRepository,
    ) -> None:
        self.payment_repo = payment_repo
        self.gateway_tx_repo = gateway_tx_repo
        self.ledger_repo = ledger_repo

    def reconcile_for_date(
        self,
        db: Session,
        reconciliation_date: date,
    ) -> Dict[str, Any]:
        """
        Reconcile payments and gateway transactions for a specific date.

        Returns a summary dict.
        """
        payments = self.payment_repo.get_by_date(db, reconciliation_date)
        gateway_txs = self.gateway_tx_repo.get_by_date(db, reconciliation_date)

        # These repository methods should return list of records with minimal fields
        summary: Dict[str, Any] = {
            "date": reconciliation_date.isoformat(),
            "payments_count": len(payments),
            "gateway_transactions_count": len(gateway_txs),
            "matched": 0,
            "unmatched_payments": [],
            "unmatched_gateway_transactions": [],
        }

        # Simple matching by payment_reference or gateway_payment_id
        tx_by_payment_ref = {
            tx.payment_reference: tx for tx in gateway_txs if tx.payment_reference
        }
        matched = 0
        unmatched_payments = []
        for p in payments:
            tx = tx_by_payment_ref.get(p.payment_reference)
            if tx:
                matched += 1
            else:
                unmatched_payments.append(str(p.id))

        unmatched_gateway = [
            str(tx.id)
            for tx in gateway_txs
            if not any(tx.payment_reference == p.payment_reference for p in payments)
        ]

        summary["matched"] = matched
        summary["unmatched_payments"] = unmatched_payments
        summary["unmatched_gateway_transactions"] = unmatched_gateway

        return summary