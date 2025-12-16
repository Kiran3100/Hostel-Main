# models/mixins/soft_delete_mixin.py
from datetime import datetime
from typing import Union

from sqlalchemy import Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column


class SoftDeleteMixin:
    """Soft delete support."""
    is_deleted: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    deleted_at: Mapped[Union[datetime, None]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )