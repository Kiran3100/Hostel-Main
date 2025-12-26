# app/services/payment/payment_fraud_service.py
"""
Payment Fraud Service

Performs risk assessment and fraud detection:
- Rule-based fraud detection
- Risk scoring for transactions
- Security event creation
- Velocity checks and pattern analysis
"""

from __future__ import annotations

from typing import Dict, Any, List, Optional
from uuid import UUID
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.repositories.payment import PaymentRepository, GatewayTransactionRepository
from app.repositories.auth import SecurityEventRepository
from app.core.exceptions import ValidationException, NotFoundException
from app.core.logging import LoggingContext, logger


class PaymentFraudService:
    """
    High-level service for fraud detection and risk assessment.

    Responsibilities:
    - Assess transaction risk using rule-based engine
    - Create security events for suspicious activity
    - Track fraud patterns and velocity
    - Support blacklist/whitelist management
    - Provide fraud analytics

    This is intentionally simple and rule-based.
    Can be replaced with ML-based scoring engine.
    """

    __slots__ = (
        "payment_repo",
        "gateway_tx_repo",
        "security_event_repo",
    )

    # Risk thresholds
    RISK_THRESHOLD_LOW = 30
    RISK_THRESHOLD_MEDIUM = 50
    RISK_THRESHOLD_HIGH = 70
    RISK_THRESHOLD_CRITICAL = 90

    # Velocity limits
    MAX_PAYMENTS_PER_HOUR = 5
    MAX_AMOUNT_PER_HOUR = Decimal("100000.00")
    MAX_FAILED_ATTEMPTS_PER_HOUR = 3

    # Amount thresholds
    HIGH_AMOUNT_THRESHOLD = Decimal("50000.00")
    VERY_HIGH_AMOUNT_THRESHOLD = Decimal("100000.00")

    def __init__(
        self,
        payment_repo: PaymentRepository,
        gateway_tx_repo: GatewayTransactionRepository,
        security_event_repo: SecurityEventRepository,
    ) -> None:
        self.payment_repo = payment_repo
        self.gateway_tx_repo = gateway_tx_repo
        self.security_event_repo = security_event_repo

    # -------------------------------------------------------------------------
    # Risk assessment
    # -------------------------------------------------------------------------

    def assess_transaction_risk(
        self,
        db: Session,
        payment_id: UUID,
    ) -> Dict[str, Any]:
        """
        Compute a risk score for a payment transaction.

        Uses multiple factors:
        - Transaction amount
        - Gateway fraud flags
        - User payment history
        - Velocity checks
        - Time-based patterns
        - Geographic anomalies (if available)

        Args:
            db: Database session
            payment_id: Payment UUID

        Returns:
            Risk assessment with score, level, and reasons

        Raises:
            NotFoundException: If payment not found
        """
        payment = self.payment_repo.get_by_id(db, payment_id)
        if not payment:
            raise NotFoundException(f"Payment not found: {payment_id}")

        with LoggingContext(payment_id=str(payment_id)):
            risk_score = 0
            reasons: List[str] = []
            factors: Dict[str, Any] = {}

            # Factor 1: High amount
            amount_score, amount_reasons = self._assess_amount_risk(payment)
            risk_score += amount_score
            reasons.extend(amount_reasons)
            factors["amount"] = amount_score

            # Factor 2: Gateway fraud flags
            gateway_score, gateway_reasons = self._assess_gateway_risk(
                db, payment_id
            )
            risk_score += gateway_score
            reasons.extend(gateway_reasons)
            factors["gateway"] = gateway_score

            # Factor 3: User velocity
            velocity_score, velocity_reasons = self._assess_velocity_risk(
                db, payment
            )
            risk_score += velocity_score
            reasons.extend(velocity_reasons)
            factors["velocity"] = velocity_score

            # Factor 4: Failed payment history
            history_score, history_reasons = self._assess_history_risk(db, payment)
            risk_score += history_score
            reasons.extend(history_reasons)
            factors["history"] = history_score

            # Factor 5: Time-based anomalies
            time_score, time_reasons = self._assess_time_risk(payment)
            risk_score += time_score
            reasons.extend(time_reasons)
            factors["time"] = time_score

            # Factor 6: Pattern anomalies
            pattern_score, pattern_reasons = self._assess_pattern_risk(db, payment)
            risk_score += pattern_score
            reasons.extend(pattern_reasons)
            factors["pattern"] = pattern_score

            risk_level = self._map_score_to_level(risk_score)

            assessment = {
                "payment_id": str(payment_id),
                "risk_score": risk_score,
                "risk_level": risk_level,
                "reasons": reasons,
                "factors": factors,
                "assessed_at": datetime.utcnow().isoformat(),
                "requires_review": risk_score >= self.RISK_THRESHOLD_HIGH,
                "auto_block": risk_score >= self.RISK_THRESHOLD_CRITICAL,
            }

            logger.info(
                f"Risk assessment completed: score={risk_score}, level={risk_level}",
                extra={
                    "payment_id": str(payment_id),
                    "risk_score": risk_score,
                    "risk_level": risk_level,
                },
            )

            return assessment

    def _assess_amount_risk(self, payment: Any) -> tuple[int, List[str]]:
        """Assess risk based on transaction amount."""
        score = 0
        reasons = []
        amount = Decimal(str(payment.amount))

        if amount > self.VERY_HIGH_AMOUNT_THRESHOLD:
            score += 50
            reasons.append("very_high_amount")
        elif amount > self.HIGH_AMOUNT_THRESHOLD:
            score += 30
            reasons.append("high_amount")

        return score, reasons

    def _assess_gateway_risk(
        self, db: Session, payment_id: UUID
    ) -> tuple[int, List[str]]:
        """Assess risk based on gateway fraud indicators."""
        score = 0
        reasons = []

        tx = self.gateway_tx_repo.get_latest_for_payment(db, payment_id)

        if tx and tx.fraud_flagged:
            score += 60
            reasons.append("gateway_fraud_flag")

        if tx and tx.risk_score:
            # If gateway provides its own risk score
            gateway_risk = int(tx.risk_score)
            if gateway_risk > 70:
                score += 40
                reasons.append("high_gateway_risk_score")
            elif gateway_risk > 50:
                score += 20
                reasons.append("medium_gateway_risk_score")

        return score, reasons

    def _assess_velocity_risk(
        self, db: Session, payment: Any
    ) -> tuple[int, List[str]]:
        """Assess risk based on payment velocity."""
        score = 0
        reasons = []

        cutoff = datetime.utcnow() - timedelta(hours=1)

        # Check payment count velocity
        recent_count = self.payment_repo.count_recent_payments_for_user(
            db=db,
            user_id=payment.payer_user_id,
            cutoff=cutoff,
        )

        if recent_count > self.MAX_PAYMENTS_PER_HOUR:
            score += 40
            reasons.append(f"high_payment_velocity_{recent_count}_per_hour")

        # Check amount velocity
        recent_amount = self.payment_repo.sum_recent_payments_for_user(
            db=db,
            user_id=payment.payer_user_id,
            cutoff=cutoff,
        )

        if recent_amount > self.MAX_AMOUNT_PER_HOUR:
            score += 40
            reasons.append("high_amount_velocity")

        return score, reasons

    def _assess_history_risk(
        self, db: Session, payment: Any
    ) -> tuple[int, List[str]]:
        """Assess risk based on payment failure history."""
        score = 0
        reasons = []

        cutoff = datetime.utcnow() - timedelta(hours=1)

        # Multiple recent failures
        recent_failures = self.payment_repo.count_recent_failures_for_user(
            db=db,
            user_id=payment.payer_user_id,
            cutoff=cutoff,
        )

        if recent_failures > self.MAX_FAILED_ATTEMPTS_PER_HOUR:
            score += 35
            reasons.append(f"multiple_recent_failures_{recent_failures}")

        # Check overall failure rate
        total_payments = self.payment_repo.count_total_payments_for_user(
            db=db,
            user_id=payment.payer_user_id,
        )

        if total_payments > 0:
            failure_rate = recent_failures / total_payments
            if failure_rate > 0.5:  # More than 50% failure rate
                score += 25
                reasons.append("high_failure_rate")

        return score, reasons

    def _assess_time_risk(self, payment: Any) -> tuple[int, List[str]]:
        """Assess risk based on time patterns (unusual hours, etc.)."""
        score = 0
        reasons = []

        payment_time = payment.created_at or datetime.utcnow()
        hour = payment_time.hour

        # Payments during unusual hours (midnight to 5 AM)
        if 0 <= hour < 5:
            score += 15
            reasons.append("unusual_hour")

        return score, reasons

    def _assess_pattern_risk(
        self, db: Session, payment: Any
    ) -> tuple[int, List[str]]:
        """Assess risk based on unusual patterns."""
        score = 0
        reasons = []

        # Check for round amount (might indicate testing)
        amount = Decimal(str(payment.amount))
        if amount % 1000 == 0 and amount > 10000:
            score += 10
            reasons.append("round_amount")

        # Check for same amount repeated
        recent_same_amount = self.payment_repo.count_recent_payments_with_amount(
            db=db,
            user_id=payment.payer_user_id,
            amount=amount,
            hours=24,
        )

        if recent_same_amount > 3:
            score += 20
            reasons.append("repeated_same_amount")

        return score, reasons

    def _map_score_to_level(self, score: int) -> str:
        """Map risk score to risk level."""
        if score >= self.RISK_THRESHOLD_CRITICAL:
            return "critical"
        if score >= self.RISK_THRESHOLD_HIGH:
            return "high"
        if score >= self.RISK_THRESHOLD_MEDIUM:
            return "medium"
        if score >= self.RISK_THRESHOLD_LOW:
            return "low"
        return "none"

    # -------------------------------------------------------------------------
    # Security event creation
    # -------------------------------------------------------------------------

    def create_security_event_if_suspicious(
        self,
        db: Session,
        payment_id: UUID,
    ) -> Optional[Dict[str, Any]]:
        """
        Create a SecurityEvent if risk assessment indicates suspicious activity.

        Args:
            db: Database session
            payment_id: Payment UUID

        Returns:
            Security event details if created, None otherwise
        """
        assessment = self.assess_transaction_risk(db, payment_id)

        if assessment["risk_score"] >= self.RISK_THRESHOLD_HIGH:
            with LoggingContext(payment_id=str(payment_id)):
                event = self.security_event_repo.create_payment_fraud_event(
                    db=db,
                    payment_id=payment_id,
                    risk_score=assessment["risk_score"],
                    risk_level=assessment["risk_level"],
                    reasons=assessment["reasons"],
                )

                logger.warning(
                    f"Security event created for suspicious payment: {payment_id}",
                    extra={
                        "payment_id": str(payment_id),
                        "event_id": str(event.id),
                        "risk_score": assessment["risk_score"],
                    },
                )

                return {
                    "event_id": str(event.id),
                    "payment_id": str(payment_id),
                    "risk_assessment": assessment,
                    "created_at": event.created_at.isoformat(),
                }

        return None

    # -------------------------------------------------------------------------
    # Batch assessment
    # -------------------------------------------------------------------------

    def assess_batch_risk(
        self,
        db: Session,
        payment_ids: List[UUID],
    ) -> Dict[str, Any]:
        """
        Assess risk for multiple payments in batch.

        Args:
            db: Database session
            payment_ids: List of payment UUIDs

        Returns:
            Batch risk assessment summary
        """
        results = {
            "total_assessed": len(payment_ids),
            "risk_distribution": {
                "none": 0,
                "low": 0,
                "medium": 0,
                "high": 0,
                "critical": 0,
            },
            "assessments": [],
            "high_risk_payments": [],
        }

        for payment_id in payment_ids:
            try:
                assessment = self.assess_transaction_risk(db, payment_id)
                results["assessments"].append(assessment)

                # Update distribution
                risk_level = assessment["risk_level"]
                results["risk_distribution"][risk_level] += 1

                # Track high risk
                if assessment["risk_score"] >= self.RISK_THRESHOLD_HIGH:
                    results["high_risk_payments"].append(assessment)

            except Exception as e:
                logger.error(
                    f"Failed to assess risk for payment {payment_id}: {str(e)}"
                )

        return results

    # -------------------------------------------------------------------------
    # Analytics
    # -------------------------------------------------------------------------

    def get_fraud_statistics(
        self,
        db: Session,
        hostel_id: Optional[UUID] = None,
        days: int = 30,
    ) -> Dict[str, Any]:
        """
        Get fraud detection statistics.

        Args:
            db: Database session
            hostel_id: Optional hostel filter
            days: Number of days to analyze

        Returns:
            Fraud statistics summary
        """
        since = datetime.utcnow() - timedelta(days=days)

        # Get all payments in period
        payments = self.payment_repo.get_payments_since(
            db=db,
            since=since,
            hostel_id=hostel_id,
        )

        stats = {
            "period_days": days,
            "total_payments": len(payments),
            "flagged_count": 0,
            "blocked_count": 0,
            "total_flagged_amount": Decimal("0"),
            "risk_distribution": {
                "none": 0,
                "low": 0,
                "medium": 0,
                "high": 0,
                "critical": 0,
            },
            "top_fraud_reasons": {},
        }

        # Assess each payment
        for payment in payments:
            try:
                assessment = self.assess_transaction_risk(db, payment.id)

                # Update distribution
                risk_level = assessment["risk_level"]
                stats["risk_distribution"][risk_level] += 1

                # Track flagged
                if assessment["risk_score"] >= self.RISK_THRESHOLD_HIGH:
                    stats["flagged_count"] += 1
                    stats["total_flagged_amount"] += Decimal(str(payment.amount))

                if assessment["auto_block"]:
                    stats["blocked_count"] += 1

                # Count reasons
                for reason in assessment["reasons"]:
                    stats["top_fraud_reasons"][reason] = (
                        stats["top_fraud_reasons"].get(reason, 0) + 1
                    )

            except Exception as e:
                logger.error(f"Failed to assess payment {payment.id}: {str(e)}")

        # Convert Decimal to float for JSON serialization
        stats["total_flagged_amount"] = float(stats["total_flagged_amount"])

        # Sort top reasons
        stats["top_fraud_reasons"] = dict(
            sorted(
                stats["top_fraud_reasons"].items(),
                key=lambda x: x[1],
                reverse=True,
            )[:10]
        )

        return stats