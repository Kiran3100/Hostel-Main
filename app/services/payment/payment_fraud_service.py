# app/services/payment/payment_fraud_service.py
"""
Payment Fraud Service

Performs simple risk assessment over payments and gateway transactions,
and can create security events for suspicious activity.
"""

from __future__ import annotations

from typing import Dict, Any
from uuid import UUID
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.repositories.payment import PaymentRepository, GatewayTransactionRepository
from app.repositories.auth import SecurityEventRepository
from app.core.exceptions import ValidationException


class PaymentFraudService:
    """
    High-level service for basic fraud detection.

    This is intentionally simple and rule-based; you can replace it
    with an ML-based scoring engine later.
    """

    def __init__(
        self,
        payment_repo: PaymentRepository,
        gateway_tx_repo: GatewayTransactionRepository,
        security_event_repo: SecurityEventRepository,
    ) -> None:
        self.payment_repo = payment_repo
        self.gateway_tx_repo = gateway_tx_repo
        self.security_event_repo = security_event_repo

    def assess_transaction_risk(
        self,
        db: Session,
        payment_id: UUID,
    ) -> Dict[str, Any]:
        """
        Compute a simple risk score for a payment.
        """
        payment = self.payment_repo.get_by_id(db, payment_id)
        if not payment:
            raise ValidationException("Payment not found")

        tx = self.gateway_tx_repo.get_latest_for_payment(db, payment_id)

        # Simple risk heuristic:
        risk_score = 0
        reasons: list[str] = []

        if payment.amount > 50000:
            risk_score += 40
            reasons.append("high_amount")

        if tx and tx.fraud_flagged:
            risk_score += 50
            reasons.append("gateway_fraud_flag")

        # Example: multiple failed attempts in the last hour
        recent_failures = self.payment_repo.count_recent_failures_for_user(
            db=db,
            user_id=payment.payer_user_id,
            cutoff=datetime.utcnow() - timedelta(hours=1),
        )
        if recent_failures > 3:
            risk_score += 30
            reasons.append("multiple_recent_failures")

        return {
            "payment_id": str(payment_id),
            "risk_score": risk_score,
            "risk_level": self._map_score_to_level(risk_score),
            "reasons": reasons,
        }

    def create_security_event_if_suspicious(
        self,
        db: Session,
        payment_id: UUID,
    ) -> None:
        """
        Create a SecurityEvent if risk is above threshold.
        """
        assessment = self.assess_transaction_risk(db, payment_id)
        if assessment["risk_score"] >= 70:
            self.security_event_repo.create_payment_fraud_event(
                db=db,
                payment_id=payment_id,
                risk_score=assessment["risk_score"],
                reasons=assessment["reasons"],
            )

    def _map_score_to_level(self, score: int) -> str:
        if score >= 80:
            return "high"
        if score >= 50:
            return "medium"
        if score > 0:
            return "low"
        return "none"