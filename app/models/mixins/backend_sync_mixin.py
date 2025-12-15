# models/mixins/backend_sync_mixin.py
from __future__ import annotations

from typing import Optional

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column


class BackendSyncMixin:
    """For entities synchronized with a backend/external service."""
    backend_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        unique=False,
    )