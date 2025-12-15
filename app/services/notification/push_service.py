# app/services/notification/push_service.py
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import List, Optional, Protocol
from uuid import UUID, uuid4

from app.schemas.notification.push_notification import (
    PushRequest,
    PushConfig,
    DeviceRegistration,
    DeviceUnregistration,
    DeviceToken,
    PushDeliveryStatus,
    PushStats,
)
from app.schemas.common.filters import DateRangeFilter
from app.services.common import errors


class PushProvider(Protocol):
    """
    Provider-agnostic push sender (FCM/APNs/etc).
    """

    def send(self, request: PushRequest, config: PushConfig, device_token: str) -> Optional[str]:
        """
        Send a push notification to a single device_token.
        Returns provider_message_id or None.
        """
        ...


class PushConfigStore(Protocol):
    """Storage for PushConfig."""

    def get_config(self) -> Optional[dict]: ...
    def save_config(self, data: dict) -> None: ...


class DeviceStore(Protocol):
    """
    Storage for device tokens and delivery statuses.
    """

    # Device tokens
    def save_device(self, record: dict) -> dict: ...
    def get_device(self, device_token: str) -> Optional[dict]: ...
    def deactivate_device(self, device_token: str) -> None: ...
    def list_devices_for_user(self, user_id: UUID) -> List[dict]: ...

    # Delivery status
    def save_delivery_status(self, record: dict) -> None: ...
    def list_delivery_status_range(self, *, start: date, end: date) -> List[dict]: ...


class PushService:
    """
    Push notifications & device registration.

    - Configure push (PushConfig)
    - Register / unregister devices
    - Send push (to user or explicit tokens)
    - Basic stats from delivery records
    """

    def __init__(
        self,
        config_store: PushConfigStore,
        device_store: DeviceStore,
        provider: PushProvider,
    ) -> None:
        self._config_store = config_store
        self._device_store = device_store
        self._provider = provider

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    # ------------------------------------------------------------------ #
    # Config
    # ------------------------------------------------------------------ #
    def get_config(self) -> PushConfig:
        record = self._config_store.get_config()
        if not record:
            raise errors.ServiceError("Push configuration not set")
        return PushConfig.model_validate(record)

    def set_config(self, cfg: PushConfig) -> None:
        self._config_store.save_config(cfg.model_dump())

    # ------------------------------------------------------------------ #
    # Device registration
    # ------------------------------------------------------------------ #
    def register_device(self, req: DeviceRegistration) -> DeviceToken:
        """
        Register (or update) a device token for a user.
        """
        now = self._now()
        record = {
            "id": uuid4(),
            "user_id": req.user_id,
            "device_token": req.device_token,
            "device_type": req.device_type,
            "device_name": req.device_name,
            "device_model": req.device_model,
            "os_version": req.os_version,
            "app_version": req.app_version,
            "is_active": True,
            "last_used_at": now,
            "registered_at": now,
        }
        saved = self._device_store.save_device(record)
        return DeviceToken.model_validate(saved)

    def unregister_device(self, req: DeviceUnregistration) -> None:
        """
        Deactivate a device token.
        """
        self._device_store.deactivate_device(req.device_token)

    # ------------------------------------------------------------------ #
    # Send push
    # ------------------------------------------------------------------ #
    def send_push(self, req: PushRequest) -> List[PushDeliveryStatus]:
        """
        Send a push notification to:

        - all active devices of req.user_id, or
        - specific device_token(s) if provided.
        """
        config = self.get_config()
        now = self._now()

        # Determine target tokens
        tokens: List[str] = []
        if req.device_tokens:
            tokens.extend(req.device_tokens)
        if req.device_token:
            tokens.append(req.device_token)
        if req.user_id:
            for dev in self._device_store.list_devices_for_user(req.user_id):
                if dev.get("is_active"):
                    tokens.append(dev["device_token"])

        tokens = list(dict.fromkeys(tokens))  # de-duplicate

        results: List[PushDeliveryStatus] = []
        for token in tokens:
            status = "queued"
            provider_message_id = None
            error_message = None

            try:
                provider_message_id = self._provider.send(req, config, token)
                status = "sent"
            except Exception as exc:  # pragma: no cover
                status = "failed"
                error_message = str(exc)

            record = {
                "notification_id": uuid4(),
                "device_token": token,
                "status": status,  # queued|sent|delivered|failed|expired
                "sent_at": now if status in ("sent", "delivered") else None,
                "delivered_at": None,
                "failed_at": now if status == "failed" else None,
                "error_code": None,
                "error_message": error_message,
                "provider_message_id": provider_message_id,
            }
            self._device_store.save_delivery_status(record)
            results.append(PushDeliveryStatus.model_validate(record))

        return results

    # ------------------------------------------------------------------ #
    # Stats
    # ------------------------------------------------------------------ #
    def get_stats(self, period: DateRangeFilter) -> PushStats:
        start = period.start_date or date.min
        end = period.end_date or date.max

        records = self._device_store.list_delivery_status_range(start=start, end=end)
        total_sent = len(records)
        total_delivered = sum(1 for r in records if r.get("status") == "delivered")
        total_failed = sum(1 for r in records if r.get("status") == "failed")
        total_opened = 0  # requires app-side tracking

        def _pct(num: int, denom: int) -> Decimal:
            return (
                Decimal(str(num)) / Decimal(str(denom)) * Decimal("100")
                if denom > 0
                else Decimal("0")
            )

        # Platform breakdown would need device_type in delivery records; set 0 here.
        ios_sent = android_sent = web_sent = 0

        return PushStats(
            total_sent=total_sent,
            total_delivered=total_delivered,
            total_failed=total_failed,
            delivery_rate=_pct(total_delivered, total_sent),
            ios_sent=ios_sent,
            android_sent=android_sent,
            web_sent=web_sent,
            total_opened=total_opened,
            open_rate=_pct(total_opened, total_sent),
            period_start=start,
            period_end=end,
        )