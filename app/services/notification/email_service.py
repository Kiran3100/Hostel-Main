# app/services/notification/email_service.py
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import List, Optional, Protocol
from uuid import UUID, uuid4

from app.schemas.notification.email_notification import (
    EmailRequest,
    EmailConfig,
    EmailTracking,
    BulkEmailRequest,
    EmailStats,
)
from app.schemas.common.filters import DateRangeFilter
from app.services.common import errors


class EmailProvider(Protocol):
    """
    Provider-agnostic email sender (SendGrid, SES, SMTP, etc.).
    """

    def send_email(self, request: EmailRequest, config: EmailConfig) -> Optional[str]:
        """
        Send a single email.

        Returns:
            provider_message_id (if available) or None.
        """
        ...

    def send_bulk(
        self,
        request: BulkEmailRequest,
        config: EmailConfig,
    ) -> List[Optional[str]]:
        """
        Send a bulk email.

        Returns:
            List of provider_message_id per recipient (same order as recipients).
        """
        ...


class EmailConfigStore(Protocol):
    """
    Storage abstraction for EmailConfig.
    """

    def get_config(self) -> Optional[dict]: ...
    def save_config(self, data: dict) -> None: ...


class EmailTrackingStore(Protocol):
    """
    Storage abstraction for EmailTracking records.
    """

    def save_tracking(self, record: dict) -> None: ...
    def get_tracking(self, email_id: UUID) -> Optional[dict]: ...
    def list_tracking_range(self, *, start: date, end: date) -> List[dict]: ...


class EmailService:
    """
    Email sending + basic tracking/stats.

    - get/set EmailConfig
    - send single email (returns EmailTracking)
    - send bulk emails (returns EmailStats)
    - compute stats over a period
    """

    def __init__(
        self,
        config_store: EmailConfigStore,
        tracking_store: EmailTrackingStore,
        provider: EmailProvider,
    ) -> None:
        self._config_store = config_store
        self._tracking_store = tracking_store
        self._provider = provider

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    # ------------------------------------------------------------------ #
    # Config
    # ------------------------------------------------------------------ #
    def get_config(self) -> EmailConfig:
        record = self._config_store.get_config()
        if not record:
            raise errors.ServiceError("Email configuration not set")
        return EmailConfig.model_validate(record)

    def set_config(self, cfg: EmailConfig) -> None:
        self._config_store.save_config(cfg.model_dump())

    # ------------------------------------------------------------------ #
    # Send
    # ------------------------------------------------------------------ #
    def send_email(self, request: EmailRequest) -> EmailTracking:
        """
        Send a single email and persist an EmailTracking record.
        """
        config = self.get_config()
        email_id = uuid4()
        sent_at = self._now()

        status = "sent"
        delivered_at = None
        bounced_at = None
        error_message: Optional[str] = None
        provider_message_id: Optional[str] = None

        try:
            provider_message_id = self._provider.send_email(request, config)
        except Exception as exc:  # pragma: no cover - provider-specific
            status = "failed"
            error_message = str(exc)

        record = {
            "email_id": email_id,
            "recipient_email": str(request.recipient_email),
            "sent_at": sent_at,
            "delivered_at": delivered_at,
            "bounced_at": bounced_at,
            "delivery_status": status,  # sent|delivered|bounced|failed|spam
            "opened": False,
            "first_opened_at": None,
            "open_count": 0,
            "clicked": False,
            "first_clicked_at": None,
            "click_count": 0,
            "bounce_type": None,
            "error_message": error_message,
        }
        self._tracking_store.save_tracking(record)
        return EmailTracking.model_validate(record)

    def send_bulk(self, request: BulkEmailRequest) -> EmailStats:
        """
        Simple bulk implementation via fan-out to send_email.

        For large volumes, prefer a queue/worker.
        """
        if not request.recipients:
            raise errors.ValidationError("At least one recipient is required")

        total_sent = 0
        total_failed = 0

        for recipient in request.recipients:
            single_req = EmailRequest(
                recipient_email=recipient,
                cc_emails=[],
                bcc_emails=[],
                subject=request.subject,
                body_html=request.body_html,
                body_text=None,
                attachments=[],
                template_code=request.template_code,
                template_variables=(
                    (request.recipient_variables or {}).get(str(recipient))
                    if request.recipient_variables
                    else None
                ),
                reply_to=None,
                from_name=None,
                track_opens=True,
                track_clicks=True,
                priority="normal",
            )
            tracking = self.send_email(single_req)
            total_sent += 1
            if tracking.delivery_status != "sent":
                total_failed += 1

        total_delivered = total_sent - total_failed
        total_bounced = 0  # bounce webhooks would update this later

        def _pct(num: int, denom: int) -> Decimal:
            return (
                Decimal(str(num)) / Decimal(str(denom)) * Decimal("100")
                if denom > 0
                else Decimal("0")
            )

        today = date.today()

        return EmailStats(
            total_sent=total_sent,
            total_delivered=total_delivered,
            total_bounced=total_bounced,
            total_failed=total_failed,
            delivery_rate=_pct(total_delivered, total_sent),
            bounce_rate=_pct(total_bounced, total_sent),
            total_opened=0,
            open_rate=Decimal("0"),
            total_clicked=0,
            click_rate=Decimal("0"),
            period_start=today,
            period_end=today,
        )

    # ------------------------------------------------------------------ #
    # Stats
    # ------------------------------------------------------------------ #
    def get_stats(self, period: DateRangeFilter) -> EmailStats:
        """
        Aggregate stats from tracking store for a given period.
        """
        start = period.start_date or date.min
        end = period.end_date or date.max

        records = self._tracking_store.list_tracking_range(start=start, end=end)
        total_sent = len(records)
        total_delivered = sum(1 for r in records if r.get("delivery_status") == "delivered")
        total_failed = sum(1 for r in records if r.get("delivery_status") == "failed")
        total_bounced = sum(1 for r in records if r.get("delivery_status") == "bounced")

        total_opened = sum(1 for r in records if r.get("opened"))
        total_clicked = sum(1 for r in records if r.get("clicked"))

        def _pct(num: int, denom: int) -> Decimal:
            return (
                Decimal(str(num)) / Decimal(str(denom)) * Decimal("100")
                if denom > 0
                else Decimal("0")
            )

        return EmailStats(
            total_sent=total_sent,
            total_delivered=total_delivered,
            total_bounced=total_bounced,
            total_failed=total_failed,
            delivery_rate=_pct(total_delivered, total_sent),
            bounce_rate=_pct(total_bounced, total_sent),
            total_opened=total_opened,
            open_rate=_pct(total_opened, total_sent),
            total_clicked=total_clicked,
            click_rate=_pct(total_clicked, total_sent),
            period_start=start,
            period_end=end,
        )