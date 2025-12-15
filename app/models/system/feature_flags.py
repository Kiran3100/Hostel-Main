# app.models/system/feature_flags.py
from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseItem


class FeatureFlag(BaseItem):
    """Feature toggles."""
    __tablename__ = "sys_feature_flag"

    name: Mapped[str] = mapped_column(String(100), unique=True)
    description: Mapped[Optional[str]] = mapped_column(String(500))

    is_enabled: Mapped[bool] = mapped_column(Boolean, default=False)

    # optional rollout
    rollout_percentage: Mapped[Optional[int]] = mapped_column()
    last_updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))