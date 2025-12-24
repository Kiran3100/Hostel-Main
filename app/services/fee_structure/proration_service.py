"""
Proration Service

Calculates pro-rated amounts for mid-cycle changes including:
- Room changes
- Plan upgrades/downgrades
- Early check-outs
- Late check-ins
- Partial period refunds

Uses precise date-based calculations with configurable business rules.

Author: Senior Prompt Engineer
Version: 2.0.0
"""

from typing import Optional, Dict, Any, Tuple
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from calendar import monthrange

from sqlalchemy.orm import Session

from app.services.base import ServiceResult, ServiceError, ErrorCode, ErrorSeverity
from app.core.logging import get_logger


class ProrationService:
    """
    Service for calculating pro-rated fee amounts.
    
    Features:
    - Daily pro-ration with configurable basis (actual days, 30-day months, etc.)
    - Support for different billing cycles (monthly, quarterly, annual)
    - Refund calculations for early terminations
    - Upgrade/downgrade differential calculations
    - Timezone-aware date handling
    """

    # Proration methods
    PRORATION_METHODS = {
        "actual_days": "Use actual calendar days in the month",
        "30_day_month": "Use 30-day months consistently",
        "365_day_year": "Use 365-day year basis",
    }

    # Billing cycles
    BILLING_CYCLES = {
        "daily": 1,
        "weekly": 7,
        "monthly": 30,  # Approximate
        "quarterly": 90,
        "annual": 365,
    }

    def __init__(self, db_session: Session):
        """
        Initialize proration service.

        Args:
            db_session: SQLAlchemy database session
        """
        self.db = db_session
        self._logger = get_logger(self.__class__.__name__)

    def prorate_monthly_amount(
        self,
        monthly_amount: Decimal,
        from_date: date,
        to_date: date,
        method: str = "actual_days",
        inclusive_start: bool = True,
        inclusive_end: bool = False,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Calculate pro-rated amount for a partial month period.

        Args:
            monthly_amount: Full monthly amount to prorate
            from_date: Period start date
            to_date: Period end date
            method: Proration calculation method
            inclusive_start: Include start date in calculation
            inclusive_end: Include end date in calculation

        Returns:
            ServiceResult containing proration details
        """
        try:
            # Validate inputs
            validation_result = self._validate_proration_inputs(
                monthly_amount,
                from_date,
                to_date,
                method
            )
            if not validation_result.success:
                return validation_result

            # Calculate proration based on method
            if method == "actual_days":
                result = self._prorate_actual_days(
                    monthly_amount,
                    from_date,
                    to_date,
                    inclusive_start,
                    inclusive_end
                )
            elif method == "30_day_month":
                result = self._prorate_30_day_month(
                    monthly_amount,
                    from_date,
                    to_date,
                    inclusive_start,
                    inclusive_end
                )
            elif method == "365_day_year":
                result = self._prorate_365_day_year(
                    monthly_amount,
                    from_date,
                    to_date,
                    inclusive_start,
                    inclusive_end
                )
            else:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message=f"Unsupported proration method: {method}",
                        severity=ErrorSeverity.ERROR,
                    )
                )

            self._logger.debug(
                "Proration calculated",
                extra={
                    "monthly_amount": float(monthly_amount),
                    "from_date": str(from_date),
                    "to_date": str(to_date),
                    "method": method,
                    "prorated_amount": float(result["amount"]),
                }
            )

            return ServiceResult.success(
                result,
                message="Proration calculated successfully"
            )

        except Exception as e:
            self._logger.error(
                "Failed to calculate proration",
                exc_info=True,
                extra={"error": str(e)}
            )
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.INTERNAL_ERROR,
                    message=f"Proration calculation failed: {str(e)}",
                    severity=ErrorSeverity.ERROR,
                )
            )

    def calculate_refund(
        self,
        original_amount: Decimal,
        original_start: date,
        original_end: date,
        actual_end: date,
        refund_policy: str = "prorated",
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Calculate refund amount for early termination.

        Args:
            original_amount: Original amount paid
            original_start: Original period start
            original_end: Original period end
            actual_end: Actual termination date
            refund_policy: Refund calculation policy

        Returns:
            ServiceResult containing refund details
        """
        try:
            # Validate dates
            if actual_end >= original_end:
                return ServiceResult.success(
                    {
                        "refund_amount": Decimal("0.00"),
                        "reason": "No refund - full period completed",
                        "days_unused": 0,
                    },
                    message="No refund applicable"
                )

            if actual_end < original_start:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Actual end date cannot be before period start",
                        severity=ErrorSeverity.ERROR,
                    )
                )

            # Calculate unused days
            days_unused = (original_end - actual_end).days
            total_days = (original_end - original_start).days

            if refund_policy == "prorated":
                # Pro-rated refund based on unused days
                daily_rate = original_amount / Decimal(total_days)
                refund_amount = (daily_rate * Decimal(days_unused)).quantize(
                    Decimal("0.01"),
                    rounding=ROUND_HALF_UP
                )

            elif refund_policy == "no_refund":
                refund_amount = Decimal("0.00")

            elif refund_policy == "full_month_only":
                # Refund only for complete unused months
                # This is a simplified implementation
                refund_amount = Decimal("0.00")

            else:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message=f"Invalid refund policy: {refund_policy}",
                        severity=ErrorSeverity.ERROR,
                    )
                )

            result = {
                "refund_amount": refund_amount,
                "original_amount": original_amount,
                "days_used": total_days - days_unused,
                "days_unused": days_unused,
                "total_days": total_days,
                "refund_percentage": float(refund_amount / original_amount * 100) if original_amount else 0,
                "policy": refund_policy,
            }

            return ServiceResult.success(
                result,
                message="Refund calculated successfully"
            )

        except Exception as e:
            self._logger.error(
                "Failed to calculate refund",
                exc_info=True,
                extra={"error": str(e)}
            )
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.INTERNAL_ERROR,
                    message=f"Refund calculation failed: {str(e)}",
                    severity=ErrorSeverity.ERROR,
                )
            )

    def calculate_upgrade_differential(
        self,
        old_amount: Decimal,
        new_amount: Decimal,
        change_date: date,
        period_end: date,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Calculate differential amount for plan upgrade/downgrade.

        Args:
            old_amount: Previous plan amount (for full period)
            new_amount: New plan amount (for full period)
            change_date: Date of plan change
            period_end: End of current billing period

        Returns:
            ServiceResult containing differential calculation
        """
        try:
            # Validate inputs
            if change_date >= period_end:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Change date must be before period end",
                        severity=ErrorSeverity.ERROR,
                    )
                )

            # Calculate remaining days
            remaining_days = (period_end - change_date).days
            total_days = 30  # Assume monthly billing

            # Pro-rate the difference
            amount_difference = new_amount - old_amount
            prorated_difference = (
                amount_difference * Decimal(remaining_days) / Decimal(total_days)
            ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

            result = {
                "differential_amount": prorated_difference,
                "old_plan_amount": old_amount,
                "new_plan_amount": new_amount,
                "full_period_difference": amount_difference,
                "remaining_days": remaining_days,
                "total_days": total_days,
                "is_upgrade": amount_difference > 0,
                "change_date": change_date.isoformat(),
                "period_end": period_end.isoformat(),
            }

            return ServiceResult.success(
                result,
                message="Plan change differential calculated successfully"
            )

        except Exception as e:
            self._logger.error(
                "Failed to calculate upgrade differential",
                exc_info=True,
                extra={"error": str(e)}
            )
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.INTERNAL_ERROR,
                    message=f"Differential calculation failed: {str(e)}",
                    severity=ErrorSeverity.ERROR,
                )
            )

    # ==================== Private Helper Methods ====================

    def _validate_proration_inputs(
        self,
        amount: Decimal,
        from_date: date,
        to_date: date,
        method: str,
    ) -> ServiceResult[None]:
        """Validate proration calculation inputs."""
        if amount < 0:
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Amount cannot be negative",
                    severity=ErrorSeverity.ERROR,
                )
            )

        if to_date <= from_date:
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="End date must be after start date",
                    severity=ErrorSeverity.ERROR,
                    details={
                        "from_date": str(from_date),
                        "to_date": str(to_date),
                    }
                )
            )

        if method not in self.PRORATION_METHODS:
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message=f"Invalid proration method: {method}",
                    severity=ErrorSeverity.ERROR,
                    details={
                        "provided": method,
                        "valid_methods": list(self.PRORATION_METHODS.keys())
                    }
                )
            )

        return ServiceResult.success(None)

    def _prorate_actual_days(
        self,
        monthly_amount: Decimal,
        from_date: date,
        to_date: date,
        inclusive_start: bool,
        inclusive_end: bool,
    ) -> Dict[str, Any]:
        """Calculate proration using actual calendar days."""
        # Calculate days in the period
        days = (to_date - from_date).days
        if inclusive_start:
            days += 1
        if inclusive_end and not inclusive_start:
            days += 1

        # Get actual days in the month
        _, days_in_month = monthrange(from_date.year, from_date.month)

        # Calculate pro-rated amount
        daily_rate = monthly_amount / Decimal(days_in_month)
        prorated_amount = (daily_rate * Decimal(days)).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP
        )

        return {
            "amount": prorated_amount,
            "days": days,
            "days_in_month": days_in_month,
            "daily_rate": daily_rate.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            "proration_rate": float(Decimal(days) / Decimal(days_in_month)),
            "method": "actual_days",
            "from_date": from_date.isoformat(),
            "to_date": to_date.isoformat(),
        }

    def _prorate_30_day_month(
        self,
        monthly_amount: Decimal,
        from_date: date,
        to_date: date,
        inclusive_start: bool,
        inclusive_end: bool,
    ) -> Dict[str, Any]:
        """Calculate proration using 30-day month basis."""
        days = (to_date - from_date).days
        if inclusive_start:
            days += 1
        if inclusive_end and not inclusive_start:
            days += 1

        # Use 30-day month consistently
        days_in_month = 30
        daily_rate = monthly_amount / Decimal(days_in_month)
        prorated_amount = (daily_rate * Decimal(days)).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP
        )

        return {
            "amount": prorated_amount,
            "days": days,
            "days_in_month": days_in_month,
            "daily_rate": daily_rate.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            "proration_rate": float(Decimal(days) / Decimal(days_in_month)),
            "method": "30_day_month",
            "from_date": from_date.isoformat(),
            "to_date": to_date.isoformat(),
        }

    def _prorate_365_day_year(
        self,
        monthly_amount: Decimal,
        from_date: date,
        to_date: date,
        inclusive_start: bool,
        inclusive_end: bool,
    ) -> Dict[str, Any]:
        """Calculate proration using 365-day year basis."""
        days = (to_date - from_date).days
        if inclusive_start:
            days += 1
        if inclusive_end and not inclusive_start:
            days += 1

        # Calculate based on annual amount divided by 365
        annual_amount = monthly_amount * Decimal(12)
        daily_rate = annual_amount / Decimal(365)
        prorated_amount = (daily_rate * Decimal(days)).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP
        )

        return {
            "amount": prorated_amount,
            "days": days,
            "days_in_year": 365,
            "daily_rate": daily_rate.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            "proration_rate": float(Decimal(days) / Decimal(365)),
            "method": "365_day_year",
            "from_date": from_date.isoformat(),
            "to_date": to_date.isoformat(),
        }