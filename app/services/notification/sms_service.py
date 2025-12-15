# app/services/notification/sms_service.py
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import List, Optional, Protocol
from uuid import UUID, uuid4

from app.schemas.notification.sms_notification import (
    SMSRequest,
    SMSConfig,
    DeliveryStatus as SMSDeliveryStatus,
    SMSTemplate,
    BulkSMSRequest,
    SMSStats,
)
from app.schemas.common.filters import DateRangeFilter
from app.services.common import errors


class SMSProvider(Protocol):
    """
    Provider-agnostic SMS sender (Twilio, SNS, MSG91, etc.).
    """

    def send_sms(self, request: SMSRequest, config: SMSConfig) -> Optional[str]:
        """
        Send a single SMS. Returns provider_message_id or None.
        """
        ...

    def send_bulk(
        self,
        request: BulkSMSRequest,
        config: SMSConfig,
    ) -> List[Optional[str]]:
        """
        Send bulk SMS messages. Returns list of provider_message_id per recipient.
        """
        ...


class SMSConfigStore(Protocol):
    """Storage for SMSConfig."""

    def get_config(self) -> Optional[dict]: ...
    def save_config(self, data: dict) -> None: ...


class SMSStatusStore(Protocol):
    """Storage for SMS delivery status records."""

    def save_status(self, record: dict) -> None: ...
    def get_status(self, sms_id: UUID) -> Optional[dict]: ...
    def list_status_range(self, *, start: date, end: date) -> List[dict]: ...


class SMSService:
    """
    SMS sending + basic delivery status & stats.
    """

    def __init__(
        self,
        config_store: SMSConfigStore,
        status_store: SMSStatusStore,
        provider: SMSProvider,
    ) -> None:
        self._config_store = config_store
        self._status_store = status_store
        self._provider = provider

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    # ------------------------------------------------------------------ #
    # Config
    # ------------------------------------------------------------------ #
    def get_config(self) -> SMSConfig:
        record = self._config_store.get_config()
        if not record:
            raise errors.ServiceError("SMS configuration not set")
        return SMSConfig.model_validate(record)

    def set_config(self, cfg: SMSConfig) -> None:
        self._config_store.save_config(cfg.model_dump())

    # ------------------------------------------------------------------ #
    # Send
    # ------------------------------------------------------------------ #
    def send_sms(self, request: SMSRequest) -> SMSDeliveryStatus:
        """
        Send a single SMS and persist DeliveryStatus.
        """
        config = self.get_config()
        sms_id = uuid4()
        now = self._now()

        status = "queued"
        error_message: Optional[str] = None
        provider_message_id: Optional[str] = None

        try:
            provider_message_id = self._provider.send_sms(request, config)
            status = "sent"
        except Exception as exc:  # pragma: no cover
            status = "failed"
            error_message = str(exc)

        record = {
            "sms_id": sms_id,
            "recipient_phone": request.recipient_phone,
            "status": status,  # queued|sent|delivered|failed|undelivered
            "queued_at": now,
            "sent_at": now if status == "sent" else None,
            "delivered_at": None,
            "failed_at": now if status == "failed" else None,
            "error_code": None,
            "error_message": error_message,
            "provider_message_id": provider_message_id,
            "segments_count": 1,
            "cost": None,
        }
        self._status_store.save_status(record)
        return SMSDeliveryStatus.model_validate(record)

    def send_bulk(self, request: BulkSMSRequest) -> SMSStats:
        """
        Naive bulk implementation via fan-out to send_sms.
        """
        if not request.recipients:
            raise errors.ValidationError("At least one recipient is required")

        total_sent = 0
        total_failed = 0
        total_segments = 0

        for phone in request.recipients:
            single_req = SMSRequest(
                recipient_phone=phone,
                message=request.message,
                template_code=request.template_code,
                template_variables=(
                    (request.recipient_variables or {}).get(phone)
                    if request.recipient_variables
                    else None
                ),
                sender_id=None,
                priority="normal",
                dlt_template_id=None,
            )
            status = self.send_sms(single_req)
            total_sent += 1
            total_segments += status.segments_count
            if status.status != "sent":
                total_failed += 1

        total_delivered = total_sent - total_failed

        def _pct(num: int, denom: int) -> Decimal:
            return (
                Decimal(str(num)) / Decimal(str(denom)) * Decimal("100")
                if denom > 0
                else Decimal("0")
            )

        today = date.today()
        total_cost = Decimal("0")
        avg_cost = Decimal("0")
        avg_seg = (
            Decimal(str(total_segments)) / Decimal(str(total_sent))
            if total_sent > 0
            else Decimal("0")
        )

        return SMSStats(
            total_sent=total_sent,
            total_delivered=total_delivered,
            total_failed=total_failed,
            delivery_rate=_pct(total_delivered, total_sent),
            failure_rate=_pct(total_failed, total_sent),
            total_cost=total_cost,
            average_cost_per_sms=avg_cost,
            total_segments=total_segments,
            average_segments_per_sms=avg_seg,
            period_start=today,
            period_end=today,
        )

    # ------------------------------------------------------------------ #
    # Stats
    # ------------------------------------------------------------------ #
    def get_stats(self, period: DateRangeFilter) -> SMSStats:
        start = period.start_date or date.min
        end = period.end_date or date.max

        records = self._status_store.list_status_range(start=start, end=end)
        total_sent = len(records)
        total_delivered = sum(1 for r in records if r.get("status") == "delivered")
        total_failed = sum(1 for r in records if r.get("status") == "failed")
        total_segments = sum(int(r.get("segments_count", 1)) for r in records)

        def _pct(num: int, denom: int) -> Decimal:
            return (
                Decimal(str(num)) / Decimal(str(denom)) * Decimal("100")
                if denom > 0
                else Decimal("0")
            )

        total_cost = sum(
            Decimal(str(r.get("cost"))) for r in records if r.get("cost") is not None
        ) or Decimal("0")
        avg_cost = (
            total_cost / Decimal(str(total_sent)) if total_sent > 0 else Decimal("0")
        )
        avg_seg = (
            Decimal(str(total_segments)) / Decimal(str(total_sent))
            if total_sent > 0
            else Decimal("0")
        )

        return SMSStats(
            total_sent=total_sent,
            total_delivered=total_delivered,
            total_failed=total_failed,
            delivery_rate=_pct(total_delivered, total_sent),
            failure_rate=_pct(total_failed, total_sent),
            total_cost=total_cost,
            average_cost_per_sms=avg_cost,
            total_segments=total_segments,
            average_segments_per_sms=avg_seg,
            period_start=start,
            period_end=end,
        )