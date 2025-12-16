# models/mixins/backend_sync_mixin.py
from typing import Union

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column


class BackendSyncMixin:
    """For entities synchronized with a backend/external service."""
    backend_id: Mapped[Union[str, None]] = mapped_column(
        String(100),
        nullable=True,
        unique=False,
    )