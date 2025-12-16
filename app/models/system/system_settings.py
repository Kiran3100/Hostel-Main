# app.models/system/system_settings.py
from typing import Dict, Any
from uuid import UUID

from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseItem


class SystemSettings(BaseItem):
    """
    Arbitrary system-wide key/value settings.
    """
    __tablename__ = "sys_settings"

    key: Mapped[str] = mapped_column(String(100), unique=True)
    value: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)