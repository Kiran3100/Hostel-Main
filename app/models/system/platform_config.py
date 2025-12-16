# app.models/system/platform_config.py
from uuid import UUID

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseItem


class PlatformConfig(BaseItem):
    """
    Platform settings (branding, support info, theme colors).
    Typically one row.
    """
    __tablename__ = "sys_platform_config"

    portal_title: Mapped[str] = mapped_column(String(255))
    welcome_message: Mapped[str] = mapped_column(String(1000))

    support_email: Mapped[str] = mapped_column(String(255))
    support_phone: Mapped[str] = mapped_column(String(20))

    primary_color: Mapped[str] = mapped_column(String(20))
    secondary_color: Mapped[str] = mapped_column(String(20))
    text_color: Mapped[str] = mapped_column(String(20))
    accent_color: Mapped[str] = mapped_column(String(20))
    surface_color: Mapped[str] = mapped_column(String(20))