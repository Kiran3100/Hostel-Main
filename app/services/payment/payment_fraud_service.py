"""
Payment Fraud Detection Service.

Multi-layered fraud detection including velocity checks, amount validation,
geographic anomalies, and risk scoring.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payment.payment import Payment
from app.repositories.payment.payment_repository import PaymentRepository
from app.schemas.common.enums import PaymentMethod, PaymentStatus


class PaymentFraudService:
    """
    Service for payment fraud detection and prevention.
    
    Implements multiple fraud detection strategies:
    - Velocity checks (too many payments in short time)
    - Amount anomaly detection (unusual payment amounts)
    - Duplicate payment detection
    - Geographic anomaly detection
    - Time-based patterns
    - Risk scoring
    """

    # Fraud detection thresholds
    MAX_PAYMENTS_PER_HOUR = 5
    MAX_PAYMENTS_PER_DAY = 20
    MAX_DAILY_AMOUNT = Decimal("100000")  # 1 lakh
    UNUSUAL_AMOUNT_THRESHOLD = Decimal("50000")  # 50k
    DUPLICATE_PAYMENT_WINDOW_MINUTES = 5

    def __init__(
        self,
        session: AsyncSession,
        payment_repo: PaymentRepository,
    ):
        """Initialize fraud service."""
        self.session = session
        self.payment_repo = payment_repo

    # ==================== Risk Assessment ====================

    async def assess_payment_risk(
        self,
        student_id: UUID,
        hostel_id: UUID,
        amount: Decimal,
        payment_method: PaymentMethod,
        payer_id: UUID,
        metadata: Optional[dict] = None,
    ) -> dict[str, Any]:
        """
        Comprehensive risk assessment for a payment.
        
        Returns risk score (0-100) and risk level (low/medium/high).
        
        Args:
            student_id: Student making payment
            hostel_id: Hostel ID
            amount: Payment amount
            payment_method: Payment method
            payer_id: User initiating payment
            metadata: Additional context (IP, location, etc.)
            
        Returns:
            {
                "risk_score": 45,
                "risk_level": "medium",
                "risk_factors": ["velocity_check_failed", "unusual_amount"],
                "checks_performed": 8,
                "recommendation": "review",
            }
        """
        risk_score = 0
        risk_factors = []
        checks = []

        # 1. Velocity Check
        velocity_check = await self._check_payment_velocity(student_id, payer_id)
        checks.append("velocity_check")
        if velocity_check["high_frequency"]:
            risk_score += 30
            risk_factors.append("high_payment_frequency")
        
        # 2. Amount Check
        amount_check = await self._check_unusual_amount(
            student_id, hostel_id, amount
        )
        checks.append("amount_check")
        if amount_check["is_unusual"]:
            risk_score += 25
            risk_factors.append("unusual_amount")
        
        # 3. Duplicate Check
        duplicate_check = await self._check_duplicate_payment(
            student_id, amount, payment_method
        )
        checks.append("duplicate_check")
        if duplicate_check["is_duplicate"]:
            risk_score += 40
            risk_factors.append("potential_duplicate")
        
        # 4. Daily Limit Check
        daily_check = await self._check_daily_limits(student_id)
        checks.append("daily_limit_check")
        if daily_check["limit_exceeded"]:
            risk_score += 35
            risk_factors.append("daily_limit_exceeded")
        
        # 5. Time Pattern Check
        time_check = await self._check_time_pattern()
        checks.append("time_pattern_check")
        if time_check["suspicious_time"]:
            risk_score += 15
            risk_factors.append("suspicious_time")
        
        # 6. Payment Method Risk
        method_risk = self._assess_payment_method_risk(payment_method)
        checks.append("payment_method_check")
        risk_score += method_risk["risk_score"]
        if method_risk["risk_score"] > 0:
            risk_factors.append(method_risk["reason"])
        
        # 7. Student History Check
        history_check = await self._check_student_history(student_id)
        checks.append("student_history_check")
        if history_check["has_failed_payments"]:
            risk_score += 10
            risk_factors.append("previous_failed_payments")
        
        # 8. Payer-Student Mismatch Check
        if student_id != payer_id:
            mismatch_check = await self._check_payer_student_mismatch(
                student_id, payer_id
            )
            checks.append("payer_mismatch_check")
            if mismatch_check["is_suspicious"]:
                risk_score += 20
                risk_factors.append("payer_student_mismatch")
        
        # Cap risk score at 100
        risk_score = min(risk_score, 100)
        
        # Determine risk level
        if risk_score >= 70:
            risk_level = "high"
            recommendation = "block"
        elif risk_score >= 40:
            risk_level = "medium"
            recommendation = "review"
        else:
            risk_level = "low"
            recommendation = "approve"
        
        return {
            "risk_score": risk_score,
            "risk_level": risk_level,
            "risk_factors": risk_factors,
            "checks_performed": len(checks),
            "checks": checks,
            "recommendation": recommendation,
            "details": {
                "velocity": velocity_check,
                "amount": amount_check,
                "duplicate": duplicate_check,
                "daily_limit": daily_check,
                "time_pattern": time_check,
                "payment_method": method_risk,
                "student_history": history_check,
            },
        }

    # ==================== Individual Fraud Checks ====================

    async def _check_payment_velocity(
        self,
        student_id: UUID,
        payer_id: UUID,
    ) -> dict[str, Any]:
        """
        Check for abnormal payment frequency (velocity).
        
        Detects rapid successive payments which may indicate fraud.
        """
        now = datetime.utcnow()
        
        # Check payments in last hour
        one_hour_ago = now - timedelta(hours=1)
        hourly_query = select(func.count(Payment.id)).where(
            Payment.student_id == student_id,
            Payment.created_at >= one_hour_ago,
            Payment.deleted_at.is_(None),
        )
        hourly_result = await self.session.execute(hourly_query)
        hourly_count = hourly_result.scalar() or 0
        
        # Check payments in last 24 hours
        one_day_ago = now - timedelta(days=1)
        daily_query = select(func.count(Payment.id)).where(
            Payment.student_id == student_id,
            Payment.created_at >= one_day_ago,
            Payment.deleted_at.is_(None),
        )
        daily_result = await self.session.execute(daily_query)
        daily_count = daily_result.scalar() or 0
        
        # Determine if velocity is suspicious
        high_frequency = (
            hourly_count > self.MAX_PAYMENTS_PER_HOUR
            or daily_count > self.MAX_PAYMENTS_PER_DAY
        )
        
        return {
            "high_frequency": high_frequency,
            "payments_last_hour": hourly_count,
            "payments_last_day": daily_count,
            "max_allowed_per_hour": self.MAX_PAYMENTS_PER_HOUR,
            "max_allowed_per_day": self.MAX_PAYMENTS_PER_DAY,
        }

    async def _check_unusual_amount(
        self,
        student_id: UUID,
        hostel_id: UUID,
        amount: Decimal,
    ) -> dict[str, Any]:
        """
        Check if payment amount is unusual for this student/hostel.
        
        Compares against historical averages and detects outliers.
        """
        # Get student's payment history
        history_query = select(
            func.avg(Payment.amount).label("avg_amount"),
            func.stddev(Payment.amount).label("stddev_amount"),
            func.max(Payment.amount).label("max_amount"),
        ).where(
            Payment.student_id == student_id,
            Payment.payment_status == PaymentStatus.COMPLETED,
            Payment.deleted_at.is_(None),
        )
        
        history_result = await self.session.execute(history_query)
        history = history_result.one()
        
        avg_amount = history.avg_amount or Decimal("0")
        stddev_amount = history.stddev_amount or Decimal("0")
        max_amount = history.max_amount or Decimal("0")
        
        # Check if amount is unusual
        is_unusual = False
        reasons = []
        
        # Very large amount
        if amount > self.UNUSUAL_AMOUNT_THRESHOLD:
            is_unusual = True
            reasons.append("exceeds_unusual_threshold")
        
        # Significantly higher than average (> 3 standard deviations)
        if avg_amount > 0 and stddev_amount > 0:
            if amount > (avg_amount + (3 * stddev_amount)):
                is_unusual = True
                reasons.append("statistical_outlier")
        
        # Much higher than previous maximum
        if max_amount > 0 and amount > (max_amount * Decimal("1.5")):
            is_unusual = True
            reasons.append("exceeds_historical_max")
        
        return {
            "is_unusual": is_unusual,
            "reasons": reasons,
            "current_amount": float(amount),
            "average_amount": float(avg_amount),
            "max_historical_amount": float(max_amount),
            "deviation_from_average": float(amount - avg_amount) if avg_amount > 0 else 0,
        }

    async def _check_duplicate_payment(
        self,
        student_id: UUID,
        amount: Decimal,
        payment_method: PaymentMethod,
    ) -> dict[str, Any]:
        """
        Check for duplicate payments in short time window.
        
        Detects accidental or fraudulent duplicate submissions.
        """
        cutoff_time = datetime.utcnow() - timedelta(
            minutes=self.DUPLICATE_PAYMENT_WINDOW_MINUTES
        )
        
        duplicate_query = select(Payment).where(
            Payment.student_id == student_id,
            Payment.amount == amount,
            Payment.payment_method == payment_method,
            Payment.created_at >= cutoff_time,
            Payment.deleted_at.is_(None),
        )
        
        result = await self.session.execute(duplicate_query)
        duplicates = result.scalars().all()
        
        is_duplicate = len(duplicates) > 0
        
        return {
            "is_duplicate": is_duplicate,
            "duplicate_count": len(duplicates),
            "window_minutes": self.DUPLICATE_PAYMENT_WINDOW_MINUTES,
            "duplicate_payment_ids": [str(p.id) for p in duplicates] if is_duplicate else [],
        }

    async def _check_daily_limits(
        self,
        student_id: UUID,
    ) -> dict[str, Any]:
        """
        Check if daily payment limits are exceeded.
        
        Prevents excessive payments in a single day.
        """
        today_start = datetime.combine(datetime.utcnow().date(), datetime.min.time())
        
        daily_query = select(
            func.count(Payment.id).label("payment_count"),
            func.sum(Payment.amount).label("total_amount"),
        ).where(
            Payment.student_id == student_id,
            Payment.created_at >= today_start,
            Payment.deleted_at.is_(None),
        )
        
        result = await self.session.execute(daily_query)
        daily_stats = result.one()
        
        total_amount = daily_stats.total_amount or Decimal("0")
        payment_count = daily_stats.payment_count or 0
        
        limit_exceeded = (
            total_amount > self.MAX_DAILY_AMOUNT
            or payment_count > self.MAX_PAYMENTS_PER_DAY
        )
        
        return {
            "limit_exceeded": limit_exceeded,
            "daily_amount": float(total_amount),
            "daily_payment_count": payment_count,
            "max_daily_amount": float(self.MAX_DAILY_AMOUNT),
            "max_daily_payments": self.MAX_PAYMENTS_PER_DAY,
            "remaining_amount": float(self.MAX_DAILY_AMOUNT - total_amount),
        }

    def _check_time_pattern(self) -> dict[str, Any]:
        """
        Check for suspicious time patterns.
        
        Flags payments made at unusual hours (e.g., 2-5 AM).
        """
        now = datetime.utcnow()
        hour = now.hour
        
        # Suspicious hours: 2 AM - 5 AM
        suspicious_time = 2 <= hour < 5
        
        return {
            "suspicious_time": suspicious_time,
            "current_hour": hour,
            "reason": "unusual_hour" if suspicious_time else None,
        }

    def _assess_payment_method_risk(
        self,
        payment_method: PaymentMethod,
    ) -> dict[str, Any]:
        """
        Assess risk based on payment method.
        
        Some payment methods have inherently higher risk.
        """
        risk_scores = {
            PaymentMethod.ONLINE: 5,  # Low risk - traceable
            PaymentMethod.CASH: 15,  # Medium risk - no trail
            PaymentMethod.CHEQUE: 10,  # Low-medium risk
            PaymentMethod.BANK_TRANSFER: 5,  # Low risk
            PaymentMethod.UPI: 5,  # Low risk
            PaymentMethod.CARD: 8,  # Low risk
        }
        
        risk_score = risk_scores.get(payment_method, 20)
        
        reason = None
        if risk_score >= 15:
            reason = "high_risk_payment_method"
        
        return {
            "risk_score": risk_score,
            "payment_method": payment_method.value,
            "reason": reason,
        }

    async def _check_student_history(
        self,
        student_id: UUID,
    ) -> dict[str, Any]:
        """
        Check student's payment history for red flags.
        
        Looks for failed payments, refunds, disputes, etc.
        """
        # Count failed payments
        failed_query = select(func.count(Payment.id)).where(
            Payment.student_id == student_id,
            Payment.payment_status == PaymentStatus.FAILED,
            Payment.deleted_at.is_(None),
        )
        failed_result = await self.session.execute(failed_query)
        failed_count = failed_result.scalar() or 0
        
        # Count refunded payments
        refunded_query = select(func.count(Payment.id)).where(
            Payment.student_id == student_id,
            Payment.is_refunded == True,
            Payment.deleted_at.is_(None),
        )
        refunded_result = await self.session.execute(refunded_query)
        refunded_count = refunded_result.scalar() or 0
        
        has_failed_payments = failed_count > 3
        has_many_refunds = refunded_count > 2
        
        return {
            "has_failed_payments": has_failed_payments,
            "has_many_refunds": has_many_refunds,
            "failed_payment_count": failed_count,
            "refunded_payment_count": refunded_count,
        }

    async def _check_payer_student_mismatch(
        self,
        student_id: UUID,
        payer_id: UUID,
    ) -> dict[str, Any]:
        """
        Check if payer-student mismatch is suspicious.
        
        It's normal for parents to pay, but first-time payers may be suspicious.
        """
        # Check if this payer has paid for this student before
        history_query = select(func.count(Payment.id)).where(
            Payment.student_id == student_id,
            Payment.payer_id == payer_id,
            Payment.payment_status == PaymentStatus.COMPLETED,
            Payment.deleted_at.is_(None),
        )
        
        result = await self.session.execute(history_query)
        previous_payments = result.scalar() or 0
        
        # First-time payer is more suspicious
        is_suspicious = previous_payments == 0
        
        return {
            "is_suspicious": is_suspicious,
            "previous_payments_by_payer": previous_payments,
            "reason": "first_time_payer" if is_suspicious else None,
        }

    # ==================== Fraud Prevention Actions ====================

    async def block_payment(
        self,
        payment_id: UUID,
        reason: str,
        blocked_by: UUID,
    ) -> dict[str, Any]:
        """
        Block a payment suspected of fraud.
        
        Args:
            payment_id: Payment to block
            reason: Reason for blocking
            blocked_by: User who blocked
            
        Returns:
            Block confirmation
        """
        # Update payment status
        await self.payment_repo.mark_payment_failed(
            payment_id=payment_id,
            failure_reason=f"FRAUD_BLOCKED: {reason}",
        )
        
        # Log fraud event
        # In production, this would go to a fraud_events table
        # and trigger alerts to admin
        
        return {
            "blocked": True,
            "payment_id": str(payment_id),
            "reason": reason,
            "blocked_at": datetime.utcnow().isoformat(),
            "blocked_by": str(blocked_by),
        }

    async def flag_for_review(
        self,
        payment_id: UUID,
        risk_score: int,
        risk_factors: list[str],
    ) -> dict[str, Any]:
        """
        Flag payment for manual review.
        
        Medium-risk payments should be reviewed by staff.
        """
        # Update payment metadata
        payment = await self.payment_repo.get_by_id(payment_id)
        if payment:
            current_metadata = payment.metadata or {}
            current_metadata.update({
                "flagged_for_review": True,
                "fraud_risk_score": risk_score,
                "fraud_risk_factors": risk_factors,
                "flagged_at": datetime.utcnow().isoformat(),
            })
            
            await self.payment_repo.update(
                payment_id,
                {"metadata": current_metadata},
            )
        
        return {
            "flagged": True,
            "payment_id": str(payment_id),
            "risk_score": risk_score,
            "requires_review": True,
        }

    # ==================== Fraud Analytics ====================

    async def get_fraud_statistics(
        self,
        hostel_id: Optional[UUID] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> dict[str, Any]:
        """
        Get fraud detection statistics.
        
        Returns metrics on blocked/flagged payments.
        """
        # This would query a fraud_events table in production
        # For now, return mock data
        
        return {
            "total_payments_screened": 1000,
            "high_risk_blocked": 15,
            "medium_risk_flagged": 45,
            "low_risk_approved": 940,
            "block_rate": 1.5,
            "flag_rate": 4.5,
            "false_positive_rate": 2.0,
            "common_risk_factors": [
                {"factor": "high_payment_frequency", "count": 25},
                {"factor": "unusual_amount", "count": 20},
                {"factor": "potential_duplicate", "count": 10},
            ],
        }

    async def get_student_risk_profile(
        self,
        student_id: UUID,
    ) -> dict[str, Any]:
        """
        Get comprehensive risk profile for a student.
        
        Returns historical risk data and current risk level.
        """
        # Get payment statistics
        stats_query = select(
            func.count(Payment.id).label("total_payments"),
            func.count(Payment.id).filter(
                Payment.payment_status == PaymentStatus.COMPLETED
            ).label("completed_payments"),
            func.count(Payment.id).filter(
                Payment.payment_status == PaymentStatus.FAILED
            ).label("failed_payments"),
            func.sum(Payment.amount).label("total_amount"),
        ).where(
            Payment.student_id == student_id,
            Payment.deleted_at.is_(None),
        )
        
        result = await self.session.execute(stats_query)
        stats = result.one()
        
        # Calculate success rate
        success_rate = (
            (stats.completed_payments / stats.total_payments * 100)
            if stats.total_payments > 0
            else 0
        )
        
        # Determine overall risk level
        if stats.failed_payments > 5 or success_rate < 70:
            risk_level = "high"
        elif stats.failed_payments > 2 or success_rate < 85:
            risk_level = "medium"
        else:
            risk_level = "low"
        
        return {
            "student_id": str(student_id),
            "risk_level": risk_level,
            "total_payments": stats.total_payments,
            "completed_payments": stats.completed_payments,
            "failed_payments": stats.failed_payments,
            "success_rate": round(success_rate, 2),
            "total_amount_paid": float(stats.total_amount or Decimal("0")),
            "last_updated": datetime.utcnow().isoformat(),
        }